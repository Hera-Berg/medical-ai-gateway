"""
Dimensionality reduction for the RAG Inspector scatter plot.

Projects high-dim (384) embeddings down to 2D so the vector space is visually
inspectable — each chunk a point, similar chunks landing near each other.

PCA (scikit-learn) by design: linear, fast, DETERMINISTIC (same vectors -> same
plot, no random-seed wobble across reloads), and a small dependency. The
trade-off vs UMAP: clusters are less crisply separated because PCA is linear and
UMAP is a nonlinear manifold method that actively tightens neighbourhoods. For
"make the embedding space tangible" PCA is sufficient; the spec explicitly
allows "UMAP (or PCA as fallback)".

The reducer is kept behind a tiny function boundary so swapping to UMAP later is
a one-module change — nothing else in the inspector touches the algorithm.

PCA is fit across ALL supplied points together (it must be — the projection
axes are derived from the whole set), server-side, returning 2D coords. Fine for
hundreds/thousands of chunks; for very large collections you'd sample or cache
(noted as a scaling concern, not built now).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Point2D:
    x: float
    y: float


def reduce_to_2d(vectors: list[list[float]]) -> list[Point2D]:
    """
    Project N D-dim vectors to N 2D points via PCA.

    Edge cases handled so the endpoint never 500s on sparse data:
      • 0 vectors  -> []
      • 1 vector   -> single point at origin (PCA undefined for n<2)
      • all-identical or <2 effective components -> pads missing axis with 0.0
    """
    n = len(vectors)
    if n == 0:
        return []
    if n == 1:
        return [Point2D(0.0, 0.0)]

    # Import here so the module loads even if sklearn isn't present at import
    # time in some tooling context; the endpoint depends on it at call time.
    import warnings

    import numpy as np
    from sklearn.decomposition import PCA

    arr = np.asarray(vectors, dtype="float32")
    # n_components can't exceed min(n_samples, n_features); guard small n.
    k = min(2, n, arr.shape[1])
    with warnings.catch_warnings():
        # Degenerate inputs (e.g. all-identical vectors -> zero total variance)
        # trigger a harmless divide warning in sklearn's variance-ratio calc;
        # the coordinates are still valid. Silence it for clean logs.
        warnings.simplefilter("ignore", RuntimeWarning)
        coords = PCA(n_components=k, random_state=0).fit_transform(arr)

    out: list[Point2D] = []
    for row in coords:
        x = float(row[0]) if k >= 1 else 0.0
        y = float(row[1]) if k >= 2 else 0.0
        out.append(Point2D(x=x, y=y))
    return out
