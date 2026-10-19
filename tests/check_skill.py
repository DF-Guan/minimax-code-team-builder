"""Self-contained checks for the skill package.

Mirrors the rules the Mavis skill linter enforces, so the published repository can
verify itself in CI without the runtime bundle being present.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "minimax-code-team-builder")
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
FORBIDDEN_FILES = {"README.md", "CHANGELOG.md", "INSTALLATION.md",
                   "INSTALLATION_GUIDE.md", "QUICK_REFERENCE.md"}
FORBIDDEN_KEYS = {"allowed-tools", "license", "model"}
MAX_BODY_LINES = 500


def main() -> int:
    problems = []

    if not os.path.isfile(SKILL_MD):
        print("FAIL: SKILL.md missing")
        return 1
    content = open(SKILL_MD, encoding="utf-8").read()

    if not content.startswith("---\n"):
        print("FAIL: no frontmatter")
        return 1
    end = content.find("\n---\n", 3)
    if end == -1:
        print("FAIL: unclosed frontmatter")
        return 1
    frontmatter = content[4:end]
    body = content[end + 5 :]

    fields = {}
    current = None
    block = None
    for line in frontmatter.split("\n"):
        if block is not None:
            if line.startswith("  ") or not line.strip():
                block.append(line.strip())
                continue
            fields[block[0]] = " ".join(p for p in block[1:] if p)
            block = None
            current = None
        if not line.strip():
            continue
        if line.startswith("  ") and current is not None:
            key, _, value = line.strip().partition(":")
            fields.setdefault(current, {})[key] = value.strip().strip('"')
            continue
        current = None
        key, _, value = line.partition(":")
        value = value.strip()
        if value in ("|", ">", "|-", ">-"):
            block = [key.strip()]
            fields[key.strip()] = ""
            continue
        if value == "":
            current = key.strip()
            fields.setdefault(current, {})
        else:
            fields[key.strip()] = value.strip().strip('"')

    name = fields.get("name", "")
    if not name:
        problems.append("frontmatter.name is missing")
    else:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
            problems.append(f"name {name!r} is not kebab-case")
        if name != os.path.basename(SKILL_DIR):
            problems.append(f"name {name!r} does not match the directory")

    description = fields.get("description", "")
    if not description:
        problems.append("frontmatter.description is missing")
    elif not re.search(r"when|trigger|use this|load this|[\"']", description, re.I):
        problems.append("description has no trigger phrase")

    for key in FORBIDDEN_KEYS:
        if key in fields:
            problems.append(f"forbidden frontmatter key {key!r}")

    body_lines = len(body.split("\n"))
    if body_lines > MAX_BODY_LINES:
        problems.append(f"body is {body_lines} lines (> {MAX_BODY_LINES})")

    for entry in os.listdir(SKILL_DIR):
        if entry in FORBIDDEN_FILES:
            problems.append(f"forbidden file {entry!r} in the skill directory")

    for ref in set(re.findall(r"references/([A-Za-z0-9_-]+\.md)", content)):
        if not os.path.isfile(os.path.join(SKILL_DIR, "references", ref)):
            problems.append(f"references/{ref} is referenced but missing")

    # every example blueprint must be valid JSON with the required fields
    examples = os.path.join(ROOT, "examples")
    for name in sorted(os.listdir(examples)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(examples, name), encoding="utf-8") as handle:
            try:
                data = json.load(handle)
            except json.JSONDecodeError as exc:
                problems.append(f"examples/{name} is not valid JSON: {exc}")
                continue
        for agent in data.get("agents", []):
            for field in ("slug", "display_name"):
                if not agent.get(field):
                    problems.append(f"examples/{name}: an agent is missing {field!r}")
        if not data.get("dispatch", {}).get("orchestrator"):
            problems.append(f"examples/{name}: dispatch.orchestrator is missing")

    # the npx entry point must exist and be wired up
    package = json.load(open(os.path.join(ROOT, "package.json"), encoding="utf-8"))
    for rel in package.get("bin", {}).values():
        if not os.path.isfile(os.path.join(ROOT, rel)):
            problems.append(f"package.json bin {rel!r} does not exist")

    print(f"skill dir : {os.path.relpath(SKILL_DIR, ROOT)}")
    print(f"body lines: {body_lines} (limit {MAX_BODY_LINES})")
    print(f"problems  : {len(problems)}")
    for problem in problems:
        print(f"  FAIL {problem}")
    if not problems:
        print("OK - the skill package is self-consistent")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
