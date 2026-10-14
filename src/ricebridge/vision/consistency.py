import argparse
import json
from datetime import datetime

DISAGREEMENT_CM = 5.0
AWD_SAFE_THRESHOLD_CM = -15.0
LOW_CONFIDENCE = 0.5
BLOCKING = {"UNREADABLE_PHOTO", "STALE_PHOTO", "PHOTO_SUSPECT", "SOURCES_DISAGREE"}


def parse(ts):
    return datetime.fromisoformat(ts) if ts else None


def make_flag(code, severity, message, action):
    return {"code": code, "severity": severity, "message": message, "action": action}


def sources_agree(a, b):
    return a is not None and b is not None and abs(a - b) <= DISAGREEMENT_CM


def time_flags(captured, rain, submitted):
    flags = []
    if captured is None:
        flags.append(make_flag("NO_CAPTURE_TIME", "medium", "Ảnh không có giờ chụp trong metadata.", "Không dùng ảnh làm bằng chứng duy nhất."))
        return flags
    if rain and captured < rain:
        flags.append(make_flag("STALE_PHOTO", "high", f"Ảnh chụp lúc {captured:%a %d/%m %H:%M}, trước trận mưa gần nhất ({rain:%a %d/%m %H:%M}).", "Không dùng ảnh này; xin số đo mới sau mưa."))
    if submitted and (submitted - captured).total_seconds() > 24 * 3600:
        flags.append(make_flag("OLD_PHOTO", "medium", f"Ảnh gửi lúc {submitted:%d/%m %H:%M} nhưng chụp từ {captured:%d/%m %H:%M}.", "Hỏi lại nông dân ngày chụp."))
    return flags


def reading_flags(photo_cm, sensor_cm, water_balance_cm):
    refs = {"cảm biến": sensor_cm, "cân bằng nước": water_balance_cm}
    disagree = {k: v for k, v in refs.items() if v is not None and abs(photo_cm - v) > DISAGREEMENT_CM}
    if disagree:
        detail = ", ".join(f"{k} {v:+.1f} cm" for k, v in disagree.items())
        if sources_agree(sensor_cm, water_balance_cm):
            return [make_flag("PHOTO_SUSPECT", "high", f"Ảnh {photo_cm:+.1f} cm lệch hơn {DISAGREEMENT_CM:.0f} cm so với {detail}; cảm biến và cân bằng nước khớp nhau nên nghi ảnh.", "Xin đo độc lập ở ống thứ hai hoặc thước cắm tay, không chụp lại cùng ống.")]
        return [make_flag("SOURCES_DISAGREE", "high", f"Ảnh {photo_cm:+.1f} cm lệch hơn {DISAGREEMENT_CM:.0f} cm so với {detail}.", "Xin đo độc lập trước khi đổi lịch bơm.")]
    if photo_cm < AWD_SAFE_THRESHOLD_CM:
        return [make_flag("BELOW_AWD_THRESHOLD", "high", f"Mực nước {photo_cm:+.1f} cm thấp hơn ngưỡng an toàn {AWD_SAFE_THRESHOLD_CM:.0f} cm.", "Ưu tiên bơm nước cho thửa này.")]
    return []


def check_photo(photo_cm, photo_captured_at, sensor_cm=None, water_balance_cm=None, latest_rain_at=None, submitted_at=None, photo_confidence=1.0):
    flags = time_flags(parse(photo_captured_at), parse(latest_rain_at), parse(submitted_at))
    if photo_cm is None:
        flags.append(make_flag("UNREADABLE_PHOTO", "high", "Không đọc được mực nước từ ảnh.", "Xin nông dân chụp lại rõ thang đo."))
    else:
        if photo_confidence < LOW_CONFIDENCE:
            flags.append(make_flag("LOW_CONFIDENCE", "medium", f"Độ tin cậy khi đọc ảnh thấp ({photo_confidence:.2f}).", "Xin chụp lại gần hơn, thẳng góc."))
        flags.extend(reading_flags(photo_cm, sensor_cm, water_balance_cm))
    return {"photo_usable": not any(f["code"] in BLOCKING for f in flags), "flags": flags}


def main():
    p = argparse.ArgumentParser(description="Cross-check a gauge photo reading against sensor and water balance")
    p.add_argument("--photo-cm", type=float)
    p.add_argument("--captured-at")
    p.add_argument("--sensor-cm", type=float)
    p.add_argument("--balance-cm", type=float)
    p.add_argument("--rain-at")
    p.add_argument("--submitted-at")
    p.add_argument("--confidence", type=float, default=1.0)
    a = p.parse_args()
    print(json.dumps(check_photo(a.photo_cm, a.captured_at, a.sensor_cm, a.balance_cm, a.rain_at, a.submitted_at, a.confidence), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
