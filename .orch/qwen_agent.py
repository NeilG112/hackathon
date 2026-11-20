#!/usr/bin/env python3
"""Qwen subagent worker.

An agentic tool loop over an OpenAI-compatible chat-completions endpoint.
Claude (the orchestrator) writes a task file and invokes this; the worker reads,
writes and tests code inside a sandboxed project root, then reports back.

Stdlib only, on purpose: no install step, works under any python3.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ORCH_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = ORCH_DIR.parent

# Directories never walked by glob/grep.
SKIP_DIRS = {
    ".git", ".orch", "venv", ".venv", "env", "node_modules", "__pycache__",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".next", "dist", "build",
}

MAX_TOOL_CHARS = 24_000      # per tool result
MAX_BASH_CHARS = 12_000
CONTEXT_CHAR_BUDGET = 420_000  # ~105k tokens; prune older tool output beyond this


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #

@dataclass
class Config:
    url: str
    model: str
    api_key: str
    max_output_tokens: int = 8192
    temperature: float = 0.2
    request_timeout: int = 180


def _load_dotenv(path: Path) -> dict:
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_config(model_override: str | None = None) -> Config:
    cfg_path = ORCH_DIR / "config.json"
    if not cfg_path.exists():
        die(f"missing config: {cfg_path}")
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    models = raw.get("models") or []
    if not models:
        die("config.json has no models[]")

    entry = models[0]
    if model_override:
        matches = [m for m in models if model_override in (m.get("id"), m.get("name"))]
        if not matches:
            die(f"model {model_override!r} not in config.json")
        entry = matches[0]

    dotenv = _load_dotenv(ORCH_DIR / ".env")
    key = os.environ.get("QWEN_API_KEY") or dotenv.get("QWEN_API_KEY") or ""
    if not key:
        cfg_key = str(raw.get("apiKey", ""))
        # Ignore the VS Code-style ${input:...} placeholder.
        if cfg_key and not cfg_key.startswith("${"):
            key = cfg_key
    if not key:
        die(
            "no API key. Set it one of these ways:\n"
            f"  echo 'QWEN_API_KEY=sk-...' > {ORCH_DIR / '.env'}   (gitignored)\n"
            "  export QWEN_API_KEY=sk-...\n"
            f"  or replace \"apiKey\" in {cfg_path}"
        )

    # Configs copied from VS Code sometimes give a base URL, sometimes the full path.
    url = entry["url"].rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"

    per_turn = int(raw.get("maxTokensPerTurn", 8192))
    return Config(
        url=url,
        model=entry["id"],
        api_key=key,
        max_output_tokens=min(per_turn, int(entry.get("maxOutputTokens", per_turn))),
        temperature=float(raw.get("temperature", 0.2)),
        request_timeout=int(raw.get("requestTimeoutSeconds", 180)),
    )


def die(msg: str, code: int = 3):
    print(f"[qwen] error: {msg}", file=sys.stderr)
    sys.exit(code)


# --------------------------------------------------------------------------- #
# sandbox
# --------------------------------------------------------------------------- #

class Sandbox:
    """Confines file tools to a project root. Guardrail, not a jail -- see README."""

    def __init__(self, root: Path, read_only: bool):
        self.root = root.resolve()
        self.read_only = read_only

    def resolve(self, rel: str, must_exist: bool = False) -> Path:
        if rel is None:
            raise ValueError("path is required")
        p = Path(rel)
        p = p if p.is_absolute() else self.root / p
        # resolve() collapses .. and follows symlinks, so escapes are caught here.
        p = p.resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"path escapes project root: {rel}")
        if must_exist and not p.exists():
            raise ValueError(f"no such file: {self.rel(p)}")
        return p

    def rel(self, p: Path) -> str:
        try:
            return str(p.relative_to(self.root))
        except ValueError:
            return str(p)

    def check_writable(self):
        if self.read_only:
            raise ValueError("this run is --read-only; propose a diff in your report instead")


DENY_BASH = [
    (r"\bsudo\b", "sudo is not permitted"),
    (r"\brm\s+(-[a-zA-Z]*\s+)*(/|~|/\*)(\s|$)", "refusing to delete outside the project"),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r", "recursive force delete blocked"),
    (r"\bgit\s+push\b", "pushing is the orchestrator's call, not yours"),
    (r"\bgit\s+(reset\s+--hard|clean\s+-[a-zA-Z]*f)", "destructive git blocked"),
    (r"\bmkfs|\bdd\s+if=|\bshutdown\b|\breboot\b|\bhalt\b", "system-level command blocked"),
    (r"curl[^|;]*\|\s*(ba)?sh|wget[^|;]*\|\s*(ba)?sh", "pipe-to-shell blocked"),
    (r":\(\)\s*\{", "fork bomb blocked"),
    (r"\bchmod\s+-R\s+777\s+/", "blocked"),
    (r">\s*/dev/(sd|nvme|disk)", "raw device write blocked"),
]


def vet_bash(cmd: str) -> str | None:
    for pattern, reason in DENY_BASH:
        if re.search(pattern, cmd):
            return reason
    return None


# --------------------------------------------------------------------------- #
# tools
# --------------------------------------------------------------------------- #

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file (project-relative path). Use offset/limit for big files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer", "description": "1-indexed start line"},
                    "limit": {"type": "integer", "description": "max lines to read"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or fully overwrite a file. Parent dirs are created. Prefer edit_file for small changes.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace an exact string in a file. old_string must appear exactly once unless replace_all is true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                    "replace_all": {"type": "boolean"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List entries of a directory with sizes.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Find files by glob pattern, e.g. 'core/*.py' or '**/*.json'.",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Regex search file contents. Returns path:line:text matches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string"},
                    "glob": {"type": "string", "description": "filter filenames, e.g. '*.py'"},
                    "max_results": {"type": "integer"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command from the project root. Use this to run your code and tests -- verify your work before finishing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "description": "seconds, default 120, max 600"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Call exactly once when the task is complete or you are truly blocked. Ends the run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["done", "partial", "blocked"]},
                    "summary": {"type": "string", "description": "what you did, in plain prose"},
                    "files_changed": {"type": "array", "items": {"type": "string"}},
                    "verification": {
                        "type": "string",
                        "description": "the exact command you ran to prove it works, and its result",
                    },
                    "open_questions": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["status", "summary"],
            },
        },
    },
]

READ_ONLY_TOOLS = {"read_file", "list_dir", "glob", "grep", "finish"}


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    omitted = len(text) - limit
    return f"{text[:half]}\n\n... [{omitted} chars elided] ...\n\n{text[-half:]}"


def iter_files(base: Path):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            yield Path(dirpath) / fn


class Tools:
    def __init__(self, sb: Sandbox):
        self.sb = sb
        self.files_touched: set[str] = set()
        self.commands_run: list[str] = []

    def dispatch(self, name: str, args: dict) -> str:
        fn = getattr(self, f"t_{name}", None)
        if fn is None:
            return f"ERROR: unknown tool {name!r}"
        try:
            return fn(**args)
        except Finished:
            raise  # control flow, not an error -- must reach the run loop
        except TypeError as e:
            return f"ERROR: bad arguments for {name}: {e}"
        except ValueError as e:
            return f"ERROR: {e}"
        except Exception as e:  # noqa: BLE001 - tool errors go back to the model
            return f"ERROR: {type(e).__name__}: {e}"

    # -- read -------------------------------------------------------------- #

    def t_read_file(self, path: str, offset: int = 1, limit: int = 2000) -> str:
        p = self.sb.resolve(path, must_exist=True)
        if p.is_dir():
            return f"ERROR: {path} is a directory; use list_dir"
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = p.read_bytes()
            return (
                f"[binary or non-UTF-8 file, {len(raw)} bytes]\n"
                f"Try reading it with bash, e.g. python3 -c \"open('{path}','rb')...\" "
                "with the right encoding (GAEB 90 files are cp850)."
            )
        lines = text.splitlines()
        start = max(1, int(offset))
        chunk = lines[start - 1 : start - 1 + int(limit)]
        body = "\n".join(f"{start + i}\t{ln}" for i, ln in enumerate(chunk))
        tail = ""
        if start - 1 + len(chunk) < len(lines):
            tail = f"\n\n[file has {len(lines)} lines; showing {start}-{start + len(chunk) - 1}]"
        return truncate(body, MAX_TOOL_CHARS) + tail

    def t_list_dir(self, path: str = ".") -> str:
        p = self.sb.resolve(path, must_exist=True)
        if not p.is_dir():
            return f"ERROR: {path} is not a directory"
        rows = []
        for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name)):
            if entry.name in SKIP_DIRS:
                continue
            if entry.is_dir():
                rows.append(f"{entry.name}/")
            else:
                rows.append(f"{entry.name}  ({entry.stat().st_size} bytes)")
        return "\n".join(rows) or "(empty)"

    def t_glob(self, pattern: str, path: str = ".") -> str:
        base = self.sb.resolve(path, must_exist=True)
        hits = []
        for f in iter_files(base):
            rel = str(f.relative_to(base))
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(f.name, pattern):
                hits.append(self.sb.rel(f))
            if len(hits) >= 300:
                break
        return "\n".join(sorted(hits)) or f"no files matching {pattern!r}"

    def t_grep(self, pattern: str, path: str = ".", glob: str | None = None,
               max_results: int = 150) -> str:
        base = self.sb.resolve(path, must_exist=True)
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return f"ERROR: bad regex: {e}"
        out, scanned = [], 0
        targets = [base] if base.is_file() else iter_files(base)
        for f in targets:
            if glob and not fnmatch.fnmatch(f.name, glob):
                continue
            try:
                if f.stat().st_size > 8_000_000:
                    continue
                scanned += 1
                with f.open(encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if rx.search(line):
                            out.append(f"{self.sb.rel(f)}:{i}:{line.rstrip()[:300]}")
                            if len(out) >= int(max_results):
                                out.append(f"[capped at {max_results} matches]")
                                return truncate("\n".join(out), MAX_TOOL_CHARS)
            except OSError:
                continue
        if not out:
            return f"no matches for {pattern!r} ({scanned} files scanned)"
        return truncate("\n".join(out), MAX_TOOL_CHARS)

    # -- write ------------------------------------------------------------- #

    def t_write_file(self, path: str, content: str) -> str:
        self.sb.check_writable()
        p = self.sb.resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content, encoding="utf-8")
        self.files_touched.add(self.sb.rel(p))
        verb = "overwrote" if existed else "created"
        return f"{verb} {self.sb.rel(p)} ({len(content)} chars, {content.count(chr(10)) + 1} lines)"

    def t_edit_file(self, path: str, old_string: str, new_string: str,
                    replace_all: bool = False) -> str:
        self.sb.check_writable()
        p = self.sb.resolve(path, must_exist=True)
        text = p.read_text(encoding="utf-8")
        n = text.count(old_string)
        if n == 0:
            return ("ERROR: old_string not found. Read the file again -- it must match "
                    "character for character, including indentation.")
        if n > 1 and not replace_all:
            return (f"ERROR: old_string appears {n} times. Include more surrounding context "
                    "to make it unique, or pass replace_all=true.")
        text = text.replace(old_string, new_string) if replace_all \
            else text.replace(old_string, new_string, 1)
        p.write_text(text, encoding="utf-8")
        self.files_touched.add(self.sb.rel(p))
        return f"edited {self.sb.rel(p)} ({n if replace_all else 1} replacement(s))"

    def t_bash(self, command: str, timeout: int = 120) -> str:
        self.sb.check_writable()
        reason = vet_bash(command)
        if reason:
            return f"ERROR: blocked -- {reason}"
        timeout = max(1, min(int(timeout), 600))
        self.commands_run.append(command)
        env = dict(os.environ, QWEN_AGENT="1")
        try:
            proc = subprocess.run(
                command, shell=True, cwd=self.sb.root, env=env,
                capture_output=True, text=True, errors="replace", timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return f"ERROR: timed out after {timeout}s. Make the command faster or raise timeout."
        body = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        body = truncate(body.strip(), MAX_BASH_CHARS) or "(no output)"
        return f"exit={proc.returncode}\n{body}"

    def t_finish(self, status: str, summary: str, files_changed=None,
                 verification: str = "", open_questions=None) -> str:
        raise Finished(
            status=status, summary=summary,
            files_changed=list(files_changed or []),
            verification=verification,
            open_questions=list(open_questions or []),
        )


class Finished(Exception):
    def __init__(self, status, summary, files_changed, verification, open_questions):
        super().__init__(summary)
        self.status = status
        self.summary = summary
        self.files_changed = files_changed
        self.verification = verification
        self.open_questions = open_questions


# --------------------------------------------------------------------------- #
# api
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """\
You are a senior engineer working as a subagent. An orchestrator (Claude) has delegated \
one scoped task to you and will read your final report. You are doing the work, not \
advising on it.

Operating rules:
- Use tools. Never claim you read or changed a file unless a tool call did it.
- Read before you write. Match the conventions already in the code.
- VERIFY. Run the code with `bash` (python3 -c, a script, a test) and show that it works. \
An unverified claim is worse than an admitted failure.
- Stay inside the task. If you spot other problems, list them in open_questions rather \
than fixing them.
- Never ask the orchestrator a question mid-run -- you cannot receive an answer. Pick the \
most reasonable option, proceed, and record the assumption.
- Keep your reasoning short between tool calls. Act rather than narrate.
- When done (or genuinely blocked), call `finish` exactly once. Report honestly: if a test \
failed, say so and paste the output. A `partial` with real output beats a `done` that is a \
guess.

Project root is the working directory for every path and command. Paths are project-relative.
"""


def post_json(cfg: Config, payload: dict, attempt_log=None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        cfg.url, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
            "Accept": "application/json",
        },
    )
    delay = 2.0
    last = ""
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(req, timeout=cfg.request_timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:600]
            last = f"HTTP {e.code}: {detail}"
            retryable = e.code in (408, 409, 425, 429, 500, 502, 503, 504)
            if e.code in (401, 403):
                die(f"auth rejected by endpoint -- check QWEN_API_KEY.\n{last}")
            if e.code == 404:
                die(f"endpoint or model not found.\n{last}")
            if not retryable:
                die(last)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = f"{type(e).__name__}: {e}"
        if attempt < 5:
            msg = f"[qwen] transient failure ({last}); retry {attempt}/4 in {delay:.0f}s"
            print(msg, file=sys.stderr, flush=True)
            if attempt_log is not None:
                attempt_log.append(msg)
            time.sleep(delay)
            delay *= 2
    die(f"endpoint unreachable after 5 attempts. {last}")


TOOL_CALL_XML = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


def salvage_tool_calls(content: str) -> list[dict]:
    """Some Qwen deployments emit <tool_call>{...}</tool_call> in content instead of
    populating tool_calls. Recover those so the loop doesn't stall."""
    calls = []
    for i, m in enumerate(TOOL_CALL_XML.finditer(content or "")):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        name = obj.get("name") or obj.get("tool")
        args = obj.get("arguments", obj.get("args", {}))
        if not name:
            continue
        calls.append({
            "id": f"salvaged_{i}",
            "type": "function",
            "function": {
                "name": name,
                "arguments": args if isinstance(args, str) else json.dumps(args),
            },
        })
    return calls


def prune(messages: list[dict]) -> list[dict]:
    """Keep the transcript under budget by eliding the oldest tool results."""
    size = sum(len(json.dumps(m)) for m in messages)
    if size <= CONTEXT_CHAR_BUDGET:
        return messages
    for m in messages[1:-8]:
        if m.get("role") == "tool" and not m.get("_elided"):
            freed = len(m.get("content") or "")
            if freed < 400:
                continue
            m["content"] = "[older tool output elided to save context]"
            m["_elided"] = True
            size -= freed
            if size <= CONTEXT_CHAR_BUDGET:
                break
    return messages


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #

@dataclass
class RunLog:
    path: Path
    events: list = field(default_factory=list)

    def write(self, kind: str, **data):
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": kind, **data}
        self.events.append(rec)
        with (self.path / "transcript.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run(task_text: str, cfg: Config, sb: Sandbox, run_dir: Path,
        max_turns: int, quiet: bool) -> int:
    log = RunLog(run_dir)
    tools = Tools(sb)
    schemas = [s for s in TOOL_SCHEMAS
               if not sb.read_only or s["function"]["name"] in READ_ONLY_TOOLS]

    tree = tools.t_list_dir(".")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f"\nProject root contains:\n{tree}\n"},
        {"role": "user", "content": task_text},
    ]
    log.write("task", text=task_text, model=cfg.model, read_only=sb.read_only)

    usage_in = usage_out = 0
    note = (lambda *a, **k: None) if quiet else (
        lambda msg: print(msg, file=sys.stderr, flush=True))

    for turn in range(1, max_turns + 1):
        payload = {
            "model": cfg.model,
            "messages": [{k: v for k, v in m.items() if not k.startswith("_")}
                         for m in prune(messages)],
            "tools": schemas,
            "tool_choice": "auto",
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_output_tokens,
            "stream": False,
        }
        data = post_json(cfg, payload)
        usage = data.get("usage") or {}
        usage_in += usage.get("prompt_tokens", 0) or 0
        usage_out += usage.get("completion_tokens", 0) or 0

        choices = data.get("choices") or []
        if not choices:
            die(f"endpoint returned no choices: {json.dumps(data)[:400]}")
        msg = choices[0].get("message") or {}
        content = msg.get("content") or ""
        calls = msg.get("tool_calls") or []

        if not calls and content:
            calls = salvage_tool_calls(content)
            if calls:
                note(f"[qwen] turn {turn}: recovered {len(calls)} inline tool call(s)")

        assistant_msg = {"role": "assistant", "content": content}
        if calls:
            assistant_msg["tool_calls"] = calls
        messages.append(assistant_msg)
        log.write("assistant", turn=turn, content=content,
                  tool_calls=[c.get("function", {}).get("name") for c in calls])

        if not calls:
            # No tools and no finish: nudge once, then treat silence as a partial.
            if messages[-2].get("_nudged"):
                note(f"[qwen] turn {turn}: stopped calling tools; closing out as partial")
                write_result(run_dir, "partial", content or "(no output)", [], "", [],
                             turn, usage_in, usage_out, cfg, sb)
                return 2
            nudge = {
                "role": "user",
                "content": ("You did not call a tool. Either continue with tool calls, or "
                            "call `finish` with your report. Do not reply with prose only."),
                "_nudged": True,
            }
            assistant_msg["_nudged"] = True
            messages.append(nudge)
            continue

        for call in calls:
            fname = (call.get("function") or {}).get("name", "")
            raw_args = (call.get("function") or {}).get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError as e:
                result = f"ERROR: arguments were not valid JSON ({e}). Resend this call."
                args = {}
            else:
                preview = args.get("path") or args.get("pattern") or args.get("command") or ""
                note(f"[qwen] turn {turn}: {fname}({str(preview)[:90]})")
                try:
                    result = tools.dispatch(fname, args)
                except Finished as fin:
                    note(f"[qwen] {fin.status.upper()} after {turn} turns")
                    log.write("finish", status=fin.status, summary=fin.summary,
                              files_changed=fin.files_changed, verification=fin.verification,
                              open_questions=fin.open_questions)
                    write_result(run_dir, fin.status, fin.summary,
                                 fin.files_changed or sorted(tools.files_touched),
                                 fin.verification, fin.open_questions,
                                 turn, usage_in, usage_out, cfg, sb)
                    return 0 if fin.status == "done" else 1

            log.write("tool", turn=turn, name=fname, args=args, result=truncate(result, 4000))
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id") or f"call_{turn}",
                "content": truncate(result, MAX_TOOL_CHARS),
            })

    note(f"[qwen] hit max turns ({max_turns}) without finishing")
    write_result(run_dir, "partial", f"Ran out of turns ({max_turns}) before calling finish.",
                 sorted(tools.files_touched), "", [], max_turns, usage_in, usage_out, cfg, sb)
    return 2


def write_result(run_dir: Path, status: str, summary: str, files_changed, verification,
                 open_questions, turns: int, tok_in: int, tok_out: int,
                 cfg: Config, sb: Sandbox):
    lines = [
        f"# Run result: {status}",
        "",
        f"- model: `{cfg.model}`",
        f"- turns: {turns}",
        f"- tokens: {tok_in} in / {tok_out} out",
        f"- root: `{sb.root}`" + ("  (read-only)" if sb.read_only else ""),
        "",
        "## Summary",
        "",
        summary.strip() or "(none)",
        "",
        "## Files changed",
        "",
    ]
    lines += [f"- `{f}`" for f in files_changed] or ["(none reported)"]
    lines += ["", "## Verification", "", (verification or "").strip() or "(none reported)"]
    if open_questions:
        lines += ["", "## Open questions", ""] + [f"- {q}" for q in open_questions]
    lines.append("")
    (run_dir / "result.md").write_text("\n".join(lines), encoding="utf-8")
    (run_dir / "meta.json").write_text(json.dumps({
        "status": status, "turns": turns, "tokens_in": tok_in, "tokens_out": tok_out,
        "model": cfg.model, "files_changed": files_changed,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    print(str(run_dir / "result.md"))


def probe(cfg: Config) -> int:
    print(f"[qwen] POST {cfg.url}\n[qwen] model {cfg.model}\n"
          f"[qwen] key  {cfg.api_key[:6]}...{cfg.api_key[-4:]} ({len(cfg.api_key)} chars)",
          file=sys.stderr)
    # Generous max_tokens: reasoning models spend tokens before emitting content,
    # and a tight cap returns content=None with finish_reason=length.
    data = post_json(cfg, {
        "model": cfg.model,
        "messages": [{"role": "user", "content": "Reply with exactly: PONG"}],
        "max_tokens": 512,
        "stream": False,
    })
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = msg.get("content") or ""
    print(f"[qwen] reply: {content.strip()[:120]!r} (finish={choice.get('finish_reason')})",
          file=sys.stderr)
    if msg.get("reasoning") or (data.get("usage") or {}).get(
            "completion_tokens_details", {}).get("reasoning_tokens"):
        print("[qwen] note: reasoning model -- it spends tokens thinking before answering",
              file=sys.stderr)
    if not content.strip():
        print("[qwen] warning: empty content. If finish=length, raise maxTokensPerTurn.",
              file=sys.stderr)

    tool_data = post_json(cfg, {
        "model": cfg.model,
        "messages": [{"role": "user",
                      "content": "List the project root using the list_dir tool."}],
        "tools": [s for s in TOOL_SCHEMAS if s["function"]["name"] == "list_dir"],
        "tool_choice": "auto",
        "max_tokens": 512,
        "stream": False,
    })
    tmsg = (tool_data.get("choices") or [{}])[0].get("message") or {}
    if tmsg.get("tool_calls"):
        print("[qwen] tool calling: OK (native)", file=sys.stderr)
    elif salvage_tool_calls(tmsg.get("content") or ""):
        print("[qwen] tool calling: OK (inline <tool_call>, salvage path handles it)",
              file=sys.stderr)
    else:
        print("[qwen] tool calling: NOT WORKING -- model replied with prose. "
              "The agent loop will stall; check the endpoint's tool support.", file=sys.stderr)
        return 1
    print("[qwen] probe passed", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="qwen-agent", description="Run a delegated task on the Qwen subagent.")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--task", help="path to a task markdown file")
    src.add_argument("--prompt", help="inline task text (for small jobs)")
    ap.add_argument("--workdir", default=str(DEFAULT_ROOT), help="sandbox root")
    ap.add_argument("--run-id", help="run directory name (default: timestamp-taskname)")
    ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--model", help="model id/name from config.json")
    ap.add_argument("--read-only", action="store_true", help="disable write_file/edit_file/bash")
    ap.add_argument("--quiet", action="store_true", help="suppress per-turn progress")
    ap.add_argument("--probe", action="store_true", help="test endpoint, key and tool calling")
    args = ap.parse_args()

    cfg = load_config(args.model)
    if args.probe:
        return probe(cfg)

    if args.task:
        tp = Path(args.task)
        if not tp.is_absolute():
            tp = Path.cwd() / tp
            if not tp.exists():
                tp = ORCH_DIR / "tasks" / args.task
        if not tp.exists():
            die(f"task file not found: {args.task}", 3)
        task_text = tp.read_text(encoding="utf-8")
        stem = tp.stem
    elif args.prompt:
        task_text = args.prompt
        stem = "inline"
    else:
        if sys.stdin.isatty():
            die("give me work: --task FILE, --prompt TEXT, or pipe the task on stdin", 3)
        task_text = sys.stdin.read()
        stem = "stdin"
    if not task_text.strip():
        die("task is empty", 3)

    root = Path(args.workdir)
    if not root.is_dir():
        die(f"workdir is not a directory: {root}", 3)
    sb = Sandbox(root, args.read_only)

    run_id = args.run_id or f"{datetime.now().strftime('%m%d-%H%M%S')}-{stem}"
    run_dir = ORCH_DIR / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if not args.quiet:
        print(f"[qwen] run {run_id} | model {cfg.model} | root {sb.root}",
              file=sys.stderr, flush=True)

    try:
        return run(task_text, cfg, sb, run_dir, args.max_turns, args.quiet)
    except KeyboardInterrupt:
        print("\n[qwen] interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
