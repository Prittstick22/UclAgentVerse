#!/usr/bin/env python3
"""Agent message board: one markdown file per message in board/messages/.

No dependencies. See board/README.md.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MESSAGES = ROOT / "board" / "messages"
NAMES = {"dev", "cem", "jin", "mo", "all"}
TYPES = {"question", "handoff", "missing", "blocker", "contract-change", "fyi"}
STATUSES = {"open", "answered", "resolved"}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "message"


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta: dict = {"path": path}
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return meta
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.split("#", 1)[0].strip()
    body = m.group(2)
    title = re.search(r"^# (.+)$", body, re.M)
    meta["title"] = title.group(1).strip() if title else path.stem
    meta["replies"] = body.count("\n### ")
    return meta


def set_status(path: Path, status: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^status: .*$", f"status: {status}", text, count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")


def read_body(arg: str | None) -> str:
    if arg == "-":
        return sys.stdin.read().strip()
    return (arg or "").strip()


def cmd_new(a: argparse.Namespace) -> None:
    if a.sender not in NAMES - {"all"} or a.to not in NAMES:
        sys.exit(f"--from must be one of {sorted(NAMES - {'all'})}; --to one of {sorted(NAMES)}")
    if a.type not in TYPES:
        sys.exit(f"--type must be one of {sorted(TYPES)}")
    MESSAGES.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    mid = f"{stamp}-{a.sender}-to-{a.to}-{slugify(a.title)}"
    path = MESSAGES / f"{mid}.md"
    body = read_body(a.body) or "<What you need, why, exact file paths / function or field names / shapes, and by when.>"
    issue = a.issue if a.issue else ""
    path.write_text(
        f"---\nid: {mid}\nfrom: {a.sender}\nto: {a.to}\ntype: {a.type}\nstatus: open\n"
        f"issue: {issue}\ncreated: {now()}\n---\n# {a.title}\n\n{body}\n\n## Replies\n",
        encoding="utf-8",
    )
    print(path.relative_to(ROOT))
    print("Next: git add board && git commit -m 'board: " + a.title.replace("'", "") + "' && git push")


def cmd_list(a: argparse.Namespace) -> None:
    rows = [parse(p) for p in sorted(MESSAGES.glob("*.md"))]
    if a.to:
        rows = [r for r in rows if r.get("to") in {a.to, "all"}]
    if a.sender:
        rows = [r for r in rows if r.get("from") == a.sender]
    if a.open:
        rows = [r for r in rows if r.get("status") != "resolved"]
    if not rows:
        print("No messages.")
        return
    for r in rows:
        issue = f" #{r['issue']}" if r.get("issue") else ""
        print(
            f"[{r.get('status', '?'):8}] {r.get('type', '?'):15} {r.get('from', '?')}→{r.get('to', '?'):4}"
            f"{issue}  {r.get('title', '')}  ({r.get('replies', 0)} replies)\n           {r['path'].relative_to(ROOT)}"
        )


def resolve_path(p: str) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = (Path.cwd() / path) if (Path.cwd() / path).exists() else ROOT / path
    if not path.exists():
        matches = list(MESSAGES.glob(f"*{p}*"))
        if len(matches) == 1:
            return matches[0]
        sys.exit(f"Message not found: {p}")
    return path


def cmd_show(a: argparse.Namespace) -> None:
    print(resolve_path(a.file).read_text(encoding="utf-8"))


def cmd_reply(a: argparse.Namespace) -> None:
    path = resolve_path(a.file)
    body = read_body(a.body)
    if not body:
        sys.exit("--body required (or --body - for stdin)")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n### {a.sender} · {now()}\n{body}\n")
    if parse(path).get("status") == "open":
        set_status(path, "answered")
    print(f"Replied to {path.relative_to(ROOT)}")


def cmd_resolve(a: argparse.Namespace) -> None:
    path = resolve_path(a.file)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n### {a.sender} · {now()}\nResolved.\n")
    set_status(path, "resolved")
    print(f"Resolved {path.relative_to(ROOT)}")


def main() -> None:
    p = argparse.ArgumentParser(description="Agent message board")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new")
    n.add_argument("--from", dest="sender", required=True)
    n.add_argument("--to", required=True)
    n.add_argument("--type", required=True)
    n.add_argument("--title", required=True)
    n.add_argument("--issue", type=int)
    n.add_argument("--body")
    n.set_defaults(func=cmd_new)

    ls = sub.add_parser("list")
    ls.add_argument("--to")
    ls.add_argument("--from", dest="sender")
    ls.add_argument("--open", action="store_true")
    ls.set_defaults(func=cmd_list)

    s = sub.add_parser("show")
    s.add_argument("file")
    s.set_defaults(func=cmd_show)

    r = sub.add_parser("reply")
    r.add_argument("file")
    r.add_argument("--from", dest="sender", required=True)
    r.add_argument("--body")
    r.set_defaults(func=cmd_reply)

    rs = sub.add_parser("resolve")
    rs.add_argument("file")
    rs.add_argument("--from", dest="sender", required=True)
    rs.set_defaults(func=cmd_resolve)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
