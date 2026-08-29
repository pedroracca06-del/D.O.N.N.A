#!/usr/bin/env python
"""
test_nova_guard_hook.py -- synthetic harness for the DISABLED candidate hook.

Every case is a JSON payload fed to the candidate on stdin as a subprocess.
No proposed command is ever executed.

The harness builds a SYNTHETIC repository in the OS temp directory
(nova_guard_sandbox/D.O.N.N.A + a marker directory) and points every case at it. The
real NOVA repository and the real protected files are never referenced, read,
written, or stat-ed by these tests.

Run:  python test_nova_guard_hook.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "nova_guard_hook.py")

# ---------------------------------------------------------------- synthetic repo
SANDBOX = os.path.join(tempfile.gettempdir(), "nova_guard_sandbox")
ROOT_NATIVE = os.path.join(SANDBOX, "D.O.N.N.A")
COPY_NATIVE = os.path.join(SANDBOX, "D.O.N.N.A-copy")   # prefix-confusion sibling
PLAIN_NATIVE = os.path.join(SANDBOX, "unrelated-project")


def build_sandbox():
    if os.path.isdir(SANDBOX):
        shutil.rmtree(SANDBOX)
    # marker present -> counts as a NOVA checkout
    os.makedirs(os.path.join(ROOT_NATIVE, "nova_knowledge_core"))
    os.makedirs(os.path.join(ROOT_NATIVE, "services"))
    os.makedirs(os.path.join(ROOT_NATIVE, "core"))
    os.makedirs(os.path.join(ROOT_NATIVE, "tests"))
    # no marker -> must never be treated as the project root
    os.makedirs(os.path.join(COPY_NATIVE, "services"))
    os.makedirs(os.path.join(PLAIN_NATIVE, "services"))


def posix(p):
    return p.replace("\\", "/")


def gitbash(p):
    p = posix(p)
    return "/" + p[0].lower() + p[2:] if re.match(r"^[A-Za-z]:/", p) else p


ROOT = posix(ROOT_NATIVE)
ROOT_SUB = ROOT + "/services"
COPY = posix(COPY_NATIVE)
PLAIN = posix(PLAIN_NATIVE)

ALLOW, DENY = "allow", "deny"


def run(payload, raw=None, env_root="__default__"):
    """Return (decision, exit_code, stdout, stderr). 'allow' == hook stayed silent."""
    data = raw if raw is not None else json.dumps(payload)
    env = dict(os.environ)
    if env_root == "__default__":
        env["CLAUDE_PROJECT_DIR"] = ROOT_NATIVE
    elif env_root is None:
        env.pop("CLAUDE_PROJECT_DIR", None)
    else:
        env["CLAUDE_PROJECT_DIR"] = env_root
    p = subprocess.run([sys.executable, HOOK], input=data,
                       capture_output=True, text=True, env=env)
    if p.returncode == 0 and not p.stdout.strip():
        return ALLOW, 0, p.stdout, p.stderr
    try:
        d = json.loads(p.stdout)
        return d["hookSpecificOutput"]["permissionDecision"], p.returncode, p.stdout, p.stderr
    except Exception:
        return "malformed-output", p.returncode, p.stdout, p.stderr


def edit(tool, path, cwd=None, **extra):
    ti = dict(extra)
    if tool == "NotebookEdit":
        ti["notebook_path"] = path
    elif tool == "MultiEdit":
        ti["edits"] = [{"file_path": path, "old_string": "a", "new_string": "b"}]
    else:
        ti["file_path"] = path
    return {"hook_event_name": "PreToolUse", "tool_name": tool,
            "cwd": cwd or ROOT, "tool_input": ti}


def sh(command, tool="Bash", cwd=None):
    return {"hook_event_name": "PreToolUse", "tool_name": tool,
            "cwd": cwd or ROOT, "tool_input": {"command": command}}


def cases():
    """(group, name, payload, expected, env_root)"""
    D = "__default__"
    C = []
    a = lambda g, n, p, e, env=D: C.append((g, n, p, e, env))

    # ---- safe / allowed --------------------------------------------------
    a("safe", "read protected file",           edit("Read", r"services\execution.py"), ALLOW)
    a("safe", "edit unrelated source",         edit("Edit", r"engines\reasoning.py"), ALLOW)
    a("safe", "edit similarly named file",     edit("Edit", r"services\execution_notes.py"), ALLOW)
    a("safe", "grep protected file",           sh("grep -n NOVA_TRADING services/execution.py"), ALLOW)
    a("safe", "cat protected file",            sh("cat services/execution.py"), ALLOW)
    a("safe", "sed -n range read",             sh("sed -n '1,50p' services/execution.py"), ALLOW)
    a("safe", "git diff protected file",       sh("git diff services/execution.py"), ALLOW)
    a("safe", "git show protected file",       sh("git show HEAD:core/config.py"), ALLOW)
    a("safe", "pytest collection w/ conftest", sh("python -m pytest tests/conftest.py --collect-only"), ALLOW)
    a("safe", "pytest whole suite",            sh("python -m pytest tests -q"), ALLOW)
    a("safe", "ast syntax inspection",         sh("python -c \"import ast; ast.parse(open('core/config.py').read())\""), ALLOW)
    a("safe", "wc -l on protected file",       sh("wc -l services/execution_bridge.py"), ALLOW)
    a("safe", "redirect unrelated file",       sh("echo hi > notes.txt"), ALLOW)
    a("safe", "rm unrelated file",             sh("rm scratch.txt"), ALLOW)
    a("safe", "flag set to false",             sh("export NOVA_TRADING_SUBSYSTEM_ENABLED=false"), ALLOW)
    a("safe", "auto-execute set to false",     sh("NOVA_AUTO_EXECUTE=false python -m pytest tests -q"), ALLOW)
    a("safe", "ps flag read only",             sh("$env:NOVA_AUTO_EXECUTE", tool="PowerShell"), ALLOW)
    a("safe", "grep output to /dev/null",      sh("grep -c x services/execution.py > /dev/null"), ALLOW)

    # ---- blocked file-edit tools -----------------------------------------
    a("edit", "Edit windows relative",         edit("Edit", r"services\execution.py"), DENY)
    a("edit", "Edit posix relative",           edit("Edit", "services/execution.py"), DENY)
    a("edit", "Edit dot-slash",                edit("Edit", "./services/execution_bridge.py"), DENY)
    a("edit", "Edit absolute windows",         edit("Edit", ROOT_NATIVE + r"\core\config.py"), DENY)
    a("edit", "Edit absolute posix",           edit("Edit", ROOT + "/core/config.py"), DENY)
    a("edit", "Edit git-bash drive form",      edit("Edit", gitbash(ROOT) + "/tests/conftest.py"), DENY)
    a("edit", "Edit mixed case drive",         edit("Edit", (ROOT_NATIVE + r"\services\EXECUTION.PY").upper()), DENY)
    a("edit", "Edit quoted path",              edit("Edit", '"services/execution_request.py"'), DENY)
    a("edit", "Edit traversal form",           edit("Edit", "services/../services/execution_reconcile.py"), DENY)
    a("edit", "Edit from subdirectory cwd",    edit("Edit", "execution.py", cwd=ROOT_SUB), DENY)
    a("edit", "Write to protected file",       edit("Write", r"services\execution.py", content="x"), DENY)
    a("edit", "MultiEdit protected file",      edit("MultiEdit", "core/config.py"), DENY)
    a("edit", "NotebookEdit protected path",   edit("NotebookEdit", "tests/conftest.py"), DENY)

    # ---- blocked shell mutations -----------------------------------------
    a("shell", "redirect overwrite",           sh("echo '' > services/execution.py"), DENY)
    a("shell", "redirect append",              sh("echo x >> core/config.py"), DENY)
    a("shell", "sed in-place",                 sh("sed -i 's/False/True/' services/execution.py"), DENY)
    a("shell", "perl in-place",                sh("perl -pi -e 's/a/b/' core/config.py"), DENY)
    a("shell", "patch",                        sh("patch services/execution_bridge.py < fix.diff"), DENY)
    a("shell", "git apply",                    sh("git apply revert.patch services/execution.py"), DENY)
    a("shell", "git restore",                  sh("git restore services/execution_request.py"), DENY)
    a("shell", "git checkout of path",         sh("git checkout -- services/execution_reconcile.py"), DENY)
    a("shell", "rm protected file",            sh("rm services/execution.py"), DENY)
    a("shell", "mv over protected file",       sh("mv patched.py services/execution.py"), DENY)
    a("shell", "tee into protected file",      sh("echo x | tee core/config.py"), DENY)
    a("shell", "python open-for-write",        sh("python -c \"open('services/execution.py','w').write('')\""), DENY)
    a("shell", "python pathlib write_text",    sh("python -c \"import pathlib; pathlib.Path('core/config.py').write_text('x')\""), DENY)
    a("shell", "node fs.writeFileSync",        sh("node -e \"require('fs').writeFileSync('services/execution.py','')\""), DENY)
    a("shell", "quoted windows path write",    sh('sed -i s/a/b/ "%s"' % (ROOT_NATIVE + r"\services\execution.py")), DENY)

    # ---- blocked PowerShell mutations ------------------------------------
    a("ps", "Set-Content",                     sh("Set-Content -Path services/execution.py -Value ''", tool="PowerShell"), DENY)
    a("ps", "Out-File",                        sh("'x' | Out-File core/config.py", tool="PowerShell"), DENY)
    a("ps", "Remove-Item",                     sh("Remove-Item tests/conftest.py", tool="PowerShell"), DENY)
    a("ps", "Copy-Item over target",           sh("Copy-Item patched.py services/execution.py", tool="PowerShell"), DENY)
    a("ps", "Move-Item over target",           sh("Move-Item a.py services/execution_bridge.py", tool="PowerShell"), DENY)

    # ---- guarded trading flags -------------------------------------------
    a("flag", "bash export true",              sh("export NOVA_TRADING_SUBSYSTEM_ENABLED=true"), DENY)
    a("flag", "bash inline True",              sh("NOVA_TRADING_SUBSYSTEM_ENABLED=True python main.py"), DENY)
    a("flag", "bash auto-execute true",        sh("NOVA_AUTO_EXECUTE=true python -m uvicorn main:app"), DENY)
    a("flag", "bash truthy 1",                 sh("export NOVA_AUTO_EXECUTE=1"), DENY)
    a("flag", "bash quoted true",              sh('export NOVA_TRADING_SUBSYSTEM_ENABLED="true"'), DENY)
    a("flag", "powershell env assign",         sh('$env:NOVA_TRADING_SUBSYSTEM_ENABLED = "true"', tool="PowerShell"), DENY)
    a("flag", "powershell auto-execute on",    sh("$env:NOVA_AUTO_EXECUTE = 'on'", tool="PowerShell"), DENY)
    a("flag", "setx persistence",              sh("setx NOVA_AUTO_EXECUTE true", tool="PowerShell"), DENY)

    # ---- scope -----------------------------------------------------------
    a("scope", "unrelated repo edit",          edit("Edit", "services/execution.py", cwd=PLAIN), ALLOW, PLAIN_NATIVE)
    a("scope", "unrelated repo sed in-place",  sh("sed -i s/a/b/ services/execution.py", cwd=PLAIN), ALLOW, PLAIN_NATIVE)
    a("scope", "unrelated repo flag true",     sh("export NOVA_AUTO_EXECUTE=true", cwd=PLAIN), ALLOW, PLAIN_NATIVE)
    a("scope", "project path, foreign cwd",    edit("Edit", ROOT + "/services/execution.py", cwd=PLAIN), ALLOW, PLAIN_NATIVE)
    a("scope", "missing cwd field",            {"hook_event_name": "PreToolUse", "tool_name": "Edit",
                                                "tool_input": {"file_path": "services/execution.py"}}, ALLOW)

    # ---- NEW: project-root resolution ------------------------------------
    a("root", "missing env, cwd in repo",      edit("Edit", "services/execution.py"), DENY, None)
    a("root", "missing env, cwd in subdir",    edit("Edit", "execution.py", cwd=ROOT_SUB), DENY, None)
    a("root", "missing env, cwd outside repo", edit("Edit", "services/execution.py", cwd=PLAIN), ALLOW, None)
    a("root", "empty env, cwd in repo",        edit("Edit", "services/execution.py"), DENY, "")
    a("root", "relative env, cwd in repo",     edit("Edit", "services/execution.py"), DENY, "..\\relative\\path")
    a("root", "relative env, cwd outside",     edit("Edit", "services/execution.py", cwd=PLAIN), ALLOW, "..\\relative\\path")
    a("root", "nonexistent env, cwd in repo",  edit("Edit", "services/execution.py"), DENY, ROOT_NATIVE + "-does-not-exist")
    a("root", "junk env, cwd in repo",         edit("Edit", "services/execution.py"), DENY, "???*|<>")
    a("root", "env without NOVA marker",       edit("Edit", "services/execution.py", cwd=PLAIN), ALLOW, PLAIN_NATIVE)
    a("root", "env quoted path",               edit("Edit", "services/execution.py"), DENY, '"%s"' % ROOT_NATIVE)

    # ---- NEW: prefix confusion -------------------------------------------
    a("prefix", "sibling -copy cwd, edit",     edit("Edit", "services/execution.py", cwd=COPY), ALLOW)
    a("prefix", "sibling -copy cwd, sed",      sh("sed -i s/a/b/ services/execution.py", cwd=COPY), ALLOW)
    a("prefix", "sibling -copy cwd, flag",     sh("export NOVA_AUTO_EXECUTE=true", cwd=COPY), ALLOW)
    a("prefix", "sibling -copy absolute path", edit("Edit", COPY + "/services/execution.py"), ALLOW)
    a("prefix", "sibling as env root",         edit("Edit", "services/execution.py", cwd=COPY), ALLOW, COPY_NATIVE)

    # ---- NEW: mixed-case Windows paths -----------------------------------
    a("case", "upper cwd, relative path",      edit("Edit", "services/execution.py", cwd=ROOT.upper()), DENY)
    a("case", "upper env root",                edit("Edit", "services/execution.py"), DENY, ROOT_NATIVE.upper())
    a("case", "upper absolute file path",      edit("Edit", (ROOT + "/SERVICES/EXECUTION.PY")), DENY)
    a("case", "upper shell path in command",   sh("sed -i s/a/b/ %s" % (ROOT + "/SERVICES/EXECUTION.PY").upper()), DENY)

    return C


MALFORMED = [
    ("malformed", "empty stdin", ""),
    ("malformed", "not json", "this is not json"),
    ("malformed", "truncated json", '{"tool_name": "Edit", "cwd":'),
    ("malformed", "json array not object", "[1,2,3]"),
    ("malformed", "json null", "null"),
    ("malformed", "tool_input not object", '{"tool_name":"Edit","cwd":"%s","tool_input":"x"}' % ROOT),
    ("malformed", "cwd not a string", '{"tool_name":"Edit","cwd":123,"tool_input":{"file_path":"a.py"}}'),
]

# Secret-shaped strings that must never be echoed back by the hook.
SECRET = "sk-live-SHOULD-NEVER-APPEAR-9999"


def main():
    build_sandbox()
    rows, failures = [], 0

    for group, name, payload, expected, env_root in cases():
        got, code, out, err = run(payload, env_root=env_root)
        ok = got == expected
        if expected == DENY:
            ok = ok and code == 2          # exit-2 blocking contract
        rows.append((group, name, expected, got, code, ok))
        failures += (not ok)

    for group, name, raw in MALFORMED:
        got, code, out, err = run(None, raw=raw)
        ok = got == ALLOW and code == 0
        rows.append((group, name, "no-decision", got, code, ok))
        failures += (not ok)

    # ---- exit-2 stderr contract ------------------------------------------
    got, code, out, err = run(edit("Edit", "services/execution.py"))
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    for label, cond in (
        ("exit code is 2", code == 2),
        ("stdout is valid deny JSON", got == DENY),
        ("stderr is non-empty", bool(err.strip())),
        ("stderr equals the JSON reason", err.strip() == reason.strip()),
        ("reason names the protected relpath", "services/execution.py" in reason),
        ("reason length is short (<400)", len(reason) < 400),
    ):
        rows.append(("exit2", label, "pass", "pass" if cond else "fail", code, cond))
        failures += (not cond)

    # ---- no command / secret text leaks ----------------------------------
    leaky_cmd = ("sed -i 's/x/y/' services/execution.py "
                 "&& export ALPACA_SECRET_KEY=%s" % SECRET)
    got, code, out, err = run(sh(leaky_cmd))
    blob = out + err
    leak_checks = (
        ("blocks the leaky command", got == DENY and code == 2),
        ("secret value absent from output", SECRET not in blob),
        ("full command absent from output", leaky_cmd not in blob),
        ("no 'sed -i' fragment echoed", "sed -i" not in blob),
        ("no env var name+value echoed", "ALPACA_SECRET_KEY=" not in blob),
    )
    for label, cond in leak_checks:
        rows.append(("noleak", label, "pass", "pass" if cond else "fail", code, cond))
        failures += (not cond)

    # flag-block path must not echo the value either
    got, code, out, err = run(sh("export NOVA_AUTO_EXECUTE=true && echo %s" % SECRET))
    blob = out + err
    for label, cond in (
        ("flag block emitted", got == DENY and code == 2),
        ("secret absent from flag-block output", SECRET not in blob),
        ("flag name present, value not", "NOVA_AUTO_EXECUTE" in blob and "=true" not in blob),
    ):
        rows.append(("noleak", label, "pass", "pass" if cond else "fail", code, cond))
        failures += (not cond)

    width = max(len(r[1]) for r in rows) + 2
    cur = None
    for group, name, exp, got, code, ok in rows:
        if group != cur:
            print("\n--- %s ---" % group)
            cur = group
        print("  %-4s %-*s expected=%-11s got=%-11s exit=%s" %
              ("PASS" if ok else "FAIL", width, name, exp, got, code))

    print("\n%d checks, %d passed, %d failed" % (len(rows), len(rows) - failures, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
