# Ready-made blueprints

Each file is a complete team you can run as-is. The skill uses them as a fast path: when a
request is close to one of these, it starts from that blueprint and asks only what differs.

| File | Team | Shape |
| --- | --- | --- |
| `team.example.json` | `docs-release-team` | lead → writer → reviewer |
| `team.research.json` | `research-triad` | gatherer → analyst → memo writer |
| `team.content.json` | `content-triad` | planner → writer → editor |

Every blueprint carries the same fields:

- `team` — the shared model, effort and context window for all members.
- `agents[]` — one entry per role, with an exclusive owner scope and an explicit non-owner
  scope. The `description` is what the dispatcher routes on, so it is written to be
  discriminating rather than generic.
- `dispatch.orchestrator` — the member that receives the request first.
- `dispatch.handoff_format` — the block the members use to pass work on.
- `dispatch.warm_up` — the members to run once so each one has a reachable session.

To use one directly:

```powershell
python ..\minimax-code-team-builder\scripts\scaffold_team.py --blueprint .\team.research.json --data-dir <dataDir>
python ..\minimax-code-team-builder\scripts\validate_team.py --blueprint .\team.research.json --data-dir <dataDir>
```

The `orchestrator` in these examples is the role that plans and dispatches. When you install
the team in a real client, the root session is still the only participant that can spawn
members — the orchestrator receives the request from the root and hands work down.
