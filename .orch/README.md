# Orchestrator pipeline

Claude Opus 5 orchestrates. Qwen3.8 on the TUM endpoint (free) does the labour.

```
you ──▶ Claude (orchestrator)              Qwen (subagent)
            │  decides what to build
            │  writes .orch/tasks/NNN-*.md
            │  ────────────────────────────▶ reads the task
            │                                reads/writes/tests code in the repo
            │  ◀──────────────────────────── .orch/runs/<id>/result.md
            │  reviews the diff, runs the gate
            │  fixes or re-delegates
            ▼
       reports to you
```

Claude never pastes Qwen's code into its own context wholesale — it reads `result.md`,
runs the verification command, and spot-checks the diff. That's where the token savings
come from.

## Setup (one step — your key)

```bash
cp .orch/.env.example .orch/.env
# paste your key into .orch/.env:  QWEN_API_KEY=sk-...
.orch/qwen-agent --probe
```

`.env` is gitignored. `--probe` checks three things separately: the endpoint answers, the
key is accepted, and **tool calling actually works**. If the third fails the agent loop
cannot function, and the probe says so explicitly rather than hanging.

Key resolution order: `QWEN_API_KEY` env var → `.orch/.env` → `apiKey` in `config.json`.
The `${input:chat.lm.secret...}` placeholder from your VS Code config is ignored.

## Running a task

```bash
.orch/qwen-agent --task 001-parser-gate.md          # looks in .orch/tasks/
.orch/qwen-agent --prompt "Add type hints to core/models.py"
.orch/qwen-agent --task 002.md --read-only          # analysis only, no writes
.orch/qwen-agent --task 002.md --max-turns 60       # default is 40
```

Progress goes to **stderr** one line per tool call; the path to `result.md` is the only
thing on **stdout**. So `RESULT=$(.orch/qwen-agent --task x.md)` gives you the report path
while you still watch it work.

Exit codes: `0` done · `1` partial/blocked · `2` out of turns or stalled · `3` config or
endpoint error · `130` interrupted.

Every run leaves `.orch/runs/<id>/`:

| file | contents |
|---|---|
| `result.md` | status, summary, files changed, verification, open questions |
| `transcript.jsonl` | every turn: assistant text, tool args, tool output |
| `meta.json` | status, turn count, token usage |

## The subagent's tools

`read_file` · `write_file` · `edit_file` · `list_dir` · `glob` · `grep` · `bash` · `finish`

Its system prompt forces three habits that matter: use tools rather than claim, **run the
code before reporting success**, and never ask a mid-run question (it can't receive an
answer — it must assume, proceed, and log the assumption).

## Sandbox — what it does and does not guarantee

File tools resolve every path and refuse anything outside the project root, including via
`..` and symlinks. `bash` runs with `cwd` at the root and a blocklist covering `sudo`,
recursive force-deletes, `git push`, `git reset --hard`, pipe-to-shell, and device writes.

**This is a guardrail, not a jail.** A shell is a shell: a determined or confused command
can still reach outside the project root. Two consequences worth accepting deliberately —
the repo is version-controlled, so commit before a big delegated run, and read the diff
rather than trusting the report. Use `--read-only` for anything you only want analysed.

## Writing good tasks

Copy `tasks/_TEMPLATE.md`. The template exists because the failure mode of a 27B subagent
is not bad code, it's **drifting scope and confident unverified claims**. Both are fixed by
the same thing: a definition of done that is a literal command, and a named list of files
it may touch.

Rules of thumb, learned from the shape of this repo's plan:

- One deliverable per task. "Write `parser_x83.py`" not "build the parsing layer".
- Hand it the facts you already verified (the PLAN.md tables) so it doesn't re-derive
  them and get them wrong — e.g. the cp850 encoding, the ÷1000/÷100 scaling, the
  `local-name()` namespace rule.
- Give it a machine-checkable gate wherever one exists. This project is unusually rich in
  them: the D83/X83 twin pair, the €897,305.45 bid total, the composed-OZ join.
- `--read-only` first when you want a survey before you let it write.

## Regression test

```bash
python3 .orch/test_agent.py     # 56 checks, mock endpoint, no API key or network needed
```

Covers sandbox escapes, the bash blocklist, read-only enforcement, edit uniqueness,
context pruning, the inline-`<tool_call>` salvage path, and a full four-turn loop.
Run it if you change `qwen_agent.py`.

## Notes on this endpoint

Current: **TUM AI** (`morpheus.cit.tum.de`), model `cyankiwi/Qwen3.8-Flash-Next-AWQ-INT4`,
vLLM backend. Probe-verified: auth OK, native tool calling OK.

- **It's a reasoning model.** Responses carry a separate `reasoning` field and burn
  completion tokens before emitting `content`. Consequence: a small `max_tokens` returns
  `content: null` with `finish_reason: length`, which looks like a broken endpoint but
  isn't. `maxTokensPerTurn` is 8192 (model ceiling 16k), which leaves ample room.
- `url` in `config.json` may be either a base (`.../api/v1`) or a full path; the loader
  appends `/chat/completions` when it's missing, so paste whatever your VS Code config has.
- `max_tokens` per turn is capped at `maxTokensPerTurn` in `config.json` — a tool-calling
  turn is short, and some gateways reject requests where prompt + `max_tokens` exceeds the
  context window. Raise it if a task needs one very long single reply.
- Transient failures (429, 5xx, timeouts) retry 5× with exponential backoff. 401/403/404
  fail immediately with the endpoint's own error text, since retrying won't help.
- Some Qwen deployments emit `<tool_call>{...}</tool_call>` as plain text instead of
  populating `tool_calls`. The loop recovers those automatically — you'll see
  `recovered N inline tool call(s)` in the progress output.
- Tool results are capped (24k chars, 12k for bash) and old ones are elided once the
  transcript passes ~105k tokens, so long runs degrade gracefully instead of 400-ing.
