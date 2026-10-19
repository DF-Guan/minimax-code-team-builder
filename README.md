<p align="center">
  <img src="icon.png" alt="MiniMax Code Team Builder" width="140">
</p>

<h1 align="center">minimax-code-team-builder</h1>

[![CI](https://github.com/DF-Guan/minimax-code-team-builder/actions/workflows/ci.yml/badge.svg)](https://github.com/DF-Guan/minimax-code-team-builder/actions/workflows/ci.yml)


<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  Batch-build collaborating <b>subagent teams</b> in <b>MiniMax Code</b> and the
  <b>MiniMax Inside Code</b> beta — from one plain-language sentence.
</p>

---

## Say it like this

### 1 · In MiniMax Code — just type it

No commands, no files, no jargon. Ask in whatever words come to mind:

```
建个三人小组：一个查资料，一个分析，一个写结论
```

```
发个 ai agent 对话，角色是 审校 / 翻译 / 发布
```

```
帮我搭一支做数据分析的团队
```

```
I need three agents: one researches, one writes, one checks.
```

```
Spawn a small team that can triage bugs.
```

The skill asks you at most one short round of questions, then builds the whole thing:
every `agent.md` written to the runtime's exact contract, every agent registered so it
shows up in **插件·技能 → 管理 → Agents**, a distinct generated avatar per role, a
validation pass, the roster the orchestrator reads, and a warm-up so hand-offs have
somewhere to land.

### 2 · In your terminal — one command

```bash
npx github:DF-Guan/minimax-code-team-builder --init          # write a starter team.json
npx github:DF-Guan/minimax-code-team-builder --blueprint team.json
```

The terminal path covers the reproducible half — blueprint → `agent.md` files →
validation. The interactive half (registration, avatars, roster, warm-up) is what the
skill does in chat. Use the terminal when the blueprint belongs in version control or
the build runs from CI.

### 3 · As a skill — copy the folder

The skill is a plain directory. Copy it into the MCode user-skill root, which lives
inside the runtime data directory — the same folder that holds `agents/`:

| Platform | Skills root |
| --- | --- |
| Windows | `<dataDir>\skills\` |
| macOS / Linux | `~/.minimax/skills/` |

```powershell
git clone https://github.com/DF-Guan/minimax-code-team-builder.git
Copy-Item -Recurse -Force .\minimax-code-team-builder\minimax-code-team-builder "<dataDir>\skills\minimax-code-team-builder"
```

The data directory is relocatable, so resolve it rather than assuming a fixed path —
`MINIMAX_DATA_DIR` / `MAVIS_DATA_DIR` point at it, and the app shows it in its
settings. Restart MCode afterwards.

---

## What you get

| | |
| --- | --- |
| **A real team** | One `agent.md` per role, written to the runtime's exact contract — not a draft you have to fix |
| **Registered** | Every agent appears in **插件·技能 → 管理 → Agents**, dispatchable by name |
| **Distinguishable** | A distinct generated avatar per role, so the roster is scannable instead of a wall of letters |
| **Validated** | A check that mirrors the runtime's own parser, so "green" means the runtime will accept every file |
| **Wired** | A private roster skill the orchestrator reads — the runtime injects no agent catalogue into any prompt |
| **Connected** | A warm-up pass plus a hand-off contract, so members can actually pass work to each other |

You never edit a frontmatter key, never guess a model id, and never have to read
runtime source. That is the point of this skill: the runtime specifics are already
pinned down here, so the only judgement left is the role design.

## See it

![The 全部 Agent panel in MiniMax Code with a built team](docs/agents-panel.png)

*The 全部 Agent panel in MiniMax Code. The red box is a 16-role team, created in one build.
The agent names are redacted here; the avatars are the real generated output.*

---

## Where the team lands

The team is built in the environment of the machine where the request is made, and then
it is an ordinary part of the product *on that machine*:

- it shows up in **插件·技能 → 管理 → Agents**, next to the built-in agents, exactly as if
  it had been created through the UI;
- the running orchestrator picks it up like any other agent, and dispatches to it by name.

**It does not travel to other desktop installs.** Every client keeps its own agent
collection under `<dataDir>/agents/`, and the local agent service never talks to the
account, so a team built on one machine is not present on the next one. The portable
artifact is the **blueprint**: copy `team.json` over and re-run the builder there, or
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
│       ├── build_roster_skill.py# blueprint → the orchestrator's private roster skill
│       └── push_cloud_avatars.py # local avatars → the account/web roster
├── bin/mcode-team-builder.js   # the npx entry point
├── examples/                    # ready-to-run blueprints for the fast path
│   ├── team.example.json        # a three-role release-documentation team
│   ├── team.research.json       # a three-role research team
│   └── team.content.json        # a three-role content team
├── tests/sandbox_test.py        # script tests: dry-run, idempotency, negative cases
├── package.json
├── README.md
├── README.zh-CN.md
└── LICENSE
```

## Use the scripts directly

The scripts are standalone and dependency-free — useful if you drive the build from CI or
another tool, or if you want the blueprint under version control.

```bash
# 1. plan
python minimax-code-team-builder/scripts/scaffold_team.py --blueprint examples/team.example.json --dry-run

# 2. write
python minimax-code-team-builder/scripts/scaffold_team.py --blueprint examples/team.example.json --data-dir <dataDir>

# 3. check
python minimax-code-team-builder/scripts/validate_team.py --blueprint examples/team.example.json --data-dir <dataDir>
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

Full rules, the warm-up step and the hand-off block live in
`minimax-code-team-builder/references/collaboration.md`.

## Design rules that matter

1. **One owner per capability.** Two agents claiming the same capability make routing
   random.
2. **The `description` field is the whole routing signal.** Make each one discriminating.
3. **A session exists only after an agent has run once.** Warm the team up before the
   first real task.
4. **Ship the roster with the team.** The runtime injects no agent catalogue into the
   orchestrator's prompt — install the roster as a private agent skill.
5. **Start a new team at roughly eight roles.** Past that, routing gets unreliable and
   hand-offs dominate the work.

## Quality

- The skill passes the Mavis skill linter (`lint-skill.js`): valid frontmatter, kebab-case
  name, no forbidden files, all `references/` links resolve, body under the line limit.
- The scripts are exercised against a scratch data directory on every change; the
  scaffolder is idempotent and preserves an existing avatar.
- The skill was eval-tested against a no-skill baseline on the same build request. The
  baseline arm had to extract the runtime's parser out of the app bundle and hand-write
  registry rows to register anything; the skill arm got the parser rules, the registry
  shape, the roster and the avatars from this repo.
- **The whole flow was run end to end in a live runtime**: scaffold → native registration →
  generated avatars → validator → roster skill → warm-up → a real peer hand-off
  (`session send` with `sync: true`, reply received). Two bugs surfaced that way and are
  fixed: a roster skill whose frontmatter name did not match its directory could not be
  loaded by name, and an agent asked to report its own model / context window / effort
  answers from guesswork — the runtime's frozen agent definition is the authoritative
  record, not the transcript.
- A fresh `git clone` passes the linter and the script tests, so the published repo is
  verified as a clone, not just as a working copy.

## Requirements

- MiniMax Code Desktop or the `mcode` CLI, with a local runtime.
- Python 3.9+ (no third-party packages) for the scripts; Node 18+ for the `npx` entry.
- The native `mavis` tool for registration and dispatch. It is a runtime tool of the app,
  not a shell command.
- A signed-in account, if you also want the generated avatars pushed to the web/account
  roster via `scripts/push_cloud_avatars.py`.

## License

MIT — see [LICENSE](LICENSE).
