---
name: minimax-code-team-builder
description: |
  Build a collaborating team of MiniMax Code subagents from a plain-language request: role
  design, agent.md generation, native registration, avatar generation, validation, the dispatch
  wiring that makes the agents hand work to each other, and the roster the orchestrator reads.
  Use this skill in MiniMax Code and in the MiniMax Inside Code beta when the user says "build
  an agent team", "batch create subagents", "create several agents for me", "make these agents
  work together", "组一个 Agent 团队", "批量建 Subagent", "建个小组", "搭一支团队",
  "发个 ai agent 对话", or asks for a reusable recipe for standing up a new roster of
  specialists. Do NOT use it for a single one-off agent (use create-agent), for editing an
  existing agent's prompt, or for general prompt-writing advice.
descriptions:
  zh-Hans: |
    在 MiniMax Code / MiniMax Inside Code 内测版里，用一句自然语言需求批量建立一支能互相协作的
    Subagent 团队：角色设计、agent.md 生成、原生注册、头像生成、校验、让 Agent 之间互相交接的
    调度接线，以及编排器读到的团队名册。当用户说"帮我建一个 Agent 团队"、"批量建 Subagent"、
    "创建几个 Agent"、"让这些 Agent 协同工作"、"组一个 Agent 团队"，或想要一套可复用的组建配方
    时使用。单个一次性 Agent 请用 create-agent；修改已有 Agent 的提示词、或一般的提示词写作建议
    不要用本 Skill。
displayNames:
  zh-Hans: MiniMax Code 团队 Subagent 构建器
  en: MiniMax Code Team Subagent Builder
metadata:
  icon: icon.png
---

# Agent Team Builder

Turn a plain-language request into a working, illustrated, validated agent team in MiniMax
Code — built in the environment where the request is made, and portable to the others from
the blueprint.

## What you deliver

The user asks for a team in a sentence. You hand back a team that already works:

- one `agent.md` per role, written to the runtime's exact contract — not a draft the user has
  to fix;
- native registration, so the agents appear in 插件·技能 → 管理 → Agents;
- a distinct generated avatar per role, so the roster is scannable instead of a wall of
  letters;
- a validator run that mirrors the runtime's own parser, so "green" means the runtime will
  accept every file;
- a private roster skill the orchestrator can read, because the runtime injects no agent
  catalogue into any prompt;
- a working hand-off path between the members;
- the team sitting in 插件·技能 → 管理 → Agents on the machine where it was built.

The user never edits a frontmatter key, never guesses a model id, and never has to read
runtime source. That is the point of this skill: the runtime specifics are already pinned
down here, so the only judgement left is the role design.

## Targets

- **Runtime**: MiniMax Code (MCode) — Desktop app and the `mcode` CLI share the same local
  runtime and the same agent collection.
- **Creation happens once, in the local environment.** The blueprint is applied to the
  runtime's data directory on the machine where the request is made, then the team is
  registered natively.
- **Where the team lands**: in the app's **插件·技能 → 管理 → Agents** panel on the machine
  where the request was made, next to the built-in agents — the same place a team created
  through the UI appears.
- **One machine, one team**: the desktop client keeps its own agent collection under
  `<dataDir>/agents/`, and its agent service never talks to the account. A team built on
  one desktop does **not** appear on the user's other desktop installs — they each have
  their own collection. The portable artifact is the **blueprint**: copy the blueprint to
  another machine and re-run the scaffolder there, or copy the agent directories. The
  account roster behind the web product is a separate store; avatars can be pushed into it
  with `scripts/push_cloud_avatars.py`, but that does not populate a desktop install.
- **One avatar, two records**: a custom agent's avatar is a **local file** in its own
  directory, and the account keeps its own avatar record for the same agent. The generated
  icons therefore show up in the local panel, while the account copy can still show the
  default avatar until the avatar is set on the account side too. Say this plainly in the
  hand-over instead of letting the user discover it as a bug. See
  `references/collaboration.md` for the full picture.
- **Storage**: `<dataDir>/agents/<agent-name>/agent.md`, where `<dataDir>` is the runtime
  data directory — the folder that contains `agents/`. It differs per install and can be
  relocated, so never hardcode it: read `MINIMAX_DATA_DIR` / `MAVIS_DATA_DIR` /
  `__MAVIS_RUNTIME_DATA_DIR`, or ask the user, and always pass `--data-dir` explicitly.
- **Registration**: the native `mavis` tool, command `agent create` / `agent get` /
  `agent list`. There is no HTTP API reachable from a shell; the local runtime serves it
  over the desktop IPC bridge.
- **Not targeted**: hosting the team in a Plugin (a Plugin manifest carries skills, MCP
  servers and apps — not agents).

## Inputs to collect

Ask with `ask_user` in one questionnaire, only for what the blueprint cannot be inferred
from. Skip a question when the user already answered it in the conversation.

1. **Team purpose** — the outcome the team owns, in one sentence. The purpose decides role
   boundaries; without it every agent drifts toward general assistance.
2. **Roles** — how many specialists, and what each one exclusively owns. Ask for the
   division of work, not a list of job titles.
3. **Orchestrator** — which role receives the user's request first and decomposes it.
4. **Shared rules** — the house rules every agent must obey (evidence standard, language,
   approval boundaries, handoff format).
5. **Model budget** — model, reasoning effort, and context window per agent. Defaults:
   `minimax/MiniMax-M3.1-Flash`, `max`, `1000000`.

If the user says "you decide", produce a reasonable role split from the purpose, state the
split, and continue. Do not block on a questionnaire.

**Fast path**: if the request is close to a ready-made team in `examples/`, start from that
blueprint and ask only what differs. Say which example you started from so the user can
correct the starting point instead of describing it from scratch.

## Procedure

1. **Draft the blueprint** as JSON. Schema and field rules: `references/blueprint-schema.md`.
   Reason: the blueprint is the single source of truth — the scaffolder, the validator and
   the avatar generator all read it, so a later change is one edit, not N file edits.

2. **Give every role exactly one exclusive owner-scope, and one explicit non-owner-scope.**
   Reason: the runtime routes by `description` alone. Two agents that both claim a
   capability produce random routing; the non-owner line is what lets the dispatcher hand
   work away instead of doing it.

3. **Write each agent's file, then register it natively.** Run the scaffolder, then call
   `mavis({ command: "agent create", args: { name, display_name, description } })` for
   each entry:
   ```powershell
   python scripts\scaffold_team.py --blueprint <path>\team.json --data-dir <dataDir>
   ```
   Reason: the canonical `agent.md` is the source of truth — the runtime lists file-only
   agents and repairs a missing index row for them at startup — so the file alone is
   enough to make an agent valid. `agent create` is the fast path: it registers the agent
   immediately instead of at the next restart, and it creates the agent's instance id.
   Write the file first so `agent create` does not overwrite a populated `agent.md` with
   its placeholder. The scaffolder is idempotent and keeps an existing avatar.

4. **Give each agent a distinct avatar.** Build the image request with:
   ```powershell
   python scripts\avatar_batch.py --blueprint <path>\team.json --out <path>\avatars
   ```
   then call the `matrix` image generator through `mcode-tools` (the script already splits
   into batches of at most 10), download each result, and save it as
   `<dataDir>/agents/<slug>/avatar.<ext>`. The generator must be loaded before any
   `mcode-tools` call. Name each file after its **real** format — a `.png` request can come
   back as JPEG, and the runtime sniffs the bytes against the extension.
   Reason: default avatars are a single letter; a roster of 16 letters is unreadable at a
   glance. One symbol and one distinct hue per role fixes that.
   Skip this step when the user does not want images, and never let it block the build.

   The generated icons are local files. If the same agents also exist in the account
   roster, the account copy keeps its own avatar and falls back to a letter. Offer
   `python scripts\push_cloud_avatars.py` to push the icons to the account side as well —
   that is an account write, so ask before doing it. Details in
   `references/collaboration.md`.

5. **Validate.** Run the validator, then confirm the runtime agrees:
   ```powershell
   python scripts\validate_team.py --blueprint <path>\team.json --data-dir <dataDir>
   mavis({ command: "agent list", args: { limit: 30 } })
   ```
   Reason: the validator mirrors the runtime's own parser rules, so a green run means the
   runtime will accept every file rather than merely that the files look right. The list
   call proves the agents are actually registered and visible.

6. **Wire the dispatch path.** Two things, and neither is optional:
   - **The roster**: install the orchestrator's private skill at
     `<dataDir>/agents/<orchestrator>/skills/<team-name>/SKILL.md` (for the built-in `mavis`
     agent use `<dataDir>/agents/mavis/skills/<team-name>/SKILL.md`). Generate it with
     `python scripts\build_roster_skill.py --blueprint <path>\team.json --data-dir <dataDir>
     --orchestrator <slug> --team-name <team-name>`.
     Reason: the runtime injects no agent roster into any prompt, so without this the
     orchestrator cannot know the team exists. A private agent skill is the supported
     place for it.
   - **The warm-up**: run every member once with a one-line probe
     (`mavis({ command: "task", args: { agent_name: "agent:<slug>", prompt: "Reply with OK and state your role." } })`)
     and keep the session ids. Reason: a session exists only after an agent has actually
     run, and a specialist can only reach a peer through an existing session. Without the
     warm-up, peer hand-offs have nowhere to land.
   The full model, the hand-off contract and the verification steps are in
   `references/collaboration.md`. Reason: a team that is built but never dispatched is a
   list, not a team.

7. **Prove it works.** Spawn one member with a realistic one-line task and confirm it
   answers, then confirm the roster skill is where the orchestrator can read it — and that
   it resolves **by name**, since a skill whose frontmatter `name` differs from its
   directory cannot be loaded that way.
   Reason: files on disk are not the same as a working team. This is the step that turns
   "the build finished" into "the team works", and it catches a wrong model id or an
   unreadable prompt before the user finds out.

   **Never ask the agent what model, context window or effort it is running with.** An
   agent answers that from guesswork, not from the runtime — in testing, agents with
   `effort: max` and `contextWindow: 1000000` in their frontmatter reported `low`,
   `medium` and `204800`. Read the frozen agent definition the runtime writes when a
   session starts instead; that is the authoritative record.

8. **Hand over.** Report the roster, the dispatch path, the validation result and the first
   task to try. See the output contract.

## Moving the team to another machine

Desktop installs do not share an agent collection, so the team has to be carried over
explicitly. The blueprint is the portable form:

1. Copy the blueprint JSON to the target machine.
2. Run `scripts/scaffold_team.py --blueprint <path> --data-dir <dataDir>` there, then
   `scripts/validate_team.py` to confirm it.
3. Register each agent on that machine with `mavis agent create`, and rebuild the
   orchestrator's roster skill with `scripts/build_roster_skill.py`.
4. Copy the avatar files too, or regenerate them with `scripts/avatar_batch.py`.

Copying the whole `agents/<slug>/` directories achieves the same result in one move.
State plainly that the other machine starts with an empty collection — nothing syncs on
its own.

## Changing the team later

- **Add or change a role**: edit the blueprint, re-run the scaffolder (it backs up the old
  `agent.md` and preserves the avatar), re-run the validator, rebuild the roster skill.
  One file changes; nothing else does.
- **Retire a role**: `mavis({ command: "agent delete", args: { agent_name } })` removes the
  agent; also delete its directory and its entry in the roster skill, or the orchestrator
  keeps routing to a name that no longer resolves.
- **Tear the whole team down**: delete each agent, then delete
  `<dataDir>/agents/<orchestrator>/skills/<team-name>/`. Leave the blueprint — it is the
  cheapest way to rebuild the team later.

## Output contract

Report to the user:

- **Blueprint path** and the data directory the team was written to.
- **Roster table**: agent name, what it owns, what it hands off.
- **Dispatch path**: which agent receives a request first, and how a specialist reaches a
  peer.
- **Validation result**: counts of agents written / registered / validated, plus any
  failure with its cause.
- **Where to find it**: the team appears in **插件·技能 → 管理 → Agents** on the machine
  that built it. Other desktop installs each keep their own collection, so hand over the
  blueprint — that is what makes the team reproducible elsewhere.
- **Avatar note**: the generated icons are local files, so the account copy of the same
  agent keeps its own avatar. If the user notices different icons on another device, that
  is the cause. Offer `scripts/push_cloud_avatars.py` to align the account side — it is
  an account write, so get the go-ahead first.
- **Next steps**: restart the app to refresh the panel, and the one first task to try.

## Failure handling

- **`mavis agent create` reports the name is taken** — an agent with that slug already
  exists. Read it with `mavis({ command: "agent get", args: { agent_name } })`, then either
  reuse it or pick a different slug. Do not delete an existing agent to make room.
- **The `mavis` tool is not available in this session** — it is bound to the root
  interactive agent, so a delegated worker may not have it. The files are still valid:
  custom agents are file-first and get their index row repaired at the next runtime start.
  Say that registration will happen on the next launch instead of hand-editing the
  runtime's database.
- **The runtime rejects an `agent.md`** — read the reported field. The accepted frontmatter
  keys and the body rules are in `references/agent-md-spec.md`; the usual causes are a
  `features:` block (built-in only), a `model` value that is not in `provider/model` form,
  or a `{{#if ...}}` template in the body.
- **A specialist cannot reach a peer** — the peer has no session yet. Run the warm-up step
  in `references/collaboration.md`; a session appears only after the agent has run once.
- **Avatar generation fails** — continue without avatars and say so. Avatars are cosmetic;
  a missing image must not block a working team.
- **The user abandons the blueprint** — remove the half-written agent directories rather
  than leaving a partial roster in the panel.

## Examples

Input: "帮我建一个负责发布文档的团队：一个负责人拆任务，一个写文档，一个审校。"

Output: a blueprint with three agents (`release-lead`, `doc-writer`, `doc-reviewer`),
three `agent.md` files under `<dataDir>/agents/`, three native registrations, one avatar
per agent, a green validator run, a private `mavis` skill listing the roster with
`release-lead` as the orchestrator, the hand-off block the three share, and the first task
to try.

Input: "给我搭一个看数据做决策的团队。"

Output: the skill proposes a role split from the purpose (data collection, analysis,
decision memo), confirms it with the user in one line, then produces the same artifact set
for that trio.

Input: "帮我搭一支卖货的团队" — a request with no role list at all.

Output: the same artifact set, with the role split proposed from the purpose and confirmed
in one line before the build starts.

Input: "发个 ai agent 对话，角色是 审校 / 翻译 / 发布"

Output: the three named roles become the blueprint's agents; the skill still adds the
owner / non-owner scopes, the shared rules and the hand-off contract that bare role names
leave out.

Input: "我想要三个 agent：一个查、一个写、一个查错"

Output: the same, with the third role's "查错" turned into an explicit review role that
owns verification and hands nothing to itself.

## Windows (win32) platform notes

- Run Python as `python` or `py`; `python3` is not standard on Windows.
- Pass `--data-dir` explicitly, pointing at the folder that contains `agents/`. The data
  directory is relocatable, so resolve it instead of assuming a fixed path. The runtime
  reads `MINIMAX_DATA_DIR` / `MAVIS_DATA_DIR` / `__MAVIS_RUNTIME_DATA_DIR`.
- Invoke the scripts by their absolute path from a location without non-ASCII characters
  when you can. A path containing CJK characters can fail to open under Windows
  PowerShell even when the file exists; the installed skill copy under `<dataDir>\skills\`
  is a safe place to run them from.
- The `mcode-tools` CLI ships as a `.cmd` wrapper, so a bare argv list in a script does
  not resolve it. Use `shutil.which("mcode-tools")` and invoke it through
  `["cmd", "/c", launcher, ...]`.
- Read and write files with an explicit UTF-8 encoding. Windows PowerShell 5.1 defaults to
  the system ANSI code page and corrupts non-ASCII content.
