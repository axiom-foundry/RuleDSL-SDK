"""
RuleDSL Workbench — a zero-dependency Tkinter GUI for exploring the engine.

Edit a ruleset on the left, inputs on the right, then:
  - "Compile & Run" shows the decision, its output fields, the engine's
    evaluation trace (why this decision), and a canonical decision hash.
  - "Run 100x" re-evaluates the same bytecode and inputs 100 times and
    reports whether every run produced the identical decision hash — the
    determinism contract, live.

The decision hash is the producer-side convention used by
examples/replay_proof_producer.py: SHA-256 over a canonical JSON view of the
decision. The engine itself does not hand out a hash; deterministic
serialization is the host's choice, and this tool uses the documented one.

Usage:
    python workbench.py [--dll path/to/ruledsl_capi.dll]

Library resolution order: --dll argument, RULEDSL_DLL environment variable,
the SDK bundle layout relative to this file (../../bin/), then the binding's
own auto-discovery.

Requires: Python 3.7+ with Tkinter (both in the standard CPython installer),
no third-party dependencies.
"""

import argparse
import hashlib
import json
import os
import platform
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ruledsl import RuleDSL, RuleDSLError  # noqa: E402


# ---------------------------------------------------------------------------
# Scenarios — the same rulesets shipped under examples/.
# ---------------------------------------------------------------------------

SCENARIOS = {
    "01 Risk Scoring — threshold decline": {
        "rules": """\
rule high_risk {
  when amount >= 1000;
  then decline;
}

rule default_allow {
  when amount < 1000;
  then allow;
}
""",
        "inputs": "amount = 1200\n",
        "now_utc_ms": "",
    },
    "04 KYC Compliance — lists, match, priority": {
        "rules": """\
# KYC Compliance — boolean logic, IN lists, MATCH, and priority

rule block_sanctioned_country priority 200 {
  when ip_country in [KP, IR, SY];
  then reason = "sanctioned_country", decline;
}

rule flag_suspicious_email priority 100 {
  when email match "@tempmail" or email match "@throwaway";
  then reason = "disposable_email", review;
}

rule trusted_verified_customer priority 50 {
  when is_verified and not is_new_device and amount <= 5000;
  then reason = "trusted_customer", allow;
}

rule new_device_review priority 40 {
  when is_new_device and (amount > 1000 or not is_verified);
  then reason = "new_device_risk", review;
}

rule default_allow {
  when true;
  then reason = "baseline", allow;
}
""",
        "inputs": (
            "ip_country = \"US\"\n"
            "email = \"someone@tempmail.com\"\n"
            "is_verified = true\n"
            "is_new_device = false\n"
            "amount = 800\n"
        ),
        "now_utc_ms": "",
    },
    "05 Velocity Limit — arithmetic, limit windows": {
        "rules": """\
# Velocity Limits — arithmetic, limit clauses, and currency thresholds

rule block_extreme priority 200 {
  when amount > 25000;
  then reason = "extreme_amount", risk_score = 99, decline;
}

rule high_value_daily_cap priority 100 {
  when amount > 5000 and amount <= 25000;
  then reason = "daily_cap", risk_score = (amount / 500) + 20, limit 3000 USD per 1 D;
}

rule medium_hourly_cap priority 50 {
  when amount > 1000 and amount <= 5000;
  then reason = "hourly_cap", risk_score = (amount / 1000) * 10, limit 10000 USD per 1 H;
}

rule allow_small {
  when amount <= 1000;
  then reason = "low_value", risk_score = 5, allow;
}
""",
        "inputs": "amount = 2500\n",
        # Time-based rules REQUIRE an explicit clock — the engine never reads
        # the system clock. Clear this box to see the deterministic error.
        "now_utc_ms": "1700000000000",
    },
}

_ACTION_COLORS = {"ALLOW": "#1a7f37", "DECLINE": "#c62828",
                  "REVIEW": "#e07b00", "LIMIT": "#1565c0"}


# ---------------------------------------------------------------------------
# Input parsing: one "name = value" per line.
# ---------------------------------------------------------------------------

def parse_inputs(text):
    """Parse 'name = value' lines into a fields dict.

    Values: true/false -> bool, null -> None (MISSING), "quoted" -> string,
    numeric literal -> float, anything else -> string.
    """
    fields = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"inputs line {lineno}: expected 'name = value', got: {raw!r}")
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if not name:
            raise ValueError(f"inputs line {lineno}: empty field name")
        low = value.lower()
        if low == "true":
            fields[name] = True
        elif low == "false":
            fields[name] = False
        elif low in ("null", "none", "missing"):
            fields[name] = None
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            fields[name] = value[1:-1]
        else:
            try:
                fields[name] = float(value)
            except ValueError:
                fields[name] = value
    return fields


def decision_hash(decision):
    """Canonical decision hash — same payload as replay_proof_producer.py."""
    payload = {
        "matched": decision.matched,
        "action_type": decision.action_type,
        "amount": decision.amount,
        "currency": decision.currency,
        "window_count": decision.window_count,
        "window_unit": decision.window_unit,
        "rule_name": decision.rule_name,
        "outputs": decision.outputs,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def resolve_library(cli_dll):
    """Resolve the engine library path (see module docstring for the order)."""
    if cli_dll:
        return cli_dll
    env = os.environ.get("RULEDSL_DLL")
    if env:
        return env
    libname = "ruledsl_capi.dll" if platform.system() == "Windows" else "libruledsl_capi.so"
    bundled = Path(__file__).resolve().parent.parent.parent / "bin" / libname
    if bundled.exists():
        return str(bundled)
    return None  # binding auto-discovery


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------

class Workbench(tk.Tk):
    RUNS = 100

    def __init__(self, engine, library_label):
        super().__init__()
        self.engine = engine
        self.title(f"RuleDSL Workbench — {engine.version()}")
        self.geometry("1080x720")
        self.minsize(860, 560)
        self._build_ui(library_label)
        self.load_scenario(next(iter(SCENARIOS)))

    # -- UI construction ----------------------------------------------------

    def _build_ui(self, library_label):
        mono = ("Consolas", 10) if platform.system() == "Windows" else ("Courier", 10)

        top = ttk.Frame(self, padding=(8, 6))
        top.pack(fill="x")
        ttk.Label(top, text="Scenario:").pack(side="left")
        self.scenario_var = tk.StringVar()
        self.scenario_box = ttk.Combobox(
            top, textvariable=self.scenario_var, state="readonly",
            width=44, values=list(SCENARIOS))
        self.scenario_box.pack(side="left", padx=(6, 4))
        self.scenario_box.bind("<<ComboboxSelected>>",
                               lambda _e: self.load_scenario(self.scenario_var.get()))
        ttk.Label(top, text=self.engine.version()).pack(side="right")

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8)

        left = ttk.Frame(panes)
        ttk.Label(left, text="Rules").pack(anchor="w")
        self.rules_text = tk.Text(left, font=mono, wrap="none", undo=True)
        self.rules_text.pack(fill="both", expand=True)
        panes.add(left, weight=3)

        right = ttk.Frame(panes)
        ttk.Label(right, text="Inputs — one per line:  name = value").pack(anchor="w")
        self.inputs_text = tk.Text(right, font=mono, wrap="none", undo=True, height=12)
        self.inputs_text.pack(fill="both", expand=True)
        clock = ttk.Frame(right)
        clock.pack(fill="x", pady=(6, 0))
        ttk.Label(clock, text="now_utc_ms:").pack(side="left")
        self.now_var = tk.StringVar()
        ttk.Entry(clock, textvariable=self.now_var, width=18).pack(side="left", padx=(6, 4))
        ttk.Label(clock, text="(explicit clock; empty = omitted — the engine never reads"
                              " the system clock)").pack(side="left")
        panes.add(right, weight=2)

        actions = ttk.Frame(self, padding=(8, 6))
        actions.pack(fill="x")
        ttk.Button(actions, text="Compile & Run", command=self.run_once).pack(side="left")
        ttk.Button(actions, text=f"Run {self.RUNS}×",
                   command=self.run_many).pack(side="left", padx=(6, 0))
        self.stability_var = tk.StringVar(value="")
        self.stability_label = tk.Label(actions, textvariable=self.stability_var, anchor="w")
        self.stability_label.pack(side="left", padx=(12, 0))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        result_tab = ttk.Frame(notebook)
        self.result_text = tk.Text(result_tab, font=mono, wrap="word", state="disabled", height=12)
        self.result_text.pack(fill="both", expand=True)
        notebook.add(result_tab, text="Result")
        trace_tab = ttk.Frame(notebook)
        self.trace_text = tk.Text(trace_tab, font=mono, wrap="none", state="disabled", height=12)
        self.trace_text.pack(fill="both", expand=True)
        notebook.add(trace_tab, text="Trace — why this decision")
        for text in (self.result_text, self.trace_text):
            for action, color in _ACTION_COLORS.items():
                text.tag_configure(action, foreground=color, font=mono + ("bold",))
            text.tag_configure("ERROR", foreground="#c62828", font=mono + ("bold",))

        status = ttk.Frame(self, padding=(8, 2))
        status.pack(fill="x")
        self.status_var = tk.StringVar(value=f"engine: {library_label}")
        ttk.Label(status, textvariable=self.status_var, anchor="w").pack(fill="x")

    # -- Behaviors ----------------------------------------------------------

    def load_scenario(self, name):
        scenario = SCENARIOS[name]
        self.scenario_var.set(name)
        self.rules_text.delete("1.0", "end")
        self.rules_text.insert("1.0", scenario["rules"])
        self.inputs_text.delete("1.0", "end")
        self.inputs_text.insert("1.0", scenario["inputs"])
        self.now_var.set(scenario["now_utc_ms"])
        self.stability_var.set("")
        self._set_text(self.result_text, [("Scenario loaded. Compile & Run to evaluate.", None)])
        self._set_text(self.trace_text, [])

    def _gather(self):
        """Read the editors; returns (bytecode, fields, now_utc_ms)."""
        fields = parse_inputs(self.inputs_text.get("1.0", "end"))
        now_raw = self.now_var.get().strip()
        now_utc_ms = float(now_raw) if now_raw else None
        bytecode = self.engine.compile(self.rules_text.get("1.0", "end"))
        return bytecode, fields, now_utc_ms

    def run_once(self):
        self.stability_var.set("")
        try:
            bytecode, fields, now_utc_ms = self._gather()
            trace = []
            decision = self.engine.evaluate(bytecode, fields, now_utc_ms=now_utc_ms,
                                            on_trace=trace.append)
        except (RuleDSLError, ValueError) as exc:
            self._show_error(exc)
            return
        digest = decision_hash(decision)
        lines = [(f"{decision.action}", decision.action if decision.matched else None),
                 (f"matched      : {decision.matched}", None),
                 (f"rule         : {decision.rule_name or '-'}", None)]
        if decision.action == "LIMIT":
            window = f" per {decision.window_count:g} {decision.window_unit}" \
                if decision.window_unit else ""
            currency = f" {decision.currency}" if decision.currency else ""
            lines.append((f"limit        : {decision.amount:g}{currency}{window}", None))
        if decision.outputs:
            lines.append(("outputs      :", None))
            for key in sorted(decision.outputs):
                lines.append((f"    {key} = {decision.outputs[key]!r}", None))
        lines += [(f"bytecode     : {len(bytecode)} bytes", None),
                  (f"decision hash: {digest}", None)]
        self._set_text(self.result_text, lines)
        self._set_text(self.trace_text,
                       [(line, None) for line in trace] or [("(no trace lines)", None)])
        self.status_var.set(f"evaluated with {self.engine.version()}")

    def run_many(self):
        try:
            bytecode, fields, now_utc_ms = self._gather()
            hashes = set()
            trace = []
            for i in range(self.RUNS):
                collector = trace.append if i == 0 else None
                decision = self.engine.evaluate(bytecode, fields, now_utc_ms=now_utc_ms,
                                                on_trace=collector)
                hashes.add(decision_hash(decision))
        except (RuleDSLError, ValueError) as exc:
            self._show_error(exc)
            return
        self.run_once()
        if len(hashes) == 1:
            digest = next(iter(hashes))
            self.stability_var.set(
                f"{self.RUNS}/{self.RUNS} runs → identical decision hash "
                f"({digest[:16]}…)  ✓")
            self.stability_label.configure(fg="#1a7f37")
        else:
            self.stability_var.set(
                f"NON-DETERMINISTIC: {len(hashes)} distinct hashes across "
                f"{self.RUNS} runs ✗")
            self.stability_label.configure(fg="#c62828")

    def _show_error(self, exc):
        if isinstance(exc, RuleDSLError):
            lines = [(f"{exc.code_name} (code={exc.code})", "ERROR"),
                     (str(exc), None),
                     ("", None),
                     ("Deterministic by contract: the same inputs raise this same "
                      "error on every run.", None)]
        else:
            lines = [("INPUT ERROR", "ERROR"), (str(exc), None)]
        self._set_text(self.result_text, lines)
        self._set_text(self.trace_text, [])
        self.stability_var.set("")

    @staticmethod
    def _set_text(widget, lines):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        for content, tag in lines:
            widget.insert("end", content + "\n", tag or ())
        widget.configure(state="disabled")


def main(argv=None):
    parser = argparse.ArgumentParser(description="RuleDSL Workbench (Tkinter GUI)")
    parser.add_argument("--dll", help="path to ruledsl_capi.dll / libruledsl_capi.so")
    args = parser.parse_args(argv)

    library = resolve_library(args.dll)
    try:
        engine = RuleDSL(library)
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "RuleDSL Workbench",
            "Could not load the RuleDSL engine library.\n\n"
            f"{exc}\n\n"
            "Pass it explicitly:  python workbench.py --dll path/to/ruledsl_capi.dll")
        return 1

    app = Workbench(engine, library or "(auto-discovered)")
    app.mainloop()
    engine.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
