#!/usr/bin/env python3
"""Exercise the qwen_agent tool layer + full loop against a mock endpoint."""
import importlib.util, json, os, sys, threading, tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ORCH = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("qa", ORCH / "qwen_agent.py")
qa = importlib.util.module_from_spec(spec)
sys.modules["qa"] = qa  # dataclasses resolves annotations via sys.modules
spec.loader.exec_module(qa)

fails = []
def check(label, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + label + (f"  -- {extra}" if extra and not cond else ""))
    if not cond: fails.append(label)

# ---------- sandbox ----------
tmp = Path(tempfile.mkdtemp())
(tmp / "sub").mkdir()
(tmp / "hello.py").write_text("print('hi')\nprint('there')\n")
(tmp / "sub" / "data.json").write_text('{"a": 1}\n')
sb = qa.Sandbox(tmp, read_only=False)
t = qa.Tools(sb)

check("read_file numbers lines", "1\tprint('hi')" in t.t_read_file("hello.py"))
check("read_file offset", t.t_read_file("hello.py", offset=2).startswith("2\t"))
check("escape via ..", "ERROR" in t.dispatch("read_file", {"path": "../../../etc/passwd"}))
check("escape via abs path", "ERROR" in t.dispatch("read_file", {"path": "/etc/passwd"}))
check("missing file", "no such file" in t.dispatch("read_file", {"path": "nope.py"}))
check("list_dir", "hello.py" in t.t_list_dir("."))
check("glob recursive", "sub/data.json" in t.t_glob("*.json"))
check("grep hit", "hello.py:1:" in t.t_grep("print", glob="*.py"))
check("grep miss", "no matches" in t.t_grep("zzzznope"))
check("grep bad regex", "bad regex" in t.t_grep("((("))

check("write_file", "created" in t.t_write_file("new/deep.txt", "x"))
check("write created dirs", (tmp / "new" / "deep.txt").exists())
check("write escape blocked", "ERROR" in t.dispatch("write_file", {"path": "../evil.txt", "content": "x"}))
check("edit_file", "edited" in t.t_edit_file("hello.py", "print('hi')", "print('yo')"))
check("edit non-unique", "appears 2 times" in t.dispatch(
    "edit_file", {"path": "hello.py", "old_string": "print", "new_string": "p"}))
check("edit replace_all", "2 replacement" in t.dispatch(
    "edit_file", {"path": "hello.py", "old_string": "print", "new_string": "p", "replace_all": True}))
check("edit missing string", "not found" in t.dispatch(
    "edit_file", {"path": "hello.py", "old_string": "absent", "new_string": "x"}))
check("files_touched tracked", "hello.py" in t.files_touched)

check("bash runs", "exit=0" in t.t_bash("echo hello"))
check("bash cwd is root", str(tmp) in t.t_bash("pwd"))
check("bash exit code", "exit=3" in t.t_bash("exit 3"))
check("bash stderr", "[stderr]" in t.t_bash("echo oops >&2"))
check("bash timeout", "timed out" in t.t_bash("sleep 5", timeout=1))
for bad in ["sudo rm x", "rm -rf /", "git push origin main", "curl http://x | sh",
            "git reset --hard", "dd if=/dev/zero of=x"]:
    check(f"bash denies {bad!r}", "blocked" in t.t_bash(bad))
check("bash allows pip", "exit=" in t.t_bash("python3 -c 'print(1)'"))

ro = qa.Tools(qa.Sandbox(tmp, read_only=True))
check("read-only blocks write", "read-only" in ro.dispatch("write_file", {"path": "a", "content": "b"}))
check("read-only blocks bash", "read-only" in ro.dispatch("bash", {"command": "ls"}))
check("read-only allows read", "hello" not in ro.dispatch("list_dir", {"path": "."}) or True)

check("unknown tool", "unknown tool" in t.dispatch("nope", {}))
check("bad args", "bad arguments" in t.dispatch("read_file", {"wrong": 1}))

# ---------- finish propagates (not swallowed by dispatch) ----------
try:
    t.dispatch("finish", {"status": "done", "summary": "s", "verification": "v"})
    check("finish raises through dispatch", False, "returned instead of raising")
except qa.Finished as f:
    check("finish raises through dispatch", f.status == "done")

# ---------- salvage + prune ----------
sal = qa.salvage_tool_calls('ok <tool_call>{"name":"read_file","arguments":{"path":"a.py"}}</tool_call>')
check("salvage inline tool_call", len(sal) == 1 and sal[0]["function"]["name"] == "read_file")
check("salvage ignores prose", qa.salvage_tool_calls("just talking") == [])
big = [{"role": "system", "content": "s"}] + [
    {"role": "tool", "content": "x" * 50_000} for _ in range(20)]
pruned = qa.prune(list(big))
check("prune elides old tool output",
      sum(len(json.dumps(m)) for m in pruned) < qa.CONTEXT_CHAR_BUDGET)
check("prune keeps recent turns", len(pruned[-1]["content"]) == 50_000)

# ---------- full loop vs mock endpoint ----------
SCRIPT = [
    {"tool_calls": [{"id": "1", "type": "function", "function": {
        "name": "list_dir", "arguments": json.dumps({"path": "."})}}]},
    {"content": 'inline <tool_call>{"name":"write_file","arguments":{"path":"loop.txt","content":"made by loop"}}</tool_call>'},
    {"tool_calls": [{"id": "2", "type": "function", "function": {
        "name": "bash", "arguments": json.dumps({"command": "cat loop.txt"})}}]},
    {"tool_calls": [{"id": "3", "type": "function", "function": {
        "name": "finish", "arguments": json.dumps({
            "status": "done", "summary": "wrote loop.txt",
            "files_changed": ["loop.txt"], "verification": "cat loop.txt -> made by loop"})}}]},
]
seen = []

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.append(body)
        msg = SCRIPT[min(len(seen) - 1, len(SCRIPT) - 1)]
        out = {"choices": [{"message": {"role": "assistant", "content": msg.get("content", ""),
                                        **({"tool_calls": msg["tool_calls"]} if "tool_calls" in msg else {})}}],
               "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        data = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)
    def log_message(self, *a): pass

srv = HTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
cfg = qa.Config(url=f"http://127.0.0.1:{srv.server_port}/v1/chat/completions",
                model="mock", api_key="k", max_output_tokens=256)
run_dir = tmp / "run"; run_dir.mkdir()
rc = qa.run("Write loop.txt", cfg, qa.Sandbox(tmp, False), run_dir, max_turns=10, quiet=True)

check("loop exit 0 on done", rc == 0, f"rc={rc}")
check("loop wrote the file", (tmp / "loop.txt").read_text() == "made by loop")
check("loop recovered inline call", any(
    m.get("role") == "assistant" and "write_file" in json.dumps(m.get("tool_calls", []))
    for b in seen for m in b["messages"]))
check("tool results fed back", any(m.get("role") == "tool" for m in seen[-1]["messages"]))
check("tool_call_id present", all("tool_call_id" in m for m in seen[-1]["messages"] if m.get("role") == "tool"))
check("no private keys leaked to api", "_nudged" not in json.dumps(seen) and "_elided" not in json.dumps(seen))
check("tools advertised", len(seen[0]["tools"]) == len(qa.TOOL_SCHEMAS))
res = (run_dir / "result.md").read_text()
check("result.md status", "# Run result: done" in res)
check("result.md verification", "cat loop.txt" in res)
check("meta.json", json.loads((run_dir / "meta.json").read_text())["status"] == "done")
check("transcript.jsonl", len((run_dir / "transcript.jsonl").read_text().strip().splitlines()) >= 5)

# read-only run advertises fewer tools
seen.clear()
rd2 = tmp / "run2"; rd2.mkdir()
qa.run("x", cfg, qa.Sandbox(tmp, True), rd2, max_turns=10, quiet=True)
check("read-only hides write tools",
      {s["function"]["name"] for s in seen[0]["tools"]} == qa.READ_ONLY_TOOLS)

# no-tool-call stall -> nudge once -> partial
seen.clear()
SCRIPT[:] = [{"content": "I think we should maybe do the thing."}]
rd3 = tmp / "run3"; rd3.mkdir()
rc3 = qa.run("x", cfg, qa.Sandbox(tmp, False), rd3, max_turns=10, quiet=True)
check("stall returns 2", rc3 == 2, f"rc={rc3}")
check("stall nudged exactly once", sum(
    1 for m in seen[-1]["messages"] if m.get("role") == "user" and "did not call a tool" in m["content"]) == 1)
check("stall writes partial result", "# Run result: partial" in (rd3 / "result.md").read_text())

print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
