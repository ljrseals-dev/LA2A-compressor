"""Pure-Python glue for the LA-2A GUI (no Qt). Testable headless.
All calibration constants marked [?] are NOT from the manual."""
import numpy as np
from la2a_manual_faithful import LA2A

SERIAL_HAS_SLOPE_SWITCH = True    # the panel photo shows the switch; per addendum 11-66 it exists only after serial 572 (default: Limit)
DBFS_TO_DBM_OFFSET = 16.0         # [?] assumes 0 dBFS = +16 dBm (the manual's max input/peak output). UNVERIFIED
GAIN_RANGE_DB = 20.0              # [?] +/-20 dB over the Gain knob; manual gives only "normal output near 50%" (p.5)

def knob_to_params(gain_knob, pr_knob):
    return dict(gain_db=(gain_knob - 50.0) / 50.0 * GAIN_RANGE_DB, peak_reduction=pr_knob / 100.0)

def process_file(x, sr, gain_knob, pr_knob, powered=True, progress=None, mode="limit"):
    """x: float array (n,) or (n,2) in [-1,1]. Channels processed independently (stereo link NOT implemented).
    Returns (y, gr_db_per_channel list). Power off -> silence (the unit has no bypass)."""
    x = np.asarray(x, float)
    chans = [x] if x.ndim == 1 else [x[:, i] for i in range(x.shape[1])]
    if not powered:
        z = np.zeros_like(x); return z, [np.zeros(len(c)) for c in chans]
    outs, grs = [], []
    p = knob_to_params(gain_knob, pr_knob)
    for k, c in enumerate(chans):
        u = LA2A(sr, p["peak_reduction"], p["gain_db"], mode=mode)
        outs.append(u.process(c)); grs.append(u.gr_db.copy())
        if progress: progress((k + 1) / len(chans))
    y = outs[0] if x.ndim == 1 else np.stack(outs, axis=1)
    return y, grs

def meter_track(y, grs, sr, mode, hop_s=0.02):
    """Per-hop meter value in VU units. mode: 'gr' | 'out10' | 'out4'.
    GR mode: 0 VU = no reduction; more GR moves the needle LEFT (manual p.5). Output: 0 VU = +10 or +4 dBm."""
    hop = max(1, int(sr * hop_s)); n = len(y) // hop
    if mode == "gr":
        g = np.mean([gr[:n * hop].reshape(n, hop).mean(1) for gr in grs], axis=0)
        v = -np.clip(g, 0, 20)                      # displayed range [?]
    else:
        ref = 10.0 if mode == "out10" else 4.0
        yy = y if y.ndim == 1 else y.max(axis=1)
        rms = np.sqrt((yy[:n * hop] ** 2).reshape(n, hop).mean(1)) + 1e-9
        v = np.clip(20 * np.log10(rms) + DBFS_TO_DBM_OFFSET - ref, -20, 3)
    a = 1 - np.exp(-hop_s / 0.3)                    # ~300 ms VU ballistics (standard VU, not manual-specific)
    out = np.empty(n); s = v[0] if n else 0
    for i in range(n): s += a * (v[i] - s); out[i] = s
    return out, hop_s
