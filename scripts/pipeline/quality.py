"""Statistics on the agreement between the two evidence sources (maps, events).

Used by s12. Kept separate so each estimator is unit-tested on its own.

Two-source capture-recapture (Chapman's bias-corrected Lincoln-Petersen)
    The maps detect a set of district creations (new CKs); the events
    compilation names a set of new districts; m are found by both. Assuming
    the two sources detect creations independently, every creation is equally
    detectable within a source, and neither source contains false positives,
        N_hat = (n1 + 1)(n2 + 1) / (m + 1) - 1
    estimates the total number of creations, and N_hat - (n1 + n2 - m) the
    number BOTH sources missed. Violations bias it predictably: positive
    dependence (both miss the same obscure changes) -> N_hat too LOW; false
    positives (a respelling counted as a new district) -> too HIGH. Report it as
    an order of magnitude with those caveats, never as a count.
"""

from __future__ import annotations

import math

import numpy as np


def chapman(n1: int, n2: int, m: int, z: float = 1.959964) -> dict:
    if not (0 <= m <= min(n1, n2)):
        raise ValueError("need 0 <= m <= min(n1, n2)")
    n_hat = (n1 + 1) * (n2 + 1) / (m + 1) - 1
    var = (n1 + 1) * (n2 + 1) * (n1 - m) * (n2 - m) / ((m + 1) ** 2 * (m + 2))
    se = math.sqrt(var)
    observed = n1 + n2 - m
    # log-normal interval on the unobserved part (Chao 1987): stays above `observed`
    f0 = max(n_hat - observed, 0.0)
    if f0 > 0 and se > 0:
        c = math.exp(z * math.sqrt(math.log(1 + var / f0 ** 2)))
        lo, hi = observed + f0 / c, observed + f0 * c
    else:
        lo = hi = n_hat
    return {"n1": n1, "n2": n2, "m": m, "observed": observed, "n_hat": n_hat, "se": se,
            "ci_low": lo, "ci_high": hi, "missed_by_both": f0}


def auc(scores: np.ndarray, positive: np.ndarray, z: float = 1.959964) -> dict:
    """Mann-Whitney AUC of `scores` for `positive`, with the Hanley-McNeil SE.
    Returns status CONSTANT when the scores carry no information at all."""
    scores, positive = np.asarray(scores, float), np.asarray(positive, bool)
    ok = np.isfinite(scores)
    scores, positive = scores[ok], positive[ok]
    n_pos, n_neg = int(positive.sum()), int((~positive).sum())
    if len(scores) == 0 or n_pos == 0 or n_neg == 0:
        return {"status": "NOT_TESTABLE", "auc": np.nan, "ci_low": np.nan, "ci_high": np.nan,
                "n_pos": n_pos, "n_neg": n_neg}
    if np.nanstd(scores) == 0:
        return {"status": "CONSTANT", "auc": 0.5, "ci_low": np.nan, "ci_high": np.nan,
                "n_pos": n_pos, "n_neg": n_neg, "value": float(scores[0])}
    order = scores.argsort(kind="mergesort")
    ranks = np.empty(len(scores))
    sorted_scores = scores[order]
    i = 0
    while i < len(scores):  # average ranks for ties
        j = i
        while j + 1 < len(scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    a = (ranks[positive].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    se = math.sqrt((a * (1 - a) + (n_pos - 1) * (q1 - a * a) + (n_neg - 1) * (q2 - a * a)) / (n_pos * n_neg))
    return {"status": "TESTED", "auc": a, "ci_low": max(0.0, a - z * se), "ci_high": min(1.0, a + z * se),
            "n_pos": n_pos, "n_neg": n_neg}
