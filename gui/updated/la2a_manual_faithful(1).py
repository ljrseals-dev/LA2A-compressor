"""
LA-2A Manual-Faithful DSP Core
==============================

Module        : la2a_manual_faithful.py
Purpose       : Behavioral (not hardware-equivalent) emulation of the
                Teletronix LA-2A leveling amplifier, derived exclusively
                from the LA-2A Instruction Manual (3-66) and the 11-66
                addendum.
Author        : Lewis James Seals Jr — ljrseals-dev
Agent         : Boy Scouts Agent — "Be Prepared"
Doc standard  : Anthropic / Claude-grade

────────────────────────────────────────────────────────────────────────
SOURCE OF TRUTH
────────────────────────────────────────────────────────────────────────
All behavior is anchored to the Teletronix LA-2A Instruction Manual.
Any parameter not explicitly measured in that document is marked
``UNVERIFIED`` or ``[?]`` inline. This module does **not** claim
hardware equivalence; it is a *behavioral* model.

────────────────────────────────────────────────────────────────────────
SIGNAL ARCHITECTURE (Manual p.3–4, Fig.2)
────────────────────────────────────────────────────────────────────────
  input
    │
    ▼
  T4 shunt attenuator  (AHEAD of V1; the photocell is the bottom leg)
    │
    ▼
  gain stage (V1/V2/transformer: constant bias — modeled as linear)
    │
    ▼
  output

  Sidechain (feed-forward, per Teletronix p.4 / schematic):
    sample of the INPUT (pre-T4)
      → R37 / C12 pre-emphasis (flat by default)
      → R2 Peak Reduction
      → V3 → R3 → V4
      → EL panel

  The EL panel responds to |V|; the original design therefore requires
  no explicit rectifier (p.4). The ``abs()`` in this module models that
  physical property — it is not an added circuit.

────────────────────────────────────────────────────────────────────────
HONESTY LEDGER — MODELING DECISIONS
────────────────────────────────────────────────────────────────────────
  • No audio-path response shaping is modeled. The model is flat
    DC→Nyquist; the manual's ±0.1 dB over 30 Hz–15 kHz (p.2) is
    therefore UNMODELED.                             [HYPOTHESIS]
  • Deliberately removed from earlier revisions: sidechain HPF,
    10 ms RMS detector, 'T4B' label, 6BC8 tube nonlinearity,
    tanh transformer saturation, wet/dry mix, unity-bypass path,
    lookahead, M/S processing.
  • Every unmeasured coefficient is flagged inline as ``[?]`` or
    ``UNVERIFIED``. When the manual is silent, we say so.

────────────────────────────────────────────────────────────────────────
AGENT LAYER — Boy Scouts Agent ("Be Prepared")
────────────────────────────────────────────────────────────────────────
The :class:`BoyScoutsAgent` wraps the DSP core with:

  • strict argument validation and documented safe ranges,
  • dtype normalization (int → float64, ±Inf/NaN sanitized),
  • mono *and* multichannel handling with **per-channel engines**
    (no inter-channel state bleed — important for streaming),
  • persistent streaming state across blocks within a channel,
  • structured telemetry: per-sample gain-reduction trace and
    peak GR in dB,
  • idempotent ``configure()`` for live parameter changes,
  • an idempotent ``reset()`` for transport / playhead jumps.

The agent is intentionally defensive: "Be Prepared" means it will
never emit NaN/Inf on the audio bus, never silently corrupt state,
and always expose a clean interface for a DAW or pipeline.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

import numpy as np

__all__ = ["T4Cell", "LA2A", "BoyScoutsAgent"]


# ══════════════════════════════════════════════════════════════════════
#  T4 cell — EL panel + CdS photocell
# ══════════════════════════════════════════════════════════════════════
class T4Cell:
    """
    Electroluminescent panel + CdS photocell.

    Both internal stages attack fast (manual p.2: ~10 µs) but differ in
    release: a fast stage and a slow tail (Teletronix p.2 / p.4: ~60 ms
    to 50 %, full release 0.5–5 s). Illumination is the **average** of
    the two stages — a modeling hypothesis; a cascade is the plausible
    alternative.                                                [HYPOTHESIS]

    Parameters
    ----------
    sr : int
        Sample rate in Hz.
    attack_s : float, default 10e-6
        Target attack time. At 48 kHz one sample is ~20.8 µs, so the
        coefficient is clamped to one sample; effective attack becomes
        ~2–3 samples (~40–60 µs).                           UNVERIFIED
    fast_rel_s : float, default 15e-3
        Fast release constant, chosen so ``0.5·f + 0.5·s`` crosses 50 %
        near 60 ms. Not a manual value.                     UNVERIFIED
    slow_rel_s : float, default 2.5
        Slow release tail.                                  [?] UNVERIFIED
    """

    def __init__(
        self,
        sr: int,
        attack_s: float = 10e-6,
        fast_rel_s: float = 0.015,
        slow_rel_s: float = 2.5,
    ) -> None:
        c = lambda t: float(np.exp(-1.0 / (max(t, 1.0 / sr) * sr)))
        self.fa = self.sa = c(attack_s)
        self.fr, self.sr_ = c(fast_rel_s), c(slow_rel_s)
        self.f = self.s = 0.0

    def reset(self) -> None:
        """Clear both detector stages to dark state."""
        self.f = self.s = 0.0

    def step(self, light: float) -> float:
        """Advance both stages by one sample and return the averaged light."""
        k = self.fa if light > self.f else self.fr
        self.f = k * self.f + (1 - k) * light

        k = self.sa if light > self.s else self.sr_
        self.s = k * self.s + (1 - k) * light

        return 0.5 * self.f + 0.5 * self.s


# ══════════════════════════════════════════════════════════════════════
#  LA-2A engine (single-channel, streaming-stateful)
# ══════════════════════════════════════════════════════════════════════
class LA2A:
    """
    Single-channel LA-2A behavioral engine.

    The engine is **stateful**: detector and pre-emphasis state persist
    across :meth:`process` calls so that block-based (streaming) audio
    remains continuous. Call :meth:`reset` on transport jumps.

    Parameters
    ----------
    sr : int, default 48000
        Sample rate in Hz.
    peak_reduction : float in [0, 1], default 0.5
        R2 Peak Reduction knob position. Drives sidechain gain ``K``.
    gain_db : float, default 0.0
        Makeup / output gain in dB.
    mode : {"limit", "compress"}, default "limit"
        Limiter or 3:1 compressor (per 11-66 addendum). Mechanism
        of the 3:1 ratio is a behavioral fit.             [?] UNVERIFIED
    r37_hf_boost_db : float, default 0.0
        R37 pre-emphasis. ``0`` = flat (manual default). Non-zero
        values attenuate LF in the sidechain only.
    attack_s : float, default 10e-6
        Target attack; see :class:`T4Cell`.

    Attributes
    ----------
    gr_db : np.ndarray
        Per-sample gain reduction (positive dB) from the most recent
        :meth:`process` call. Useful for metering and debugging.

    Notes
    -----
    * Gain is applied *post*-attenuation (makeup style). The manual
      calls this "input level" (p.3), which may instead mean pre-T4
      drive. See note in honesty ledger.                     [?]
    * Tube and transformer stages are modeled as **linear** in this
      module. No tanh saturation is applied.
    """

    def __init__(
        self,
        sr: int = 48000,
        peak_reduction: float = 0.5,
        gain_db: float = 0.0,
        mode: str = "limit",
        r37_hf_boost_db: float = 0.0,
        attack_s: float = 10e-6,
    ) -> None:
        self.sr = int(sr)
        self.pr = float(peak_reduction)
        self.gain = 10 ** (gain_db / 20)
        self.mode = mode
        self.cell = T4Cell(self.sr, attack_s)

        # R37 pre-emphasis: flat default → no LF trim in sidechain.
        self.hf = float(r37_hf_boost_db)
        self._lp = 0.0
        # C12 sidechain corner.                          [?] UNVERIFIED
        self._a = 1 - np.exp(-2 * np.pi * 1000.0 / self.sr)

        self.gr_db = np.zeros(0)

    # ── public API ───────────────────────────────────────────────────
    def reset(self) -> None:
        """Clear detector and pre-emphasis state (idempotent)."""
        self.cell.reset()
        self._lp = 0.0

    def process(self, x: np.ndarray) -> np.ndarray:
        """
        Process a mono block of samples.

        Parameters
        ----------
        x : np.ndarray, shape (N,)
            Input samples. Caller is responsible for finite values;
            :class:`BoyScoutsAgent` sanitizes on the way in.

        Returns
        -------
        np.ndarray, shape (N,)
            Processed samples.
        """
        x = np.asarray(x, dtype=np.float64)
        y = np.empty_like(x)

        gamma = 1.0 if self.mode == "limit" else 0.62  # 3:1 addendum; mechanism [?]
        K = 400.0 * self.pr ** 2 + 1e-9                 # PR gain taper is a guess [?]
        r37 = 10 ** (-self.hf / 20)
        self.gr_db = np.empty_like(x)

        for i, v in enumerate(x):
            # Sidechain taps the pre-attenuator input (feed-forward).
            self._lp += self._a * (v - self._lp)
            sc = self._lp * r37 + (v - self._lp)
            light = abs(sc)  # EL panel responds to |V|; physics, not a circuit.

            L = self.cell.step(light)
            att = 1.0 / (1.0 + K * L ** gamma)
            y[i] = v * att * self.gain
            self.gr_db[i] = -20 * np.log10(att)

        return y


# ══════════════════════════════════════════════════════════════════════
#  Boy Scouts Agent — "Be Prepared"
# ══════════════════════════════════════════════════════════════════════
class BoyScoutsAgent:
    """
    Boy Scouts Agent — *"Be Prepared."*

    A thin, defensive orchestration layer around :class:`LA2A`. The
    agent owns the DSP engine(s), validates every input, normalizes
    dtypes and shapes, and guarantees a well-formed output array.

    Why an agent, not just a function?
    ----------------------------------
    Real pipelines are noisy: int16 buffers, ±Inf from an upstream
    filter, mid-stream parameter changes, transport rewinds, stereo
    stems. The agent absorbs that friction so the DSP math stays
    honest and the caller always receives ``float64`` audio with a
    clean telemetry trace.

    Responsibilities
    ----------------
    • Validate and clamp constructor arguments to documented ranges.
    • Accept mono ``(N,)`` or multichannel ``(N, C)`` input.
    • Sanitize non-finite samples before they reach the detector.
    • Maintain **one engine per channel** so multichannel audio does
      not bleed detector state between channels, while preserving
      streaming continuity *within* each channel.
    • Expose ``last_gr_db`` (per-sample GR) and ``last_peak_gr_db``.
    • ``configure()`` for live parameter changes (rebuilds engines
      only when parameters actually change).
    • ``reset()`` for transport jumps (idempotent).

    The agent is "prepared", not "clever": it never alters the DSP
    semantics of :class:`LA2A`.
    """

    _MODES = ("limit", "compress")

    def __init__(
        self,
        sr: int = 48000,
        peak_reduction: float = 0.5,
        gain_db: float = 0.0,
        mode: str = "limit",
        r37_hf_boost_db: float = 0.0,
        attack_s: float = 10e-6,
    ) -> None:
        self._validate(sr, peak_reduction, gain_db, mode)
        self._params = dict(
            sr=int(sr),
            peak_reduction=float(peak_reduction),
            gain_db=float(gain_db),
            mode=str(mode),
            r37_hf_boost_db=float(r37_hf_boost_db),
            attack_s=float(attack_s),
        )
        self._engines: List[LA2A] = []
        self._engines_sig: Optional[tuple] = None
        self.last_gr_db: Optional[np.ndarray] = None
        self.last_peak_gr_db: float = 0.0

    # ── validation ───────────────────────────────────────────────────
    @classmethod
    def _validate(cls, sr, pr, gain_db, mode) -> None:
        if not (isinstance(sr, (int, np.integer)) and sr > 0):
            raise ValueError(f"sr must be a positive integer, got {sr!r}")
        if not (0.0 <= float(pr) <= 1.0):
            raise ValueError(
                f"peak_reduction must be in [0, 1], got {pr!r}"
            )
        if not np.isfinite(gain_db):
            raise ValueError(f"gain_db must be finite, got {gain_db!r}")
        if mode not in cls._MODES:
            raise ValueError(
                f"mode must be one of {cls._MODES}, got {mode!r}"
            )

    # ── configuration & lifecycle ────────────────────────────────────
    def configure(self, **kwargs) -> "BoyScoutsAgent":
        """
        Update one or more parameters. Idempotent: no-op if nothing
        actually changes. Rebuilds per-channel engines if needed.
        """
        merged = {**self._params, **kwargs}
        self._validate(
            merged["sr"],
            merged["peak_reduction"],
            merged["gain_db"],
            merged["mode"],
        )
        if merged == self._params:
            return self
        self._params = merged
        # Engines will be lazily rebuilt on next process().
        self._engines_sig = None
        self._engines = []
        return self

    def reset(self) -> None:
        """Clear all per-channel engine state (idempotent)."""
        for eng in self._engines:
            eng.reset()
        self.last_gr_db = None
        self.last_peak_gr_db = 0.0

    # ── engine management ────────────────────────────────────────────
    def _signature(self) -> tuple:
        p = self._params
        return (
            p["sr"], p["peak_reduction"], p["gain_db"],
            p["mode"], p["r37_hf_boost_db"], p["attack_s"],
        )

    def _engines_for(self, n_channels: int) -> List[LA2A]:
        sig = self._signature()
        if self._engines_sig != sig or len(self._engines) != n_channels:
            p = self._params
            self._engines = [
                LA2A(
                    sr=p["sr"],
                    peak_reduction=p["peak_reduction"],
                    gain_db=p["gain_db"],
                    mode=p["mode"],
                    r37_hf_boost_db=p["r37_hf_boost_db"],
                    attack_s=p["attack_s"],
                )
                for _ in range(n_channels)
            ]
            self._engines_sig = sig
        return self._engines

    # ── input preparation ────────────────────────────────────────────
    @staticmethod
    def _as_float64(x) -> np.ndarray:
        arr = np.asarray(x)
        if arr.dtype.kind in "iu":
            arr = arr.astype(np.float64)
        elif not np.issubdtype(arr.dtype, np.floating):
            raise TypeError(
                f"expected integer or float input, got dtype={arr.dtype}"
            )
        else:
            arr = arr.astype(np.float64, copy=False)
        if arr.ndim == 0:
            raise ValueError("input must be at least 1-D")
        if arr.ndim > 2:
            raise ValueError(
                f"input must be 1-D mono or 2-D (samples, channels); "
                f"got ndim={arr.ndim}"
            )
        return arr

    @staticmethod
    def _sanitize(x: np.ndarray) -> np.ndarray:
        """Replace non-finite samples with 0.0 before they reach the
        detector (a single NaN would otherwise poison the whole tail)."""
        if np.isfinite(x).all():
            return x
        return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)

    # ── main entry point ─────────────────────────────────────────────
    def process(self, x) -> np.ndarray:
        """
        Process mono ``(N,)`` or multichannel ``(N, C)`` audio.

        Returns an array of the same shape as the input, in ``float64``.
        Per-sample gain reduction from the last call is available as
        :attr:`last_gr_db`; the maximum is :attr:`last_peak_gr_db`.
        """
        x = self._as_float64(x)

        squeeze = x.ndim == 1
        if squeeze:
            x = x[:, None]

        n_ch = x.shape[1]
        engines = self._engines_for(n_ch)

        y = np.empty_like(x)
        gr = np.empty_like(x)
        for c in range(n_ch):
            xc = self._sanitize(x[:, c])
            y[:, c] = engines[c].process(xc)
            gr[:, c] = engines[c].gr_db

        self.last_gr_db = gr
        self.last_peak_gr_db = float(gr.max()) if gr.size else 0.0
        return y[:, 0] if squeeze else y


# ══════════════════════════════════════════════════════════════════════
#  Smoke-test — proves the agent is prepared
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    sr = 48000
    t = np.arange(sr) / sr
    # -6 dBFS 1 kHz sine — good enough to exercise the detector
    sig = 0.5 * np.sin(2 * np.pi * 1000 * t)

    agent = BoyScoutsAgent(sr=sr, peak_reduction=0.8, mode="limit")
    out = agent.process(sig)
    print(f"in  peak = {np.max(np.abs(sig)):.3f}")
    print(f"out peak = {np.max(np.abs(out)):.3f}")
    print(f"peak GR  = {agent.last_peak_gr_db:.2f} dB")
    print(f"out finite: {np.isfinite(out).all()}")
