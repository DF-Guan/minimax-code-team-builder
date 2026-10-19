# Team Blueprint Schema

The blueprint is the single source of truth for a team. `scripts/scaffold_team.py`,
`scripts/validate_team.py` and `scripts/avatar_batch.py` all read it, so changing a role
means editing one file and re-running the scaffolder.

## Shape

```json
{
  "team": {
    "name": "docs-release-team",
    "description": "Owns release documentation: drafting, review, and publication readiness.",
    "model": "minimax/MiniMax-M3.1-Flash",
    "effort": "max",
    "context_window": 1000000
  },
  "agents": [
    {
      "slug": "release-lead",
      "display_name": "Release Lead",
      "description": "Decomposes release-doc requests, assigns drafting and review, and ships the final result.",
      "persona": "You are the release lead. ...",
      "instructions": "You own decomposition, assignment and final acceptance. ...",
      "tools": null,
      "skills": null,
      "avatar": {
        "symbol": "a compass rose",
        "palette": "bright gold",
        "background": "solid deep navy blue"
      }
    }
  ],
  "dispatch": {
    "orchestrator": "release-lead",
    "handoff_format": "[TASK HANDOFF]\nTask:\nOwner:\nDone:\nOpen questions:\nNext:",
    "warm_up": ["release-lead", "doc-writer", "doc-reviewer"]
  }
}
```

## `team`

| Field | Required | Notes |
| --- | --- | --- |
| `name` | yes | kebab-case; used for the private roster skill directory |
| `description` | no | one line describing what the team owns |
| `model` | no | provider-qualified model id, applied to every agent |
| `effort` | no | reasoning effort, applied to every agent |
| `context_window` | no | applied to every agent |

Per-agent `model` / `effort` / `context_window` override the team defaults.

## `agents[]`

| Field | Required | Notes |
| --- | --- | --- |
| `slug` | yes | kebab-case; becomes the directory name and the dispatcher name |
| `display_name` | yes | human label shown in the panel and to the user |
| `description` | no | one concrete sentence; the dispatcher routes on this — make it discriminating |
| `persona` | no | positioning: scope owned, scope not owned, working style |
| `instructions` | no | the role's operating rules and deliverable contract |
| `tools` | no | `null` (default) = no restriction; an array is a strict allowlist |
| `skills` | no | `null` (default) = no restriction; `[]` withholds every skill |
| `avatar` | no | `{"symbol", "palette", "background"}` — drives image generation |
| `model` / `effort` / `context_window` | no | per-agent overrides |

The written body is `persona` + `\n\n# Role: <display_name>\n\n` + `instructions`. Keep
`persona` to positioning and `instructions` to the operating contract; merging them makes
both harder to maintain.

## `dispatch`

| Field | Required | Notes |
| --- | --- | --- |
| `orchestrator` | no | slug of the agent that receives the user's request first |
| `handoff_format` | no | the block a specialist uses when passing work on |
| `warm_up` | no | slugs to run once so every peer has a reachable session |

`warm_up` matters: a session exists only after the agent has actually run. A specialist
can hand work to a peer through `mavis session send`, but it needs that peer's session
id, and a peer that has never run has none. Running each agent once at the start of a
team's life removes that dead end. See `collaboration.md`.

## Design rules that make a team work

1. **One owner per capability.** Two agents that both claim a capability make routing
   random. Give each capability exactly one owner and write the other agents' non-owner
   scope explicitly.
2. **Descriptions must be discriminating.** The dispatcher sees only the `description`
   line. "Helps with research" loses to "Researches competitor pricing in the EU market".
3. **The orchestrator needs a decomposable job.** If the request cannot be split, the
   orchestrator does the work itself and the team collapses to one agent.
4. **Every agent needs a stopping condition.** State what "done" means for that role,
   otherwise specialists keep producing and never hand back.
5. **Shared rules belong in every `instructions` block.** The runtime gives each agent its
   own prompt; a rule that lives only in the orchestrator's prompt does not reach the
   specialists.
6. **Keep the roster small.** Past roughly eight roles, the dispatcher's choice becomes
   unreliable and hand-offs dominate the work. Split into two teams instead of adding a
   ninth role.
