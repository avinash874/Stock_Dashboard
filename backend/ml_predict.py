from __future__ import annotations

import numpy as np
from sklearn.linear_model import LinearRegression


def predict_next_closes(closes: np.ndarray, horizon: int = 5) -> tuple[list[float], list[float]]:
    # Fit a straight line through past closes (day 0, 1, 2, … vs price), then extend the line.
    # Demo only — real forecasting is much messier.
    y = np.asarray(closes, dtype=float)
    n = len(y)
    if n < 5:
        return [], []

    x = np.arange(n).reshape(-1, 1)
    model = LinearRegression()
    model.fit(x, y)
    line_through_history = model.predict(x).tolist()

    future_x = np.arange(n, n + horizon).reshape(-1, 1)
    extended = model.predict(future_x).tolist()
    return line_through_history, extended
