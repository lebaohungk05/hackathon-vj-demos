# RiceBridge Ops · vision: đọc ảnh ống đo mực nước

Ảnh trong `testset/` là **ảnh tổng hợp (SYNTHETIC)**, do `make_testset.py` vẽ bằng PIL/numpy, không phải ảnh chụp ngoài ruộng.

| File | Vai trò |
|---|---|
| `make_testset.py` | Vẽ 28 ảnh ống đo (−20..+5 cm, nhiễu, mờ, xoay, ánh sáng) kèm EXIF DateTimeOriginal và `testset/ground_truth.json`. Ảnh hero `hero_thua2_minus8.jpg`: −8 cm, chụp Chủ nhật 22/02/2026 16:42 |
| `gauge_reader.py` | `read_gauge_photo(path) -> {reading_cm, confidence, reason, captured_at, source, llm_seconds}`. Gọi `claude -p --model claude-sonnet-5-5 --allowedTools Read` (prompt qua stdin), kiểm JSON, thử lại 1 lần, cache theo SHA-256 trong `cache/`. Giờ chụp đọc từ EXIF, không qua LLM |
| `consistency.py` | `check_photo(...)`: cờ STALE_PHOTO, OLD_PHOTO, PHOTO_SUSPECT, SOURCES_DISAGREE, BELOW_AWD_THRESHOLD, LOW_CONFIDENCE, UNREADABLE_PHOTO, NO_CAPTURE_TIME |
| `evaluate.py` | Chạy cả bộ, ghi `out/metrics.json` |

## Lệnh

```bash
cd demo/vision
python make_testset.py
python gauge_reader.py testset/hero_thua2_minus8.jpg
python gauge_reader.py --replay testset/hero_thua2_minus8.jpg
python consistency.py --photo-cm -8.3 --captured-at 2026-02-22T16:42:00 --sensor-cm 2 --balance-cm 2 --rain-at 2026-02-24T19:00:00 --submitted-at 2026-02-25T07:10:00
python evaluate.py
python evaluate.py --replay
```

`--replay` chỉ dùng cache, không gọi model (chạy offline khi demo). Chạy lại `make_testset.py` sẽ ghi đè ảnh và làm cache cũ không còn khớp.

## Kết quả đo (live, claude-sonnet-5-5, 28 ảnh tổng hợp)

MAE 0,24 cm; sai số lớn nhất 0,7 cm; 100% ảnh trong ±2 cm (và ±1 cm); 0 ảnh lỗi; ~7,0 s/ảnh (trung vị 6,9 s, tối đa 9,2 s); 28/28 giờ chụp EXIF đúng. Ảnh hero đọc −8,3 cm và bị gắn cờ STALE_PHOTO + PHOTO_SUSPECT.

Ảnh tổng hợp sạch hơn ảnh thật (thang in rõ, không bùn bám, không phản chiếu), nên con số này là cận trên, chưa phải độ chính xác ngoài ruộng.
