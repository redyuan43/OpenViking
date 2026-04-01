#!/usr/bin/env python3
"""Locate exported WeChat archive files for analysis workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_EXPORT_ROOT = Path("/home/nx/chat_archive/.openviking_export")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Locate WeChat archive export files.")
    parser.add_argument(
        "--export-root",
        default=str(DEFAULT_EXPORT_ROOT),
        help="Export root produced by examples/wechat_archive_index.py index",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("chats", help="List all chats with chat.md paths")

    daily = subparsers.add_parser("daily-files", help="List all daily files for a date")
    daily.add_argument("date", help="Date in YYYY-MM-DD format")
    daily.add_argument("--chat", default=None, help="Optional chat name filter")

    chat = subparsers.add_parser("chat-files", help="Find chat overview and daily files")
    chat.add_argument("query", help="Substring to match against chat directory names")

    grep = subparsers.add_parser("topic-grep", help="Text grep over exported markdown")
    grep.add_argument("query", help="Substring to search for")
    grep.add_argument("--date", default=None, help="Optional date filter")
    grep.add_argument("--chat", default=None, help="Optional chat filter")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    export_root = Path(args.export_root).expanduser().resolve()

    if not export_root.exists():
        raise SystemExit(f"Export root not found: {export_root}")

    if args.command == "chats":
        return cmd_chats(export_root)
    if args.command == "daily-files":
        return cmd_daily_files(export_root, args.date, args.chat)
    if args.command == "chat-files":
        return cmd_chat_files(export_root, args.query)
    if args.command == "topic-grep":
        return cmd_topic_grep(export_root, args.query, args.date, args.chat)
    parser.error(f"Unsupported command: {args.command}")
    return 2


def cmd_chats(export_root: Path) -> int:
    chats_root = export_root / "chats"
    for chat_dir in sorted(p for p in chats_root.iterdir() if p.is_dir()):
        chat_md = chat_dir / "chat.md"
        if chat_md.exists():
            print(chat_dir.name)
            print(f"  {chat_md}")
    return 0


def cmd_daily_files(export_root: Path, date: str, chat_filter: str | None) -> int:
    matched = []
    for path in sorted(export_root.glob(f"chats/*/days/{date}.md")):
        if chat_filter and chat_filter.lower() not in path.parts[-3].lower():
            continue
        matched.append(path)

    if not matched:
        print("No daily files found.")
        return 0

    for path in matched:
        print(path)
    return 0


def cmd_chat_files(export_root: Path, query: str) -> int:
    query_lower = query.lower()
    matched = []
    for chat_dir in sorted((export_root / "chats").iterdir()):
        if not chat_dir.is_dir():
            continue
        if query_lower not in chat_dir.name.lower():
            continue
        matched.append(chat_dir)

    if not matched:
        print("No chats matched.")
        return 0

    for chat_dir in matched:
        print(chat_dir.name)
        print(f"  overview: {chat_dir / 'chat.md'}")
        for day_file in sorted((chat_dir / 'days').glob("*.md")):
            print(f"  day: {day_file}")
    return 0


def cmd_topic_grep(export_root: Path, query: str, date: str | None, chat_filter: str | None) -> int:
    query_lower = query.lower()
    matches = []
    for path in iter_markdown_files(export_root, date=date, chat_filter=chat_filter):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if query_lower not in text.lower():
            continue
        snippet = first_matching_line(text, query_lower)
        matches.append({"path": str(path), "snippet": snippet})

    if not matches:
        print("No matches found.")
        return 0

    for item in matches:
        print(item["path"])
        if item["snippet"]:
            print(f"  {item['snippet']}")
    return 0


def iter_markdown_files(export_root: Path, date: str | None, chat_filter: str | None):
    chats_root = export_root / "chats"
    for chat_dir in sorted(p for p in chats_root.iterdir() if p.is_dir()):
        if chat_filter and chat_filter.lower() not in chat_dir.name.lower():
            continue
        if date:
            day_file = chat_dir / "days" / f"{date}.md"
            if day_file.exists():
                yield day_file
            continue
        overview = chat_dir / "chat.md"
        if overview.exists():
            yield overview
        for day_file in sorted((chat_dir / "days").glob("*.md")):
            yield day_file


def first_matching_line(text: str, query_lower: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if query_lower in stripped.lower():
            return stripped
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
