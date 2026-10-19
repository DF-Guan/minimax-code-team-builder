"""Sandbox test for the minimax-code-team-builder scripts.

Covers: dry-run without a data dir, scaffold, validate green, idempotent re-run
(avatar preserved), and a negative case where a broken agent.md must be rejected.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(REPO, "minimax-code-team-builder")
SCRIPTS = os.path.join(SKILL, "scripts")
BLUEPRINT = os.path.join(REPO, "examples", "team.example.json")

failures = []


def run(args, expect_code=0):
    proc = subprocess.run(
        [sys.executable] + args, capture_output=True, text=True, encoding="utf-8"
    )
    label = args[0].rsplit("\\", 1)[-1]
    ok = proc.returncode == expect_code
    print(f"  [{'ok' if ok else 'FAIL'}] {label} -> exit {proc.returncode} (expected {expect_code})")
    if not ok:
        failures.append(label)
        print("     stdout:", proc.stdout[-600:])
        print("     stderr:", proc.stderr[-600:])
    return proc


print("== 1. dry-run without --data-dir ==")
run([os.path.join(SCRIPTS, "scaffold_team.py"), "--blueprint", BLUEPRINT, "--dry-run"])

with tempfile.TemporaryDirectory(prefix="team_builder_test_") as tmp:
    agents_dir = os.path.join(tmp, "agents")
    print("\n== 2. scaffold ==")
    run([os.path.join(SCRIPTS, "scaffold_team.py"), "--blueprint", BLUEPRINT, "--data-dir", tmp])

    print("\n== 3. validate (green) ==")
    run([os.path.join(SCRIPTS, "validate_team.py"), "--blueprint", BLUEPRINT, "--data-dir", tmp])

    print("\n== 4. idempotent re-run keeps the avatar ==")
    slug = "doc-writer"
    adir = os.path.join(agents_dir, slug)
    with open(os.path.join(adir, "avatar.png"), "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    run([os.path.join(SCRIPTS, "scaffold_team.py"), "--blueprint", BLUEPRINT, "--data-dir", tmp])
    md = open(os.path.join(adir, "agent.md"), encoding="utf-8").read()
    if "  avatar: avatar.png" in md:
        print("  [ok] avatar reference preserved after re-run")
    else:
        failures.append("avatar-preservation")
        print("  [FAIL] avatar reference lost after re-run")
    backups = [f for f in os.listdir(adir) if ".bak-" in f]
    if backups:
        print(f"  [ok] backup written: {backups[0]}")
    else:
        failures.append("backup")
        print("  [FAIL] no backup written")

    print("\n== 5. negative: broken agent must be rejected ==")
    bad = os.path.join(agents_dir, "doc-reviewer", "agent.md")
    original = open(bad, encoding="utf-8").read()
    broken = original.replace(
        "model: minimax/MiniMax-M3.1-Flash", "model: MiniMax-M3.1-Flash"
    ).replace("x-mavis:\n", "features:\n  mavis: true\nx-mavis:\n")
    with open(bad, "w", encoding="utf-8", newline="") as fh:
        fh.write(broken)
    proc = run(
        [os.path.join(SCRIPTS, "validate_team.py"), "--blueprint", BLUEPRINT, "--data-dir", tmp],
        expect_code=1,
    )
    caught_model = "provider/model form" in proc.stdout
    caught_feature = "built-in only" in proc.stdout
    print(f"  [{'ok' if caught_model else 'FAIL'}] bad model form detected")
    print(f"  [{'ok' if caught_feature else 'FAIL'}] builtin-only 'features' key detected")
    if not caught_model:
        failures.append("detect-bad-model")
    if not caught_feature:
        failures.append("detect-features")
    with open(bad, "w", encoding="utf-8", newline="") as fh:
        fh.write(original)

    print("\n== 6. negative: missing avatar file must be reported ==")
    os.remove(os.path.join(agents_dir, slug, "avatar.png"))
    proc = run(
        [os.path.join(SCRIPTS, "validate_team.py"), "--blueprint", BLUEPRINT, "--data-dir", tmp],
        expect_code=1,
    )
    caught = "avatar file is missing" in proc.stdout
    print(f"  [{'ok' if caught else 'FAIL'}] missing avatar detected")
    if not caught:
        failures.append("detect-missing-avatar")

    print("\n== 7. avatar batch request shape ==")
    out = os.path.join(tmp, "avatars")
    run([os.path.join(SCRIPTS, "avatar_batch.py"), "--blueprint", BLUEPRINT, "--out", out])
    payload = json.load(open(os.path.join(out, "avatars-1.json"), encoding="utf-8"))
    reqs = payload["requests"]
    shape_ok = (
        len(reqs) == 3
        and all(r["aspect_ratio"] == "1:1" for r in reqs)
        and all("no text" in r["prompt"] for r in reqs)
        and len(reqs) <= 10
    )
    print(f"  [{'ok' if shape_ok else 'FAIL'}] request shape valid ({len(reqs)} requests)")
    if not shape_ok:
        failures.append("avatar-request-shape")

    print("\n== 8. every shipped example blueprint scaffolds and validates ==")
    examples = sorted(
        f for f in os.listdir(os.path.join(REPO, "examples")) if f.endswith(".json")
    )
    for example in examples:
        path = os.path.join(REPO, "examples", example)
        with tempfile.TemporaryDirectory(prefix="example_check_") as tmp2:
            run([os.path.join(SCRIPTS, "scaffold_team.py"), "--blueprint", path, "--data-dir", tmp2])
            proc = run(
                [os.path.join(SCRIPTS, "validate_team.py"), "--blueprint", path, "--data-dir", tmp2]
            )
            if "failed: 0" not in proc.stdout:
                failures.append(f"example-{example}")

    print("\n== 9. the npx entry point: --init into a directory that does not exist ==")
    node = shutil.which("node")
    if not node:
        print("  (node is not on PATH - skipped)")
    else:
        with tempfile.TemporaryDirectory(prefix="mctb_init_") as tmp2:
            target = os.path.join(tmp2, "does", "not", "exist", "team.json")
            proc = subprocess.run(
                [node, os.path.join(REPO, "bin", "mcode-team-builder.js"), "--init",
                 os.path.dirname(target)],
                capture_output=True, text=True, encoding="utf-8",
            )
            if proc.returncode == 0 and os.path.isfile(target):
                print("  [ok] --init creates the missing target directory")
            else:
                failures.append("init-missing-dir")
                print("  [FAIL] --init into a missing directory:", proc.stderr.strip()[:200])

print("\n" + "=" * 50)
if failures:
    print("FAILED:", failures)
    sys.exit(1)
print("ALL SANDBOX TESTS PASSED")
