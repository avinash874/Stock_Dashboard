"""Simple linear trend forecast for closing prices (demo ML)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def predict_next_closes(
    closes: np.ndarray, horizon: int = 5
) -> tuple[list[float], list[float]]:
    """
    Fit linear regression on time index vs close; extrapolate `horizon` days.
    Returns (historical_fitted_line, future_predicted).
    """
    y = np.asarray(closes, dtype=float)
    n = len(y)
    if n < 5:
        return [], []

    x = np.arange(n).reshape(-1, 1)
    model = LinearRegression()
    model.fit(x, y)
    fitted = model.predict(x).tolist()
    future_x = np.arange(n, n + horizon).reshape(-1, 1)
    future = model.predict(future_x).tolist()
    return fitted, future
