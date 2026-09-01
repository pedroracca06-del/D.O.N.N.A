#!/usr/bin/env python
"""
test_nova_guard_hook.py -- PHASE 2J candidate harness.

Every case is a JSON payload fed to the candidate hook on stdin as a subprocess.
No proposed command is ever executed.

The harness builds a SYNTHETIC repository in the OS temp directory
(nova_guard_sandbox/D.O.N.N.A + a marker directory) and points every case at it.
The real NOVA repository and the real protected files are never referenced.

Groups:
  safe/edit/shell/ps/flag/scope/root/prefix/case/malformed/exit2/noleak
      -- the 104 checks inherited from commit ee91955, unchanged
  h1/h2/h3/m1/m2/m3/m4
      -- Phase 2I findings, each with negative controls
  config
      -- settings.json wiring assertions (Phase 2I L-3)

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
# The harness lives in <project>/.claude/hooks/ once installed, so the settings
# file it must assert against is one directory up. Resolved from the harness
# location only -- never from the working directory, an absolute repo path, or
# an environment variable.
CLAUDE_DIR = os.path.normpath(os.path.join(HERE, os.pardir))
SETTINGS = os.path.join(CLAUDE_DIR, "settings.json")

SANDBOX = os.path.join(tempfile.gettempdir(), "nova_guard_sandbox_2j")
ROOT_NATIVE = os.path.join(SANDBOX, "D.O.N.N.A")
COPY_NATIVE = os.path.join(SANDBOX, "D.O.N.N.A-copy")
PLAIN_NATIVE = os.path.join(SANDBOX, "unrelated-project")


def build_sandbox():
    if os.path.isdir(SANDBOX):
        shutil.rmtree(SANDBOX)
    os.makedirs(os.path.join(ROOT_NATIVE, "nova_knowledge_core"))
    for d in ("services", "core", "tests", "engines"):
        os.makedirs(os.path.join(ROOT_NATIVE, d))
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

# Real kill-switch text, copied read-only from main.py:2268 and monitor.py:307.
MAIN_GUARD_OLD = "    if not NOVA_TRADING_SUBSYSTEM_ENABLED:\n        return {'status': 'TRADING_SUBSYSTEM_DISABLED', 'positions_closed': 0}"
MAIN_GUARD_NEW = "    n = await asyncio.to_thread(close_all_positions_eod)"
MON_GUARD_OLD = "    if os.getenv('NOVA_TRADING_SUBSYSTEM_ENABLED', 'false').strip().lower() != 'true':"


def run(payload, raw=None, env_root="__default__"):
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
        ti.setdefault("edits", [{"file_path": path, "old_string": "a", "new_string": "b"}])
    else:
        ti["file_path"] = path
    return {"hook_event_name": "PreToolUse", "tool_name": tool,
            "cwd": cwd or ROOT, "tool_input": ti}


def sh(command, tool="Bash", cwd=None):
    return {"hook_event_name": "PreToolUse", "tool_name": tool,
            "cwd": cwd or ROOT, "tool_input": {"command": command}}


def cases():
    D = "__default__"
    C = []
    a = lambda g, n, p, e, env=D: C.append((g, n, p, e, env))

    # ================= inherited 104 =================
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

    a("ps", "Set-Content",                     sh("Set-Content -Path services/execution.py -Value ''", tool="PowerShell"), DENY)
    a("ps", "Out-File",                        sh("'x' | Out-File core/config.py", tool="PowerShell"), DENY)
    a("ps", "Remove-Item",                     sh("Remove-Item tests/conftest.py", tool="PowerShell"), DENY)
    a("ps", "Copy-Item over target",           sh("Copy-Item patched.py services/execution.py", tool="PowerShell"), DENY)
    a("ps", "Move-Item over target",           sh("Move-Item a.py services/execution_bridge.py", tool="PowerShell"), DENY)

    a("flag", "bash export true",              sh("export NOVA_TRADING_SUBSYSTEM_ENABLED=true"), DENY)
    a("flag", "bash inline True",              sh("NOVA_TRADING_SUBSYSTEM_ENABLED=True python main.py"), DENY)
    a("flag", "bash auto-execute true",        sh("NOVA_AUTO_EXECUTE=true python -m uvicorn main:app"), DENY)
    a("flag", "bash truthy 1",                 sh("export NOVA_AUTO_EXECUTE=1"), DENY)
    a("flag", "bash quoted true",              sh('export NOVA_TRADING_SUBSYSTEM_ENABLED="true"'), DENY)
    a("flag", "powershell env assign",         sh('$env:NOVA_TRADING_SUBSYSTEM_ENABLED = "true"', tool="PowerShell"), DENY)
    a("flag", "powershell auto-execute on",    sh("$env:NOVA_AUTO_EXECUTE = 'on'", tool="PowerShell"), DENY)
    a("flag", "setx persistence",              sh("setx NOVA_AUTO_EXECUTE true", tool="PowerShell"), DENY)

    a("scope", "unrelated repo edit",          edit("Edit", "services/execution.py", cwd=PLAIN), ALLOW, PLAIN_NATIVE)
    a("scope", "unrelated repo sed in-place",  sh("sed -i s/a/b/ services/execution.py", cwd=PLAIN), ALLOW, PLAIN_NATIVE)
    a("scope", "unrelated repo flag true",     sh("export NOVA_AUTO_EXECUTE=true", cwd=PLAIN), ALLOW, PLAIN_NATIVE)
    a("scope", "project path, foreign cwd",    edit("Edit", ROOT + "/services/execution.py", cwd=PLAIN), ALLOW, PLAIN_NATIVE)
    a("scope", "missing cwd field",            {"hook_event_name": "PreToolUse", "tool_name": "Edit",
                                                "tool_input": {"file_path": "services/execution.py"}}, ALLOW)

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

    a("prefix", "sibling -copy cwd, edit",     edit("Edit", "services/execution.py", cwd=COPY), ALLOW)
    a("prefix", "sibling -copy cwd, sed",      sh("sed -i s/a/b/ services/execution.py", cwd=COPY), ALLOW)
    a("prefix", "sibling -copy cwd, flag",     sh("export NOVA_AUTO_EXECUTE=true", cwd=COPY), ALLOW)
    a("prefix", "sibling -copy absolute path", edit("Edit", COPY + "/services/execution.py"), ALLOW)
    a("prefix", "sibling as env root",         edit("Edit", "services/execution.py", cwd=COPY), ALLOW, COPY_NATIVE)

    a("case", "upper cwd, relative path",      edit("Edit", "services/execution.py", cwd=ROOT.upper()), DENY)
    a("case", "upper env root",                edit("Edit", "services/execution.py"), DENY, ROOT_NATIVE.upper())
    a("case", "upper absolute file path",      edit("Edit", (ROOT + "/SERVICES/EXECUTION.PY")), DENY)
    a("case", "upper shell path in command",   sh("sed -i s/a/b/ %s" % (ROOT + "/SERVICES/EXECUTION.PY").upper()), DENY)

    # ================= H-1 : directory-changing commands =================
    a("h1", "cd core && sed -i config.py",     sh("cd core && sed -i 's/False/True/' config.py"), DENY)
    a("h1", "cd services; sed -i execution",   sh("cd services; sed -i s/a/b/ execution.py"), DENY)
    a("h1", "pushd services && sed -i",        sh("pushd services && sed -i s/a/b/ execution.py"), DENY)
    a("h1", "cd tests && rm conftest.py",      sh("cd tests && rm conftest.py"), DENY)
    a("h1", "cd core && redirect into config", sh("cd core && echo x > config.py"), DENY)
    a("h1", "quoted cd target",                sh('cd "services" && sed -i s/a/b/ execution.py'), DENY)
    a("h1", "two hops cd .. then into core",   sh("cd services && cd ../core && sed -i s/a/b/ config.py"), DENY)
    a("h1", "PS Set-Location core; Set-Content", sh("Set-Location core; Set-Content -Path config.py -Value ''", tool="PowerShell"), DENY)
    a("h1", "PS cd services; Remove-Item",     sh("cd services; Remove-Item execution.py", tool="PowerShell"), DENY)
    a("h1", "PS sl services; Set-Content",     sh("sl services; Set-Content -Path execution.py -Value ''", tool="PowerShell"), DENY)
    # negative controls
    a("h1", "NEG cd elsewhere, mutate other",  sh("cd engines && sed -i s/a/b/ reasoning.py"), ALLOW)
    a("h1", "NEG cd core, read config",        sh("cd core && grep -n FLAG config.py"), ALLOW)
    a("h1", "NEG cd core then back out",       sh("cd core && cd .. && sed -i s/a/b/ engines/reasoning.py"), ALLOW)
    a("h1", "NEG cd services, sed -n read",    sh("cd services && sed -n '1,5p' execution.py"), ALLOW)

    # ================= H-2 : main.py / monitor.py two-tier =================
    a("h2", "unrelated Edit in main.py",       edit("Edit", "main.py", old_string="def health():", new_string="def health_v2():"), ALLOW)
    a("h2", "unrelated Edit in monitor.py",    edit("Edit", "monitor.py", old_string="poll_interval = 60", new_string="poll_interval = 30"), ALLOW)
    a("h2", "Edit removing main kill switch",  edit("Edit", "main.py", old_string=MAIN_GUARD_OLD, new_string=MAIN_GUARD_NEW), DENY)
    a("h2", "Edit inserting flag into main",   edit("Edit", "main.py", old_string="x = 1", new_string="NOVA_AUTO_EXECUTE = True"), DENY)
    a("h2", "Edit removing monitor guard",     edit("Edit", "monitor.py", old_string=MON_GUARD_OLD, new_string="    if True:"), DENY)
    a("h2", "MultiEdit touching guard",        edit("MultiEdit", "main.py", edits=[
        {"file_path": "main.py", "old_string": "a", "new_string": "b"},
        {"file_path": "main.py", "old_string": MAIN_GUARD_OLD, "new_string": "pass"}]), DENY)
    a("h2", "MultiEdit unrelated only",        edit("MultiEdit", "main.py", edits=[
        {"file_path": "main.py", "old_string": "a", "new_string": "b"}]), ALLOW)
    a("h2", "full Write of main.py",           edit("Write", "main.py", content="print('x')"), DENY)
    a("h2", "full Write of monitor.py",        edit("Write", "monitor.py", content="print('x')"), DENY)
    a("h2", "NotebookEdit of main.py",         edit("NotebookEdit", "main.py"), DENY)
    a("h2", "shell sed -i on main.py",         sh("sed -i 's/False/True/' main.py"), DENY)
    a("h2", "shell redirect into main.py",     sh("echo x > main.py"), DENY)
    a("h2", "shell rm monitor.py",             sh("rm monitor.py"), DENY)
    a("h2", "PS Set-Content main.py",          sh("Set-Content -Path main.py -Value ''", tool="PowerShell"), DENY)
    a("h2", "cd-then-mutate main.py",          sh("cd . && sed -i s/a/b/ main.py"), DENY)
    # negative controls
    a("h2", "read main.py",                    sh("cat main.py"), ALLOW)
    a("h2", "grep main.py",                    sh("grep -n NOVA_TRADING_SUBSYSTEM_ENABLED main.py"), ALLOW)
    a("h2", "git diff main.py",                sh("git diff main.py"), ALLOW)
    a("h2", "pytest referencing main",         sh("python -m pytest tests -q -k main"), ALLOW)
    a("h2", "copy main.py OUT as backup",      sh("cp main.py /tmp/main_backup.py"), ALLOW)

    # ================= H-3 : redirect destination =================
    a("h3", "grep protected -> notes.txt",     sh("grep -n NOVA services/execution.py > notes.txt"), ALLOW)
    a("h3", "pytest conftest -> results.txt",  sh("python -m pytest tests/conftest.py -q > results.txt"), ALLOW)
    a("h3", "diff two protected -> d.txt",     sh("diff services/execution.py services/execution_bridge.py > d.txt"), ALLOW)
    a("h3", "append read output elsewhere",    sh("sed -n '1,5p' core/config.py >> log.txt"), ALLOW)
    a("h3", "stderr redirect only",            sh("grep x services/execution.py 2> err.txt"), ALLOW)
    a("h3", "redirect INTO protected",         sh("grep x foo.txt > services/execution.py"), DENY)
    a("h3", "append INTO protected",           sh("cat notes.txt >> core/config.py"), DENY)
    a("h3", "quoted redirect INTO protected",  sh('echo x > "services/execution.py"'), DENY)

    # ================= M-1 : flag assignment context =================
    a("m1", "quoted doc mention in echo",      sh('echo "the retired default is NOVA_AUTO_EXECUTE=true" >> notes.md'), ALLOW)
    a("m1", "quoted doc mention, single q",    sh("echo 'set NOVA_TRADING_SUBSYSTEM_ENABLED=true to re-enable' > doc.md"), ALLOW)
    a("m1", "PS Write-Output quoted mention",  sh('Write-Output "NOVA_AUTO_EXECUTE=true is the retired default"', tool="PowerShell"), ALLOW)
    a("m1", "grep for the flag literal",       sh("grep -rn 'NOVA_AUTO_EXECUTE=true' docs/"), ALLOW)
    a("m1", "real export still denied",        sh("export NOVA_AUTO_EXECUTE=true"), DENY)
    a("m1", "real inline assignment denied",   sh("NOVA_AUTO_EXECUTE=true python x.py"), DENY)
    a("m1", "python os.environ assignment",    sh("python -c \"import os; os.environ['NOVA_AUTO_EXECUTE']='true'\""), DENY)
    a("m1", "node process.env assignment",     sh("node -e \"process.env.NOVA_AUTO_EXECUTE='true'\""), DENY)
    a("m1", "env VAR=true prefix",             sh("env NOVA_TRADING_SUBSYSTEM_ENABLED=true python x.py"), DENY)

    # ================= M-2 : Windows persistence =================
    a("m2", "Environment::SetEnvironmentVariable", sh('[Environment]::SetEnvironmentVariable("NOVA_AUTO_EXECUTE","true","User")', tool="PowerShell"), DENY)
    a("m2", "System.Environment:: form",       sh('[System.Environment]::SetEnvironmentVariable("NOVA_TRADING_SUBSYSTEM_ENABLED","1","Machine")', tool="PowerShell"), DENY)
    a("m2", "Set-Item Env: form",              sh('Set-Item -Path Env:NOVA_AUTO_EXECUTE -Value "true"', tool="PowerShell"), DENY)
    a("m2", "NEG SetEnvironmentVariable false", sh('[Environment]::SetEnvironmentVariable("NOVA_AUTO_EXECUTE","false","User")', tool="PowerShell"), ALLOW)
    a("m2", "NEG SetEnvironmentVariable 0",    sh('[System.Environment]::SetEnvironmentVariable("NOVA_TRADING_SUBSYSTEM_ENABLED","0","Machine")', tool="PowerShell"), ALLOW)
    a("m2", "NEG Set-Item Env: off",           sh('Set-Item -Path Env:NOVA_AUTO_EXECUTE -Value "off"', tool="PowerShell"), ALLOW)
    a("m2", "NEG $env: disabled",              sh("$env:NOVA_AUTO_EXECUTE = 'disabled'", tool="PowerShell"), ALLOW)

    # ================= M-3 : copy direction =================
    a("m3", "cp protected -> backup",          sh("cp services/execution.py /tmp/backup.py"), ALLOW)
    a("m3", "Copy-Item protected -> temp",     sh(r"Copy-Item services/execution.py C:\Temp\backup.py", tool="PowerShell"), ALLOW)
    a("m3", "cp INTO protected",               sh("cp patched.py services/execution.py"), DENY)
    a("m3", "Copy-Item INTO protected",        sh(r"Copy-Item C:\Temp\patched.py services/execution.py", tool="PowerShell"), DENY)
    a("m3", "Copy-Item -Destination protected", sh("Copy-Item -Path a.py -Destination core/config.py", tool="PowerShell"), DENY)
    a("m3", "mv protected away is denied",     sh("mv services/execution.py /tmp/gone.py"), DENY)

    # ================= M-4 : narrow writer matching =================
    a("m4", "stdout.write of protected read",  sh("python -c \"import sys; sys.stdout.write(open('services/execution.py').read())\""), ALLOW)
    a("m4", "mkdir while naming protected",    sh("mkdir -p out && echo services/execution.py"), ALLOW)
    a("m4", "node console.log of read",        sh("node -e \"console.log(require('fs').readFileSync('services/execution.py','utf8'))\""), ALLOW)
    a("m4", "python del statement",            sh("python -c \"x=1; del x; print(open('core/config.py').read())\""), ALLOW)
    a("m4", "os.mkdir unrelated",              sh("python -c \"import os; os.mkdir('out'); print('core/config.py')\""), ALLOW)
    a("m4", "shutil.copy INTO protected",      sh("python -c \"import shutil; shutil.copy('a.py','services/execution.py')\""), DENY)
    a("m4", "shutil.copy FROM protected",      sh("python -c \"import shutil; shutil.copy('services/execution.py','/tmp/b.py')\""), ALLOW)
    a("m4", "os.replace onto protected",       sh("python -c \"import os; os.replace('a.py','core/config.py')\""), DENY)
    a("m4", "fs.appendFile onto protected",    sh("node -e \"require('fs').appendFileSync('core/config.py','x')\""), DENY)
    a("m4", "quoted data mention, no mutation", sh("python -c \"PROT=['services/execution.py']; RISKY={'git restore': 1}; print(len(PROT), len(RISKY))\""), ALLOW)

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

SECRET = "sk-live-SHOULD-NEVER-APPEAR-9999"
EXPECTED_TOOLS = ["Edit", "Write", "NotebookEdit", "MultiEdit", "Bash", "PowerShell"]


def config_checks(rows):
    """Phase 2I L-3: assert the candidate settings.json wires the hook correctly."""
    fails = 0

    def chk(label, cond):
        nonlocal fails
        rows.append(("config", label, "pass", "pass" if cond else "fail", 0, cond))
        fails += (not cond)

    try:
        cfg = json.load(open(SETTINGS, encoding="utf-8"))
        ok = True
    except Exception:
        cfg, ok = {}, False
    chk("settings.json parses", ok)
    hooks = cfg.get("hooks", {})
    pre = hooks.get("PreToolUse")
    chk("PreToolUse exists", isinstance(pre, list) and len(pre) == 1)
    entry = pre[0] if isinstance(pre, list) and pre else {}
    matcher = entry.get("matcher", "")
    chk("matcher contains exactly the six expected tools",
        sorted(matcher.split("|")) == sorted(EXPECTED_TOOLS))
    handlers = entry.get("hooks", [])
    h = handlers[0] if handlers else {}
    chk("exactly one handler", len(handlers) == 1)
    chk("handler type is command", h.get("type") == "command")
    chk("command is python", h.get("command") == "python")
    chk("args point at the hook under CLAUDE_PROJECT_DIR",
        h.get("args") == ["${CLAUDE_PROJECT_DIR}/.claude/hooks/nova_guard_hook.py"])
    chk("timeout is 10", h.get("timeout") == 10)
    chk("mcpServers still present", "mcpServers" in cfg)
    chk("mcpServers tradingview intact",
        cfg.get("mcpServers", {}).get("tradingview", {}).get("args") == ["src/server.js"])
    return fails


def main():
    build_sandbox()
    rows, failures = [], 0

    for group, name, payload, expected, env_root in cases():
        got, code, out, err = run(payload, env_root=env_root)
        ok = got == expected
        if expected == DENY:
            ok = ok and code == 2
        rows.append((group, name, expected, got, code, ok))
        failures += (not ok)

    for group, name, raw in MALFORMED:
        got, code, out, err = run(None, raw=raw)
        ok = got == ALLOW and code == 0
        rows.append((group, name, "no-decision", got, code, ok))
        failures += (not ok)

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

    leaky_cmd = ("sed -i 's/x/y/' services/execution.py "
                 "&& export ALPACA_SECRET_KEY=%s" % SECRET)
    got, code, out, err = run(sh(leaky_cmd))
    blob = out + err
    for label, cond in (
        ("blocks the leaky command", got == DENY and code == 2),
        ("secret value absent from output", SECRET not in blob),
        ("full command absent from output", leaky_cmd not in blob),
        ("no 'sed -i' fragment echoed", "sed -i" not in blob),
        ("no env var name+value echoed", "ALPACA_SECRET_KEY=" not in blob),
    ):
        rows.append(("noleak", label, "pass", "pass" if cond else "fail", code, cond))
        failures += (not cond)

    got, code, out, err = run(sh("export NOVA_AUTO_EXECUTE=true && echo %s" % SECRET))
    blob = out + err
    for label, cond in (
        ("flag block emitted", got == DENY and code == 2),
        ("secret absent from flag-block output", SECRET not in blob),
        ("flag name present, value not", "NOVA_AUTO_EXECUTE" in blob and "=true" not in blob),
    ):
        rows.append(("noleak", label, "pass", "pass" if cond else "fail", code, cond))
        failures += (not cond)

    failures += config_checks(rows)

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
