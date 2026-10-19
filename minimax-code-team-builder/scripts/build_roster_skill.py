"""Generate the orchestrator's private roster skill for a local agent team.

Writes a Mavis skill into <dataDir>/agents/<orchestrator>/skills/<team-name>/SKILL.md
so the orchestrator can discover the team on demand. The runtime injects no agent
catalogue into the orchestrator's prompt, so without this the team is invisible to
the dispatcher.

Usage:
    python build_roster_skill.py --blueprint team.json --data-dir <dataDir> \
        --orchestrator mavis --team-name <team-name>
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import datetime


def resolve_data_dir(explicit: str | None) -> str:
    if explicit:
        return os.path.abspath(explicit)
    for name in ("MINIMAX_DATA_DIR", "MAVIS_DATA_DIR", "__MAVIS_RUNTIME_DATA_DIR", "__MAVIS_PARENT_DATA_DIR"):
        value = os.environ.get(name)
        if value:
            return os.path.abspath(value)
    if platform.system() == "Windows":
        raise SystemExit("Pass --data-dir or set MINIMAX_DATA_DIR.")
    return os.path.abspath(os.path.join(os.path.expanduser("~"), ".minimax"))


def yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_skill(team: dict, agents: list[dict], orchestrator: str, team_name: str) -> str:
    by_slug = {a["slug"]: a for a in agents}
    lead = by_slug.get(orchestrator)
    root_is_lead = lead is not None
    summary = (team.get("description") or team_name).rstrip(".。!！?？ 　")

    lines = [
        "---",
        # The skill name MUST equal the directory name, or the loader cannot
        # find it by name. The blueprint's team.name is a human label only.
        f"name: {team_name}",
        "description: |",
        f"  Roster and dispatch rules for the {summary} team.",
        "  Load this skill when a request must be split across the team, when a hand-off is",
        "  needed, or when you need to know which member owns which part.",
        "---",
        "",
        f"# {team_name}",
        "",
        summary,
        "",
        "## Roster",
        "",
        "| Agent | requestRef | Owns | Does not own |",
        "| --- | --- | --- | --- |",
    ]

    for agent in agents:
        owns, hands = split_scope(agent)
        lines.append(
            f"| {agent.get('display_name', agent['slug'])} "
            f"| `{agent['slug']}` | {owns} | {hands} |"
        )

    lines += [
        "",
        "## Dispatch",
        "",
    ]

    if root_is_lead:
        lines += [
            f"You are the root session and the request enters through "
            f"**{lead.get('display_name', orchestrator)}** (`{orchestrator}`).",
            "",
            "1. Decompose the request into one piece per owning agent, with an acceptance criterion each.",
            "2. Spawn each owner with the `task` tool:",
            "   `agent_name: \"agent:<slug>\"` (use the `agent:` prefix — a bare name can collide",
            "   with a built-in role).",
            "3. Collect the results, check them against the acceptance criteria, and integrate them",
            "   into one answer. Do not forward raw agent output.",
        ]
    else:
        lines += [
            "The request reaches you from the root session, which is the only participant that",
            "can spawn sub-agents.",
            "",
            "1. Find the members that own the pieces of this request.",
            "2. For a member that has no session yet, hand the piece back to the root with the",
            "   hand-off block below, naming the member — the root can spawn it.",
            "3. For a member that already has a session, hand the piece over directly:",
            "   `mavis({ command: \"session send\", args: { session_id, content, sync: true } })`.",
            "4. Integrate the replies into one answer and hand the result back to the root.",
        ]

    lines += [
        "",
        "Only the root interactive session can call `task`. If you are a team member rather than",
        "the root, hand work to a peer with `mavis session send` instead:",
        "`session_id` = the peer's session, `content` = the hand-off block, `sync: true`.",
        "",
        "## Hand-off block",
        "",
        "```text",
        "[TASK HANDOFF]",
        "Task: <what was asked>",
        "Owner: <who now owns it>",
        "Done: <what is finished, with evidence>",
        "Open questions: <what is still unknown>",
        "Next: <the concrete next action>",
        "```",
        "",
        "## Shared rules",
        "",
        "Every team member follows the same rules. If a member's own instructions contradict",
        "this list, the member's instructions win for that member.",
        "",
    ]

    for rule in team.get("shared_rules", []):
        lines.append(f"- {rule}")

    lines += [
        "",
        "## Notes",
        "",
        "- A peer that has never run has no session yet, so `session send` cannot reach it. Warm",
        "  the team up once at the start (run each member with a one-line probe) before relying",
        "  on peer hand-offs.",
        "- Members that need a different capability hand off instead of guessing.",
        "",
    ]

    return "\n".join(lines)


def split_scope(agent: dict) -> tuple[str, str]:
    """Pull the 'owns' and 'hands off' hints out of the persona text."""
    persona = agent.get("persona") or ""
    owns = ""
    hands = ""
    for line in persona.split("\n"):
        stripped = line.strip()
        if stripped.startswith("负责：") and not owns:
            owns = stripped[len("负责：") :]
        elif stripped.startswith("不负责：") and not hands:
            hands = stripped[len("不负责：") :]
    if not owns:
        owns = agent.get("description", "")
    if not hands:
        hands = "—"
    return owns.replace("|", "/"), hands.replace("|", "/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", required=True)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--orchestrator", default="mavis", help="agent that receives requests first")
    parser.add_argument("--team-name", required=True)
    args = parser.parse_args()

    with open(args.blueprint, "r", encoding="utf-8") as handle:
        blueprint = json.load(handle)

    team = dict(blueprint.get("team") or {})
    team.setdefault("name", args.team_name)
    if team["name"] != args.team_name:
        # Not fatal: the blueprint's team.name is only a label. The skill name
        # follows the directory so the loader can resolve it.
        print(f"note: blueprint team.name {team['name']!r} differs from the directory "
              f"{args.team_name!r}; using the directory name as the skill name")
    agents = blueprint.get("agents") or []
    if not agents:
        print("blueprint has no agents", file=sys.stderr)
        return 2

    data_dir = resolve_data_dir(args.data_dir)
    skill_dir = os.path.join(data_dir, "agents", args.orchestrator, "skills", args.team_name)
    os.makedirs(skill_dir, exist_ok=True)
    target = os.path.join(skill_dir, "SKILL.md")

    if os.path.isfile(target):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        os.replace(target, f"{target}.bak-{stamp}")

    content = render_skill(team, agents, args.orchestrator, args.team_name)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)

    print(f"roster skill -> {target}")
    print(f"agents listed: {len(agents)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
