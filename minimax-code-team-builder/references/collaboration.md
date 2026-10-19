# Collaboration Model

What the runtime permits between agents, and how to wire a team so work actually moves
between roles. Every constraint here was verified against the running client.

## The one-way rule

| From | Can spawn a sub-agent (`task`)? | Can message a peer (`mavis session send`)? |
| --- | --- | --- |
| Root interactive agent (`mavis`) | yes | yes |
| A custom agent | **no** | yes, to a peer that already has a session |

The `task` tool is gated to the authoritative main profile — an interactive or CLI session
that is a trusted built-in with the `mavis` canonical role. A custom agent running as a
task child does not get it. A custom agent that runs as its own root session does not get
it either.

Consequences:

- **The root agent is the only spawner.** Every new worker enters the team through the
  root's `task` call.
- **Specialists can still talk to each other.** A custom agent keeps the native `mavis`
  tool, so it can list sessions, read one, and send into it. This is what makes a
  lead-style agent able to hand work to a specialist without going back through the root.
- **A peer with no session is unreachable.** Sessions materialise when an agent first
  runs. `agent create` does not leave a durable root session behind
  (`main_session_id` stays null). Until an agent has run once, there is no session id to
  address.

## Wiring pattern

```
user ──▶ root agent (mavis)
            │  task(agent_name="agent:<slug>")   ← the only spawn path
            ▼
         lead / orchestrator  ── mavis session send(sibling_session_id, sync=true) ──▶ specialist
            ▲                                                                        │
            └────────────────── reply, session send back ───────────────────────────┘
```

### Step 1 — give the orchestrator the roster

The runtime injects **no** agent catalogue into the orchestrator's prompt: the built-in
role directory covers only the bundled templates, and the agent-list reminder field is
never populated. An orchestrator that has not been told about the team cannot route to it.

Ship the roster as a private skill for the orchestrator agent:

```
<dataDir>/agents/<orchestrator>/skills/<team-name>/SKILL.md
```

For the built-in `mavis` agent that path is `<dataDir>/agents/mavis/skills/<team-name>/SKILL.md`.
Put the role table (slug, display name, what it owns, what it hands off) and the handoff
format in that file. The skill catalogue is visible to the agent, so it can load the
roster on demand instead of carrying it in every prompt.

### Step 2 — warm the team up

Run every agent once before the first real task, so each one has a session:

```
mavis({ command: "task", args: { agent_name: "agent:<slug>", prompt: "Reply with OK and state your role." } })
```

Record the session ids from the task results. From then on the orchestrator can address
any teammate directly.

### Step 3 — dispatch

The root decomposes and spawns:

```
mavis({ command: "task", args: {
  agent_name: "agent:<slug>",
  prompt: "<task>\n\nContext: ...\nAccept when: ...\nReturn: ..."
}})
```

A specialist hands work to a peer with:

```
mavis({ command: "session send", args: {
  session_id: "<peer session id>",
  content: "<handoff block>",
  sync: true
}})
```

`sync: true` waits for the peer's reply, which is what a handoff needs. Without it the
call only returns an admission acknowledgement.

To find a peer the specialist calls `mavis({ command: "session list", args: { limit: 30 } })`
and matches on the agent name in each row.

### Step 4 — the handoff block

Use one fixed block for every hand-off, and put it in every agent's `instructions`:

```
[TASK HANDOFF]
Task: <what was asked>
Owner: <who now owns it>
Done: <what is already finished, with evidence>
Open questions: <what is still unknown>
Next: <the concrete next action>
```

Three properties make it work: the receiving agent can tell what is already done and
does not redo it; the unknown items are explicit instead of silently guessed; and the
receiver has a single clear next action.

## What lands where

An agent exists as **two independent records**, and they do not sync between each other:

| | Local collection | Account roster |
| --- | --- | --- |
| Where it lives | `<dataDir>/agents/<slug>/agent.md` plus a local index row | the account side, behind the web product |
| Avatar | a **local file** in the agent directory, served by `/agent/<slug>/identity/avatar` | a **remote URL** the UI renders directly |
| Display name / description | read from the `agent.md` frontmatter | the account's own copy |
| Dispatch | this is the one the local runtime spawns and hands work to | a different surface |
| Other desktop clients | **not reached** — every install keeps its own collection | the account copy is what the web side shows |

Three consequences worth stating in the hand-over:

1. **One desktop, one team.** A team built on one machine does not appear on the user's
   other desktop installs; each install owns its collection under `<dataDir>/agents/`, and
   the local agent service makes no cloud calls at all. The portable artifact is the
   **blueprint**: copy it to the other machine and re-run the scaffolder there, or copy
   the agent directories across.
2. **The generated icons are local.** The account copy of the same agent keeps its own
   avatar record, so it falls back to the default letter avatar until someone sets it.
   That is what the account-side push in `scripts/push_cloud_avatars.py` fixes — but it
   changes the **web/account** copy only, and still does not populate a desktop install.
3. **Which copy the desktop app uses.** The desktop panel and the `task` dispatcher work
   off the local collection. That is the copy that matters for day-to-day use.

## Pushing avatars to the account (optional, web side only)

The account agent API accepts an `avatar_object_key`, so the generated icons *can* be
pushed into the account roster that the web product shows:

```powershell
python scripts\push_cloud_avatars.py --dry-run   # plan
python scripts\push_cloud_avatars.py             # push all
```

The script matches local agents to account agents by `display_name` (the account stores a
numeric id, not a slug) and reuses the signed-in token, so it only ever touches the
signed-in account.

Scope this honestly: it updates the **account / web** copy of the avatar. It does not
copy the agents themselves, and it does not populate another desktop install. Offer the
step explicitly — it is an account write, and the user may prefer to set avatars through
the product UI instead.

## Patterns that fail

- **The lead spawns specialists.** A custom agent has no `task` tool, so a lead that
  tries to dispatch fails silently or improvises. The lead must either hand back to the
  root, or hand to a peer that already has a session.
- **A specialist answers a question outside its scope.** Give every agent a non-owner
  scope line and make the handoff the expected behaviour.
- **Every agent answers the user directly.** A team that produces fifteen parallel
  answers instead of one integrated one is worse than a single agent. The root owns the
  final integration.
- **Relying on the description alone for routing.** Descriptions are the only routing
  signal, and they are short. Make each one discriminating, and keep the roster in the
  orchestrator's skill.

## Verifying the wiring

1. `mavis({ command: "agent list", args: { limit: 30 } })` — every team member present.
2. `mavis({ command: "session list", args: { limit: 30 } })` — warmed agents have sessions.
3. Send a one-line message to a peer with `session send` and `sync: true` — a reply
   proves the path works.
4. Run one real task end to end and check that the final answer was integrated by the
   root rather than returned raw from a specialist.
5. Check the roster skill resolves **by name** through the `skill` tool. A roster whose
   frontmatter `name` differs from its directory name exists on disk but cannot be
   loaded that way, so the dispatcher falls back to reading the file — which works, but
   burns a turn and is not what the procedure describes. Generate the roster with
   `scripts/build_roster_skill.py --team-name <directory name>`; the script uses the
   directory name as the skill name for exactly this reason.

### Do not trust an agent's self-report

Ask an agent "what model / context window / effort are you running with" and it answers
from guesswork. In testing, three agents whose frontmatter said `effort: max` and
`contextWindow: 1000000` self-reported `low`, `medium` and `204800` — all wrong, while
their actual runtime configuration was correct.

The authoritative record is the frozen agent definition the runtime writes when a
session starts: it carries `model.providerId`, `model.modelId`,
`model.thinking.effort` and `model.contextWindow`. Read that, not the transcript.
