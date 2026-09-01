"""test_cowork_evidence_formatter.py -- tests for the Cowork Evidence Formatter.

Every case runs the formatter as a subprocess with a JSON payload, or calls its
pure functions directly. No network, no repository mutation, no persistent
environment change, no external dependency. File-input cases use pytest's
tmp_path, which lives outside the repository.
"""
from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FORMATTER = REPO_ROOT / "tools" / "cowork" / "evidence_formatter.py"

# A value that must never appear in stdout or stderr.
CANARY = "NOVA_3K_CANARY_9d41f7ac2be05513"

EM_DASH = "\u2014"
CP1252_EM_DASH = bytes([0x97])


def run(payload=None, fmt="markdown", raw=None, input_file=None):
    """Invoke the formatter as a subprocess. Returns (rc, stdout, stderr)."""
    cmd = [sys.executable, "-B", str(FORMATTER), "--format", fmt]
    if input_file is not None:
        cmd += ["--input", str(input_file)]
        data = b""
    else:
        text = raw if raw is not None else json.dumps(payload)
        data = text.encode("utf-8") if isinstance(text, str) else text
    p = subprocess.run(cmd, input=data, capture_output=True)
    return (p.returncode,
            p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def doc(checks=None, **extra):
    d = {
        "schema_version": 1,
        "phase": "Phase 3K",
        "scope": "evidence formatter",
        "checks": [{"id": "C1", "label": "example", "status": "pass"}]
        if checks is None else checks,
    }
    d.update(extra)
    return d


# ---------------------------------------------------------------- status logic

def test_valid_minimal_passing_document():
    rc, out, err = run(doc(), fmt="json")
    assert rc == 0, err
    assert json.loads(out)["overall_status"] == "passed"


def test_one_failed_check_makes_the_report_failed():
    rc, out, _ = run(doc([
        {"id": "A", "label": "ok", "status": "pass"},
        {"id": "B", "label": "broken", "status": "fail"},
    ]), fmt="json")
    assert rc == 0
    assert json.loads(out)["overall_status"] == "failed"


def test_stopped_takes_precedence_over_warning():
    rc, out, _ = run(doc([
        {"id": "A", "label": "w", "status": "warning"},
        {"id": "B", "label": "s", "status": "stopped"},
    ]), fmt="json")
    assert json.loads(out)["overall_status"] == "stopped"


def test_fail_takes_precedence_over_stopped():
    rc, out, _ = run(doc([
        {"id": "A", "label": "s", "status": "stopped"},
        {"id": "B", "label": "f", "status": "fail"},
    ]), fmt="json")
    assert json.loads(out)["overall_status"] == "failed"


def test_warning_yields_passed_with_warnings():
    rc, out, _ = run(doc([
        {"id": "A", "label": "p", "status": "pass"},
        {"id": "B", "label": "w", "status": "warning"},
    ]), fmt="json")
    assert json.loads(out)["overall_status"] == "passed_with_warnings"


def test_informational_only_still_passes():
    rc, out, _ = run(doc([{"id": "A", "label": "i", "status": "informational"}]),
                     fmt="json")
    assert json.loads(out)["overall_status"] == "passed"


def test_zero_checks_can_never_pass():
    rc, out, _ = run(doc([]), fmt="json")
    assert rc == 0
    assert json.loads(out)["overall_status"] == "stopped"


def test_planted_failure_is_never_reported_as_passed():
    """The load-bearing test: a caller insisting on success is ignored."""
    payload = doc([
        {"id": "A", "label": "planted failure", "status": "fail",
         "evidence": "1 assertion failed"},
    ])
    payload["notes"] = ["everything passed"]          # a false claim in prose
    rc, out, _ = run(payload, fmt="json")
    assert json.loads(out)["overall_status"] == "failed"
    _, md, _ = run(payload, fmt="markdown")
    assert "FAILED" in md
    assert "Evidence Report " + EM_DASH + " PASSED" not in md


def test_caller_supplied_success_claim_is_rejected_as_unknown_field():
    payload = doc([{"id": "A", "label": "x", "status": "fail"}])
    payload["passed"] = True
    rc, out, err = run(payload, fmt="json")
    assert rc == 2
    assert "unrecognized top-level field" in err


# ------------------------------------------------------------------ validation

def test_duplicate_check_ids_rejected():
    rc, _, err = run(doc([
        {"id": "A", "label": "one", "status": "pass"},
        {"id": "A", "label": "two", "status": "pass"},
    ]))
    assert rc == 2 and "duplicate check id" in err


def test_invalid_status_rejected():
    rc, _, err = run(doc([{"id": "A", "label": "x", "status": "green"}]))
    assert rc == 2 and "invalid check status" in err


def test_unsupported_schema_rejected():
    rc, _, err = run(doc(schema_version=2))
    assert rc == 2 and "unsupported schema_version" in err


def test_missing_required_field_rejected():
    d = doc()
    del d["scope"]
    rc, _, err = run(d)
    assert rc == 2 and "missing required field: scope" in err


def test_wrong_type_rejected():
    rc, _, err = run(doc(checks={"not": "a list"}))
    assert rc == 2 and "checks must be a list" in err


def test_wrong_numeric_type_in_tests_rejected():
    rc, _, err = run(doc(tests=[{"command": "pytest -q", "passed": "911"}]))
    assert rc == 2 and "must be an integer" in err


def test_malformed_json_rejected_without_echoing_payload():
    bad = '{"schema_version": 1, "phase": "p", ' + CANARY
    rc, out, err = run(raw=bad)
    assert rc == 2
    assert "not valid JSON" in err
    assert CANARY not in err and CANARY not in out
    assert bad not in err


def test_nan_rejected():
    rc, _, err = run(raw='{"schema_version":1,"phase":"p","scope":"s",'
                         '"checks":[],"notes":[NaN]}')
    assert rc == 2 and "non-standard numeric" in err


def test_infinity_rejected():
    rc, _, err = run(raw='{"schema_version":1,"phase":"p","scope":"s",'
                         '"checks":[],"notes":[Infinity]}')
    assert rc == 2 and "non-standard numeric" in err


def test_non_utf8_input_rejected():
    cmd = [sys.executable, "-B", str(FORMATTER), "--format", "json"]
    p = subprocess.run(cmd, input=bytes([0xFF, 0xFE, 0x00]) + b"bad",
                       capture_output=True)
    assert p.returncode == 2
    assert b"not valid UTF-8" in p.stderr


# --------------------------------------------------------------- safety limits

def test_oversized_input_rejected_with_exit_3():
    payload = json.dumps(doc(notes=["x" * 2000]))
    payload = payload[:-2] + ',"' + "y" * (1024 * 1024) + '":1}'
    rc, _, err = run(raw=payload)
    assert rc == 3 and "maximum accepted size" in err


def test_excessive_depth_rejected_with_exit_3():
    nested = cur = {}
    for _ in range(60):
        cur["n"] = {}
        cur = cur["n"]
    rc, _, err = run(doc(changes=nested))
    assert rc == 3 and "depth" in err


def test_excessive_collection_count_rejected_with_exit_3():
    rc, _, err = run(doc(notes=["n"] * 1500))
    assert rc == 3 and "maximum of" in err


# ------------------------------------------------------------------ redaction

def test_credential_key_values_redacted():
    payload = doc(changes={
        "api_key": CANARY, "token": CANARY, "password": CANARY,
        "passphrase": CANARY, "cookie": CANARY, "authorization": CANARY,
        "bearer": CANARY, "private_key": CANARY, "access_key": CANARY,
        "refresh_token": CANARY, "client_secret": CANARY, "secret": CANARY,
        "apikey": CANARY,
    })
    rc, out, err = run(payload, fmt="json")
    assert rc == 0
    assert CANARY not in out and CANARY not in err
    assert out.count("[REDACTED]") >= 13


def test_credential_format_redacted_even_under_innocent_key():
    payload = doc(notes=[
        "sk-ant-" + "a" * 30,
        "ghp_" + "b" * 20,
        "AKIA" + "C" * 16,
        "Authorization: Bearer " + CANARY,
    ])
    rc, out, err = run(payload, fmt="json")
    assert rc == 0
    for leak in ("sk-ant-aaa", "ghp_bbb", "AKIACCC", CANARY):
        assert leak not in out and leak not in err
    assert "[REDACTED]" in out


def test_environment_value_redacted():
    payload = doc(notes=["ran with MY_API_KEY=%s inline" % CANARY])
    rc, out, _ = run(payload, fmt="json")
    assert CANARY not in out and "[REDACTED]" in out


def test_authorization_header_redacted():
    payload = doc(notes=["curl -H 'Authorization: Bearer %s' https://x" % CANARY])
    rc, out, _ = run(payload, fmt="json")
    assert CANARY not in out


def test_url_query_secret_redacted():
    payload = doc(notes=["https://example.invalid/x?api_key=%s&z=1" % CANARY])
    rc, out, _ = run(payload, fmt="json")
    assert CANARY not in out


def test_canary_never_appears_anywhere():
    payload = doc(
        checks=[{"id": "A", "label": "auth", "status": "pass",
                 "evidence": "token=%s" % CANARY}],
        notes=["cookie: %s" % CANARY],
        permission_state={"secret": CANARY},
    )
    for fmt in ("markdown", "json"):
        rc, out, err = run(payload, fmt=fmt)
        assert rc == 0
        assert CANARY not in out, fmt
        assert CANARY not in err, fmt


def test_ordinary_prose_is_not_over_redacted():
    payload = doc(notes=[
        "the tokenizer split the input",
        "a secret scan found nothing",
        "credential check passed",
    ], changes={"secret_scan_status": "clean", "token_count": "12"})
    rc, out, _ = run(payload, fmt="json")
    assert "tokenizer" in out
    assert "secret scan found nothing" in out
    assert "credential check passed" in out
    assert "clean" in out and "12" in out


# ------------------------------------------------------- path normalization

def test_windows_home_path_normalized_and_username_absent():
    payload = doc(notes=[r"C:\Users\someperson\D.O.N.N.A\main.py"])
    rc, out, _ = run(payload, fmt="json")
    assert "${HOME}" in out
    assert "someperson" not in out


def test_gitbash_home_path_normalized():
    payload = doc(notes=["/c/Users/someperson/D.O.N.N.A/main.py"])
    rc, out, _ = run(payload, fmt="json")
    assert "${HOME}" in out
    assert "someperson" not in out


def test_posix_home_path_normalized():
    payload = doc(notes=["/home/someperson/project/x.py"])
    rc, out, _ = run(payload, fmt="json")
    assert "${HOME}" in out and "someperson" not in out


def test_real_username_absent_from_output():
    """Whatever this machine's user is called, it must not survive rendering."""
    user = Path.home().name
    payload = doc(notes=[str(Path.home() / "somewhere" / "file.txt")])
    rc, out, err = run(payload, fmt="json")
    assert rc == 0
    assert user not in out and user not in err


# ------------------------------------------------------------- determinism

def test_markdown_is_byte_identical_across_runs():
    payload = doc([
        {"id": "B", "label": "second", "status": "pass"},
        {"id": "A", "label": "first", "status": "warning"},
    ], tests=[{"command": "python -B -m pytest tests -q", "passed": 911,
               "failed": 2, "skipped": 13, "exit_code": 1,
               "failures": ["tests/test_a.py::test_x"]}])
    first = run(payload, fmt="markdown")[1]
    for _ in range(3):
        assert run(payload, fmt="markdown")[1] == first


def test_json_identical_when_mappings_are_logically_reordered():
    a = {"schema_version": 1, "phase": "p", "scope": "s",
         "checks": [{"id": "A", "label": "l", "status": "pass"}],
         "notes": ["n"]}
    b = {"notes": ["n"],
         "checks": [{"status": "pass", "label": "l", "id": "A"}],
         "scope": "s", "phase": "p", "schema_version": 1}
    assert run(a, fmt="json")[1] == run(b, fmt="json")[1]


def test_checks_render_in_stable_id_order():
    payload = doc([
        {"id": "C", "label": "c", "status": "pass"},
        {"id": "A", "label": "a", "status": "pass"},
        {"id": "B", "label": "b", "status": "pass"},
    ])
    ids = [c["id"] for c in json.loads(run(payload, fmt="json")[1])["checks"]]
    assert ids == ["A", "B", "C"]
    md = run(payload, fmt="markdown")[1]
    assert md.index("`A`") < md.index("`B`") < md.index("`C`")


def test_tests_render_in_stable_order():
    payload = doc(tests=[{"command": "zzz"}, {"command": "aaa"}])
    cmds = [t["command"] for t in json.loads(run(payload, fmt="json")[1])["tests"]]
    assert cmds == ["aaa", "zzz"]


def test_output_is_utf8_bytes_regardless_of_locale_encoding():
    """Output bytes must not depend on the platform's stdout codec.

    Writing through sys.stdout would encode with cp1252 on a redirected Windows
    pipe, so the em dash in the heading would differ byte-for-byte between
    machines. The formatter must emit UTF-8 explicitly.
    """
    env = dict(os.environ)
    env.pop("PYTHONIOENCODING", None)
    p = subprocess.run([sys.executable, "-B", str(FORMATTER),
                        "--format", "markdown"],
                       input=json.dumps(doc()).encode("utf-8"),
                       capture_output=True, env=env)
    assert p.returncode == 0
    text = p.stdout.decode("utf-8")            # must not raise
    assert EM_DASH in text                     # survived as UTF-8
    assert CP1252_EM_DASH not in p.stdout      # not cp1252-encoded


def test_output_bytes_stable_under_forced_locale_env():
    baseline = None
    for enc in ("utf-8", "cp1252"):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = enc
        p = subprocess.run([sys.executable, "-B", str(FORMATTER),
                            "--format", "markdown"],
                           input=json.dumps(doc()).encode("utf-8"),
                           capture_output=True, env=env)
        assert p.returncode == 0
        if baseline is None:
            baseline = p.stdout
        else:
            assert p.stdout == baseline


def test_output_ends_with_exactly_one_newline():
    for fmt in ("markdown", "json"):
        out = run(doc(), fmt=fmt)[1]
        assert out.endswith("\n")
        assert not out.endswith("\n\n")


# --------------------------------------------------------------------- CLI

def test_stdin_input_works():
    rc, out, _ = run(doc(), fmt="json")
    assert rc == 0 and json.loads(out)["phase"] == "Phase 3K"


def test_explicit_file_input_works_and_leaves_file_untouched(tmp_path):
    p = tmp_path / "evidence.json"
    p.write_text(json.dumps(doc(), indent=2), encoding="utf-8")
    before = p.read_bytes()
    rc, out, err = run(fmt="json", input_file=p)
    assert rc == 0, err
    assert p.read_bytes() == before            # input file byte-identical


def test_missing_input_file_rejected(tmp_path):
    rc, _, err = run(fmt="json", input_file=tmp_path / "nope.json")
    assert rc == 2 and "could not be read" in err


def test_no_output_file_option_exists():
    p = subprocess.run([sys.executable, "-B", str(FORMATTER), "--help"],
                       capture_output=True, text=True)
    assert p.returncode == 0
    for flag in ("--output", "--outfile", "--write"):
        assert flag not in p.stdout


def test_missing_format_is_usage_error():
    p = subprocess.run([sys.executable, "-B", str(FORMATTER)],
                       input=b"{}", capture_output=True)
    assert p.returncode == 2


def test_invalid_format_is_usage_error():
    p = subprocess.run([sys.executable, "-B", str(FORMATTER), "--format", "xml"],
                       input=b"{}", capture_output=True)
    assert p.returncode == 2


# ----------------------------------------------------- non-execution boundary

def test_command_text_is_data_and_never_executed(tmp_path):
    """A command that would create a file must not create it."""
    sentinel = tmp_path / "MUST_NOT_EXIST.txt"
    hostile = "python -c \"open(r'%s','w').write('x')\"" % sentinel
    payload = doc(tests=[{"command": hostile, "passed": 0}])
    rc, out, _ = run(payload, fmt="markdown")
    assert rc == 0
    assert not sentinel.exists()
    assert "MUST_NOT_EXIST" in out             # rendered as text only


def test_formatter_creates_no_file(tmp_path):
    before = set(os.listdir(tmp_path))
    root_before = set(os.listdir(REPO_ROOT))
    run(doc(), fmt="markdown")
    run(doc(), fmt="json")
    assert set(os.listdir(tmp_path)) == before
    assert set(os.listdir(REPO_ROOT)) == root_before


def test_source_contains_no_execution_or_network_primitives():
    """Scan executable code only.

    Comments and docstrings legitimately name the primitives the tool promises
    not to use, so they are stripped before scanning; otherwise the tool's own
    safety documentation would fail its own safety test.
    """
    src = FORMATTER.read_text(encoding="utf-8")
    tree = ast.parse(src)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            ds = ast.get_docstring(node, clean=False)
            if ds:
                docstrings.add(ds)
    kept = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING:
            try:
                value = ast.literal_eval(tok.string)
            except Exception:
                value = None
            if isinstance(value, str) and value in docstrings:
                continue
        kept.append(tok.string)
    body = "\n".join(kept)

    for forbidden in ("subprocess", "os.system", "eval(", "exec(",
                      "socket", "urllib", "requests", "httpx", "popen",
                      "shutil"):
        assert forbidden not in body, forbidden
    # The only filesystem access is the read-only input file read.
    assert body.count("open(") <= 1


def test_repository_status_unchanged_by_formatting():
    def status():
        return subprocess.run(["git", "status", "--porcelain", "-uall"],
                              cwd=REPO_ROOT, capture_output=True,
                              text=True).stdout
    before = status()
    run(doc(), fmt="markdown")
    assert status() == before


def test_stderr_never_contains_the_whole_rejected_payload():
    payload = json.dumps(doc(notes=[CANARY, "z" * 500]))
    broken = payload[:-1]                      # truncate -> malformed
    rc, out, err = run(raw=broken)
    assert rc == 2
    assert CANARY not in err
    assert broken not in err
    assert len(err) < 300


# ------------------------------------------------------------ pure functions

def _import_formatter():
    sys.path.insert(0, str(FORMATTER.parent))
    try:
        import evidence_formatter as ef
        return ef
    finally:
        sys.path.pop(0)


def test_derive_overall_precedence_directly():
    ef = _import_formatter()
    assert ef.derive_overall([]) == "stopped"
    assert ef.derive_overall([{"status": "pass"}]) == "passed"
    assert ef.derive_overall([{"status": "informational"}]) == "passed"
    assert ef.derive_overall([{"status": "warning"}]) == "passed_with_warnings"
    assert ef.derive_overall([{"status": "stopped"},
                              {"status": "warning"}]) == "stopped"
    assert ef.derive_overall([{"status": "fail"},
                              {"status": "stopped"}]) == "failed"


def test_sanitize_does_not_mutate_the_input_structure():
    ef = _import_formatter()
    original = {"token": "abc", "notes": ["/home/someone/x"]}
    snapshot = json.dumps(original, sort_keys=True)
    ef.sanitize(original)
    assert json.dumps(original, sort_keys=True) == snapshot
