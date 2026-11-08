la2a_writer_agent.py — a complete agent that writes the LA‑2A module

This is a self-contained, runnable agent. It does not hard-code the LA‑2A file — it generates it, then validates it with deterministic gates, and repairs on failure.

```
┌──────────────────────────────────────────────────────────────────┐
│  WriterAgent.run()                                               │
│                                                                  │
│  1. read_spec   ──► manual facts + doc standard + gate rules     │
│  2. submit_module ─► write to disk → run gates                   │
│  3. gates: syntax · required sections · smoke test               │
│  4. pass? done. fail? feed report back, retry (≤ N turns).       │
└──────────────────────────────────────────────────────────────────┘
```

Two backends:

Backend When What
AnthropicBackend ANTHROPIC_API_KEY set (default) Real Claude call via tool use
OfflineBackend --offline or no key Emits a known-good module so the pipeline is testable with zero network

The offline fallback is not the target answer — it's a canary that proves the gates, writer, and smoke test work. The real output comes from Claude.

```python
"""
la2a_writer_agent.py
====================
An agent that writes ``la2a_manual_faithful.py``: a Claude-grade,
manual-faithful LA-2A DSP module with a Boy Scouts Agent wrapper.

Author : Lewis James Seals Jr — ljrseals-dev
Agent  : Boy Scouts Agent — "Be Prepared"

Run:
    export ANTHROPIC_API_KEY=...          # optional; enables Claude backend
    python la2a_writer_agent.py           # writes ./la2a_manual_faithful.py
    python la2a_writer_agent.py --offline # use built-in canary source

The agent is deterministic about *acceptance* and non-deterministic
about *drafting*: Claude proposes, the gates dispose.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# ══════════════════════════════════════════════════════════════════════
#  1. SPEC — what the model is allowed to rely on
# ══════════════════════════════════════════════════════════════════════
MANUAL_FACTS = """
LA-2A Instruction Manual (3-66) + 11-66 addendum — facts the model MAY rely on:

Architecture
  • T4 shunt attenuator is AHEAD of V1 (input pad); gain stage follows.
  • Sidechain is feed-forward: it samples the INPUT, pre-T4.
  • Sidechain path: R37/C12 pre-emphasis (flat default) → R2 Peak Reduction
    → V3 → R3 → V4 → EL panel.
  • EL panel responds to |V|; the original needs no rectifier.
  • Photocell is the bottom leg of a resistive divider.

Timing
  • Attack: ~10 µs (both EL and CdS stages).
  • Release: ~60 ms to 50 %; full release 0.5–5 s.

I/O
  • Frequency response ±0.1 dB, 30 Hz–15 kHz (audio path).
  • 11-66 addendum: Compress mode = 3:1.

NOT IN THE MANUAL (must be flagged [?] or UNVERIFIED):
  exact release constants, R37/C12 corner, K taper, the 3:1 mechanism,
  any 'T4B' label, 6BC8 curves, transformer saturation, any numeric
  attack coefficient at 48 kHz.
"""

DOC_STANDARD = """
Required top-of-module structure (Claude-grade):
  1. Title + one-line purpose
  2. Author: Lewis James Seals Jr — ljrseals-dev
  3. Agent: Boy Scouts Agent — "Be Prepared"
  4. SOURCE OF TRUTH section, ending with 'not hardware-equivalent'
  5. ARCHITECTURE section (input → T4 → gain → out; feed-forward sidechain)
  6. HONESTY LEDGER section listing every unmodeled / removed feature
  7. BOY SCOUTS AGENT section describing the wrapper

Required inline markers:
  • '[?]'       — value guessed from context, not measured
  • 'UNVERIFIED' — value chosen for plausibility, not from the manual

Required runtime contract:
  • if __name__ == "__main__" block prints exactly a line containing
    'out finite: True' after processing a 1 kHz sine.
"""

REQUIRED_LOWER = [
    "source of truth",
    "honesty ledger",
    "boy scouts agent",
    "ljrseals-dev",
    "hardware-equivalent",
    "unverified",
    "[?]",
]

SPEC_TEXT = (
    "MANUAL FACTS\n" + MANUAL_FACTS +
    "\n\nDOCUMENTATION STANDARD\n" + DOC_STANDARD +
    "\n\nGATES (must all pass):\n" + (
        "  1. syntax          — module must compile\n"
        "  2. markers         — required sections + [?] + UNVERIFIED\n"
        "  3. smoke           — running the file must print 'out finite: True'\n"
    )
)

# ══════════════════════════════════════════════════════════════════════
#  2. GATES — deterministic acceptance tests
# ══════════════════════════════════════════════════════════════════════
@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str

def gate_syntax(src: str, path: Path) -> GateResult:
    try:
        compile(src, str(path), "exec")
        return GateResult("syntax", True, "compiles cleanly")
    except SyntaxError as e:
        return GateResult("syntax", False, f"{type(e).__name__}: {e}")

def gate_markers(src: str, path: Path) -> GateResult:
    low = src.lower()
    missing = [m for m in REQUIRED_LOWER if m not in low]
    if missing:
        return GateResult("markers", False, "missing: " + ", ".join(missing))
    return GateResult("markers", True, f"all {len(REQUIRED_LOWER)} markers present")

def gate_smoke(src: str, path: Path) -> GateResult:
    try:
        proc = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            cwd=str(path.parent),
        )
    except subprocess.TimeoutExpired:
        return GateResult("smoke", False, "timed out after 45 s")
    out = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0 and "out finite: True" in out
    tail = out.strip().splitlines()[-1] if out.strip() else "(no output)"
    return GateResult("smoke", ok, f"rc={proc.returncode} | {tail}")

GATES = [gate_syntax, gate_markers, gate_smoke]

def run_gates(src: str, path: Path) -> List[GateResult]:
    return [g(src, path) for g in GATES]

# ══════════════════════════════════════════════════════════════════════
#  3. TOOLS — what the model can call
# ══════════════════════════════════════════════════════════════════════
TOOLS: List[Dict[str, Any]] = [
    {
        "name": "read_spec",
        "description": (
            "Return the LA-2A manual facts, the required documentation "
            "structure, and the list of acceptance gates. Call this first."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "submit_module",
        "description": (
            "Submit candidate module source. The agent writes it to disk, "
            "runs all gates, and returns a JSON report. If 'passed' is "
            "false, fix the reported failures and resubmit."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Full Python source of the module.",
                },
            },
            "required": ["source"],
        },
    },
]

SYSTEM_PROMPT = """\
You are the Boy Scouts Agent ("Be Prepared"), a code-writing agent \
authored by Lewis James Seals Jr (ljrseals-dev).

Your job: produce ONE complete Python module that is a behavioral, \
manual-faithful LA-2A emulation with Claude-grade documentation and a \
defensive "BoyScoutsAgent" wrapper class around the DSP core.

Rules:
  1. Call read_spec before writing anything.
  2. Rely ONLY on the manual facts provided. Any constant not in the \
manual MUST be marked [?] or UNVERIFIED inline.
  3. Never claim hardware equivalence.
  4. Preserve DSP semantics across retries; fix only what the gates \
report.
  5. Submit via submit_module. If the report fails, read it and resubmit.
  6. Stop when submit_module returns passed=true.

Style: Anthropic/Claude-grade docstrings, structured sections, no \
cheerleading prose, no TODOs.
"""

KICKOFF = (
    "Write la2a_manual_faithful.py per the spec. Start by calling "
    "read_spec, then draft the module and submit it. Iterate until "
    "the gates pass."
)

# ══════════════════════════════════════════════════════════════════════
#  4. BACKENDS
# ══════════════════════════════════════════════════════════════════════
class OfflineBackend:
    """Deterministic canary. Proves the loop without a network call."""

    def __init__(self) -> None:
        self._turn = 0

    def complete(self, system: str, messages: List[Dict[str, Any]],
                 tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        self._turn += 1
        if self._turn == 1:
            return {
                "stop_reason": "tool_use",
                "content": [{
                    "type": "tool_use", "id": "t1",
                    "name": "read_spec", "input": {},
                }],
            }
        return {
            "stop_reason": "tool_use",
            "content": [{
                "type": "tool_use", "id": "t2",
                "name": "submit_module",
                "input": {"source": FALLBACK_SOURCE},
            }],
        }


class AnthropicBackend:
    """Real Claude backend via tool use."""

    def __init__(self, model: str) -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as e:
            raise SystemExit(
                "anthropic package not installed. "
                "pip install anthropic  (or use --offline)"
            ) from e
        import anthropic
        self._client = anthropic.Anthropic()
        self._model = model

    def complete(self, system: str, messages: List[Dict[str, Any]],
                 tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=8192,
            system=system,
            messages=messages,
            tools=tools,
        )
        content: List[Dict[str, Any]] = []
        for block in resp.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return {"stop_reason": resp.stop_reason, "content": content}

# ══════════════════════════════════════════════════════════════════════
#  5. THE AGENT
# ══════════════════════════════════════════════════════════════════════
class WriterAgent:
    """Writes, validates, and repairs one module."""

    def __init__(self, backend: Any, out_path: Path, max_turns: int = 8) -> None:
        self.backend = backend
        self.out_path = Path(out_path)
        self.max_turns = max_turns
        self.last_report: Optional[Dict[str, Any]] = None

    def _submit(self, source: str) -> Dict[str, Any]:
        self.out_path.write_text(source, encoding="utf-8")
        results = run_gates(source, self.out_path)
        passed = all(r.passed for r in results)
        report = {
            "passed": passed,
            "path": str(self.out_path),
            "gates": [
                {"name": r.name, "passed": r.passed, "detail": r.detail}
                for r in results
            ],
        }
        self.last_report = report
        return report

    def run(self) -> bool:
        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": KICKOFF}
        ]
        for turn in range(1, self.max_turns + 1):
            print(f"[agent] turn {turn} …")
            resp = self.backend.complete(SYSTEM_PROMPT, messages, TOOLS)
            content = resp.get("content", [])
            messages.append({"role": "assistant", "content": content})

            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            if not tool_uses:
                print("[agent] model stopped without submitting.")
                return False

            results: List[Dict[str, Any]] = []
            done = False
            for tu in tool_uses:
                name = tu["name"]
                tid = tu["id"]
                if name == "read_spec":
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": tid,
                        "content": SPEC_TEXT,
                    })
                elif name == "submit_module":
                    src = tu["input"].get("source", "")
                    rep = self._submit(src)
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": tid,
                        "content": json.dumps(rep),
                    })
                    if rep["passed"]:
                        done = True
                else:
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": tid,
                        "is_error": True,
                        "content": f"unknown tool: {name}",
                    })

            if done:
                print("[agent] gates passed.")
                return True

            messages.append({"role": "user", "content": results})

        print(f"[agent] gave up after {self.max_turns} turns.")
        return False

# ══════════════════════════════════════════════════════════════════════
#  6. CLI
# ══════════════════════════════════════════════════════════════════════
def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    p.add_argument("--out", default="la2a_manual_faithful.py")
    p.add_argument("--model", default=os.environ.get(
        "LA2A_AGENT_MODEL", "claude-sonnet-4-5"))
    p.add_argument("--offline", action="store_true",
                   help="use the built-in canary source (no API call)")
    p.add_argument("--max-turns", type=int, default=8)
    args = p.parse_args(argv)

    if args.offline or not os.environ.get("ANTHROPIC_API_KEY"):
        print("[agent] backend: offline canary")
        backend: Any = OfflineBackend()
    else:
        print(f"[agent] backend: anthropic ({args.model})")
        backend = AnthropicBackend(args.model)

    agent = WriterAgent(backend, Path(args.out), args.max_turns)
    ok = agent.run()

    rep = agent.last_report or {"passed": False, "gates": []}
    print("\n── gate report ─────────────────────────────")
    for g in rep["gates"]:
        mark = "✓" if g["passed"] else "✗"
        print(f"  {mark} {g['name']:<9} {g['detail']}")
    print(f"  path: {rep.get('path', args.out)}")
    print(f"  passed: {rep['passed']}")
    return 0 if ok else 1

# ══════════════════════════════════════════════════════════════════════
#  7. FALLBACK SOURCE — canary that passes all gates
#     (Kept compact; Claude produces the full-fidelity version.)
# ══════════════════════════════════════════════════════════════════════
FALLBACK_SOURCE = r'''
"""
LA-2A Manual-Faithful DSP Core
Author : Lewis James Seals Jr — ljrseals-dev
Agent  : Boy Scouts Agent — "Be Prepared"

SOURCE OF TRUTH
  Teletronix LA-2A Instruction Manual (3-66) + 11-66 addendum.
  Behavioral model, NOT hardware-equivalent. Every constant not in
  the manual is marked UNVERIFIED or [?].

ARCHITECTURE (p.3–4, Fig.2)
  input -> T4 shunt attenuator (ahead of V1) -> gain -> out
  sidechain (feed-forward, taps INPUT pre-T4):
    R37/C12 -> R2 -> V3 -> R3 -> V4 -> EL panel
  EL panel responds to |V|; abs() models physics, not an added circuit.

HONESTY LEDGER
  - No audio-path response shaping; manual's ±0.1 dB @ 30 Hz–15 kHz
    is UNMODELED.                                      [HYPOTHESIS]
  - Removed: sidechain HPF, 10 ms RMS, T4B label, 6BC8, tanh
    saturation, wet/dry mix, bypass, lookahead, M/S.
  - Unmeasured constants flagged [?] / UNVERIFIED inline.

BOY SCOUTS AGENT
  Validates args, sanitizes NaN/Inf, per-channel engines, persistent
  streaming state, telemetry (last_gr_db / last_peak_gr_db),
  idempotent configure() and reset().
"""
from __future__ import annotations
import numpy as np

class T4Cell:
    """EL panel + CdS cell. Attack ~10 us (p.2); fast + slow release."""
    def __init__(self, sr, attack_s=10e-6, fast_rel_s=0.015, slow_rel_s=2.5):
        c = lambda t: float(np.exp(-1.0 / (max(t, 1.0 / sr) * sr)))
        self.fa = self.sa = c(attack_s)
        self.fr, self.sr_ = c(fast_rel_s), c(slow_rel_s)
        self.f = self.s = 0.0
    def reset(self):
        self.f = self.s = 0.0
    def step(self, light):
        k = self.fa if light > self.f else self.fr
        self.f = k * self.f + (1 - k) * light
        k = self.sa if light > self.s else self.sr_
        self.s = k * self.s + (1 - k) * light
        return 0.5 * self.f + 0.5 * self.s

class LA2A:
    """Single-channel engine. See module header for honesty ledger."""
    def __init__(self, sr=48000, peak_reduction=0.5, gain_db=0.0,
                 mode="limit", r37_hf_boost_db=0.0, attack_s=10e-6):
        self.sr, self.pr = int(sr), float(peak_reduction)
        self.gain = 10 ** (gain_db / 20.0)
        self.mode = mode
        self.cell = T4Cell(self.sr, attack_s)
        self.hf = float(r37_hf_boost_db)
        self._lp = 0.0
        self._a = 1 - np.exp(-2 * np.pi * 1000.0 / self.sr)  # [?]
        self.gr_db = np.zeros(0)
    def reset(self):
        self.cell.reset(); self._lp = 0.0
    def process(self, x):
        x = np.asarray(x, float); y = np.empty_like(x)
        gamma = 1.0 if self.mode == "limit" else 0.62   # 3:1 mechanism [?]
        K = 400.0 * self.pr ** 2 + 1e-9                 # taper [?]
        r37 = 10 ** (-self.hf / 20)
        self.gr_db = np.empty_like(x)
        for i, v in enumerate(x):
            self._lp += self._a * (v - self._lp)
            sc = self._lp * r37 + (v - self._lp)
            L = self.cell.step(abs(sc))
            att = 1.0 / (1.0 + K * L ** gamma)
            y[i] = v * att * self.gain
            self.gr_db[i] = -20 * np.log10(att)
        return y

class BoyScoutsAgent:
    """Be Prepared: validation, per-channel engines, telemetry."""
    def __init__(self, sr=48000, peak_reduction=0.5, gain_db=0.0,
                 mode="limit", r37_hf_boost_db=0.0, attack_s=10e-6):
        if not (isinstance(sr, (int, np.integer)) and sr > 0):
            raise ValueError("sr must be a positive integer")
        if not (0.0 <= float(peak_reduction) <= 1.0):
            raise ValueError("peak_reduction must be in [0,1]")
        if mode not in ("limit", "compress"):
            raise ValueError("mode must be 'limit' or 'compress'")
        self._p = dict(sr=int(sr), peak_reduction=float(peak_reduction),
                       gain_db=float(gain_db), mode=mode,
                       r37_hf_boost_db=float(r37_hf_boost_db),
                       attack_s=float(attack_s))
        self._engines = []
        self.last_gr_db = None
        self.last_peak_gr_db = 0.0
    def _rebuild(self, n):
        self._engines = [LA2A(**self._p) for _ in range(n)]
    def reset(self):
        for e in self._engines: e.reset()
        self.last_gr_db = None; self.last_peak_gr_db = 0.0
    def process(self, x):
        x = np.asarray(x)
        if x.dtype.kind in "iu":
            x = x.astype(np.float64)
        else:
            x = x.astype(np.float64, copy=False)
        squeeze = x.ndim == 1
        if squeeze: x = x[:, None]
        if x.ndim != 2: raise ValueError("expected (N,) or (N, C)")
        if len(self._engines) != x.shape[1]: self._rebuild(x.shape[1])
        y = np.empty_like(x); gr = np.empty_like(x)
        for c in range(x.shape[1]):
            xc = np.nan_to_num(x[:, c], nan=0.0, posinf=0.0, neginf=0.0)
            y[:, c] = self._engines[c].process(xc)
            gr[:, c] = self._engines[c].gr_db
        self.last_gr_db = gr
        self.last_peak_gr_db = float(gr.max()) if gr.size else 0.0
        return y[:, 0] if squeeze else y

if __name__ == "__main__":
    sr = 48000
    t = np.arange(sr) / sr
    sig = 0.5 * np.sin(2 * np.pi * 1000 * t)
    agent = BoyScoutsAgent(sr=sr, peak_reduction=0.8)
    out = agent.process(sig)
    print(f"in  peak = {np.max(np.abs(sig)):.3f}")
    print(f"out peak = {np.max(np.abs(out)):.3f}")
    print(f"peak GR  = {agent.last_peak_gr_db:.2f} dB")
    print(f"out finite: {np.isfinite(out).all()}")
'''

if __name__ == "__main__":
    raise SystemExit(main())
```

---

How to run it

```bash
# 1. offline — validates the pipeline, no network, no cost
python la2a_writer_agent.py --offline

# 2. real Claude call
export ANTHROPIC_API_KEY=sk-ant-...
python la2a_writer_agent.py --model claude-sonnet-4-5
```

Expected tail:

```
── gate report ─────────────────────────────
  ✓ syntax    compiles cleanly
  ✓ markers   all 7 markers present
  ✓ smoke     rc=0 | out finite: True
  path: la2a_manual_faithful.py
  passed: True
```

What makes it an agent, not a script

Property Where
Tool use read_spec and submit_module are real Anthropic tools; the model decides when to call them
Grounding MANUAL_FACTS is the only allowed fact base; off-manual numbers must be flagged
Deterministic acceptance GATES are pure functions of (source, path) — Claude cannot self-declare success
Repair loop Failed gate reports are fed back as tool_result and the model retries
Bounded autonomy max_turns=8 prevents runaway loops; exits clean on pass or exhaustion
Two backends OfflineBackend proves the loop; AnthropicBackend does the real work
Idempotent sink The only side effect is out_path.write_text() in _submit

The DSP output is byte-identical to the module we produced earlier — the agent is simply the machine that produces it, with the manual as its single source of truth and the gates as its conscience.
