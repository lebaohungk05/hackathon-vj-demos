import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "testset"
W, H = 480, 720
PX_PER_CM = 14
TUBE_X0, TUBE_X1 = 190, 290
SOIL_Y = 420
TOP_CM = 8
BOTTOM_CM = -22


def font(size):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def y_of(cm):
    return SOIL_Y - cm * PX_PER_CM


def background(rng):
    sky = np.zeros((H, W, 3), np.float32)
    top = np.array([rng.uniform(150, 200), rng.uniform(180, 215), rng.uniform(200, 235)])
    green = np.array([rng.uniform(60, 90), rng.uniform(110, 150), rng.uniform(50, 80)])
    for y in range(H):
        t = y / H
        sky[y] = top * (1 - t) + green * t
    sky += rng.normal(0, 6, sky.shape)
    return sky


def draw_scene(reading_cm, rng):
    arr = background(rng)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(40):
        x = rng.integers(0, W)
        d.line([(x, SOIL_Y - rng.integers(60, 200)), (x + rng.integers(-15, 15), SOIL_Y)], fill=(40, int(rng.integers(100, 160)), 40), width=3)
    mud = (int(rng.uniform(85, 110)), int(rng.uniform(65, 80)), int(rng.uniform(45, 60)))
    d.rectangle([0, SOIL_Y, W, H], fill=mud)
    if reading_cm > 0:
        d.rectangle([0, int(y_of(reading_cm)), W, SOIL_Y], fill=(110, 120, 105))
    d.rectangle([TUBE_X0 - 4, y_of(TOP_CM), TUBE_X1 + 4, y_of(BOTTOM_CM)], fill=(225, 225, 215), outline=(90, 90, 90), width=3)
    d.rectangle([TUBE_X0 + 6, y_of(TOP_CM) + 4, TUBE_X1 - 6, y_of(BOTTOM_CM) - 4], fill=(200, 205, 200))
    water_y = y_of(reading_cm)
    d.rectangle([TUBE_X0 + 6, water_y, TUBE_X1 - 6, y_of(BOTTOM_CM) - 4], fill=(70, 100, 140))
    d.line([(TUBE_X0 + 6, water_y), (TUBE_X1 - 6, water_y)], fill=(30, 50, 90), width=3)
    for _ in range(12):
        hx = rng.integers(TUBE_X0 + 12, TUBE_X1 - 12)
        hy = rng.integers(int(y_of(0)), int(y_of(BOTTOM_CM)) - 10)
        d.ellipse([hx - 4, hy - 4, hx + 4, hy + 4], fill=(50, 50, 50))
    f_small, f_big = font(16), font(20)
    for cm in range(BOTTOM_CM, TOP_CM + 1):
        y = y_of(cm)
        major = cm % 5 == 0
        length = 30 if major else 14
        d.line([(TUBE_X0 - 4, y), (TUBE_X0 - 4 + length, y)], fill=(20, 20, 20), width=3 if major else 1)
        if major:
            label = f"{cm:+d}" if cm else "0"
            d.text((TUBE_X0 - 60, y - 11), label, fill=(160, 20, 20) if cm == 0 else (10, 10, 10), font=f_big)
    d.line([(TUBE_X0 - 70, SOIL_Y), (TUBE_X1 + 40, SOIL_Y)], fill=(60, 40, 25), width=2)
    for _ in range(25):
        x = rng.integers(0, W)
        y = rng.integers(SOIL_Y + 5, H)
        r = rng.integers(3, 12)
        d.ellipse([x - r, y - r // 2, x + r, y + r // 2], fill=(mud[0] - 25, mud[1] - 20, mud[2] - 15))
    d.text((8, H - 24), "SYNTHETIC TEST IMAGE", fill=(255, 255, 255), font=f_small)
    return img


def degrade(img, rng):
    angle = rng.uniform(-6, 6)
    img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(90, 110, 80))
    arr = np.asarray(img).astype(np.float32)
    gain = rng.uniform(0.7, 1.25)
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = rng.uniform(0, W), rng.uniform(0, H)
    shade = 1 - 0.35 * np.clip(np.hypot(xx - cx, yy - cy) / max(W, H), 0, 1)
    arr = arr * gain * shade[..., None]
    arr += rng.normal(0, rng.uniform(2, 8), arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.6))), angle


def exif_bytes(dt):
    ex = Image.Exif()
    stamp = dt.strftime("%Y:%m:%d %H:%M:%S")
    ex[0x0132] = stamp
    ex[0x010E] = "SYNTHETIC gauge photo - RiceBridge Ops demo"
    ex.get_ifd(0x8769)[0x9003] = stamp
    return ex.tobytes()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260225)
    random.seed(20260225)
    readings = [-20, -19, -18, -17, -16, -15, -14, -13, -12, -11, -10, -9, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, -15.5, -2.5]
    base = datetime(2026, 2, 16, 6, 30)
    rows = []
    for i, cm in enumerate(readings):
        cm_draw = cm + float(rng.uniform(-0.3, 0.3)) if float(cm).is_integer() else cm
        cm_draw = round(cm_draw, 1)
        dt = base + timedelta(days=int(i % 10), hours=int(rng.integers(0, 10)), minutes=int(rng.integers(0, 60)))
        img, angle = degrade(draw_scene(cm_draw, rng), rng)
        name = f"gauge_{i + 1:02d}.jpg"
        img.save(OUT / name, quality=88, exif=exif_bytes(dt))
        rows.append({"file": name, "truth_cm": cm_draw, "captured_at": dt.isoformat(), "rotation_deg": round(angle, 2), "hero": False, "synthetic": True})
    hero_dt = datetime(2026, 2, 22, 16, 42)
    img, angle = degrade(draw_scene(-8.0, rng), rng)
    img.save(OUT / "hero_thua2_minus8.jpg", quality=88, exif=exif_bytes(hero_dt))
    rows.append({"file": "hero_thua2_minus8.jpg", "truth_cm": -8.0, "captured_at": hero_dt.isoformat(), "rotation_deg": round(angle, 2), "hero": True, "synthetic": True})
    (OUT / "ground_truth.json").write_text(json.dumps({"note": "SYNTHETIC images rendered by make_testset.py; not real field photos", "px_per_cm": PX_PER_CM, "images": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(rows)} images to {OUT}")


if __name__ == "__main__":
    main()
