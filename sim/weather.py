"""Ambient weather driving the tank simulator.

Primary source (label: REAL DATA — ERA5 reanalysis): Open-Meteo historical
weather API, hourly 2 m temperature, 2 m relative humidity, precipitation and
28-100 cm soil temperature for Varanasi (IIT BHU), cached under data/weather/.
ERA5 is a reanalysis (model + assimilated observations), not a station record;
the site says so.

Fallback (label: SYNTHETIC): seeded diurnal + seasonal model, used only if the
API cannot be reached and no cache exists.
"""

from __future__ import annotations

import json
import ssl
import urllib.request
from dataclasses import dataclass

import numpy as np
import pandas as pd

from common.config import ROOT

CACHE = ROOT / "data" / "weather"
LOCATION = {"name": "Varanasi (IIT BHU)", "latitude": 25.26, "longitude": 82.99}
CITIES = {
    "varanasi": LOCATION,
    "delhi": {"name": "Delhi", "latitude": 28.61, "longitude": 77.21},
    "mumbai": {"name": "Mumbai", "latitude": 19.08, "longitude": 72.88},
    "chennai": {"name": "Chennai", "latitude": 13.08, "longitude": 80.27},
    "kolkata": {"name": "Kolkata", "latitude": 22.57, "longitude": 88.36},
    "guwahati": {"name": "Guwahati", "latitude": 26.14, "longitude": 91.74},
}
VARS = ["temperature_2m", "relative_humidity_2m", "precipitation", "soil_temperature_28_to_100cm"]
STEP = "30min"


def _cafile():
    try:
        import certifi

        return certifi.where()
    except ImportError:
        return None


@dataclass
class Weather:
    frame: pd.DataFrame  # index: timestamps every 30 min; cols t_amb, rh, precip_mm, t_soil
    label: str
    source: str


def _fetch(start: str, end: str, loc: dict = LOCATION) -> dict:
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={loc['latitude']}&longitude={loc['longitude']}"
        f"&start_date={start}&end_date={end}&hourly={','.join(VARS)}&timezone=Asia%2FKolkata"
    )
    try:
        ctx = ssl.create_default_context(cafile=_cafile())
        with urllib.request.urlopen(url, timeout=120, context=ctx) as r:
            return json.load(r)
    except Exception:  # noqa: BLE001 - e.g. TLS proxy only trusted by the system keychain
        import subprocess

        out = subprocess.run(["curl", "-sf", "--max-time", "180", url], check=True, capture_output=True)
        return json.loads(out.stdout)


def _to_frame(raw: dict) -> pd.DataFrame:
    h = raw["hourly"]
    df = pd.DataFrame(
        {
            "t_amb": h["temperature_2m"],
            "rh": h["relative_humidity_2m"],
            "precip_mm": h["precipitation"],
            "t_soil": h["soil_temperature_28_to_100cm"],
        },
        index=pd.to_datetime(h["time"]),
    ).astype(float)
    df = df.interpolate(limit_direction="both")
    # 30-min grid: interpolate state variables, split hourly precipitation in two
    grid = pd.date_range(df.index[0], df.index[-1] + pd.Timedelta("30min"), freq=STEP)
    out = df[["t_amb", "rh", "t_soil"]].reindex(grid).interpolate(limit_direction="both")
    p = df["precip_mm"].reindex(grid).ffill() / 2.0
    out["precip_mm"] = p.fillna(0.0)
    out["rh"] = out["rh"].clip(0, 100)
    return out


def synthetic(start="2022-01-01", end="2024-12-31", seed=0) -> Weather:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, pd.Timestamp(end) + pd.Timedelta("23h30min"), freq=STEP)
    doy = idx.day_of_year.to_numpy()
    hour = idx.hour.to_numpy() + idx.minute.to_numpy() / 60
    season = -np.cos(2 * np.pi * (doy - 15) / 365)
    t_mean = 26 + 8 * season
    swing = 10 - 4 * np.clip(np.sin(2 * np.pi * (doy - 150) / 365), 0, None)
    t_amb = t_mean + swing / 2 * np.sin(2 * np.pi * (hour - 9) / 24) + rng.normal(0, 0.7, len(idx))
    monsoon = np.exp(-(((doy - 215) / 40) ** 2))
    rh = np.clip(55 + 30 * monsoon - 15 * np.sin(2 * np.pi * (hour - 9) / 24) + rng.normal(0, 4, len(idx)), 5, 100)
    precip = np.where(rng.random(len(idx)) < 0.04 * monsoon, rng.exponential(3, len(idx)), 0.0)
    t_soil = pd.Series(t_mean).rolling(24 * 2 * 20, min_periods=1).mean().to_numpy()
    df = pd.DataFrame({"t_amb": t_amb, "rh": rh, "precip_mm": precip, "t_soil": t_soil}, index=idx)
    return Weather(df, "SYNTHETIC", "seeded diurnal + seasonal model (sim/weather.py)")


def load(start="2022-01-01", end="2024-12-31", city: str = "varanasi") -> Weather:
    CACHE.mkdir(parents=True, exist_ok=True)
    loc = CITIES[city]
    path = CACHE / f"openmeteo_{city}_{start}_{end}.json"
    if not path.exists():
        try:
            raw = _fetch(start, end, loc)
            path.write_text(json.dumps(raw))
        except Exception as e:  # noqa: BLE001 - any network failure -> labelled fallback
            print(f"weather fetch failed ({e}); using SYNTHETIC fallback")
            return synthetic(start, end)
    raw = json.loads(path.read_text())
    return Weather(
        _to_frame(raw),
        "REAL DATA (ERA5 reanalysis)",
        f"Open-Meteo historical API, ERA5/ERA5-Land, {loc['name']} "
        f"{loc['latitude']}N {loc['longitude']}E, {start} to {end}",
    )
