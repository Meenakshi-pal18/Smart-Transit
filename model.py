from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

import joblib
import numpy as np
from sklearn.linear_model import LinearRegression

MODEL_PATH = Path(__file__).resolve().parent / "eta_model.joblib"


@dataclass
class ETAModelService:
    model: LinearRegression

    def predict_minutes(self, distance_km: float, speed_kmph: float, historical_delay: float) -> float:
        safe_speed = max(speed_kmph, 6.0)
        prediction = self.model.predict([[distance_km, safe_speed, historical_delay]])[0]
        return round(max(prediction, 2.0), 1)


def build_training_data() -> Tuple[np.ndarray, np.ndarray]:
    rows = []
    labels = []
    for distance in np.linspace(0.8, 18.0, 80):
        for speed in np.linspace(12.0, 42.0, 7):
            for delay in np.linspace(0.0, 8.0, 5):
                eta = (distance / max(speed, 8.0)) * 60 + (delay * 0.9) + (distance * 0.35)
                rows.append([distance, speed, delay])
                labels.append(eta)
    return np.array(rows), np.array(labels)


def train_eta_model() -> ETAModelService:
    features, labels = build_training_data()
    model = LinearRegression()
    model.fit(features, labels)
    joblib.dump(model, MODEL_PATH)
    return ETAModelService(model=model)


def load_or_train_model() -> ETAModelService:
    if MODEL_PATH.exists():
        return ETAModelService(model=joblib.load(MODEL_PATH))
    return train_eta_model()
