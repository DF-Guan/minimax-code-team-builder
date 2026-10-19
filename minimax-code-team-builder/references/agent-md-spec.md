# `agent.md` Runtime Contract

What the MiniMax Code runtime actually accepts in a custom agent's `agent.md`. Every rule
here was verified against the running client, not inferred from documentation.

## File layout

```
<dataDir>/agents/<agent-name>/
├── agent.md        # frontmatter + body; the body IS the system prompt
└── avatar.<ext>    # optional; referenced from frontmatter
```

The directory name is the agent's stable name. It must equal the frontmatter `name`
field, and it must be kebab-case.

## Frontmatter

Only these top-level keys are accepted for a custom agent:

| Key | Required | Value |
| --- | --- | --- |
| `name` | yes | kebab-case, must equal the directory name |
| `description` | yes | one concrete sentence; this is what the dispatcher reads |
| `model` | no | must be `provider/model` (e.g. `minimax/MiniMax-M3.1-Flash`) |
| `effort` | no | reasoning effort, e.g. `max` |
| `tools` | no | array of tool names — a **strict allowlist** when present |
| `disallowedTools` | no | array of tool names to block |
| `mcpServers` | no | array of MCP server names to allow |
| `skills` | no | array of skill names to allow |
| `x-mavis` | no | mapping, see below |

`x-mavis` accepts exactly: `displayName`, `avatar`, `contextWindow`, `maxOutputTokens`,
`defaultWorkspaceDir`, `extensionSkills`.

Anything else is reported as an unsupported field. In particular:

- **`features:` is built-in only.** A custom agent that declares it gets an
  `unsupported_agent_field` diagnostic. The `mavis` / `delegation` / `webSearch` feature
  flags belong to the bundled templates, not to custom agents.
- **`model` must contain a slash.** A bare `M3.1-flash` is rejected with
  `model must use the provider/model form`. Use the provider-qualified id from the
  runtime's own model config.

### Selector semantics for `tools` and `skills`

An omitted key means "no restriction". A present key is a strict allowlist:

- `tools: [read, grep]` → every other tool is withheld.
- `skills: []` → **every** skill is withheld, because the empty array becomes an empty
  allowlist rather than "unset".

So omit both keys unless you specifically want to restrict the agent. A custom agent that
omits them inherits the full ready inventory, including web search and the native `mavis`
tool.

## Body = the system prompt

For a custom agent the entire body after the frontmatter is used **verbatim** as the
system prompt. There is no template rendering and no persona/system-prompt split.

This is the single most common mistake. The bundled templates contain a
`{{#if persona.enabled}} ... {{/if}}` block, but that block is only meaningful for the
built-in templates. Copying it into a custom agent puts the literal text
`{{#if persona.enabled}}` into the prompt.

Write the body as plain text:

```
<persona / positioning>

# Role: <display name>

<operating rules, deliverable contract, handoff format>
```

## Avatar

`x-mavis.avatar` must be a **relative path inside the agent directory**, e.g.
`avatar.png`. Rules the runtime enforces:

- extension ∈ `.png .jpg .jpeg .gif .webp`
- the file must exist, be a regular file, and not be reached through a symlink
- the bytes must really be that image format
- size ≤ 10 MiB

A data URL (`data:image/png;base64,...`) is also accepted, but a file reference is easier
to maintain and keeps `agent.md` readable.

The image generator does not always honour the requested extension: a request for a `.png`
can come back as JPEG. The runtime sniffs the real bytes against the extension and
rejects a mismatch, so name each file after its actual format and re-run the scaffolder
so the frontmatter points at the right one.

## Registration

The canonical `agent.md` is the source of truth. The runtime enumerates custom agents
from disk, and a startup repair pass creates the missing index row for any agent that has
a valid `agent.md` but no row. A file-only agent is therefore valid and listed.

`agent create` is the fast path, not a requirement:

- it registers the agent immediately instead of at the next restart;
- it creates the agent's instance id (`.agent-instance-id`);
- it fills in the display name and description for the panel.

`agent create` writes a placeholder `agent.md` when the agent does not exist yet, so
**write the real file first and register second** — otherwise the placeholder wins.

An agent reconciled from disk alone is registered as a `worker` role with a `manual`
creation source. A custom agent's display name, description and avatar are never stored in
the index row; they live in its `agent.md` frontmatter.

Once registered, the agent is an ordinary member of the product on that machine: it
appears in **插件·技能 → 管理 → Agents** alongside the built-in ones, and the running
orchestrator can dispatch to it by name. Each desktop install owns its own collection
under `<dataDir>/agents/`, so a team is not carried to other desktop installs — the
blueprint is what makes it reproducible there.

## Verification

```
mavis({ command: "agent get", args: { agent_name: "<name>" } })
```

Returns the parsed `displayName`, `description`, `avatar` and the resolved `systemPrompt`.
If the frontmatter were invalid this call fails with the offending field, which is the
fastest way to see what the runtime dislikes.

To confirm the model, effort and context window actually took effect, read the frozen
agent definition the runtime writes when a session starts — it contains
`model.providerId`, `model.modelId`, `model.thinking.effort` and `model.contextWindow`.
