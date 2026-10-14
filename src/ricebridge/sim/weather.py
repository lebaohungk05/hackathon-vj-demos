from pathlib import Path

import pandas as pd
import requests

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
SITES = {"an_giang": (10.37, 105.43), "can_tho": (10.03, 105.78)}
START, END = "2025-12-01", "2026-03-31"
CACHE = Path(__file__).parent / "data"


def fetch_site(name, lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": START,
        "end_date": END,
        "daily": "precipitation_sum,et0_fao_evapotranspiration",
        "timezone": "Asia/Bangkok",
    }
    response = requests.get(ARCHIVE_URL, params=params, timeout=60)
    response.raise_for_status()
    daily = response.json()["daily"]
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(daily["time"]),
            "rain_mm": daily["precipitation_sum"],
            "et0_mm": daily["et0_fao_evapotranspiration"],
        }
    )
    if frame[["rain_mm", "et0_mm"]].isna().any().any():
        raise RuntimeError(f"missing values in Open-Meteo response for {name}")
    frame["site"] = name
    return frame


def load_weather():
    CACHE.mkdir(exist_ok=True)
    frames = []
    for name, (lat, lon) in SITES.items():
        path = CACHE / f"weather_{name}.csv"
        if not path.exists():
            fetch_site(name, lat, lon).to_csv(path, index=False)
        frames.append(pd.read_csv(path, parse_dates=["date"]))
    return {frame["site"].iloc[0]: frame for frame in frames}


if __name__ == "__main__":
    for name, frame in load_weather().items():
        print(name, len(frame), frame[["rain_mm", "et0_mm"]].describe().round(2).to_dict())
        print(frame.sort_values("rain_mm", ascending=False).head(5).to_string(index=False))
