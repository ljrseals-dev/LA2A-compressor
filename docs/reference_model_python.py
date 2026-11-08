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
    """EL panel + CdS cell. Both stages ATTACK fast (manual p.2: ~10 us); they differ in release.
    Release: fast stage then slow tail (Teletronix p.2/4: ~60 ms for 50%, 0.5-5 s full).
    Illumination is an average of the two stages (HYPOTHESIS; a cascade is the alternative)."""
    def __init__(self, sr, attack_s=10e-6,
                 fast_rel_s=0.015,   # chosen so 0.5*f+0.5*s crosses 50% near 60 ms (see check); not a manual value. UNVERIFIED
                 slow_rel_s=2.5):    # [?] UNVERIFIED
        # Manual target is 10 us. At 48 kHz one sample = 20.8 us, so the coefficient is clamped to one
        # sample; effective attack is ~2-3 samples (~40-60 us). UNVERIFIED.
        c = lambda t: float(np.exp(-1.0 / (max(t, 1.0 / sr) * sr)))
        self.fa = self.sa = c(attack_s)
        self.fr, self.sr_ = c(fast_rel_s), c(slow_rel_s)
        self.f = self.s = 0.0
    def reset(self): self.f = self.s = 0.0
    def step(self, light):
        k = self.fa if light > self.f else self.fr
        self.f = k * self.f + (1 - k) * light
        k = self.sa if light > self.s else self.sr_
        self.s = k * self.s + (1 - k) * light
        return 0.5 * self.f + 0.5 * self.s

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
        gamma = 1.0 if self.mode == "limit" else 0.62    # 3:1 per addendum; mechanism [?]
        K = 400.0 * self.pr ** 2 + 1e-9                  # PR = sidechain gain (UA p.10); quadratic taper is a guess [?]
        r37 = 10 ** (-self.hf / 20)
        self.gr_db = np.empty_like(x)
        for i, v in enumerate(x):
            # sidechain taps the pre-attenuator input (feed-forward)
            self._lp += self._a * (v - self._lp)
            sc = self._lp * r37 + (v - self._lp)         # R37 trims LF only; HF untouched
            light = abs(sc)   # EL panel responds to |V|; abs() models that physics, not an added rectifier (p.4)
            L = self.cell.step(light)
            # Smooth 1/(1+K*L^gamma): does NOT model the -30 dB breakaway or -20 dB limiter knee (p.3). [HYPOTHESIS]
            att = 1.0 / (1.0 + K * L ** gamma)           # photocell = bottom leg of divider
            # Gain applied post-attenuation (makeup style). Manual says 'input level' (p.3), which may mean pre-T4 drive. [?]
            y[i] = v * att * self.gain                   # tubes/xfmr fixed: linear in this model
            self.gr_db[i] = -20 * np.log10(att)
        return y
