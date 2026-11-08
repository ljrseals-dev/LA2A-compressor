"""
LA-2A manual-faithful DSP core (behavioral model, NOT hardware-equivalent).
Source of truth: Teletronix LA-2A Instruction Manual (3-66 + 11-66 addendum).
Every unmeasured number is UNVERIFIED. [?] = value not in manual.

Architecture (manual p.3-4, Fig.2):
  input -> T4 shunt attenuator (AHEAD of V1) -> gain -> [V1/V2/xfmr: constant bias]
  sidechain = sample of the INPUT (pre-T4, feed-forward per Teletronix p.4/schematic)
              -> R37/C12 pre-emphasis (flat default) -> R2 Peak Reduction
              -> V3 -> R3 -> V4 -> EL panel.
  The EL panel responds to |V|, so the original needs no rectifier (p.4); the abs() below models that physics, not an added circuit.
No audio-path response shaping is modeled at all: the model is flat DC-to-Nyquist, so the manual's +/-0.1 dB over 30 Hz-15 kHz (p.2) is unmodeled. [HYPOTHESIS]
Removed from the old code: sidechain HPF, 10 ms RMS detector, 'T4B', 6BC8 tube,
tanh transformer saturation, wet/dry mix, 'Bypass (Unity)', lookahead, M/S.
"""
import numpy as np

class T4Cell:
    """Two-exponential cell model in the dB (gain-reduction) domain.
    Manual p.2: attack ~10 us; ~60 ms for 50% release; 0.5-5 s complete release.
    'Release' is interpreted as GAIN recovery (dB domain). [HYPOTHESIS] The manual does not state the domain.
    Both stages attack fast, so the slow stage does not 'remember' burst duration (the UA manual describes
    that memory; modeling it would slow the attack, conflicting with p.2). Release length still grows with
    reduction depth. Weights/constants are one fit, UNVERIFIED."""
    def __init__(self, sr, attack_s=10e-6, fast_rel_s=0.030, slow_rel_s=2.0, w_fast=0.56, w_slow=0.44):
        # 10 us is below one sample at 48 kHz (20.8 us): coefficient clamps to one sample (effective ~40-60 us).
        c = lambda t: float(np.exp(-1.0 / (max(t, 1.0 / sr) * sr)))
        self.fa = self.sa = c(attack_s); self.fr, self.sr_ = c(fast_rel_s), c(slow_rel_s)
        self.wf, self.ws = w_fast, w_slow
        self.gf = self.gs = 0.0
    def reset(self): self.gf = self.gs = 0.0
    def step(self, target_db):
        k = self.fa if target_db > self.gf else self.fr; self.gf = k * self.gf + (1 - k) * target_db
        k = self.sa if target_db > self.gs else self.sr_; self.gs = k * self.gs + (1 - k) * target_db
        return self.wf * self.gf + self.ws * self.gs   # weights sum to 1 -> steady state = target

class LA2A:
    def __init__(self, sr=48000, peak_reduction=0.5, gain_db=0.0, mode="limit",
                 r37_hf_boost_db=0.0, attack_s=10e-6):
        self.sr, self.pr, self.gain = sr, peak_reduction, 10 ** (gain_db / 20)
        self.mode, self.cell = mode, T4Cell(sr, attack_s)
        # R37: flat (default) = no emphasis; away from flat -> LF reduced in sidechain only
        self.hf = r37_hf_boost_db
        self._lp = 0.0
        self._a = 1 - np.exp(-2 * np.pi * 1000.0 / sr)   # C12 corner [?] UNVERIFIED
    def reset(self):
        self.cell.reset(); self._lp = 0.0
    def process(self, x):
        x = np.asarray(x, float); y = np.empty_like(x)
        gamma = 1.0 if self.mode == "limit" else 2.0 / 3.0   # slope 1-gamma = 1/3 -> 3:1 (addendum); mechanism [?]
        K = 400.0 * self.pr ** 2 + 1e-9                  # PR = sidechain gain (UA p.10); quadratic taper is a guess [?]
        r37 = 10 ** (-self.hf / 20)
        self.gr_db = np.empty_like(x)
        for i, v in enumerate(x):
            # sidechain taps the pre-attenuator input (feed-forward)
            self._lp += self._a * (v - self._lp)
            sc = self._lp * r37 + (v - self._lp)         # R37 trims LF only; HF untouched
            light = abs(sc)   # EL panel responds to |V|; abs() models that physics, not an added rectifier (p.4)
            # Smooth divider 1/(1+K*L^gamma) expressed in dB, then two-stage dynamics. Does NOT model the
            # -30 dB breakaway / -20 dB knee (p.3). [HYPOTHESIS]
            gr = self.cell.step(20.0 * np.log10(1.0 + K * light ** gamma))
            att = 10.0 ** (-gr / 20.0)
            # Gain applied post-attenuation (makeup style). Manual says 'input level' (p.3), which may mean pre-T4 drive. [?]
            y[i] = v * att * self.gain                   # tubes/xfmr fixed: linear in this model
            self.gr_db[i] = gr
        return y
