#!/usr/bin/env python3
"""Scaffold a MiniMax Code agent team from a blueprint file.

Reads a team blueprint (see references/blueprint-schema.md) and writes one
<dataDir>/agents/<slug>/agent.md per role, using the frontmatter keys the
runtime's custom-agent parser accepts.

The scaffolder is idempotent: re-running it rewrites agent.md but keeps an
existing avatar reference and never touches the avatar file itself.

Usage:
    python scaffold_team.py --blueprint team.json --data-dir <dataDir>
    python scaffold_team.py --blueprint team.json --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from datetime import datetime

AVATAR_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
DEFAULT_MODEL = "minimax/MiniMax-M3.1-Flash"
DEFAULT_EFFORT = "max"
DEFAULT_CONTEXT_WINDOW = 1_000_000


def resolve_data_dir(explicit: str | None, required: bool = True) -> str:
    """Resolve the MiniMax Code data directory without hardcoding a machine path."""
    if explicit:
        return os.path.abspath(explicit)
    for name in ("MINIMAX_DATA_DIR", "MAVIS_DATA_DIR", "__MAVIS_RUNTIME_DATA_DIR", "__MAVIS_PARENT_DATA_DIR"):
        value = os.environ.get(name)
        if value:
            return os.path.abspath(value)
    if platform.system() == "Windows":
        if not required:
            return ""
        raise SystemExit(
            "No data directory given. Pass --data-dir, or set MINIMAX_DATA_DIR.\n"
            "It is the folder that contains the 'agents' directory."
        )
    return os.path.abspath(os.path.join(os.path.expanduser("~"), ".minimax"))


def yaml_scalar(value: str) -> str:
    """A YAML double-quoted scalar (also valid JSON) so any text is safe."""
    return json.dumps(value, ensure_ascii=False)


def find_avatar(agent_dir: str) -> str | None:
    if not agent_dir:
        return None
    for ext in AVATAR_EXTENSIONS:
        candidate = os.path.join(agent_dir, f"avatar{ext}")
        if os.path.isfile(candidate):
            return f"avatar{ext}"
    return None


def build_agent_md(agent: dict, team: dict) -> str:
    slug = agent["slug"]
    display_name = agent.get("display_name") or slug
    model = agent.get("model") or team.get("model") or DEFAULT_MODEL
    effort = agent.get("effort") or team.get("effort") or DEFAULT_EFFORT
    context_window = (
        agent.get("context_window")
        or team.get("context_window")
        or DEFAULT_CONTEXT_WINDOW
    )

    mavis: list[str] = ["x-mavis:"]
    avatar = find_avatar(os.path.join(AGENTS_DIR, slug))
    if avatar:
        mavis.append(f"  avatar: {avatar}")
    mavis.append(f"  displayName: {yaml_scalar(display_name)}")
    mavis.append(f"  contextWindow: {int(context_window)}")

    frontmatter = [
        "---",
        f"name: {slug}",
        f"description: {yaml_scalar(agent.get('description', ''))}",
        f"model: {model}",
        f"effort: {effort}",
    ]

    tools = agent.get("tools")
    if tools:
        frontmatter.append("tools:")
        frontmatter.extend(f"  - {yaml_scalar(t)}" for t in tools)
    skills = agent.get("skills")
    if skills:
        frontmatter.append("skills:")
        frontmatter.extend(f"  - {yaml_scalar(s)}" for s in skills)

    frontmatter.extend(mavis)
    frontmatter.append("---")

    persona = (agent.get("persona") or "").rstrip()
    instructions = (agent.get("instructions") or "").strip()
    body_parts = [p for p in (persona, f"# Role: {display_name}", instructions) if p]
    body = "\n\n".join(body_parts) + "\n"

    return "\n".join(frontmatter) + "\n\n" + body


AGENTS_DIR = ""


def main() -> int:
    global AGENTS_DIR

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", required=True, help="path to the team blueprint JSON")
    parser.add_argument("--data-dir", default=None, help="MiniMax Code data directory")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir, required=not args.dry_run)
    AGENTS_DIR = os.path.join(data_dir, "agents") if data_dir else ""

    with open(args.blueprint, "r", encoding="utf-8") as handle:
        blueprint = json.load(handle)

    team = blueprint.get("team") or {}
    agents = blueprint.get("agents") or []
    if not agents:
        print("blueprint has no agents", file=sys.stderr)
        return 2

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    written, skipped, failed = [], [], []

    for agent in agents:
        slug = agent.get("slug")
        if not slug:
            failed.append(("<missing slug>", "no slug field"))
            continue
        agent_dir = os.path.join(AGENTS_DIR, slug)
        target = os.path.join(agent_dir, "agent.md")
        try:
            if args.dry_run:
                written.append((slug, "would write", len(build_agent_md(agent, team))))
                continue
            os.makedirs(agent_dir, exist_ok=True)
            if os.path.isfile(target):
                shutil.copy2(target, f"{target}.bak-{stamp}")
            content = build_agent_md(agent, team)
            with open(target, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
            written.append((slug, "written", len(content.encode("utf-8"))))
        except Exception as exc:  # noqa: BLE001
            failed.append((slug, repr(exc)))

    verb = "would write" if args.dry_run else "written"
    print(f"data dir : {data_dir}")
    print(f"agents   : {len(agents)}")
    print(f"{verb} : {len(written)}   failed: {len(failed)}")
    for slug, state, size in written:
        print(f"  {state:<12} {slug:<40} {size} bytes")
    for slug, err in failed:
        print(f"  FAILED       {slug:<40} {err}", file=sys.stderr)
    if not args.dry_run:
        print("\nNext: register each agent with `mavis agent create` if it is not listed yet,")
        print("then validate with scripts/validate_team.py.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
