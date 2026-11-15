"""Write dev_series.npz: the full build cut at TRAIN_END (Oct 15 in v8.1) (run once by gpuloop, outside the sandbox)."""
import sys

import numpy as np

from core import TRAIN_END, day

src, dst = sys.argv[1], sys.argv[2]
z = np.load(src, allow_pickle=False)
off, cut = z["offsets"], day(TRAIN_END)
days, vals, offsets = [], [], [0]
for i in range(len(z["sids"])):
    d, v = z["days"][off[i]:off[i + 1]], z["vals"][off[i]:off[i + 1]]
    keep = d <= cut
    days.append(d[keep]); vals.append(v[keep]); offsets.append(offsets[-1] + int(keep.sum()))
np.savez_compressed(dst, sids=z["sids"], groups=z["groups"], headline=z["headline"],
                    days=np.concatenate(days), vals=np.concatenate(vals), offsets=np.array(offsets, dtype=np.int64))
print(f"wrote {dst}: {len(z['sids'])} series, last day {np.concatenate(days).max()} <= {cut}")
