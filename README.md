<p align="center">
  <img src="icon.png" alt="MiniMax Code Team Builder" width="140">
</p>

<h1 align="center">minimax-code-team-builder</h1>

<p align="center">
  Batch-build collaborating <b>subagent teams</b> in <b>MiniMax Code</b> and the
  <b>MiniMax Inside Code</b> beta — from one plain-language sentence.
</p>

**Say it in one sentence. Get a working, illustrated, validated agent team in MiniMax Code.**

> "帮我建一个负责产品发布的团队：一个负责人拆任务，一个写文案，一个做合规检查。"

That is the whole interface. The skill turns the request into a blueprint, writes every
`agent.md` to the runtime's exact contract, registers the agents natively, gives each one a
distinct generated avatar, validates the result against the runtime's own parser, installs
the roster the orchestrator reads, and warms the team up so hand-offs have somewhere to
land. The user never touches a frontmatter key and never has to read runtime source.

The name says what it does and who it is for: `minimax-code` — the two product surfaces it
targets, MiniMax Code and the MiniMax Inside Code beta; `team-builder` — it builds a team
of subagents, not a single agent.

## Where the team lands

The team is built in the environment of the machine where the request is made, and then it
is an ordinary part of the product *on that machine*:

- it shows up in **插件·技能 → 管理 → Agents**, next to the built-in agents, exactly as if
  it had been created through the UI;
- the running orchestrator picks it up like any other agent, and dispatches to it by name.

**It does not travel to other desktop installs.** Every client keeps its own agent
collection under `<dataDir>/agents/`, and the local agent service never talks to the
account, so a team built on one machine is not present on the next one. The portable
artifact is the **blueprint**: copy `team.json` over and re-run the scaffolder there, or
copy the agent directories across.

The **web / account roster is a separate store** — that is the side the account-level
agent list and the avatars live on. Pushing the generated icons into it
(`scripts/push_cloud_avatars.py`) updates the account copy of the avatar; it still does
not populate a desktop install.

## Why not just ask the model to write `agent.md`?

Because a model that has not studied the runtime will get these wrong, and each mistake is
silent:

| What goes wrong | Why it is silent | What this repo pins down |
| --- | --- | --- |
| The body contains a literal `{{#if persona.enabled}}` | The custom-agent parser does not render templates — the block ships as-is, inside your prompt | Custom-agent bodies are used **verbatim**; there is no persona split |
| The agent has no display name in the panel | A custom agent's index row stores **no** identity — name, description and avatar live only in the `agent.md` | Exactly which frontmatter keys exist, and where identity actually lives |
| `skills: []` | An empty array is a *deny-all* allowlist, not "no restriction" | Selector semantics for `tools` / `skills` |
| The team never dispatches | A custom agent cannot spawn sub-agents, and a peer that has never run has no session | The one-way spawn rule, the warm-up step, the hand-off contract |
| The model id is rejected | `model` must be `provider/model`; a bare name is refused | The provider-qualified id and the effort / context options |
| Avatars show as broken images | The generator can return JPEG for a `.png` request, and the runtime sniffs the bytes against the extension | Name the file after its real format |

Every row above is a rule verified against the running client, not a guess from
documentation.

## What's inside

```
minimax-code-team-builder/
├── minimax-code-team-builder/          # the installable Mavis skill
│   ├── SKILL.md                 # procedure: intake → blueprint → build → wire → validate
│   ├── icon.png                 # the skill logo
│   ├── references/
│   │   ├── agent-md-spec.md     # the runtime contract for agent.md
│   │   ├── blueprint-schema.md  # the blueprint format and team design rules
│   │   └── collaboration.md     # spawn/hand-off model, warm-up, handoff block
│   └── scripts/
│       ├── scaffold_team.py     # blueprint → agent.md files (idempotent)
│       ├── validate_team.py     # check a collection against the runtime's rules
│       ├── avatar_batch.py      # blueprint → image-generation requests
│       └── build_roster_skill.py# blueprint → the orchestrator's private roster skill
├── icon.png                     # the project logo
├── examples/                    # ready-to-run blueprints for the fast path
│   ├── team.example.json        # a three-role release-documentation team
│   ├── team.research.json       # a three-role research team
│   └── team.content.json        # a three-role content team
├── tests/sandbox_test.py        # script tests: dry-run, idempotency, negative cases
├── README.md
└── LICENSE
```

## Install

The skill is a plain directory. Copy it into the MCode user-skill root, which lives inside
the runtime data directory — the same folder that holds `agents/`:

| Platform | Skills root |
| --- | --- |
| Windows | `<dataDir>\skills\` |
| macOS / Linux | `~/.minimax/skills/` |

The data directory is relocatable, so resolve it rather than assuming a fixed path — the
`MINIMAX_DATA_DIR` / `MAVIS_DATA_DIR` environment variables point at it, and the app shows
it in its settings.

```powershell
Copy-Item -Recurse -Force .\minimax-code-team-builder "<dataDir>\skills\minimax-code-team-builder"
```

Restart MCode. The skill then activates on phrases like *"build an agent team"*,
*"batch create subagents"*, *"create several agents for me"*, *"make these agents work
together"*, *"组一个 Agent 团队"*, *"批量建 Subagent"* or *"帮我建几个 Agent"*.

## Try it

```
帮我建一个负责产品发布的团队：一个负责人拆任务，一个写文案，一个做合规检查。
```

```
Build me a research team: one gathers sources, one analyses them, one writes the memo.
```

```
I need a content team — someone plans topics, someone drafts, someone edits.
```

```
批量建一组 Subagent：一个做检索，一个做分析，一个做审校。
```

Or skip the conversation entirely and ask for a template by name: *"给我一个 research 团队的模板"*.

## Use the scripts directly

The scripts are standalone and dependency-free — useful if you drive the build from CI or
another tool, or if you want the blueprint under version control.

```powershell
# 1. plan
python minimax-code-team-builder\scripts\scaffold_team.py --blueprint .\examples\team.example.json --dry-run

# 2. write
python minimax-code-team-builder\scripts\scaffold_team.py --blueprint .\examples\team.example.json --data-dir <dataDir>

# 3. check
python minimax-code-team-builder\scripts\validate_team.py --blueprint .\examples\team.example.json --data-dir <dataDir>
```

`--data-dir` is the MCode data directory — the folder that contains `agents/`. The
scripts also honour `MINIMAX_DATA_DIR` / `MAVIS_DATA_DIR` / `__MAVIS_RUNTIME_DATA_DIR`, so
no machine path is ever hardcoded.

## The collaboration model in one diagram

```
user ──▶ root agent (mavis)
            │  task(agent_name="agent:<slug>")   ← the only spawn path
            ▼
         lead / orchestrator  ── mavis session send(sibling_session_id, sync=true) ──▶ specialist
            ▲                                                                        │
            └────────────────── reply, session send back ───────────────────────────┘
```

| From | Spawn (`task`) | Message a peer (`session send`) |
| --- | --- | --- |
| Root interactive agent | yes | yes |
| A custom agent | no | yes, to a peer that already has a session |

Full rules, the warm-up step and the handoff block live in
`minimax-code-team-builder/references/collaboration.md`.

## Design rules that matter

1. **One owner per capability.** Two agents claiming the same capability make routing
   random.
2. **The `description` field is the whole routing signal.** Make each one discriminating.
3. **A session exists only after an agent has run once.** Warm the team up before the
   first real task.
4. **Ship the roster with the team.** The runtime injects no agent catalogue into the
   orchestrator's prompt — install the roster as a private agent skill.
5. **Keep it to roughly eight roles.** Past that, routing gets unreliable and hand-offs
   dominate the work.

## Quality

- The skill passes the Mavis skill linter (`lint-skill.js`): valid frontmatter, kebab-case
  name, no forbidden files, all `references/` links resolve, body under the line limit.
- The scripts are exercised against a scratch data directory on every change; the
  scaffolder is idempotent and preserves an existing avatar.
- The skill is eval-tested against a no-skill baseline on a realistic build request. The
  eval also corrected two claims in this documentation that the baseline disproved.

## Requirements

- MiniMax Code Desktop or the `mcode` CLI, with a local runtime.
- Python 3.9+ (no third-party packages).
- The native `mavis` tool for registration and dispatch — the local runtime serves its API
  over the desktop IPC bridge and does not expose it on a TCP port.
- A signed-in account, if you also want the generated avatars pushed to the web/account
  roster via `scripts/push_cloud_avatars.py`.

## License

MIT — see [LICENSE](LICENSE).
