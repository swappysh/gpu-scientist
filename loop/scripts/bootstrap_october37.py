"""Bootstrap over series: how sure are the October wins over the starter on the 37?

Resamples the 37 scored series with replacement and recomputes the pooled
skill of each config on the same resample.

    uv run python scripts/bootstrap_october37.py data/series_scored.npz [draws]
"""
import sys

import numpy as np

from pacific_hack import pack
from pacific_hack.data import HORIZONS, heldout_origins
from pacific_hack.forecaster import Changes, ForecasterConfig, _cell_loss, _last, forecast

CONFIGS = {
    "starter": ForecasterConfig(),
    "model": ForecasterConfig(pool_weight=0.5, half_life_days=14.0, band_scale=1.2),
    # the final config of loop run scored37-e (results/loop_rounds.json)
    "loop": ForecasterConfig(half_life_days=14.0, drift_weight=0.03, pool_weight=0.7, min_samples=6, momentum_fit=0.2),
}


def per_series(cfg, s, ch, origins):
    """(model loss, flat last-value loss) summed over one series' October cells."""
    truth = dict(zip(s.days.tolist(), s.vals.tolist()))
    loss = base = 0.0
    for o in origins:
        for h in HORIZONS:
            y = truth.get(o + h)
            f = None if y is None else forecast(cfg, s, ch, o, h)
            if f is None:
                continue
            loss += _cell_loss(y, f)
            base += _cell_loss(y, (_last(s, o),) * 3)
    return loss, base


world = pack.load(sys.argv[1])
draws = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
ids = pack.scored_ids(sys.argv[1])
sub = [s for s in world if s.sid in ids]
ch = Changes(world)
origins = heldout_origins()
L = {k: np.array([per_series(c, s, ch, origins) for s in sub]) for k, c in CONFIGS.items()}
base = L["starter"][:, 1]  # the flat forecast does not depend on the config


def skill(loss, b):
    return 1.0 - loss.sum(-1) / b.sum(-1)


idx = np.random.default_rng(0).integers(0, len(sub), size=(draws, len(sub)))
print(f"october, {len(sub)} scored series, {draws} series resamples")
print("skill " + " ".join(f"{k} {skill(L[k][:, 0], base):+.4f}" for k in CONFIGS))
for a, b in (("model", "starter"), ("loop", "starter"), ("loop", "model")):
    diff = skill(L[a][idx, 0], base[idx]) - skill(L[b][idx, 0], base[idx])
    point = skill(L[a][:, 0], base) - skill(L[b][:, 0], base)
    lo, hi = np.quantile(diff, [0.025, 0.975])
    wins = int((L[a][:, 0] < L[b][:, 0]).sum())
    print(f"{a} - {b}: {point:+.4f}, 95% interval [{lo:+.4f}, {hi:+.4f}], share of resamples above 0: "
          f"{(diff > 0).mean():.3f}, series with lower October loss: {wins} of {len(sub)}")
