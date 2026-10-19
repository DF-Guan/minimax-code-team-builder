#!/usr/bin/env python3
"""Validate a scaffolded MiniMax Code agent team against the runtime's own rules.

Checks, per agent:
  - agent.md exists, has a closed frontmatter block
  - frontmatter keys are inside the set the custom-agent parser accepts
  - name is kebab-case and equals the directory name
  - model is in provider/model form
  - x-mavis.avatar, when present, is a relative in-directory image file
  - the body carries the "# Role: <display name>" line
  - the body equals persona + role + instructions from the blueprint

Usage:
    python validate_team.py --blueprint team.json --data-dir <dataDir>
    python validate_team.py --data-dir <dataDir> --list
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys

AVATAR_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
KNOWN_KEYS = {
    "name",
    "description",
    "model",
    "effort",
    "tools",
    "disallowedTools",
    "mcpServers",
    "skills",
    "x-mavis",
}
KNOWN_MAVIS_KEYS = {
    "displayName",
    "avatar",
    "contextWindow",
    "maxOutputTokens",
    "defaultWorkspaceDir",
    "extensionSkills",
}
KEBAB = re.compile(r"^[a-z][a-z0-9-]*$")
MODEL_FORM = re.compile(r"^[^/\s]+/[^/\s]+$")


def resolve_data_dir(explicit: str | None) -> str:
    if explicit:
        return os.path.abspath(explicit)
    for name in ("MINIMAX_DATA_DIR", "MAVIS_DATA_DIR", "__MAVIS_RUNTIME_DATA_DIR", "__MAVIS_PARENT_DATA_DIR"):
        value = os.environ.get(name)
        if value:
            return os.path.abspath(value)
    if platform.system() == "Windows":
        raise SystemExit(
            "No data directory given. Pass --data-dir, or set MINIMAX_DATA_DIR.\n"
            "It is the folder that contains the 'agents' directory."
        )
    return os.path.abspath(os.path.join(os.path.expanduser("~"), ".minimax"))


def split_frontmatter(raw: str):
    if not raw.startswith("---\n"):
        raise ValueError("missing opening frontmatter marker")
    end = raw.find("\n---\n", 3)
    if end == -1:
        raise ValueError("missing closing frontmatter marker")
    body = raw[end + 5 :]
    if body.startswith("\n"):
        body = body[1:]  # the runtime strips one line ending after the closing marker
    return raw[4:end], body


def parse_frontmatter(text: str) -> tuple[dict, list[str]]:
    """Read the flat / one-level mapping this writer emits."""
    data: dict = {}
    problems: list[str] = []
    current = None
    for raw_line in text.split("\n"):
        if not raw_line.strip():
            continue
        if raw_line.startswith("  ") and current is not None:
            key, _, value = raw_line.strip().partition(":")
            current[key] = parse_scalar(value.strip())
            continue
        current = None
        key, _, value = raw_line.partition(":")
        value = value.strip()
        if value == "":
            current = {}
            data[key.strip()] = current
        else:
            data[key.strip()] = parse_scalar(value)
    return data, problems


def parse_scalar(value: str):
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value == "[]":
        return []
    return value


def check_avatar(agent_dir: str, ref: str) -> list[str]:
    issues = []
    if not ref:
        return issues
    if os.path.isabs(ref):
        return ["avatar path is absolute; it must be relative to the agent directory"]
    target = os.path.abspath(os.path.join(agent_dir, ref))
    root = os.path.abspath(agent_dir)
    if os.path.commonpath([target, root]) != root:
        return ["avatar path escapes the agent directory"]
    ext = os.path.splitext(ref)[1].lower()
    if ext not in AVATAR_EXTENSIONS:
        issues.append(f"avatar extension {ext} is not supported")
    if not os.path.exists(target):
        issues.append("avatar file is missing")
    elif os.path.islink(target):
        issues.append("avatar file is a symlink")
    elif not os.path.isfile(target):
        issues.append("avatar path is not a regular file")
    return issues


def validate_agent(agents_dir: str, slug: str, expected: dict | None) -> tuple[list[str], dict]:
    agent_dir = os.path.join(agents_dir, slug)
    path = os.path.join(agent_dir, "agent.md")
    issues: list[str] = []

    if not os.path.isfile(path):
        return [f"agent.md is missing in {agent_dir}"], {}

    raw = open(path, "r", encoding="utf-8", newline="").read()
    try:
        fm_text, body = split_frontmatter(raw)
    except ValueError as exc:
        return [str(exc)], {}

    fm, _ = parse_frontmatter(fm_text)

    for key in fm:
        if key in KNOWN_KEYS:
            continue
        if key == "features":
            issues.append(
                "unsupported frontmatter key 'features' (built-in only; a custom agent that declares it "
                "gets an unsupported_agent_field diagnostic — remove the block)"
            )
        else:
            issues.append(f"unsupported frontmatter key {key!r} (not accepted for a custom agent)")
    mavis = fm.get("x-mavis")
    if isinstance(mavis, dict):
        for key in mavis:
            if key not in KNOWN_MAVIS_KEYS:
                issues.append(f"unsupported x-mavis key {key!r}")

    name = fm.get("name")
    if not name:
        issues.append("name is missing")
    else:
        if not KEBAB.match(str(name)):
            issues.append(f"name {name!r} is not kebab-case")
        if name != slug:
            issues.append(f"name {name!r} does not match the directory {slug!r}")

    description = fm.get("description")
    if not description or not str(description).strip():
        issues.append("description is missing; the dispatcher routes on this field")

    model = fm.get("model")
    if model and not MODEL_FORM.match(str(model)):
        issues.append(f"model {model!r} must use the provider/model form")

    if isinstance(mavis, dict):
        issues.extend(check_avatar(agent_dir, str(mavis.get("avatar") or "")))

    display_name = (mavis or {}).get("displayName") or name
    role_line = f"# Role: {display_name}"
    if role_line not in body:
        issues.append(f"body is missing the {role_line!r} line")

    if expected:
        expected_body = "\n\n".join(
            part
            for part in (
                (expected.get("persona") or "").rstrip(),
                role_line,
                (expected.get("instructions") or "").strip(),
            )
            if part
        ) + "\n"
        if body != expected_body:
            issues.append("body does not match persona + role + instructions in the blueprint")

    return issues, fm


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--list", action="store_true", help="validate every agent in the collection")
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    agents_dir = os.path.join(data_dir, "agents")
    if not os.path.isdir(agents_dir):
        print(f"no agents directory at {agents_dir}", file=sys.stderr)
        return 2

    blueprint_agents: dict[str, dict] = {}
    if args.blueprint:
        with open(args.blueprint, "r", encoding="utf-8") as handle:
            blueprint = json.load(handle)
        blueprint_agents = {a["slug"]: a for a in (blueprint.get("agents") or [])}

    if args.list:
        slugs = sorted(
            d for d in os.listdir(agents_dir) if os.path.isdir(os.path.join(agents_dir, d)) and d != ".builtin"
        )
    else:
        slugs = sorted(blueprint_agents)
        if not slugs:
            print("nothing to check: pass --blueprint or --list", file=sys.stderr)
            return 2

    failures = 0
    print(f"data dir : {data_dir}")
    print(f"agents   : {len(slugs)}")
    for slug in slugs:
        issues, fm = validate_agent(agents_dir, slug, blueprint_agents.get(slug))
        if issues:
            failures += 1
            print(f"  FAIL {slug}")
            for issue in issues:
                print(f"       - {issue}")
        else:
            model = fm.get("model", "-")
            effort = fm.get("effort", "-")
            window = (fm.get("x-mavis") or {}).get("contextWindow", "-")
            print(f"  OK   {slug:<40} model={model} effort={effort} context={window}")

    print(f"\npassed: {len(slugs) - failures}   failed: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
