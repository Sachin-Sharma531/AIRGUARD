from pathlib import Path
import warnings

import joblib
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = BASE_DIR / "app" / "ml" / "artifacts" / "pm25_model.joblib"
DATA_PATH = BASE_DIR / "app" / "ml" / "artifacts" / "delhi_clean.csv"

FEATURES = [
    "location",
    "PM2.5",
    "pm25_lag_1",
    "pm25_lag_2",
    "pm25_lag_3",
    "temperature",
    "humidity",
    "wind_speed",
    "wind_direction",
    "hour_sin",
    "hour_cos",
    "day_sin",
    "day_cos",
]

_model = None
_historical_data = None


def _get_model():
    global _model

    if _model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError("PM2.5 model artifact was not found.")
        with warnings.catch_warnings():
            try:
                from sklearn.exceptions import InconsistentVersionWarning
                warnings.simplefilter("ignore", InconsistentVersionWarning)
            except ImportError:
                pass
            _model = joblib.load(MODEL_PATH)

    return _model


def _get_historical_data():
    global _historical_data

    if _historical_data is None:
        if not DATA_PATH.exists():
            raise FileNotFoundError("Historical dataset was not found.")

        _historical_data = pd.read_csv(DATA_PATH)
        _historical_data["timestamp"] = pd.to_datetime(
            _historical_data["timestamp"], errors="raise"
        )

    return _historical_data


def get_available_locations() -> list:
    df = _get_historical_data()
    return sorted([str(loc) for loc in df["location"].dropna().unique()])


def predict_pollution(location: str) -> dict:
    df = _get_historical_data()
    df = df[df["location"] == location].sort_values("timestamp")

    if len(df) < 4:
        raise ValueError(
            f"Insufficient historical observations for location: {location}"
        )

    recent = df.tail(4).reset_index(drop=True)
    differences = recent["timestamp"].diff().dropna()

    if not (differences == pd.Timedelta(hours=3)).all():
        raise ValueError(
            "The latest observations are not exactly three hours apart."
        )

    current = recent.iloc[-1]
    prediction_time = current["timestamp"] + pd.Timedelta(hours=3)

    hour = current["timestamp"].hour
    day = current["timestamp"].dayofweek

    row = {
        "location": location,
        "PM2.5": float(current["PM2.5"]),
        "pm25_lag_1": float(recent.iloc[-2]["PM2.5"]),
        "pm25_lag_2": float(recent.iloc[-3]["PM2.5"]),
        "pm25_lag_3": float(recent.iloc[-4]["PM2.5"]),
        "temperature": float(current["temperature"]),
        "humidity": float(current["humidity"]),
        "wind_speed": float(current["wind_speed"]),
        "wind_direction": float(current["wind_direction"]),
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24),
        "day_sin": np.sin(2 * np.pi * day / 7),
        "day_cos": np.cos(2 * np.pi * day / 7),
    }

    features = pd.DataFrame([row], columns=FEATURES)
    prediction = float(_get_model().predict(features)[0])

    return {
        "location": location,
        "current_pm25": round(float(current["PM2.5"]), 2),
        "predicted_pm25": round(max(0.0, prediction), 2),
        "observation_time": current["timestamp"].isoformat(),
        "prediction_time": prediction_time.isoformat(),
        "horizon_minutes": 180,
        "model": "random_forest",
        "data_source": "historical_dataset",
        "dataset_latest_observation": df["timestamp"].max().isoformat(),
        "is_live_forecast": False,
    }
