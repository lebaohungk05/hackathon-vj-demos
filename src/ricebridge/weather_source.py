import datetime as dt
import json
import urllib.parse
import urllib.request
from pathlib import Path

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SITE_NAME = "Long Xuyên, An Giang"
SITE_LAT, SITE_LON = 10.37, 105.43
WINDOW_START, WINDOW_END = "2026-02-16", "2026-03-12"
DAILY_VARS = "precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max"
CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / f"open_meteo_an_giang_{WINDOW_START}_{WINDOW_END}.json"
FORECAST_CACHE = Path(__file__).resolve().parents[1] / "data" / "open_meteo_forecast_latest.json"


def request_params():
    return {
        "latitude": SITE_LAT,
        "longitude": SITE_LON,
        "start_date": WINDOW_START,
        "end_date": WINDOW_END,
        "daily": DAILY_VARS,
        "timezone": "Asia/Bangkok",
    }


def fetch():
    url = ARCHIVE_URL + "?" + urllib.parse.urlencode(request_params())
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.load(response)
    record = {
        "source": "Open-Meteo Historical Weather API (ERA5-based archive)",
        "request_url": url,
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "site_name": SITE_NAME,
        "response": payload,
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


def load(refresh=False):
    if refresh or not CACHE_PATH.exists():
        record = fetch()
    else:
        record = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    daily = record["response"]["daily"]
    days = {}
    for i, day in enumerate(daily["time"]):
        rain, et0 = daily["precipitation_sum"][i], daily["et0_fao_evapotranspiration"][i]
        if rain is None or et0 is None:
            raise RuntimeError(f"Open-Meteo returned a missing value on {day}")
        days[dt.date.fromisoformat(day)] = {"rain_mm": rain, "et0_mm": et0, "tmax_c": daily["temperature_2m_max"][i]}
    meta = {
        "source": record["source"],
        "request_url": record["request_url"],
        "fetched_at": record["fetched_at"],
        "site_name": record["site_name"],
        "requested_lat": SITE_LAT,
        "requested_lon": SITE_LON,
        "grid_lat": record["response"]["latitude"],
        "grid_lon": record["response"]["longitude"],
        "window": [WINDOW_START, WINDOW_END],
        "cache_file": CACHE_PATH.name,
    }
    return days, meta


def summarize_forecast(payload):
    daily = payload["daily"]
    days = [{"date": d, "rain_mm": daily["precipitation_sum"][i], "rain_prob": daily["precipitation_probability_max"][i],
             "et0_mm": daily["et0_fao_evapotranspiration"][i], "tmax_c": daily["temperature_2m_max"][i]}
            for i, d in enumerate(daily["time"])]
    current = payload.get("current", {})
    return {"days": days, "current": {"time": current.get("time"), "temp_c": current.get("temperature_2m"),
                                      "rain_mm": current.get("precipitation")}}


def forecast(timeout=6):
    params = {"latitude": SITE_LAT, "longitude": SITE_LON, "timezone": "Asia/Bangkok", "forecast_days": 3,
              "daily": "precipitation_sum,precipitation_probability_max,et0_fao_evapotranspiration,temperature_2m_max",
              "current": "temperature_2m,precipitation"}
    url = FORECAST_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
        record = {"fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "request_url": url, "response": payload}
        FORECAST_CACHE.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        status = "live"
    except (OSError, ValueError) as exc:
        if not FORECAST_CACHE.exists():
            return {"status": "offline", "error": str(exc), "site_name": SITE_NAME}
        record = json.loads(FORECAST_CACHE.read_text(encoding="utf-8"))
        status = "cached"
    return {"status": status, "fetched_at": record["fetched_at"], "site_name": SITE_NAME, "lat": SITE_LAT, "lon": SITE_LON,
            "source": "Open-Meteo Forecast API", **summarize_forecast(record["response"])}


if __name__ == "__main__":
    days, meta = load(refresh=True)
    print(json.dumps(meta, indent=1, ensure_ascii=False))
    for day, values in days.items():
        print(day, values)
