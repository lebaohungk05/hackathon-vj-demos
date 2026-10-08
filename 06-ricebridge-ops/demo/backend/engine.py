import copy
import datetime as dt
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[2] / "sim"
sys.path.insert(0, str(SIM_DIR))

from policies import AWD_MARGIN_CM, SENSOR_PHOTO_CONFLICT_CM, WET_MARGIN_CM
from scenario import AWD_THRESHOLD_CM, BUND_CM, FILL_LEVEL_CM, NO_DRYING_STAGES, PUMP_CAPACITY, crop_coefficient, stage, step_level

import i18n
import vision_hook
import weather_source
from i18n import tr
from interpreter import REFUSAL_EN, REFUSAL_T, REFUSAL_VI, RuleBasedInterpreter, get_interpreter, instruction_hits
from llm import FAST_MODEL, REASON_MODEL, LLMClient

FORECAST_HORIZON_DAYS = 1
STALE_READING_DAYS = 3
CHECK_BEFORE_OPEN_DAYS = 2
FAST_DRAINING_MM = 3.0
MRV_WINDOW_START = dt.date(2026, 2, 20)
MODEL_START = dt.datetime(2026, 2, 20, 6, 0)
DEMO_DIR = Path(__file__).resolve().parents[1]
ACCEPT_CONFIDENCE = 0.75
PARSER_AGREEMENT_CM = 0.5
GAUGE_FLOOR_CM = -40.0
SIGNIFICANT_RAIN_MM = 10.0
FLOWERING_DAYS = 20
MAX_WHATIF_RAIN_MM = 150.0
MAX_PUMP_SHIFT_DAYS = 10
SCENARIO_LABEL = "Team demo scenario"
CLUSTER_NAME = "Cluster A (Cụm A)"
HTX_OFFICER = "Anh Hùng (HTX)"
STATION_MANAGER = "Pump-station manager (người phụ trách trạm)"
TECH_OFFICER = "technical officer (cán bộ kỹ thuật)"
PERSON_READ_SOURCES = ("photo", "htx_voice", "second_gauge", "farmer_text")
MUTABLE_STATE = ("clock", "levels", "runs", "log", "log_t", "pending", "measure_requests", "plan", "plan_history", "history",
                 "step", "report_cursor", "chat", "trace", "deferred", "stage_override", "extra_rain")
TITLE_KEYS = {"Plan before the rain": "title.start", "Re-plan after the rain": "title.rain", "Re-plan with the photo held": "title.photo",
              "Re-plan after the second-gauge reading": "title.remeasure", "Re-plan with the HTX report": "title.voice",
              "Re-plan after the pump moved": "title.pump"}

STAGE_LABELS = {
    "establishment": ("Establishment", "lúa mạ"),
    "topdress": ("Top-dressing window", "bón thúc"),
    "heading": ("Flowering", "trổ bông"),
    "awd": ("AWD drying allowed", "phơi ruộng"),
    "drain": ("Pre-harvest drain", "rút nước trước gặt"),
    "off": ("Off season", "ngoài vụ"),
}

ACTION_LABELS = {
    "irrigate": ("Open inlet", "Mở cống"),
    "hold_rain": ("Hold: rain will refill", "Chờ mưa, đóng cống"),
    "keep_water": ("Wait: next run", "Đủ nước, lùi đợt sau"),
    "deferred": ("Deferred: pump full", "Dời lượt sau"),
}

SOURCE_LABELS = {
    "sensor": "sensor",
    "photo": "gauge photo",
    "second_gauge": "second-gauge reading",
    "htx_voice": "HTX report",
    "htx_check": "HTX field check",
    "htx_record": "HTX pump log",
    "farmer_text": "farmer chat report",
}

SENDERS = {f"Hộ thửa {n}": f"F{n}" for n in (1, 2, 4, 5, 6)} | {HTX_OFFICER: None}


class DemoError(ValueError):
    def __init__(self, message):
        self.t = message if isinstance(message, dict) else None
        super().__init__(message["en"] if isinstance(message, dict) else message)


@dataclass
class FieldSpec:
    fid: str
    owner: str
    owner_note: str
    sowing: dt.date
    percolation: float
    seepage: float
    sy: float
    has_sensor: bool
    sensor_bias: float
    start_level: float
    lat: float
    lon: float
    polygon: str
    label_xy: tuple


FIELDS = [
    FieldSpec("F1", "Hộ thửa 1", "photo app", dt.date(2026, 1, 10), 0.6, 0.4, 0.3, False, 0.0, 5.0,
              10.3712, 105.4281, "40,70 210,70 210,200 40,200", (125, 135)),
    FieldSpec("F2", "Hộ thửa 2", "photo app + sensor", dt.date(2026, 1, 10), 0.4, 0.2, 0.2, True, 0.2, 2.0,
              10.3713, 105.4298, "220,70 380,70 380,200 220,200", (300, 135)),
    FieldSpec("F3", "Bà Sáu", "74, no smartphone; HTX officer records by voice", dt.date(2026, 1, 9), 0.6, 0.4, 0.3, False, 0.0, 4.0,
              10.3714, 105.4315, "390,70 560,70 560,200 390,200", (475, 135)),
    FieldSpec("F4", "Hộ thửa 4", "photo app", dt.date(2026, 1, 6), 3.6, 0.8, 0.3, False, 0.0, 5.0,
              10.3699, 105.4282, "40,210 210,210 210,340 40,340", (125, 275)),
    FieldSpec("F5", "Hộ thửa 5", "sensor only", dt.date(2026, 1, 10), 0.5, 0.3, 0.3, True, -0.3, 2.0,
              10.3698, 105.4299, "220,210 380,210 380,340 220,340", (300, 275)),
    FieldSpec("F6", "Hộ thửa 6", "photo app", dt.date(2026, 1, 25), 1.4, 0.6, 0.3, False, 0.0, 3.0,
              10.3697, 105.4316, "390,210 560,210 560,340 390,340", (475, 275)),
]
FIELD_IDS = [f.fid for f in FIELDS]

REMEASURE_OPTIONS = {
    "F2": [
        {"name": "Hộ thửa 2, same gauge", "role": "re-photograph the same tube", "walk_min": 0, "response_rate": 0.88, "independent": False},
        {"name": "Hộ thửa 2, gauge near the inlet", "role": "farmer measures a second tube", "walk_min": 2, "response_rate": 0.88, "independent": True},
        {"name": HTX_OFFICER, "role": "HTX officer measures a second tube", "walk_min": 12, "response_rate": 0.95, "independent": True},
    ]
}
TECH_OFFICER_OPTION = {"name": "Cán bộ kỹ thuật", "role": "technical officer measures a second tube", "walk_min": 30, "response_rate": 0.9, "independent": True}

ROUTINE_REPORTS = [
    ("2026-02-21T07:10", "F1", "photo", "Hộ thửa 1"),
    ("2026-02-21T07:40", "F4", "photo", "Hộ thửa 4"),
    ("2026-02-22T07:05", "F2", "photo", "Hộ thửa 2"),
    ("2026-02-22T08:30", "F3", "htx_voice", HTX_OFFICER),
    ("2026-02-22T17:00", "F6", "photo", "Hộ thửa 6"),
    ("2026-02-24T07:00", "F1", "photo", "Hộ thửa 1"),
    ("2026-02-24T07:30", "F4", "photo", "Hộ thửa 4"),
    ("2026-02-25T08:30", "F3", "htx_voice", HTX_OFFICER),
    ("2026-02-25T17:10", "F6", "photo", "Hộ thửa 6"),
    ("2026-02-27T07:15", "F1", "photo", "Hộ thửa 1"),
    ("2026-02-28T17:00", "F6", "photo", "Hộ thửa 6"),
    ("2026-03-01T07:20", "F1", "photo", "Hộ thửa 1"),
    ("2026-03-01T17:30", "F6", "photo", "Hộ thửa 6"),
]

PUMP_RUNS = [dt.date(2026, 2, 27), dt.date(2026, 3, 3), dt.date(2026, 3, 6), dt.date(2026, 3, 10)]

EVENTS = [
    {
        "id": "start",
        "time": "2026-02-25T17:00",
        "title": "Field 2 is drying; pump run planned Fri 27 Feb",
        "title_vi": "Thửa 2 đang để khô; trạm dự kiến cấp nước thứ Sáu 27/02",
        "title_ja": "区画2は乾燥中。ポンプ送水は2月27日（金）の予定",
        "short": "Context",
        "short_ja": "状況",
        "short_vi": "Bối cảnh",
        "sub": ("F2 sensor at 06:00 and the Open-Meteo forecast feed the first plan of the week",
                "06:00のF2センサーとOpen-Meteoの予報から、今週最初の計画を立てる",
                "Cảm biến F2 lúc 06:00 và dự báo Open-Meteo cho ra lịch đầu tuần"),
    },
    {
        "id": "rain",
        "time": "2026-02-27T06:00",
        "title": "Heavy rain overnight: 44 mm (Open-Meteo, 26–27/02/2026)",
        "title_vi": "Mưa lớn qua đêm: 44 mm (Open-Meteo, 26–27/02/2026)",
        "title_ja": "夜間の大雨：44 mm（Open-Meteo、2026年2月26〜27日）",
        "short": "44 mm rain",
        "short_ja": "44 mmの雨",
        "short_vi": "Mưa 44 mm",
        "sub": ("Real Open-Meteo rain: the FAO-56 water balance shows Field 2 filling up again, so the pump run is paused",
                "Open-Meteoの実測の雨：FAO-56の水収支では区画2に再び水がたまるため、送水を一時停止",
                "Mưa thật từ Open-Meteo: cân bằng nước FAO-56 cho thấy thửa 2 có nước lại nên tạm hoãn lượt bơm"),
    },
    {
        "id": "photo",
        "time": "2026-02-28T07:30",
        "title": "Morning gauge photo of Field 2 reads −8 cm",
        "title_vi": "Ảnh ống đo thửa 2 sáng nay báo −8 cm",
        "title_ja": "今朝の区画2の観測管の写真は −8 cm",
        "short": "Photo F2 −8 cm",
        "short_ja": "写真 F2 −8 cm",
        "short_vi": "Ảnh F2 −8 cm",
        "sub": ("The photo disagrees with the sensor and the water balance, so it is held and an independent re-measure is requested",
                "写真がセンサーや水収支と食い違うため保留し、独立した再測定を依頼",
                "Ảnh lệch với cảm biến và cân bằng nước nên bị tạm giữ; trợ lý xin đo lại độc lập"),
        "field": "F2",
        "reporter": "Hộ thửa 2",
        "value_cm": -8.0,
        "captured_at": "2026-02-22T07:05",
        "image": "vision/testset/hero_thua2_minus8.jpg",
        "rain_at": "2026-02-27T06:00",
        "chat_vi": "[Ảnh ống đo thửa 2]",
        "chat_en": "[Gauge photo, field 2]",
        "chat_ja": "［区画2の観測管の写真］",
    },
    {
        "id": "remeasure",
        "time": "2026-02-28T10:00",
        "title": "HTX officer measures Field 2 at a second gauge",
        "title_vi": "Cán bộ HTX đo thửa 2 ở ống thứ hai",
        "title_ja": "HTX職員が区画2を2本目の観測管で測定",
        "short": "Second gauge F2",
        "short_ja": "2本目の観測管",
        "short_vi": "Ống đo thứ hai F2",
        "sub": ("An independent second gauge closes the conflict; the photo is marked misread and kept for audit",
                "独立した2本目の観測管で矛盾を解消。写真は読み違いとして監査用に残す",
                "Ống đo thứ hai độc lập giải quyết mâu thuẫn; ảnh bị đánh dấu đọc sai và được giữ lại để kiểm tra"),
        "field": "F2",
        "reporter": HTX_OFFICER,
        "value_cm": 2.0,
        "transcript": "Thửa 2, ống gần cống, nước hai phân.",
    },
    {
        "id": "voice",
        "time": "2026-02-28T10:30",
        "title": "HTX officer records Bà Sáu's field by voice",
        "title_ui": "HTX officer records Mrs Sau's field by voice",
        "title_vi": "Cán bộ HTX ghi hộ thửa bà Sáu bằng giọng nói",
        "title_ja": "HTX職員がサウさんの区画を音声で代理記録",
        "short": "Mrs Sau, recorded by HTX",
        "short_ja": "サウさん代理記録",
        "short_vi": "Bà Sáu, HTX ghi hộ",
        "sub": ("Mrs Sau has no smartphone: the HTX officer reports by voice and the LLM understands the Mekong dialect",
                "スマートフォンを持たないサウさんの区画を、HTX職員が音声で報告し、LLMがメコン方言を理解",
                "Bà Sáu không có điện thoại thông minh: cán bộ HTX báo bằng giọng nói, LLM hiểu tiếng miền Tây"),
        "reporter": HTX_OFFICER,
        "transcript": "Thửa bà Sáu, nước ba phân.",
    },
    {
        "id": "pump_change",
        "time": "2026-03-02T07:00",
        "title": "HTX: pump station moves the next run to Friday",
        "title_vi": "HTX báo trạm dời lịch bơm sang thứ Sáu",
        "title_ja": "HTX：ポンプ場が次回の送水を金曜日に変更",
        "short": "Pump moved to Friday",
        "short_ja": "送水を金曜へ変更",
        "short_vi": "Dời bơm sang thứ Sáu",
        "sub": ("The station moves the run: the scheduler re-plans all six fields and the station manager approves",
                "ポンプ場が送水日を変更：スケジューラーが6区画すべてを再計画し、ポンプ場責任者が承認",
                "Trạm dời lượt bơm: bộ lập lịch tính lại cả 6 thửa và người phụ trách trạm duyệt"),
        "from": "2026-03-03",
        "to": "2026-03-06",
        "reporter": HTX_OFFICER,
        "transcript": "Trạm bơm báo: lượt bơm thứ Ba 03/03 dời sang thứ Sáu 06/03.",
    },
]


def fmt_day(day):
    return day.strftime("%a %d %b")


def fmt_cm(value):
    return f"{value:+.1f} cm".replace("-", "−")


def plain_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DemoError(tr("err.not_number", value=repr(value))) from exc
    if number != number:
        raise DemoError(tr("err.not_number", value="NaN"))
    return number


class Demo:
    def __init__(self, refresh_weather=False, llm_mode="auto"):
        self.weather, self.weather_meta = weather_source.load(refresh_weather)
        self.client = LLMClient(llm_mode)
        self.interpreter = get_interpreter(self.client)
        self.rules = RuleBasedInterpreter()
        self.progress_hook = None
        self.epoch = 0
        self.reset()

    def reset(self):
        self.epoch += 1
        self.clock = MODEL_START
        self.levels = {f.fid: f.start_level for f in FIELDS}
        self.runs = {day: "scheduled" for day in PUMP_RUNS}
        self.log = []
        self.log_t = {}
        self.pending = {}
        self.measure_requests = {}
        self.plan = None
        self.plan_history = []
        self.history = []
        self.step = -1
        self.report_cursor = 0
        self.chat = []
        self.trace = []
        self.deferred = []
        self.stage_override = {}
        self.extra_rain = {}
        self.whatif = None
        self.client.sink = None
        self.seed_history()

    def progress(self, text):
        if self.progress_hook:
            self.progress_hook(text)

    @property
    def spec(self):
        return {f.fid: f for f in FIELDS}

    @property
    def vision_replay(self):
        return self.client.mode in ("replay", "rules")

    def k(self, fid, day):
        return (day - self.spec[fid].sowing).days

    def stage(self, fid, day):
        override = self.stage_override.get(fid)
        if override and override[0] <= day < override[1]:
            return override[2]
        return stage(self.k(fid, day))

    def flux(self, fid, day, rain):
        f = self.spec[fid]
        return rain - crop_coefficient(self.k(fid, day)) * self.weather[day]["et0_mm"] - f.percolation - f.seepage

    def last_reading(self, fid):
        rows = [e for e in self.log if e["field"] == fid and e["kind"] == "water_level" and e["status"] == "accepted"]
        return rows[-1] if rows else None

    def last_person_reading(self, fid):
        rows = [e for e in self.log if e["field"] == fid and e["kind"] == "water_level" and e["status"] == "accepted"
                and e["source"] in PERSON_READ_SOURCES]
        return rows[-1] if rows else None

    def level_basis(self, fid):
        entry = self.last_reading(fid)
        if entry is None:
            return "water balance only"
        when = dt.datetime.fromisoformat(entry["time"])
        return f"{SOURCE_LABELS.get(entry['source'], entry['source'])} {fmt_day(when.date())}"

    def level_basis_t(self, fid):
        entry = self.last_reading(fid)
        if entry is None:
            return tr("basis.wb")
        return tr("basis.src", source=i18n.source(entry["source"]), day=i18n.day(entry["time"]))

    def latest_rain(self):
        today = self.clock.date()
        days = sorted(d for d, w in self.weather.items() if d <= today and w["rain_mm"] >= SIGNIFICANT_RAIN_MM
                      and dt.datetime.combine(d, dt.time(6, 0)) <= self.clock)
        if not days:
            return None, 0.0
        last = days[-1]
        total = self.weather[last]["rain_mm"]
        previous = last - dt.timedelta(days=1)
        if previous in self.weather and self.weather[previous]["rain_mm"] >= 1.0:
            total += self.weather[previous]["rain_mm"]
        return dt.datetime.combine(last, dt.time(6, 0)), total

    def advance_to(self, when):
        while True:
            self.apply_routine_reports(when)
            if self.clock.date() >= when.date():
                break
            day = self.clock.date()
            self.run_pump_if_due(self.clock)
            for f in FIELDS:
                self.levels[f.fid] = step_level(self.levels[f.fid], self.flux(f.fid, day, self.weather[day]["rain_mm"]), f.sy)
            self.clock = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(6, 0))
            for f in FIELDS:
                if f.has_sensor:
                    self.append(self.clock, f.fid, "water_level", "sensor", round(self.levels[f.fid] + f.sensor_bias, 1),
                                "Water-level sensor (simulated)", "auto", "accepted", note="daily 06:00 reading", note_t=tr("log.sensor"))
        self.clock = max(self.clock, when)

    def run_pump_if_due(self, now):
        day = now.date()
        if self.runs.get(day) != "scheduled" or self.plan is None or self.plan["run_date"] != day.isoformat():
            return
        if self.plan["status"] == "proposed":
            self.clock = now - dt.timedelta(minutes=35)
            self.decide("approve", "confirmed before the run (scripted in the Team demo scenario)", note_t=tr("log.scripted_ok"))
            self.clock = now
        if self.plan["status"] == "rejected":
            self.runs[day] = "held"
            self.append(now, None, "pump_schedule", "htx_record", None, STATION_MANAGER, "HTX notice", "info",
                        note=f"run {fmt_day(day)} not executed by the agent: {self.plan['id']} was rejected; HTX decides manually",
                        note_t=tr("log.held_run", day=i18n.day(day), id=self.plan["id"]))
            return
        if self.plan["pause_run"]:
            self.runs[day] = "paused"
            self.append(now, None, "pump_schedule", "htx_record", None, STATION_MANAGER, "HTX notice", "info",
                        note=f"run {fmt_day(day)} paused as proposed in {self.plan['id']}",
                        note_t=tr("log.paused", day=i18n.day(day), id=self.plan["id"]))
            return
        self.runs[day] = "ran"
        for row in self.plan["rows"]:
            if row["action"] == "irrigate":
                self.levels[row["fid"]] = FILL_LEVEL_CM
                self.append(now, row["fid"], "irrigation", "htx_record", FILL_LEVEL_CM, HTX_OFFICER, "HTX pump log", "accepted",
                            note=f"filled in run {fmt_day(day)} ({self.plan['id']})",
                            note_t=tr("log.filled", day=i18n.day(day), id=self.plan["id"]))

    def append(self, when, fid, kind, source, value, recorder, via, status, note="", ref=None, sources=None, note_t=None, sources_t=None):
        f = self.spec.get(fid)
        entry = {
            "seq": len(self.log) + 1,
            "time": when.isoformat(timespec="minutes"),
            "field": fid,
            "kind": kind,
            "source": source,
            "value_cm": value,
            "recorder": recorder,
            "via": via,
            "lat": f.lat if f else None,
            "lon": f.lon if f else None,
            "status": status,
            "ref": ref,
            "note": note,
            "sources": "; ".join(sources or []),
            "label": SCENARIO_LABEL if source not in ("model", "open-meteo") else "computed",
            "prev_hash": self.log[-1]["hash"] if self.log else "0" * 16,
        }
        entry["hash"] = hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        self.log.append(entry)
        self.log_t[entry["seq"]] = {"note": note_t or i18n.lit(note), "sources": i18n.join_list(sources_t, sep="; ") if sources_t else i18n.lit(entry["sources"])}
        return entry

    def seed_history(self):
        for f in FIELDS:
            if f.start_level >= FILL_LEVEL_CM:
                self.append(MODEL_START, f.fid, "irrigation", "htx_record", f.start_level, HTX_OFFICER, "HTX pump log", "accepted",
                            note="Fri 20 Feb run filled field", note_t=tr("log.seed_fill", day=i18n.day(MODEL_START.date())))
            else:
                self.append(MODEL_START, f.fid, "water_level", "htx_check", f.start_level, HTX_OFFICER, "HTX field check", "accepted",
                            note="checked at the Fri 20 Feb run", note_t=tr("log.seed_check", day=i18n.day(MODEL_START.date())))

    def apply_routine_reports(self, when):
        while self.report_cursor < len(ROUTINE_REPORTS):
            stamp, fid, src, who = ROUTINE_REPORTS[self.report_cursor]
            at = dt.datetime.fromisoformat(stamp)
            if at > when or at.date() > self.clock.date():
                return
            self.report_cursor += 1
            value = round(self.levels[fid] * 2) / 2
            via = "voice note by HTX officer" if src == "htx_voice" else "photo app"
            self.append(at, fid, "water_level", src, value, who, via, "accepted", note="routine report", note_t=tr("log.routine"))

    def forecast_rain(self, today, day):
        if not 0 <= (day - today).days < FORECAST_HORIZON_DAYS:
            return 0.0
        return self.weather[day]["rain_mm"] + self.extra_rain.get(day, 0.0)

    def active_runs(self):
        return sorted(day for day, status in self.runs.items() if status == "scheduled")

    def project(self, fid, today, until, with_rain):
        h = self.levels[fid]
        path = [(today, h)]
        day = today
        while day < until:
            rain = self.forecast_rain(today, day) if with_rain else 0.0
            h = step_level(h, self.flux(fid, day, rain), self.spec[fid].sy)
            day += dt.timedelta(days=1)
            path.append((day, h))
        return path

    def assess(self, fid, today, run, following, with_rain):
        path = self.project(fid, today, following, with_rain)
        priority, crossing = None, None
        for day, h in path[:-1]:
            st = self.stage(fid, day)
            starts = self.stage(fid, day - dt.timedelta(days=1)) != st
            if st == "heading" and h < WET_MARGIN_CM:
                why = "starts flowering without standing water" if starts else "flowering field loses its standing water"
                why_t = tr("why.flower_start") if starts else tr("why.flower_lose")
                crossing = crossing or (day, why, h, why_t)
                priority = 0 if priority is None else min(priority, 0)
            elif st in NO_DRYING_STAGES and h < WET_MARGIN_CM:
                why = f"{STAGE_LABELS[st][0].lower()} starts without standing water" if starts else f"{STAGE_LABELS[st][0].lower()} needs standing water"
                why_t = tr("why.stage_start" if starts else "why.stage_need", stage=i18n.stage_lower(st))
                crossing = crossing or (day, why, h, why_t)
                priority = 1 if priority is None else min(priority, 1)
            elif st == "awd" and h < AWD_THRESHOLD_CM + AWD_MARGIN_CM:
                crossing = crossing or (day, "near the −15 cm AWD limit", h, tr("why.awd"))
                priority = 2 if priority is None else min(priority, 2)
        dry_from = next((d for d, h in path if h < 0), None)
        levels = dict(path)
        return {"need": priority is not None, "priority": priority, "crossing": crossing, "at_run": levels.get(run, path[-1][1]),
                "min_level": min(h for _, h in path[:-1]) if len(path) > 1 else path[0][1], "path": path, "dry_from": dry_from}

    def sources_for(self, fid, rain_mm):
        return [x["en"] for x in self.sources_for_t(fid, rain_mm)]

    def sources_for_t(self, fid, rain_mm):
        out = [tr("src.rain", mm=f"{rain_mm:.1f}"), tr("src.wb")]
        rows = [e for e in self.log if e["field"] == fid and e["kind"] == "water_level" and e["status"] in ("accepted", "suspicious")]
        seen = []
        for e in reversed(rows):
            label = i18n.source(e["source"])
            if e["status"] == "suspicious":
                label = tr("src.photo_rejected") if any(r["ref"] == e["seq"] and r["status"] == "rejected" for r in self.log) else tr("src.photo_suspicious")
            if label["en"] not in [x["en"] for x in seen]:
                seen.append(label)
        return out + seen[:3]

    def run_window(self, today):
        runs = [day for day in self.active_runs() if day >= today]
        if not runs:
            runs = [today + dt.timedelta(days=7)]
        if len(runs) < 2:
            runs.append(runs[0] + dt.timedelta(days=7))
        return runs[0], runs[1]

    def make_plan(self, title, title_t=None):
        today = self.clock.date()
        run, following = self.run_window(today)
        rows, alerts, candidates = [], [], []
        rain_total = sum(self.forecast_rain(today, today + dt.timedelta(days=i)) for i in range(FORECAST_HORIZON_DAYS))
        for f in FIELDS:
            wet = self.assess(f.fid, today, run, following, True)
            dry = self.assess(f.fid, today, run, following, False)
            st_now = self.stage(f.fid, today)
            upcoming = next((d for d, _ in wet["path"] if self.stage(f.fid, d) in NO_DRYING_STAGES and self.stage(f.fid, d) != st_now), None)
            row = {
                "fid": f.fid, "owner": f.owner, "stage": st_now,
                "stage_label": STAGE_LABELS[st_now][0], "stage_vi": STAGE_LABELS[st_now][1],
                "next_stage": (STAGE_LABELS[self.stage(f.fid, upcoming)][0], STAGE_LABELS[self.stage(f.fid, upcoming)][1], upcoming.isoformat()) if upcoming else None,
                "level_now": round(self.levels[f.fid], 1), "level_basis": self.level_basis(f.fid), "level_basis_t": self.level_basis_t(f.fid),
                "level_at_run": round(wet["at_run"], 1), "min_level": round(wet["min_level"], 1),
                "pending_check": f.fid in self.pending, "sources": self.sources_for(f.fid, rain_total),
                "sources_t": self.sources_for_t(f.fid, rain_total),
                "next_stage_code": self.stage(f.fid, upcoming) if upcoming else None,
            }
            if wet["need"]:
                day, why, h, why_t = wet["crossing"]
                reason = f"{fmt_day(day)}: {why} (projected {fmt_cm(h)})."
                reason_t = tr("reason.need", day=i18n.day(day), why=why_t, cm=fmt_cm(h))
                if f.percolation >= FAST_DRAINING_MM and wet["dry_from"] and wet["dry_from"] <= run:
                    reason += f" Fast-draining soil ({f.percolation + f.seepage:.1f} mm/day): standing water gone by {fmt_day(wet['dry_from'])}, before the run."
                    reason_t = i18n.cat(reason_t, tr("reason.fast", rate=f"{f.percolation + f.seepage:.1f}", day=i18n.day(wet["dry_from"])))
                if day < run:
                    alerts.append(self.risk_alert(f, day, why, h, run, why_t))
                row["reason"] = reason
                row["reason_t"] = reason_t
                candidates.append((day, wet["priority"], wet["min_level"], row))
            elif dry["need"] or (rain_total >= 10 and len(wet["path"]) > 1 and wet["path"][1][1] > self.levels[f.fid] + 3):
                after = wet["path"][1][1] if len(wet["path"]) > 1 else self.levels[f.fid]
                row["action"] = "hold_rain"
                row["reason"] = f"Today's {rain_total:.1f} mm (Open-Meteo) lifts it from {fmt_cm(self.levels[f.fid])} to about {fmt_cm(after)} by tomorrow; no pumping needed."
                row["reason_t"] = tr("reason.hold", mm=f"{rain_total:.1f}", a=fmt_cm(self.levels[f.fid]), b=fmt_cm(after))
                rows.append(row)
            else:
                row["action"] = "keep_water"
                row["reason"] = f"{'Re-flooded' if self.levels[f.fid] >= WET_MARGIN_CM else 'Enough water'}: lowest projected {fmt_cm(wet['min_level'])} before {fmt_day(following)}; can wait for the next run."
                row["reason_t"] = tr("reason.keep_reflooded" if self.levels[f.fid] >= WET_MARGIN_CM else "reason.keep_enough",
                                     cm=fmt_cm(wet["min_level"]), day=i18n.day(following))
                rows.append(row)
        candidates.sort(key=lambda c: (c[0], c[1], c[2]))
        for rank, (_, priority, _, row) in enumerate(candidates):
            row["priority"], row["rank"] = priority, rank
            row["action"] = "irrigate" if rank < PUMP_CAPACITY else "deferred"
            if row["action"] == "deferred":
                row["reason"] += f" Pump full ({PUMP_CAPACITY} fields/run); next slot {fmt_day(following)}."
                row["reason_t"] = i18n.cat(row["reason_t"], tr("reason.deferred", n=PUMP_CAPACITY, day=i18n.day(following)))
            rows.append(row)
        order = {"irrigate": 0, "deferred": 1, "hold_rain": 2, "keep_water": 3}
        rows.sort(key=lambda r: (order[r["action"]], r.get("rank", 99), r["fid"]))
        self.measure_requests = {}
        for queue, row in enumerate([r for r in rows if r["action"] == "irrigate"], start=1):
            row["queue"] = queue
            last = self.last_reading(row["fid"])
            age = (today - dt.datetime.fromisoformat(last["time"]).date()).days if last else 99
            if age > CHECK_BEFORE_OPEN_DAYS:
                row["measure_first"] = True
                row["reason"] += f" Last reading is {age} days old: ask HTX to measure before opening the inlet."
                row["reason_t"] = i18n.cat(row["reason_t"], tr("reason.measure", age=age))
                self.measure_requests[row["fid"]] = {"run": fmt_day(run), "age": age}
        for row in rows:
            row["action_label"], row["action_vi"] = ACTION_LABELS[row["action"]]
        served = [r["fid"] for r in rows if r["action"] == "irrigate"]
        if served:
            summary = f"Pump run {fmt_day(run)}: open {', then '.join(served)}; other fields wait for the next run."
            summary_vi = f"Lượt bơm {fmt_day(run)}: mở cống {', rồi '.join(served)}; các thửa khác chờ đợt sau."
            summary_t = tr("summary.run", day=i18n.day(run), list=i18n.join_list(served, sep_key="list.then"))
        else:
            summary = f"Pause the {fmt_day(run)} pump run: no field needs water before {fmt_day(following)}."
            summary_vi = f"Tạm hoãn lượt bơm {fmt_day(run)}: chưa thửa nào cần nước trước {fmt_day(following)}."
            summary_t = tr("summary.pause", day=i18n.day(run), next=i18n.day(following))
        return {
            "id": f"P{len(self.plan_history) + 1}", "title": title, "title_t": title_t or (tr(TITLE_KEYS[title]) if title in TITLE_KEYS else i18n.lit(title)),
            "summary_t": summary_t, "following_date": following.isoformat(),
            "made_at": self.clock.isoformat(timespec="minutes"),
            "run_date": run.isoformat(), "run_label": fmt_day(run), "following_label": fmt_day(following),
            "pause_run": not served, "rain_forecast_mm": round(rain_total, 1), "status": "proposed",
            "rows": rows, "summary": summary, "summary_vi": summary_vi, "alerts": alerts,
            "approver": STATION_MANAGER, "decided_by": None, "decision_note": None,
        }

    def risk_alert(self, f, day, why, h, run, why_t):
        flowering = self.stage(f.fid, day) == "heading"
        return {
            "fid": f.fid, "severity": "high" if flowering else "medium",
            "text": f"{f.fid} {why} on {fmt_day(day)} ({fmt_cm(h)}), before the {fmt_day(run)} run.",
            "action": f"Notify the {TECH_OFFICER}." if flowering else "Ask the pump station for an earlier slot.",
            "text_t": tr("alert.text", fid=f.fid, why=why_t, day=i18n.day(day), cm=fmt_cm(h), run=i18n.day(run)),
            "action_t": tr("alert.tech") if flowering else tr("alert.slot"),
        }

    def diff_plans(self, old, new):
        if old is None:
            return []
        before = {r["fid"]: r for r in old["rows"]}
        out = []
        if old["run_date"] != new["run_date"]:
            out.append(f"Pump run {old['run_label']} → {new['run_label']}")
        for row in new["rows"]:
            prev = before.get(row["fid"])
            if prev and (prev["action"] != row["action"] or prev.get("queue") != row.get("queue")):
                left = prev["action"] + (f" #{prev['queue']}" if prev.get("queue") else "")
                right = row["action"] + (f" #{row['queue']}" if row.get("queue") else "")
                out.append(f"{row['fid']}: {left} → {right}")
        return out

    def diff_items(self, old, new):
        if old is None:
            return []
        out = []
        if old["run_date"] != new["run_date"]:
            out.append({"type": "run", "from": old["run_date"], "to": new["run_date"]})
        before = {r["fid"]: r for r in old["rows"]}
        for row in new["rows"]:
            prev = before.get(row["fid"])
            if prev and (prev["action"] != row["action"] or prev.get("queue") != row.get("queue")):
                out.append({"type": "row", "fid": row["fid"], "from": prev["action"], "from_queue": prev.get("queue"),
                            "to": row["action"], "to_queue": row.get("queue")})
        return out

    def diff_rows(self, old, new):
        if old is None:
            return []
        before = {r["fid"]: r for r in old["rows"]}
        out = []
        for row in new["rows"]:
            prev = before.get(row["fid"])
            if prev is None:
                continue
            changed = prev["action"] != row["action"] or prev.get("queue") != row.get("queue")
            moved = abs((prev["level_at_run"] or 0) - (row["level_at_run"] or 0)) >= 0.5
            if changed or moved:
                out.append({"fid": row["fid"], "from": prev["action"], "to": row["action"], "from_queue": prev.get("queue"),
                            "to_queue": row.get("queue"), "from_level": prev["level_at_run"], "to_level": row["level_at_run"],
                            "action_changed": changed})
        return out

    def adopt_plan(self, plan):
        diff = self.diff_plans(self.plan, plan)
        if self.plan is not None and self.plan["status"] == "proposed":
            self.plan["status"] = "superseded"
        plan["previous_id"] = self.plan["id"] if self.plan else None
        plan["diff"] = diff
        plan["diff_rows"] = self.diff_rows(self.plan, plan)
        plan["diff_items"] = self.diff_items(self.plan, plan)
        self.plan = plan
        self.plan_history.append(plan)
        self.append(self.clock, None, "schedule", "model", None, "RiceBridge Ops agent", f"proposal to {STATION_MANAGER}", "proposed",
                    note=f"{plan['id']}: {plan['summary']}", note_t=tr("log.proposal", id=plan["id"], summary=plan["summary_t"]))
        return diff

    def tasks(self):
        out = []
        for fid, pend in self.pending.items():
            out.append({"who": pend.get("ask", HTX_OFFICER), "field": fid, "due": pend.get("deadline", "today"), "kind": "urgent",
                        "text": f"Measure {fid} at a second gauge (not the same tube)", "text_vi": pend.get("message", "")})
        for fid, req in self.measure_requests.items():
            out.append({"who": HTX_OFFICER, "field": fid, "due": f"before inlet opens {req['run']}", "kind": "urgent",
                        "text": f"Measure {fid} before opening the inlet (last person reading {req['age']} days old)",
                        "text_vi": f"Anh đo giúp thửa {fid[1:]} trước giờ mở cống nhé."})
        if self.plan:
            for row in self.plan["rows"]:
                context = {"field": row["fid"], "run": self.plan["run_label"], "rain_mm": self.plan["rain_forecast_mm"]}
                if row["action"] == "irrigate":
                    text, kind = f"Open inlet when HTX calls on {self.plan['run_label']} (#{row['queue']})", "irrigate"
                elif row["action"] == "hold_rain":
                    text, kind = "Close outlet, keep the rain water", "hold_rain"
                else:
                    text, kind = f"Keep outlet closed; next run after {self.plan['run_label']}", "keep_water"
                who = f"{HTX_OFFICER} for Bà Sáu" if row["fid"] == "F3" else row["owner"]
                brief = (self.plan.get("brief") or {}).get("messages", {}).get(row["fid"])
                out.append({"who": who, "field": row["fid"], "due": self.plan["run_label"], "kind": "",
                            "text": brief["en"] if brief else text,
                            "text_vi": brief["vi"] if brief else self.rules.farmer_message(kind, context)})
            if self.plan["status"] == "proposed":
                out.insert(0, {"who": STATION_MANAGER, "field": "all", "due": "today", "kind": "boss",
                               "text": f"Review reasons and approve plan {self.plan['id']}", "text_vi": "Xem lý do và duyệt lịch bơm"})
        return out

    def tool(self, name, summary, summary_t=None):
        self.trace.append({"kind": "tool", "task": name, "summary": summary, "summary_t": summary_t or i18n.lit(summary)})

    def say(self, who, role, text_vi, text_en="", tl=None, **meta):
        tl = dict(tl) if tl else {"vi": text_vi, "en": text_en}
        tl["vi"] = i18n.localize_dates(tl.get("vi") or text_vi, "vi")
        if not tl.get("en"):
            tl["en"] = text_en
        self.chat.append({"n": len(self.chat) + 1, "time": self.clock.isoformat(timespec="minutes"), "from": who, "role": role,
                          "vi": i18n.localize_dates(text_vi, "vi"), "en": text_en, "tl": tl, **meta})

    def engine_tag(self, out):
        return {"engine": out.get("engine", "rules"), "model": out.get("model"), "ms": out.get("ms", 0),
                "source": out.get("source"), "fallback_reason": out.get("fallback_reason"), "fallback_t": out.get("fallback_t")}

    def begin(self):
        self.trace = []
        self.client.sink = self.trace
        return {"changed": [], "conflicts": [], "asks": [], "inputs": [], "diff": [], "parse": None, "state_change": True,
                "focal": None, "verdict": None}

    def finish(self, title, result, log_start, inline_brief=False, title_t=None):
        if title:
            self.progress(tr("p.scheduler"))
            plan = self.make_plan(title, title_t)
            self.tool("Pump-capacity scheduler", f"{PUMP_CAPACITY} fields per run, ordered by crop-stage risk date, priority, lowest level → {plan['summary']}",
                      tr("tr.sched", n=PUMP_CAPACITY, summary=plan["summary_t"]))
            self.tool("Approval gate", f"{plan['id']} status = proposed; only the {STATION_MANAGER} can approve. The LLM has no approve tool.",
                      tr("tr.gate", id=plan["id"]))
            result["diff"] = self.adopt_plan(plan)
            result["plan_id"] = plan["id"]
            payload = self.brief_payload(plan, title)
            if inline_brief:
                self.progress(tr("p.brief"))
                self.apply_brief(plan, self.interpreter.plan_brief(payload), focus=result.get("focus"))
            else:
                plan["brief"] = {"pending": True}
                self.deferred.append({"plan": plan, "payload": payload, "trace": self.trace, "focus": result.get("focus"), "epoch": self.epoch})
        self.whatif = None
        result["log_added"] = [e["seq"] for e in self.log[log_start:]]
        result["trace"] = self.trace
        self.client.sink = None
        return result

    def handle(self, event, inline_brief=False):
        when = dt.datetime.fromisoformat(event["time"])
        days_before = self.clock.date()
        self.advance_to(when)
        result = self.begin()
        if self.clock.date() > days_before:
            self.tool("Water-balance tool (FAO-56)", f"advanced {(self.clock.date() - days_before).days} days with Open-Meteo rain + ET0, Kc by stage, percolation and seepage per field",
                      tr("tr.advance", n=(self.clock.date() - days_before).days))
        log_start = len(self.log)
        title = getattr(self, "on_" + event["id"])(event, result)
        return self.finish(title, result, log_start, inline_brief=inline_brief)

    def brief_payload(self, plan, title):
        recent = [h["event"]["title"] for h in self.history[-2:]] + [title]
        rows = [{"fid": r["fid"], "owner": r["owner"], "stage_vi": r["stage_vi"], "action": r["action"], "action_label": r["action_label"],
                 "queue": r.get("queue"), "measure_first": bool(r.get("measure_first")), "level_now_cm": r["level_now"],
                 "level_at_run_cm": r["level_at_run"], "reason": r["reason"]} for r in plan["rows"]]
        return {"plan_id": plan["id"], "recent_events": recent, "run_label": plan["run_label"], "run_date": plan["run_date"],
                "following_label": plan["following_label"], "rain_forecast_mm": plan["rain_forecast_mm"],
                "summary": plan["summary"], "summary_vi": plan["summary_vi"], "rows": rows,
                "alerts": [a["text"] for a in plan["alerts"]]}

    def take_deferred(self):
        jobs, self.deferred = self.deferred, []
        return jobs

    def apply_brief(self, plan, brief, trace=None, focus=None, entry=None):
        if not any(p is plan for p in self.plan_history):
            return False
        if brief.get("engine") != "llm":
            brief["headline_t"] = dict(plan["summary_t"])
        plan["brief"] = brief
        if trace is not None and entry is not None and entry.get("task") == "plan_brief":
            trace.append(entry)
        if plan is not self.plan:
            plan["brief"]["late"] = True
            return True
        index = next(i for i, p in enumerate(self.plan_history) if p is plan)
        previous = self.plan_history[index - 1] if index > 0 else None
        changed = {d.split(":")[0] for d in self.diff_plans(previous, plan)}
        targets = [r["fid"] for r in plan["rows"] if previous is None or r["fid"] in changed or r["fid"] == focus]
        lines = [{"fid": fid, "vi": i18n.localize_dates(brief["messages"][fid]["vi"], "vi"), "en": brief["messages"][fid]["en"], "t": brief["messages"][fid]}
                 for fid in targets if fid in brief["messages"]]
        headline_vi = brief["headline_vi"] if brief.get("engine") == "llm" else brief["headline_t"]["vi"]
        self.say("RiceBridge agent", "agent", headline_vi, brief["headline_en"], tl=brief["headline_t"], lines=lines, plan=plan["id"], **self.engine_tag(brief))
        return True

    def on_start(self, event, result):
        sensor = self.last_reading("F2")
        forecast = self.weather[self.clock.date()]["rain_mm"]
        result["inputs"].append(f"F2 sensor {fmt_day(self.clock.date())} 06:00: {fmt_cm(sensor['value_cm'])} (AWD drying round)")
        result["inputs"].append(f"Forecast for today from Open-Meteo: {forecast:.1f} mm")
        result["changed"].append("Water balance run from the Fri 20 Feb HTX records with real daily rain and ET0.")
        self.say("Cảm biến thửa 2", "system", f"Cảm biến thửa 2: {fmt_cm(sensor['value_cm'])} (đang phơi ruộng)", f"Field 2 sensor: {fmt_cm(sensor['value_cm'])} (AWD drying)",
                 tl=tr("chat.sensor", cm=fmt_cm(sensor["value_cm"])))
        self.tool("Crop-stage safety tool", "stage per field from sowing date; flowering and top-dressing need standing water; AWD limit −15 cm", tr("tr.cropstage"))
        result["focal"] = {"kind": "sensor", "fid": "F2", "sensor_cm": sensor["value_cm"], "forecast_mm": round(forecast, 1),
                           "awd_limit_cm": AWD_THRESHOLD_CM, "run_label": fmt_day(PUMP_RUNS[0]), "run_date": PUMP_RUNS[0].isoformat(),
                           "basis_date": MODEL_START.date().isoformat()}
        return "Plan before the rain"

    def on_rain(self, event, result):
        today = self.clock.date()
        days = [today - dt.timedelta(days=1), today]
        rain = {d: self.weather[d]["rain_mm"] for d in days}
        total = sum(rain.values())
        before = round(self.levels["F2"] + self.spec["F2"].sensor_bias, 1)
        after = self.project("F2", today, today + dt.timedelta(days=1), True)[-1][1]
        self.append(self.clock, None, "forecast", "open-meteo", None, "Open-Meteo", "API", "info",
                    note="; ".join(f"{fmt_day(d)} {mm:.1f} mm" for d, mm in rain.items()) + f" (total {total:.1f} mm)",
                    note_t=i18n.cat(i18n.join_list([tr("log.day_mm", day=i18n.day(d), mm=f"{mm:.1f}") for d, mm in rain.items()], sep="; "),
                                    tr("log.total", mm=f"{total:.1f}")))
        result["inputs"].append("Open-Meteo: " + ", ".join(f"{fmt_day(d)} {mm:.1f} mm" for d, mm in rain.items()) + f" = {total:.1f} mm")
        result["changed"].append(f"Water balance: with specific yield {self.spec['F2'].sy:.2f}, 1 cm of rain lifts the water table by {1 / self.spec['F2'].sy:.1f} cm below the surface.")
        result["changed"].append(f"F2 should be re-flooded: {fmt_cm(before)} → about {fmt_cm(after)} by tomorrow morning.")
        result["changed"].append("Agent pauses the pump run and asks for readings tomorrow morning.")
        self.say("Open-Meteo", "system", f"Mưa qua đêm {total:.1f} mm (Open-Meteo, 26–27/02/2026)", f"Overnight rain {total:.1f} mm (Open-Meteo archive)",
                 tl=tr("chat.rain", mm=f"{total:.1f}"))
        self.tool("Water-balance tool (FAO-56)", f"F2 {fmt_cm(before)} → {fmt_cm(after)}: 1 cm rain lifts the water table {1 / self.spec['F2'].sy:.1f} cm",
                  tr("tr.rainlift", a=fmt_cm(before), b=fmt_cm(after), x=f"{1 / self.spec['F2'].sy:.1f}"))
        result["focal"] = {"kind": "rain", "total_mm": round(total, 1), "days": [[fmt_day(d), round(mm, 1), d.isoformat()] for d, mm in rain.items()],
                           "fid": "F2", "before_cm": before, "after_cm": round(after, 1), "sy": self.spec["F2"].sy,
                           "lift_cm_per_cm": round(1 / self.spec["F2"].sy, 1)}
        return "Re-plan after the rain"

    def candidates_for(self, fid, sender):
        if fid in REMEASURE_OPTIONS:
            options = [dict(o) for o in REMEASURE_OPTIONS[fid]]
            for option in options:
                if option["name"] == sender and option["independent"]:
                    option.update(independent=False, role=option["role"] + " (same person who sent the disputed report)")
            if sender not in (o["name"] for o in REMEASURE_OPTIONS[fid] if o["independent"]):
                return REMEASURE_OPTIONS[fid]
        else:
            farmer = self.spec[fid].owner
            options = [
                {"name": f"{sender}, same gauge", "role": "re-read the same tube", "walk_min": 0, "response_rate": 0.85, "independent": False},
                {"name": f"{farmer}, gauge near the inlet", "role": "farmer measures a second tube", "walk_min": 3, "response_rate": 0.85, "independent": fid != "F3"},
                {"name": HTX_OFFICER, "role": "HTX officer measures a second tube", "walk_min": 12, "response_rate": 0.95, "independent": True},
                {"name": "Hộ thửa bên cạnh", "role": "neighbour reads a second tube", "walk_min": 5, "response_rate": 0.8, "independent": True},
            ]
            for option in options[1:]:
                if option["name"].startswith(sender):
                    option.update(independent=False, role=option["role"] + " (same person who sent the disputed report)")
        if sum(o["independent"] for o in options) < 2:
            options.append(dict(TECH_OFFICER_OPTION))
        return options

    def ask_remeasure(self, fid, reporter, situation, result, use_llm=True):
        self.progress(tr("p.ask"))
        candidates = self.candidates_for(fid, reporter)
        interpreter = self.interpreter if use_llm else self.rules
        choice = interpreter.choose_remeasurer({"fid": fid}, reporter, candidates, situation)
        self.pending.setdefault(fid, {}).update({"ask": f"{choice['person']['name']} / {choice['fallback']['name']}", "deadline": "today", "message": choice["message_vi"]})
        not_chosen_t = [i18n.candidate(c["name"], c["role"]) for c in candidates if not c["independent"]]
        message_t = choice.get("message_t") or {"vi": choice["message_vi"], "en": choice.get("message_en", "")}
        ask = {"person": choice["person"]["name"], "role": choice["person"]["role"], "fallback": choice["fallback"]["name"],
               "field": fid, "why": choice["why"], "not_chosen": choice["rejected"], "not_chosen_t": not_chosen_t, "message_vi": choice["message_vi"],
               "message_en": choice.get("message_en", ""), "message_t": message_t, "deadline": "today", **self.engine_tag(choice)}
        result["asks"].append(ask)
        self.say("RiceBridge agent", "agent", choice["message_vi"], choice.get("message_en", ""), tl=message_t, to=self.spec[fid].owner, **self.engine_tag(choice))
        self.tool("Independence check", f"pick {choice['person']['name']} · fallback {choice['fallback']['name']}; rejected: "
                  + (", ".join(choice["rejected"]) or "none"),
                  tr("tr.indep", pick=i18n.person(choice["person"]["name"]), fallback=i18n.person(choice["fallback"]["name"]),
                     rejected=i18n.join_list(not_chosen_t) if not_chosen_t else tr("tr.none")))
        return ask

    def on_photo(self, event, result):
        fid = event["field"]
        spec = self.spec[fid]
        sensor = round(self.levels[fid] + spec.sensor_bias, 1)
        model = round(self.levels[fid], 1)
        rain = sum(self.weather[self.clock.date() - dt.timedelta(days=i)]["rain_mm"] for i in (1, 2))
        image_path = DEMO_DIR / event["image"] if event.get("image") else None
        context = {"sensor_cm": sensor, "water_balance_cm": model, "latest_rain_at": event.get("rain_at"),
                   "submitted_at": self.clock.isoformat(timespec="minutes")}
        self.progress(tr("p.vision"))
        vision = vision_hook.read_gauge_photo(image_path, replay=self.vision_replay, context=context)
        photo = round(vision["reading_cm"], 1) if vision["reading_cm"] is not None else event["value_cm"]
        captured_at = vision.get("captured_at") or event["captured_at"]
        result["vision"] = {**vision, "image": event["image"] if image_path and image_path.exists() else None, "used_cm": photo,
                            "scripted_cm": event["value_cm"]}
        if vision["engine"] == "vision":
            self.trace.append({"kind": "llm", "task": "read_gauge_photo", "model": vision.get("model"), "ms": int((vision.get("llm_seconds") or 0) * 1000),
                               "source": "cache" if vision.get("source") == "cache" else "live",
                               "summary": f"{fmt_cm(photo)} · conf {vision['confidence']:.2f} · EXIF {str(captured_at).replace('T', ' ')}",
                               "summary_t": tr("tr.vision", cm=fmt_cm(photo), c=f"{vision['confidence']:.2f}", when=str(captured_at).replace("T", " ")[:16])})
            if vision["flags"]:
                self.tool("Photo consistency check", "; ".join(f["code"] for f in vision["flags"]) + f" → photo usable: {vision['photo_usable']}",
                          tr("tr.photocheck", codes="; ".join(f["code"] for f in vision["flags"]), usable=tr("tr.yes") if vision["photo_usable"] else tr("tr.no")))
        else:
            self.tool("Gauge photo reading", f"scripted reading {fmt_cm(photo)} ({vision['reason']})",
                      tr("tr.scripted", cm=fmt_cm(photo), reason=i18n.vision_reason(vision["reason"])))
        photo_meta = {"image": result["vision"]["image"], "reading_cm": photo, "confidence": vision.get("confidence"),
                      "captured_at": captured_at, "engine": vision["engine"], "model": vision.get("model"),
                      "flags": [f["code"] for f in vision.get("flags", [])]}
        self.say(event["reporter"], "farmer", event["chat_vi"], event["chat_en"], tl={"vi": event["chat_vi"], "en": event["chat_en"], "ja": event["chat_ja"]},
                 photo=fmt_cm(photo), image=result["vision"]["image"], vision=photo_meta)
        note_t = i18n.cat(tr("log.photo", up=i18n.moment(self.clock), cap=i18n.moment(captured_at), a=f"{abs(photo - sensor):.1f}", b=f"{abs(photo - model):.1f}"),
                          tr("log.photo_read", model=vision.get("model"), c=f"{vision['confidence']:.2f}") if vision["engine"] == "vision" else None,
                          tr("log.sha", sha=vision["sha256"][:12]) if vision.get("sha256") else None, sep="; ")
        entry = self.append(self.clock, fid, "water_level", "photo", photo, event["reporter"], "photo app", "suspicious",
                            note=f"uploaded {self.clock.strftime('%d/%m %H:%M')}; capture time {str(captured_at).replace('T', ' ')}; "
                                 f"{abs(photo - sensor):.1f} cm from sensor, {abs(photo - model):.1f} cm from water balance"
                                 + (f"; read by {vision.get('model')} (confidence {vision['confidence']:.2f})" if vision["engine"] == "vision" else "")
                                 + (f"; sha {vision['sha256'][:12]}" if vision.get("sha256") else ""), note_t=note_t)
        self.pending[fid] = {"entry": entry["seq"], "captured_at": captured_at, "value_cm": photo}
        result["inputs"].append(f"Photo from {event['reporter']}: {fmt_cm(photo)}")
        result["inputs"].append(f"Sensor 06:00: {fmt_cm(sensor)} · Water balance: {fmt_cm(model)}")
        result["conflicts"].append({
            "field": fid,
            "sources": [["Gauge photo", photo], ["Sensor", sensor], ["Water balance", model]],
            "gap_cm": round(abs(photo - sensor), 1), "threshold_cm": SENSOR_PHOTO_CONFLICT_CM,
            "verdict": f"Sensor and water balance agree after {rain:.0f} mm of rain; the photo is the odd one out. The agent suspects the photo, not the sensor, and does not use it.",
            "verdict_t": tr("c.photo", mm=f"{rain:.0f}"),
        })
        self.tool("Conflict check", f"photo {fmt_cm(photo)} vs sensor {fmt_cm(sensor)}: gap {abs(photo - sensor):.1f} cm > {SENSOR_PHOTO_CONFLICT_CM} cm → photo held as suspicious",
                  tr("tr.conflict_photo", a=fmt_cm(photo), b=fmt_cm(sensor), g=f"{abs(photo - sensor):.1f}", t=SENSOR_PHOTO_CONFLICT_CM))
        self.ask_remeasure(fid, event["reporter"], {"rain_mm_last_2_days": round(rain, 1), "officer": "anh Hùng", "photo_cm": photo,
                                                    "sensor_cm": sensor, "water_balance_cm": model}, result)
        result["changed"].append(f"{fid} keeps the sensor/water-balance level {fmt_cm(model)} until an independent reading arrives.")
        result["focal"] = {"kind": "photo", "fid": fid}
        result["verdict"] = {"kind": "held", "text": f"Photo {fmt_cm(photo)} held as suspicious; independent reading requested",
                             "text_t": tr("v.held_photo", cm=fmt_cm(photo))}
        return "Re-plan with the photo held"

    def resolve_pending(self, fid, value, reporter, result):
        pend = self.pending.pop(fid)
        new = self.append(self.clock, fid, "water_level", "second_gauge", value, reporter, "second gauge tube", "accepted",
                          note=f"independent reading requested for entry #{pend['entry']}", note_t=tr("log.second", n=pend["entry"]))
        disputed = pend.get("value_cm")
        captured = dt.datetime.fromisoformat(pend["captured_at"]) if pend.get("captured_at") else None
        rain_at, rain_total = self.latest_rain()
        agrees = disputed is not None and abs(value - disputed) <= SENSOR_PHOTO_CONFLICT_CM
        if agrees:
            status, reason = "accepted", f"confirmed: the independent reading {fmt_cm(value)} agrees with entry #{pend['entry']} ({fmt_cm(disputed)})"
            reason_t = tr("res.confirmed", v=fmt_cm(value), n=pend["entry"], d=fmt_cm(disputed))
            result["changed"].append(f"The independent reading confirms entry #{pend['entry']}; both are kept as evidence.")
        elif captured and rain_at and captured < rain_at:
            status, reason = "rejected", f"misread: capture time {captured.strftime('%a %d %b %H:%M')} is before the {rain_total:.0f} mm rain (old photo re-sent)"
            reason_t = tr("res.misread", when=i18n.moment(captured), mm=f"{rain_total:.0f}")
            result["changed"].append(f"First photo marked as misread. Reason: capture time shows {captured.strftime('%A %d %b')}, before the rain.")
        else:
            status, reason = "rejected", "replaced by an independent second-gauge reading"
            reason_t = tr("res.replaced")
            result["changed"].append(f"Entry #{pend['entry']} replaced by the independent reading.")
        self.append(self.clock, fid, "review", "model", None, "RiceBridge Ops agent", "conflict check", status,
                    ref=pend["entry"], note=f"entry #{pend['entry']} {reason}; kept for audit" + ("" if agrees else f", replaced by #{new['seq']}"),
                    note_t=i18n.cat(tr("log.review", n=pend["entry"], reason=reason_t), None if agrees else tr("log.replaced_by", m=new["seq"]), sep=""))
        self.levels[fid] = value
        result["changed"].append(f"Second-gauge reading {fmt_cm(value)} kept as evidence for {fid}. The old record stays in the log.")
        self.tool("Evidence log", f"#{new['seq']} accepted; #{pend['entry']} marked {status} with its reason, never deleted (hash-chained)",
                  tr("tr.evlog", new=new["seq"], old=pend["entry"], status=tr("status." + status)))
        result["focal"] = {"kind": "resolved", "fid": fid, "new_cm": value, "old_cm": disputed, "old_seq": pend["entry"],
                           "new_seq": new["seq"], "status": status, "reason": reason, "reason_t": reason_t, "recorder": reporter,
                           "captured_at": pend.get("captured_at")}
        result["verdict"] = {"kind": "verified", "text": f"{fid} {fmt_cm(value)} from an independent gauge · #{pend['entry']} {status}",
                             "text_t": tr("v.verified", fid=fid, cm=fmt_cm(value), n=pend["entry"], status=tr("status." + status))}

    def intake(self, text, sender, source, via, default_field, result, independent=False):
        owners = {f.owner: f.fid for f in FIELDS}
        self.progress(tr("p.parse"))
        parsed = self.interpreter.parse_message(text, sender, default_field, owners)
        self.progress(tr("p.guards"))
        rule = self.rules.parse_voice(text)
        hits = instruction_hits(text)
        result["parse"] = {**parsed, "rule_value_cm": rule["value_cm"], "rule": rule["rule"], "instruction_hits": hits, "message": text,
                           "sender": sender}
        fid, value, conf = parsed.get("field"), parsed.get("value_cm"), parsed.get("confidence", 0)
        self.say(sender, "htx" if sender == HTX_OFFICER else "farmer", text, parsed.get("gloss_en", ""), tl=parsed.get("gloss_t"),
                 parsed={"intent": parsed["intent"], "field": fid, "value_cm": value, "confidence": conf}, **self.engine_tag(parsed))
        kind, check = "clarify", None
        hits_t = ", ".join(f"“{h}”" for h in hits)
        if hits:
            verdict, kind = f"message gives instructions to the agent ({', '.join(hits)}): nothing recorded; only the HTX approves plans", "refused"
            verdict_t = tr("v.refused", hits=hits_t)
            self.tool("Instruction guard", f"matched {', '.join(hits)} → message treated as data, never as a command", tr("tr.guard", hits=hits_t))
        elif parsed["intent"] != "water_level" or value is None:
            verdict, kind = "not a water-level reading: nothing recorded, no plan change", "not_reading"
            verdict_t = tr("v.not_reading")
        elif fid is None:
            verdict = "field unknown: ask which field"
            verdict_t = tr("v.no_field")
        elif not GAUGE_FLOOR_CM <= value <= BUND_CM:
            verdict = f"{fmt_cm(value)} is outside the physical range ({fmt_cm(GAUGE_FLOOR_CM)} to {fmt_cm(BUND_CM)}, bund height): not recorded; ask again"
            verdict_t, check = tr("v.range", v=fmt_cm(value), lo=fmt_cm(GAUGE_FLOOR_CM), hi=fmt_cm(BUND_CM)), "again"
        elif rule["value_cm"] is not None and abs(rule["value_cm"] - value) > PARSER_AGREEMENT_CM:
            verdict = f"LLM {fmt_cm(value)} and rule parser {fmt_cm(rule['value_cm'])} disagree: ask again"
            verdict_t, check = tr("v.disagree", a=fmt_cm(value), b=fmt_cm(rule["value_cm"])), "again"
        elif conf < ACCEPT_CONFIDENCE:
            verdict = f"confidence {conf:.2f} < {ACCEPT_CONFIDENCE}: estimate not recorded as evidence; ask for the gauge number"
            verdict_t = tr("v.lowconf", c=f"{conf:.2f}", t=ACCEPT_CONFIDENCE)
        else:
            verdict = None
        if verdict:
            self.tool("Reading intake guardrail", verdict, verdict_t)
            if parsed.get("reply_vi"):
                reply_t = dict(parsed.get("reply_t") or {"vi": parsed["reply_vi"], "en": parsed.get("reply_en", "")})
            else:
                reply_t = tr("chat.ask_field") if fid is None else tr("chat.ask_gauge_field", n=fid[1:])
            if kind == "refused":
                reply_t = dict(parsed.get("reply_t") or {}) if parsed["intent"] != "water_level" and parsed.get("reply_vi") else dict(REFUSAL_T)
            elif check == "again":
                reply_t = tr("chat.ask_again", n=fid[1:])
            if parsed["intent"] == "water_level" and fid in FIELD_IDS:
                self.append(self.clock, fid, "message", source, None, sender, via, "clarify",
                            note=f"“{text}” → not recorded ({verdict})", note_t=tr("log.clarify", quote=f"“{text}”", verdict=verdict_t))
            self.say("RiceBridge agent", "agent", reply_t["vi"], reply_t.get("en", ""), tl=reply_t, to=sender, **self.engine_tag(parsed))
            result["changed"].append(f"Guardrail: {verdict}.")
            result["state_change"] = False
            result["verdict"] = {"kind": kind, "text": verdict, "text_t": verdict_t}
            return None
        result["inputs"].append(f"{sender}: “{text}” → {fid} {fmt_cm(value)} (confidence {conf:.2f})")
        if fid in self.pending and independent:
            self.tool("Reading intake guardrail", f"{fid} {fmt_cm(value)} from an independent gauge resolves the open conflict",
                      tr("tr.indep_resolve", fid=fid, cm=fmt_cm(value)))
            self.resolve_pending(fid, value, sender, result)
            return fid
        model = round(self.levels[fid], 1)
        if abs(value - model) > SENSOR_PHOTO_CONFLICT_CM:
            entry = self.append(self.clock, fid, "water_level", source, value, sender, via, "suspicious",
                                note=f"“{text}” → {fmt_cm(value)}; water balance {fmt_cm(model)}; gap > {SENSOR_PHOTO_CONFLICT_CM} cm",
                                note_t=tr("log.suspicious", quote=f"“{text}”", v=fmt_cm(value), m=fmt_cm(model), t=SENSOR_PHOTO_CONFLICT_CM))
            self.pending[fid] = {"entry": entry["seq"], "captured_at": None, "value_cm": value}
            self.tool("Conflict check", f"{fid} report {fmt_cm(value)} vs water balance {fmt_cm(model)}: gap {abs(value - model):.1f} cm > {SENSOR_PHOTO_CONFLICT_CM} cm → held, ask for an independent reading",
                      tr("tr.conflict_held", fid=fid, v=fmt_cm(value), m=fmt_cm(model), g=f"{abs(value - model):.1f}", t=SENSOR_PHOTO_CONFLICT_CM))
            result["conflicts"].append({"field": fid, "sources": [["Chat report", value], ["Water balance", model]],
                                        "gap_cm": round(abs(value - model), 1), "threshold_cm": SENSOR_PHOTO_CONFLICT_CM,
                                        "verdict": "The report and the water balance disagree by more than 5 cm. The agent keeps the water-balance level and asks for an independent reading.",
                                        "verdict_t": tr("c.chat")})
            self.ask_remeasure(fid, sender, {"report_cm": value, "water_balance_cm": model, "reported_by": sender}, result)
            result["changed"].append(f"{fid} report {fmt_cm(value)} held as suspicious (water balance {fmt_cm(model)}); the plan keeps the water-balance level until an independent reading arrives.")
            result["verdict"] = {"kind": "held", "text": f"{fid} {fmt_cm(value)} held: {abs(value - model):.1f} cm from the water balance",
                                 "text_t": tr("v.held", fid=fid, v=fmt_cm(value), g=f"{abs(value - model):.1f}")}
            return fid
        self.append(self.clock, fid, "water_level", source, value, sender, via, "accepted",
                    note=f"“{text}” → {fmt_cm(value)}; water balance {fmt_cm(model)}",
                    note_t=tr("log.accepted", quote=f"“{text}”", v=fmt_cm(value), m=fmt_cm(model)))
        self.levels[fid] = value
        self.tool("Conflict check", f"{fid} {fmt_cm(value)} vs water balance {fmt_cm(model)}: within {SENSOR_PHOTO_CONFLICT_CM} cm → accepted with recorder {sender}",
                  tr("tr.conflict_ok", fid=fid, v=fmt_cm(value), m=fmt_cm(model), t=SENSOR_PHOTO_CONFLICT_CM, who=i18n.person(sender)))
        result["changed"].append(f"{fid} recorded at {fmt_cm(value)}, recorder {sender} (water balance said {fmt_cm(model)}).")
        result["verdict"] = {"kind": "recorded", "text": f"{fid} {fmt_cm(value)} recorded as evidence · recorder {sender}",
                             "text_t": tr("v.recorded", fid=fid, v=fmt_cm(value), who=i18n.person(sender))}
        return fid

    def on_remeasure(self, event, result):
        fid = self.intake(event["transcript"], event["reporter"], "second_gauge", "second gauge tube, chat", event["field"], result, independent=True)
        return "Re-plan after the second-gauge reading" if fid else None

    def on_voice(self, event, result):
        fid = self.intake(event["transcript"], event["reporter"], "htx_voice", "voice note by HTX officer", None, result)
        if fid == "F3":
            result["changed"].append("Bà Sáu (74) does not use a smartphone; her field has evidence like every other field.")
            result["focal"] = {"kind": "assisted", "fid": "F3", "owner": "Bà Sáu", "age": 74, "value_cm": self.levels["F3"],
                               "recorder": event["reporter"], "transcript": event["transcript"]}
        return "Re-plan with the HTX report" if fid else None

    def on_pump_change(self, event, result):
        old, new = dt.date.fromisoformat(event["from"]), dt.date.fromisoformat(event["to"])
        self.progress(tr("p.notice"))
        parsed = self.interpreter.parse_message(event["transcript"], event["reporter"], None, {f.owner: f.fid for f in FIELDS})
        self.say(event["reporter"], "htx", event["transcript"], parsed.get("gloss_en", ""), tl=parsed.get("gloss_t"),
                 parsed={"intent": parsed["intent"], "field": None, "value_cm": None, "confidence": parsed.get("confidence", 0)}, **self.engine_tag(parsed))
        self.runs[old] = "cancelled"
        self.append(self.clock, None, "pump_schedule", "htx_record", None, "HTX", "HTX notice", "info",
                    note=f"run {fmt_day(old)} moved to {fmt_day(new)}", note_t=tr("log.moved", a=i18n.day(old), b=i18n.day(new)))
        self.tool("Pump calendar", f"HTX notice applied from the station record: {fmt_day(old)} → {fmt_day(new)} (the LLM only labels the message intent)",
                  tr("tr.pumpcal", a=i18n.day(old), b=i18n.day(new)))
        result["inputs"].append(f"HTX notice: run {fmt_day(old)} moved to {fmt_day(new)}")
        days_old, days_new = (old - self.clock.date()).days, (new - self.clock.date()).days
        result["changed"].append(f"Every field must now last {days_new} days instead of {days_old}.")
        result["changed"].append("Scheduler re-run for the whole cluster with the new readings; proposal sent to the pump-station manager.")
        result["focal"] = {"kind": "pump", "from_label": fmt_day(old), "to_label": fmt_day(new), "from_date": old.isoformat(), "to_date": new.isoformat(),
                           "days_before": days_old, "days_after": days_new,
                           "intent": parsed["intent"], "transcript": event["transcript"]}
        return "Re-plan after the pump moved"

    def post_message(self, sender, text):
        if not isinstance(text, str):
            raise DemoError(tr("err.not_text"))
        text = " ".join(text.split())[:300]
        if not text:
            raise DemoError(tr("err.empty"))
        if sender not in SENDERS:
            raise DemoError(tr("err.unknown_sender_list", list=i18n.join_list([i18n.person(x) for x in SENDERS])))
        self.clock = min(self.clock + dt.timedelta(minutes=5), dt.datetime.combine(self.clock.date(), dt.time(23, 55)))
        result = self.begin()
        log_start = len(self.log)
        source = "htx_voice" if sender == HTX_OFFICER else "farmer_text"
        via = "chat by HTX officer" if sender == HTX_OFFICER else "Zalo chat"
        fid = self.intake(text, sender, source, via, SENDERS[sender], result, independent=sender == HTX_OFFICER)
        result["focus"] = fid
        result["focal"] = result["focal"] if result.get("focal") and result["focal"]["kind"] == "resolved" else {"kind": "live"}
        event = {"id": "message", "time": self.clock.isoformat(timespec="minutes"), "title": f"Live message from {sender}",
                 "title_vi": f"Tin nhắn mới từ {sender}", "title_ja": f"{sender} からのライブメッセージ", "short": "Live message",
                 "transcript": text, "sender": sender}
        self.finish(f"Re-plan after a message from {sender}" if fid else None, result, log_start,
                    title_t=tr("title.message", who=i18n.person(sender)))
        self.history.append({"event": event, "result": result})
        return self.history[-1]

    def goto(self, step):
        if isinstance(step, bool) or not isinstance(step, int):
            raise DemoError(tr("err.step_int"))
        self.reset()
        target = max(-1, min(step, len(EVENTS) - 1))
        while self.step < target:
            self.next_event(inline_brief=True)

    def verify_chain(self, tamper=False):
        rows = [dict(e) for e in self.log]
        tampered = None
        if tamper:
            target = next((e for e in rows if e["source"] == "second_gauge"), None) or next((e for e in rows if e["value_cm"] is not None), None)
            if target:
                target["value_cm"] = round(target["value_cm"] - 10, 1)
                tampered = {"seq": target["seq"], "field": target["field"], "from": round(target["value_cm"] + 10, 1), "to": target["value_cm"]}
        prev = "0" * 16
        for e in rows:
            body = {k: v for k, v in e.items() if k != "hash"}
            digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
            if e["prev_hash"] != prev or digest != e["hash"]:
                return {"ok": False, "checked": e["seq"] - 1, "total": len(rows), "broken_at": e["seq"], "tampered": tampered,
                        "expected": e["hash"], "recomputed": digest}
            prev = e["hash"]
        return {"ok": True, "checked": len(rows), "total": len(rows), "head": prev, "tampered": tampered}

    def evidence_json(self):
        return {"export": "RiceBridge Ops evidence log", "label": SCENARIO_LABEL, "cluster": CLUSTER_NAME,
                "exported_at_scenario_clock": self.clock.isoformat(timespec="minutes"),
                "hash": "sha256 of the record JSON (sorted keys, without 'hash'), first 16 hex; prev_hash links each record to the one before",
                "chain_head": self.log[-1]["hash"] if self.log else None, "verification": self.verify_chain(),
                "weather": self.weather_meta, "completeness": self.completeness(), "records": self.log}

    def next_event(self, inline_brief=False):
        if self.step + 1 >= len(EVENTS):
            return None
        self.step += 1
        event = EVENTS[self.step]
        result = self.handle(event, inline_brief=inline_brief)
        self.history.append({"event": event, "result": result})
        return self.history[-1]

    def decide(self, decision, note="", note_t=None):
        if decision not in ("approve", "reject"):
            raise DemoError(tr("err.decision"))
        if self.plan is None or self.plan["status"] != "proposed":
            return False
        note = " ".join(str(note or "").split())[:200]
        when = self.clock + dt.timedelta(minutes=35)
        self.plan["status"] = "approved" if decision == "approve" else "rejected"
        self.plan["decided_by"] = STATION_MANAGER
        self.plan["decision_note"] = note
        self.plan["decided_at"] = when.isoformat(timespec="minutes")
        note_t = note_t or (i18n.lit(note) if note else None)
        self.append(when, None, "decision", "htx_record", None, STATION_MANAGER, "dashboard", self.plan["status"],
                    note=f"{self.plan['id']} {self.plan['status']}" + (f": “{note}”" if note else ""),
                    note_t=i18n.cat(tr("log.decision", id=self.plan["id"], status=tr("status." + self.plan["status"])), note_t, sep=": "))
        verb_vi, verb_en = ("đã duyệt", "approved") if decision == "approve" else ("không duyệt", "rejected")
        run_t = i18n.day(self.plan["run_date"])
        boss_t = tr("chat.approved" if decision == "approve" else "chat.rejected", id=self.plan["id"], run=run_t)
        boss_t = i18n.cat(boss_t, i18n.capitalized(note_t)) if note_t else boss_t
        self.chat.append({"n": len(self.chat) + 1, "time": when.isoformat(timespec="minutes"), "from": STATION_MANAGER, "role": "boss",
                          "vi": boss_t["vi"], "en": f"Station {verb_en} plan {self.plan['id']} ({self.plan['run_label']}).", "tl": boss_t, "engine": "human"})
        for row in self.plan["rows"]:
            self.append(when, row["fid"], "decision", "htx_record", None, STATION_MANAGER, "dashboard", self.plan["status"],
                        note=f"{self.plan['id']} {row['action_label']} ({self.plan['run_label']}): {row['reason']}",
                        sources=row["sources"], sources_t=row["sources_t"],
                        note_t=tr("log.decision_row", id=self.plan["id"], action=i18n.action(row["action"]), run=run_t, reason=row["reason_t"]))
        if decision == "reject":
            ack = tr("chat.reject_ack", id=self.plan["id"])
            self.say("RiceBridge agent", "agent", ack["vi"], ack["en"], tl=ack, engine="rules")
        self.whatif = None
        return True

    def completeness(self):
        today = self.clock.date()
        out = []
        for f in FIELDS:
            rows = [e for e in self.log if e["field"] == f.fid]
            levels = sorted(dt.datetime.fromisoformat(e["time"]).date() for e in rows
                            if e["kind"] == "water_level" and e["status"] == "accepted")
            points = [MRV_WINDOW_START] + levels + [today]
            worst_gap = max(((b - a).days, a, b) for a, b in zip(points, points[1:]))
            person = [e for e in rows if e["kind"] == "water_level" and e["status"] == "accepted" and e["source"] in PERSON_READ_SOURCES
                      and dt.datetime.fromisoformat(e["time"]).date() > MRV_WINDOW_START]
            decided = any(e["kind"] == "decision" and e["status"] == "approved" for e in rows)
            meta_ok = all(e["time"] and e["recorder"] and e["lat"] and e["source"] for e in rows)
            waiting = f.fid in self.pending or f.fid in self.measure_requests
            checks = [
                ("Water level every ≤3 days", worst_gap[0] <= STALE_READING_DAYS,
                 f"{worst_gap[0]}-day gap in water-level readings ({fmt_day(worst_gap[1])} → {fmt_day(worst_gap[2])})",
                 tr("miss.gap", n=worst_gap[0], a=i18n.day(worst_gap[1]), b=i18n.day(worst_gap[2]))),
                ("Gauge read by a person", bool(person), "Sensor only: no gauge photo or HTX reading to cross-check it", tr("miss.person")),
                ("No open check or conflict", not waiting,
                 "Waiting for an independent reading" if f.fid in self.pending else "Waiting for HTX reading before the inlet opens",
                 tr("miss.pending") if f.fid in self.pending else tr("miss.measure")),
                ("Decision approved by HTX", decided, "Latest pump plan not yet approved", tr("miss.decision")),
                ("Source, time, GPS, recorder", meta_ok, "Record missing metadata", tr("miss.meta")),
            ]
            done = sum(ok for _, ok, _, _ in checks)
            out.append({"fid": f.fid, "owner": f.owner, "score": round(100 * done / len(checks)), "complete": done == len(checks),
                        "checks": [{"name": n, "ok": ok} for n, ok, _, _ in checks],
                        "missing": [m for _, ok, m, _ in checks if not ok], "missing_t": [mt for _, ok, _, mt in checks if not ok],
                        "records": len(rows)})
        return out

    def decision_reasons(self):
        rows = [e for e in self.log if e["kind"] == "decision" and e["field"]]
        latest = {}
        for e in rows:
            latest[e["field"]] = e
        return [latest[f.fid] for f in FIELDS if f.fid in latest]

    def save_state(self):
        return {name: copy.deepcopy(getattr(self, name)) for name in MUTABLE_STATE}

    def restore_state(self, saved):
        for name, value in saved.items():
            setattr(self, name, value)

    def photo_context(self, fid):
        spec = self.spec[fid]
        rain_at, _ = self.latest_rain()
        return {"sensor_cm": round(self.levels[fid] + spec.sensor_bias, 1) if spec.has_sensor else None,
                "water_balance_cm": round(self.levels[fid], 1),
                "latest_rain_at": rain_at.isoformat(timespec="minutes") if rain_at else None,
                "submitted_at": self.clock.isoformat(timespec="minutes")}

    def what_if(self, kind, params, vision=None):
        if self.plan is None:
            raise DemoError(tr("err.press_next"))
        base = self.plan
        params = dict(params or {})
        saved = self.save_state()
        try:
            self.trace = []
            today = self.clock.date()
            out = {"kind": kind, "params": params, "base_id": base["id"], "made_at": self.clock.isoformat(timespec="minutes"),
                   "notes": [], "notes_t": [], "flags": [], "vision": None, "conflict": None, "ask": None, "applied": True}
            if kind == "rain":
                mm = plain_number(params.get("mm", 20))
                if not 0 < mm <= MAX_WHATIF_RAIN_MM:
                    raise DemoError(tr("err.rain_range", max=f"{MAX_WHATIF_RAIN_MM:g}"))
                real = self.weather[today]["rain_mm"]
                self.extra_rain[today] = mm
                label = f"+{mm:g} mm rain forecast for {fmt_day(today)}"
                label_t = tr("wi.rain_label", mm=f"{mm:g}", day=i18n.day(today))
                self.tool("Water-balance tool (FAO-56)", f"forecast {fmt_day(today)}: {real:.1f} mm Open-Meteo + {mm:g} mm what-if = {real + mm:.1f} mm; projection re-run for 6 fields",
                          tr("tr.wi_rain", day=i18n.day(today), real=f"{real:.1f}", mm=f"{mm:g}", tot=f"{real + mm:.1f}"))
                out["notes"].append(f"Forecast for today becomes {real + mm:.1f} mm ({real:.1f} mm Open-Meteo + {mm:g} mm what-if).")
                out["notes_t"].append(tr("wi.rain_note", tot=f"{real + mm:.1f}", real=f"{real:.1f}", mm=f"{mm:g}"))
            elif kind == "flowering":
                fid = params.get("fid")
                if fid not in FIELD_IDS:
                    raise DemoError(tr("err.choose_field"))
                self.stage_override[fid] = (today, today + dt.timedelta(days=FLOWERING_DAYS), "heading")
                label = f"{fid} flowers from {fmt_day(today)}"
                label_t = tr("wi.flower_label", fid=fid, day=i18n.day(today))
                self.tool("Crop-stage safety tool", f"{fid} set to flowering for {FLOWERING_DAYS} days: needs standing water (≥ {WET_MARGIN_CM:g} cm) every day; drying not allowed",
                          tr("tr.wi_flower", fid=fid, n=FLOWERING_DAYS, w=f"{WET_MARGIN_CM:g}"))
                out["notes"].append(f"{fid} is treated as flowering for {FLOWERING_DAYS} days, so it must keep standing water.")
                out["notes_t"].append(tr("wi.flower_note", fid=fid, n=FLOWERING_DAYS))
            elif kind == "pump":
                try:
                    new = dt.date.fromisoformat(str(params.get("date")))
                except ValueError as exc:
                    raise DemoError(tr("err.choose_date")) from exc
                if not today < new <= today + dt.timedelta(days=MAX_PUMP_SHIFT_DAYS):
                    raise DemoError(tr("err.date_range", n=MAX_PUMP_SHIFT_DAYS, day=i18n.day(today)))
                current, _ = self.run_window(today)
                if new == current:
                    raise DemoError(tr("err.same_day", day=i18n.day(new)))
                if current in self.runs:
                    self.runs[current] = "cancelled"
                self.runs[new] = "scheduled"
                label = f"next pump run {fmt_day(current)} → {fmt_day(new)}"
                label_t = tr("wi.pump_label", a=i18n.day(current), b=i18n.day(new))
                self.tool("Pump calendar", f"what-if: run {fmt_day(current)} moved to {fmt_day(new)}; every field must last {(new - today).days} days instead of {(current - today).days}",
                          tr("tr.wi_pump", a=i18n.day(current), b=i18n.day(new), n=(new - today).days, m=(current - today).days))
                out["notes"].append(f"Every field must now last {(new - today).days} days instead of {(current - today).days}.")
                out["notes_t"].append(tr("wi.pump_note", n=(new - today).days, m=(current - today).days))
            elif kind == "photo":
                fid = params.get("fid")
                if fid not in FIELD_IDS:
                    raise DemoError(tr("err.choose_field"))
                if vision is None:
                    raise DemoError(tr("err.no_reading"))
                label = f"gauge photo {params.get('image_label', 'photo')} for {fid}"
                image_label = params.get("image_label", "photo")
                label_t = tr("wi.photo_label", img=tr("wi.uploaded") if image_label == "uploaded photo" else image_label, fid=fid)
                out.update(self.whatif_photo(fid, vision, params, out))
            else:
                raise DemoError(tr("err.unknown_whatif"))
            plan = self.make_plan("What-if: " + label, tr("title.whatif", label=label_t))
            plan["id"] = f"W·{base['id']}"
            plan["status"] = "what-if"
            diff = self.diff_plans(base, plan)
            plan["diff"], plan["diff_rows"], plan["diff_items"] = diff, self.diff_rows(base, plan), self.diff_items(base, plan)
            self.tool("Pump-capacity scheduler", f"{PUMP_CAPACITY} fields per run → {plan['summary']}", tr("tr.wi_sched", n=PUMP_CAPACITY, summary=plan["summary_t"]))
            self.tool("Approval gate", "what-if plans are a sandbox: nothing written to the evidence log, nothing can be approved", tr("tr.wi_gate"))
            out.update(label=label, label_t=label_t, plan=plan, diff=diff, trace=self.trace, brief={"pending": True})
            payload = self.brief_payload(plan, "What-if: " + label)
        finally:
            self.restore_state(saved)
        self.whatif = out
        return out, payload

    def whatif_photo(self, fid, vision, params, out):
        context = self.photo_context(fid)
        captured = vision.get("captured_at")
        if not params.get("use_exif", True):
            captured = context["submitted_at"]
            out["notes"].append("What-if: capture time assumed to be the upload time (EXIF ignored).")
            out["notes_t"].append(tr("wi.exif_note"))
        reading = vision.get("reading_cm")
        checked = vision_hook.check_consistency(reading, captured, context, vision.get("confidence") or 0.0)
        flags = list(checked["flags"])
        digest = vision.get("sha256")
        if digest and any(digest[:12] in (e.get("note") or "") for e in self.log if e["kind"] == "water_level" and e["source"] == "photo"):
            flags.append({"code": "DUPLICATE_PHOTO", "severity": "high", "message": "Ảnh này đã được gửi trước đó.", "action": "Không dùng ảnh trùng; xin số đo mới."})
        usable = checked["photo_usable"] and not any(f["code"] == "DUPLICATE_PHOTO" for f in flags)
        out["flags"] = flags
        out["vision"] = {**vision, "captured_used": captured, "context": context, "photo_usable": usable}
        llm_source = vision.get("source")
        if vision.get("engine") == "vision":
            self.trace.append({"kind": "llm", "task": "read_gauge_photo", "model": vision.get("model"), "ms": int((vision.get("llm_seconds") or 0) * 1000),
                               "source": "cache" if llm_source == "cache" else "live",
                               "summary": f"{fmt_cm(reading)} · conf {vision.get('confidence', 0):.2f}",
                               "summary_t": tr("tr.vision_short", cm=fmt_cm(reading), c=f"{vision.get('confidence', 0):.2f}")})
        else:
            self.trace.append({"kind": "llm", "task": "read_gauge_photo", "model": vision.get("model"), "ms": 0, "source": "fallback",
                               "error": vision.get("reason"), "summary": vision.get("reason"), "error_t": i18n.vision_reason(vision.get("reason")),
                               "summary_t": i18n.vision_reason(vision.get("reason"))})
        codes = "; ".join(f["code"] for f in flags)
        self.tool("Photo consistency check", (codes or "no flags") + f" → photo usable: {usable}",
                  tr("tr.photocheck", codes=codes or tr("tr.noflags"), usable=tr("tr.yes") if usable else tr("tr.no")))
        if reading is None:
            out["notes"].append("The photo could not be read, so nothing changes; the agent asks for a clearer photo.")
            out["notes_t"].append(tr("wi.unread_note"))
            out["verdict"] = {"kind": "clarify", "text": vision.get("reason") or "unreadable photo", "text_t": i18n.vision_reason(vision.get("reason"))}
            return {}
        reference = context["water_balance_cm"]
        gap = abs(reading - reference)
        entry_note = f"what-if photo; sha {digest[:12] if digest else '–'}"
        if not usable or gap > SENSOR_PHOTO_CONFLICT_CM:
            entry = self.append(self.clock, fid, "water_level", "photo", reading, self.spec[fid].owner, "photo app", "suspicious", note=entry_note)
            self.pending[fid] = {"entry": entry["seq"], "captured_at": captured, "value_cm": reading}
            sources = [["Gauge photo", reading], ["Water balance", reference]]
            if context["sensor_cm"] is not None:
                sources.insert(1, ["Sensor", context["sensor_cm"]])
            out["conflict"] = {"field": fid, "sources": sources, "gap_cm": round(gap, 1), "threshold_cm": SENSOR_PHOTO_CONFLICT_CM}
            self.tool("Conflict check", f"photo {fmt_cm(reading)} vs water balance {fmt_cm(reference)}: gap {gap:.1f} cm; usable {usable} → held, plan keeps the water-balance level",
                      tr("tr.wi_held", r=fmt_cm(reading), ref=fmt_cm(reference), g=f"{gap:.1f}", u=tr("tr.yes") if usable else tr("tr.no")))
            sink, self.client.sink = self.client.sink, None
            scratch = {"asks": []}
            ask = self.ask_remeasure(fid, self.spec[fid].owner, {"photo_cm": reading, "water_balance_cm": reference}, scratch, use_llm=False)
            self.client.sink = sink
            out["ask"] = ask
            blocking = ", ".join(f["code"] for f in flags if f["code"] in vision_hook.BLOCKING_FLAGS | {"DUPLICATE_PHOTO"})
            out["verdict"] = {"kind": "held", "text": f"photo {fmt_cm(reading)} not used: " + blocking if not usable else f"photo {fmt_cm(reading)} is {gap:.1f} cm from the water balance",
                              "text_t": tr("v.wi_notused", cm=fmt_cm(reading), codes=blocking) if not usable else tr("v.wi_gap", cm=fmt_cm(reading), g=f"{gap:.1f}")}
            return {}
        self.append(self.clock, fid, "water_level", "photo", reading, self.spec[fid].owner, "photo app", "accepted", note=entry_note)
        self.levels[fid] = reading
        self.tool("Conflict check", f"photo {fmt_cm(reading)} vs water balance {fmt_cm(reference)}: within {SENSOR_PHOTO_CONFLICT_CM:g} cm → accepted for the re-plan",
                  tr("tr.wi_ok", r=fmt_cm(reading), ref=fmt_cm(reference), t=f"{SENSOR_PHOTO_CONFLICT_CM:g}"))
        out["verdict"] = {"kind": "recorded", "text": f"photo {fmt_cm(reading)} accepted for {fid} (sandbox)",
                          "text_t": tr("v.wi_ok", cm=fmt_cm(reading), fid=fid)}
        return {}

    def snapshot(self):
        today = self.clock.date()
        fields = []
        for f in FIELDS:
            st = self.stage(f.fid, today)
            fields.append({
                "fid": f.fid, "owner": f.owner, "owner_note": f.owner_note, "lat": f.lat, "lon": f.lon,
                "polygon": f.polygon, "label_xy": f.label_xy, "has_sensor": f.has_sensor,
                "level": round(self.levels[f.fid], 1), "level_basis": self.level_basis(f.fid), "level_basis_t": self.level_basis_t(f.fid),
                "stage": st, "stage_label": STAGE_LABELS[st][0], "stage_vi": STAGE_LABELS[st][1],
                "pending_check": f.fid in self.pending or f.fid in self.measure_requests,
                "conflict": f.fid in self.pending,
            })
        comp = self.completeness()
        return {
            "clock": self.clock.isoformat(timespec="minutes"),
            "clock_label": self.clock.strftime("%a %d %b %Y, %H:%M"),
            "step": self.step, "total_steps": len(EVENTS), "epoch": self.epoch,
            "events": [{"id": e["id"], "title": e["title"], "title_vi": e["title_vi"], "title_ja": e["title_ja"], "short": e["short"],
                        "short_ja": e["short_ja"], "time": e["time"],
                        "title_t": {"en": e.get("title_ui", e["title"]), "ja": e["title_ja"], "vi": e["title_vi"]},
                        "short_t": {"en": e["short"], "ja": e["short_ja"], "vi": e["short_vi"]},
                        "sub_t": dict(zip(i18n.LANGS, e["sub"]))} for e in EVENTS],
            "current": self.history[-1] if self.history else None,
            "history_len": len(self.history),
            "plan": self.plan, "fields": fields, "tasks": self.tasks(),
            "runs": [{"date": d.isoformat(), "label": fmt_day(d), "status": s} for d, s in sorted(self.runs.items())],
            "weather": [{"date": d.isoformat(), **v} for d, v in sorted(self.weather.items())],
            "weather_meta": self.weather_meta, "forecast_horizon_days": FORECAST_HORIZON_DAYS,
            "log": self.log, "log_t": self.log_t, "completeness": comp,
            "complete_fields": sum(c["complete"] for c in comp),
            "decision_reasons": self.decision_reasons(),
            "thresholds": {"awd_cm": AWD_THRESHOLD_CM, "conflict_cm": SENSOR_PHOTO_CONFLICT_CM, "fill_cm": FILL_LEVEL_CM,
                           "pump_capacity": PUMP_CAPACITY, "accept_confidence": ACCEPT_CONFIDENCE, "bund_cm": BUND_CM,
                           "gauge_floor_cm": GAUGE_FLOOR_CM},
            "interpreter": self.interpreter.name, "scenario_label": SCENARIO_LABEL, "cluster_name": CLUSTER_NAME,
            "engine": {"mode": self.client.mode, "llm": self.client.enabled, "cli": bool(self.client.binary),
                       "fast_model": FAST_MODEL, "reason_model": REASON_MODEL, "stats": self.client.stats(),
                       "totals": self.client.totals(), "vision": vision_hook.READER_PATH.exists()},
            "chat": self.chat, "senders": list(SENDERS), "names": self.names(),
            "approver": STATION_MANAGER,
            "whatif": self.whatif,
        }

    def names(self):
        found = set(SENDERS) | {f.owner for f in FIELDS} | {HTX_OFFICER, STATION_MANAGER, TECH_OFFICER_OPTION["name"], "Hộ thửa bên cạnh"}
        found |= {e["recorder"] for e in self.log} | {m.get("from") for m in self.chat} | {m.get("to") for m in self.chat}
        for option in REMEASURE_OPTIONS["F2"]:
            found.add(option["name"])
        for item in self.history[-1:]:
            for ask in item["result"].get("asks", []):
                found |= {ask["person"], ask["fallback"]}
            focal = item["result"].get("focal") or {}
            found.add(focal.get("recorder"))
            found.add(item["event"].get("sender") or item["event"].get("reporter"))
        if self.whatif and self.whatif.get("ask"):
            found |= {self.whatif["ask"]["person"], self.whatif["ask"]["fallback"]}
        return {name: i18n.person(name) for name in found if name}

    def evidence_csv(self):
        cols = ["seq", "time", "field", "kind", "source", "value_cm", "recorder", "via", "lat", "lon", "status", "ref", "note", "sources", "label", "prev_hash", "hash"]
        lines = [",".join(cols)]
        for e in self.log:
            lines.append(",".join('"' + str("" if e[c] is None else e[c]).replace('"', '""') + '"' for c in cols))
        return "\n".join(lines) + "\n"


def run_script():
    demo = Demo(llm_mode="rules")
    for _ in EVENTS:
        step = demo.next_event(inline_brief=True)
        print("=" * 100)
        print(step["event"]["time"], step["event"]["title"])
        for key in ("inputs", "changed", "diff"):
            for line in step["result"][key]:
                print(f"  {key}: {line}")
        for c in step["result"]["conflicts"]:
            print("  conflict:", c["sources"])
        for a in step["result"]["asks"]:
            print("  ask:", a["person"], "|", a["fallback"], "|", a["why"])
        print("  levels:", {k: round(v, 1) for k, v in demo.levels.items()})
        print(f"  plan {demo.plan['id']}: {demo.plan['summary']}")
        for r in demo.plan["rows"]:
            print(f"    {r['fid']} {r['stage']:<8} now {r['level_now']:+5.1f} min {r['min_level']:+5.1f} {r['action']:<10} {r['reason']}")
        for a in demo.plan["alerts"]:
            print("    ALERT", a["text"])
    demo.decide("approve", "")
    snap = demo.snapshot()
    print("complete fields", snap["complete_fields"], "/ 6")
    for c in snap["completeness"]:
        print(" ", c["fid"], c["score"], c["missing"])
    return demo


if __name__ == "__main__":
    run_script()
