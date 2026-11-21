#!/usr/bin/env python3
"""Recover the lost app.py from the still-running Streamlit process.

    sudo python3 recover_app.py

Second attempt. The first anchored on strings that also appear in the tender
data, so it dumped 600 KB windows of Leistungsverzeichnis text and only caught
~1 KB of source. This version anchors on strings that can ONLY be source, then
expands outward while the bytes stay printable, so it captures whole blocks
instead of fixed windows.

**Do not stop the Streamlit process** — it is the only remaining copy.
"""

import re
import subprocess
import sys

# Strings that appear in app.py and nowhere in the tender data.
ANCHORS = [
    b'PAGES = ("Tender"',
    b"def parse_path(path: str):",
    b"def section_groups",
    b"st.set_page_config(",
    b"selected_group_key",
    b"def section_kalkulation",
    b"def section_tricky",
    b"def section_items",
    b"initial_sidebar_state",
]

PRINTABLE = set(bytes(range(32, 127)) + b"\n\r\t")


def streamlit_pid() -> int:
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        return int(sys.argv[1])
    try:
        out = subprocess.check_output(["pgrep", "-f", "streamlit run"], text=True)
    except subprocess.CalledProcessError:
        sys.exit("No running 'streamlit run' process — the copy is gone.")
    return int(out.split()[0])


def expand(buf: bytes, hit: int, limit: int = 120_000) -> bytes:
    """Grow outward from `hit` while the bytes stay plausible source."""
    start = hit
    while start > 0 and hit - start < limit and buf[start - 1] in PRINTABLE:
        start -= 1
    end = hit
    n = len(buf)
    while end < n and end - hit < limit and buf[end] in PRINTABLE:
        end += 1
    return buf[start:end]


def main() -> int:
    pid = streamlit_pid()
    print(f"scanning PID {pid} for app.py source …")

    try:
        maps = open(f"/proc/{pid}/maps").read().splitlines()
        mem = open(f"/proc/{pid}/mem", "rb", buffering=0)
    except PermissionError:
        sys.exit(f"Permission denied. Try: sudo python3 recover_app.py {pid}")

    found, scanned = [], 0
    for line in maps:
        parts = line.split()
        if len(parts) < 2 or "r" not in parts[1]:
            continue
        if any(x in line for x in ("/usr/lib", "/usr/bin", ".so", "[vvar]",
                                   "[vdso]", "[vsyscall]")):
            continue
        try:
            lo, hi = (int(x, 16) for x in parts[0].split("-"))
        except ValueError:
            continue
        if hi - lo > 600 * 1024 * 1024:
            continue
        try:
            mem.seek(lo)
            buf = mem.read(hi - lo)
        except (OSError, ValueError):
            continue
        scanned += hi - lo
        for anchor in ANCHORS:
            pos = buf.find(anchor)
            while pos != -1:
                block = expand(buf, pos)
                if len(block) > 400:
                    found.append(block)
                pos = buf.find(anchor, pos + 1)

    print(f"scanned {scanned / 1e6:.0f} MB, {len(found)} source blocks")
    if not found:
        print("Nothing. Do NOT restart Streamlit; tell Claude.")
        return 1

    # Deduplicate, keeping the longest version of each distinct block.
    best: dict[str, bytes] = {}
    for block in found:
        text = block.decode("utf-8", errors="ignore")
        key = re.sub(r"\s+", " ", text)[:120]
        if key not in best or len(block) > len(best[key]):
            best[key] = block

    ordered = sorted(best.values(), key=len, reverse=True)
    total = sum(len(b) for b in ordered)
    with open("app_recovered.py", "w", encoding="utf-8") as fh:
        fh.write("# RECOVERED FROM PROCESS MEMORY - fragments, longest first.\n")
        fh.write("# Stitch by hand; the original was ~23,000 characters.\n\n")
        for block in ordered:
            fh.write(block.decode("utf-8", errors="ignore"))
            fh.write("\n\n# " + "-" * 68 + "\n\n")

    print(f"wrote app_recovered.py — {len(ordered)} blocks, {total:,} chars "
          f"(original ~23,000)")
    for block in ordered[:5]:
        head = block.decode("utf-8", errors="ignore").strip().splitlines()[:1]
        print(f"   {len(block):>6} chars  {head[0][:64] if head else ''!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
