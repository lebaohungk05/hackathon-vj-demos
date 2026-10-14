"""Static data of the Team demo scenario: fields, people, scripted events and labels.

Moved out of engine.py without changes so that the engine only holds behaviour.
"""
import datetime as dt
from dataclasses import dataclass

MRV_WINDOW_START = dt.date(2026, 2, 20)
MODEL_START = dt.datetime(2026, 2, 20, 6, 0)

SCENARIO_LABEL = "Team demo scenario"
CLUSTER_NAME = "Cluster A (Cụm A)"
HTX_OFFICER = "Anh Hùng (HTX)"
STATION_MANAGER = "Pump-station manager (người phụ trách trạm)"
TECH_OFFICER = "technical officer (cán bộ kỹ thuật)"

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
