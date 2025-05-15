from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Point2D:
    x: float
    y: float


def reduce_to_2d(vectors: list[list[float]]) -> list[Point2D]:
    n = len(vectors)
    if n == 0:
        return []
    if n == 1:
        return [Point2D(0.0, 0.0)]

    import warnings

    import numpy as np
    from sklearn.decomposition import PCA

    arr = np.asarray(vectors, dtype="float32")
    k = min(2, n, arr.shape[1])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        coords = PCA(n_components=k, random_state=0).fit_transform(arr)

    out: list[Point2D] = []
    for row in coords:
        x = float(row[0]) if k >= 1 else 0.0
        y = float(row[1]) if k >= 2 else 0.0
        out.append(Point2D(x=x, y=y))
    return out
