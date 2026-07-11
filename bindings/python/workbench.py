"""
RuleDSL Workbench — the desktop authoring & replay companion for the engine.

It is a developer-desktop tool, never a server component: production rulesets
are compiled to artifacts by `ruledslc` and evaluated in-process by your
server through the C ABI. The workbench covers the two human ends of that
pipeline:

  Authoring — edit a ruleset (or File > Open Rules…), run it against sample
  inputs, and read the decision, its output fields, the engine's own
  evaluation trace (why this decision), and a canonical decision hash.
  "Run 100x" re-evaluates and asserts every run produced the identical
  decision hash — the determinism contract, live.

  Replay — File > Open Bytecode (Replay)… loads a compiled .axbc exactly as
  the server ran it (no recompilation; the rules editor is disabled), and
  File > Load Inputs from JSON… restores an incident's inputs. Same bytecode,
  same input, same options -> the same decision and trace, on your desk.
  The workbench deliberately does NOT export .axbc: production artifacts come
  from `ruledslc`, which stamps the authenticity manifest.

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
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ruledsl import Bytecode, RuleDSL, RuleDSLError  # noqa: E402


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
        self.replay_bc = None          # Bytecode loaded from an .axbc file
        self.replay_path = None
        self.title(f"RuleDSL Workbench — {engine.version()}")
        self.geometry("1080x720")
        self.minsize(860, 560)
        self._build_menu()
        self._build_ui(library_label)
        self.load_scenario(next(iter(SCENARIOS)))

    def _build_menu(self):
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open Rules…", accelerator="Ctrl+O",
                             command=self.open_rules)
        filemenu.add_command(label="Save Rules As…", accelerator="Ctrl+S",
                             command=self.save_rules)
        filemenu.add_separator()
        filemenu.add_command(label="Open Bytecode (Replay)…",
                             command=self.open_replay)
        filemenu.add_command(label="Load Inputs from JSON…",
                             command=self.load_inputs)
        filemenu.add_separator()
        filemenu.add_command(label="Exit Replay Mode", command=self.exit_replay)
        menubar.add_cascade(label="File", menu=filemenu)
        self.configure(menu=menubar)
        self.bind_all("<Control-o>", lambda _e: self.open_rules())
        self.bind_all("<Control-s>", lambda _e: self.save_rules())

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

        # Replay strip — visible only while evaluating a loaded .axbc.
        self.replay_strip = tk.Frame(self, bg="#B45309")
        self.replay_var = tk.StringVar()
        tk.Label(self.replay_strip, textvariable=self.replay_var, bg="#B45309",
                 fg="white", font=("Segoe UI", 10, "bold")).pack(padx=10, pady=4)

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8)
        self._panes = panes

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
        self.exit_replay()
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

    # -- Files: authoring & replay ------------------------------------------

    def open_rules(self, path=None):
        path = path or filedialog.askopenfilename(
            title="Open rules", filetypes=[("RuleDSL rules", "*.rule"),
                                           ("All files", "*.*")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.exit_replay()
        self.rules_text.delete("1.0", "end")
        self.rules_text.insert("1.0", content)
        self.stability_var.set("")
        self.status_var.set(f"rules loaded: {path}")

    def save_rules(self, path=None):
        path = path or filedialog.asksaveasfilename(
            title="Save rules as", defaultextension=".rule",
            filetypes=[("RuleDSL rules", "*.rule"), ("All files", "*.*")])
        if not path:
            return
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.rules_text.get("1.0", "end-1c"))
        self.status_var.set(f"rules saved: {path}")

    def open_replay(self, path=None):
        """Load a compiled .axbc and evaluate IT — exactly what the server ran.
        No recompilation happens; the rules editor is disabled to make that
        unmistakable."""
        path = path or filedialog.askopenfilename(
            title="Open bytecode for replay",
            filetypes=[("RuleDSL bytecode", "*.axbc"), ("All files", "*.*")])
        if not path:
            return
        with open(path, "rb") as f:
            data = f.read()
        self.replay_bc = Bytecode(data)
        self.replay_path = path
        sha = hashlib.sha256(data).hexdigest()
        self.rules_text.configure(state="disabled", bg="#F3F4F6")
        self.replay_var.set(
            f"REPLAY MODE — {os.path.basename(path)} · {len(data)} bytes · "
            f"sha256 {sha[:16]}… · rules editor disabled, evaluating the loaded bytecode")
        self.replay_strip.pack(fill="x", before=self._panes)
        self.stability_var.set("")
        self._set_text(self.result_text,
                       [("Bytecode loaded for replay. Set the inputs "
                         "(File > Load Inputs from JSON…) and Run.", None)])
        self._set_text(self.trace_text, [])
        self.status_var.set(f"replaying {path}")

    def exit_replay(self):
        if self.replay_bc is None:
            return
        self.replay_bc = None
        self.replay_path = None
        self.rules_text.configure(state="normal", bg="white")
        self.replay_strip.pack_forget()

    def load_inputs(self, path=None):
        """Accepts a flat fields dict, or {"fields": {...}, "now_utc_ms": ...}
        — the shapes used by the replay tooling."""
        path = path or filedialog.askopenfilename(
            title="Load inputs from JSON",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            self._show_error(ValueError("inputs JSON must be an object"))
            return
        if isinstance(data.get("fields"), dict):
            fields = dict(data["fields"])
            now = data.get("now_utc_ms", fields.pop("now_utc_ms", ""))
        else:
            fields = dict(data)
            now = fields.pop("now_utc_ms", "")
        self.inputs_text.delete("1.0", "end")
        for name, value in fields.items():
            self.inputs_text.insert("end", f"{name} = {json.dumps(value)}\n")
        self.now_var.set("" if now == "" else f"{float(now):.0f}")
        self.status_var.set(f"inputs loaded: {path}")

    def _gather(self):
        """Returns (bytecode, fields, now_utc_ms) — the loaded .axbc in replay
        mode, a fresh compile of the editor otherwise."""
        fields = parse_inputs(self.inputs_text.get("1.0", "end"))
        now_raw = self.now_var.get().strip()
        now_utc_ms = float(now_raw) if now_raw else None
        if self.replay_bc is not None:
            return self.replay_bc, fields, now_utc_ms
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
