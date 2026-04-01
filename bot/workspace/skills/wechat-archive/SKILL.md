---
name: wechat-archive
description: Reindex, search, summarize, and analyze the WeChat chat archive under /home/nx/chat_archive. Use when the user asks to summarize a date like 2026-03-30, analyze a specific公众号/微信群/聊天对象, search topics across the archive, compare recent updates, or refresh the OpenViking index for the archive.
---

# WeChat Archive

Use this skill for the WeChat archive workflow backed by OpenViking.

## Scope

- Source archive: `/home/nx/chat_archive`
- Exported Markdown corpus: `/home/nx/chat_archive/.openviking_export`
- OpenViking target URI: `viking://resources/wechat_archive`
- Index/search entrypoint: [examples/wechat_archive_index.py](/home/nx/github/OpenViking/examples/wechat_archive_index.py)
- File locator helper: [archive_locator.py](/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/scripts/archive_locator.py)

## Trigger Phrases

Use this skill immediately when the user asks any of:

- “总结 2026-03-30 的微信内容”
- “分析 动点科技/人民日报/某个公众号 最近发了什么”
- “检索聊天归档里关于自动驾驶/机器人/SOTIF 的内容”
- “比较 3 月 30 号和 3 月 31 号的新增信息”
- “刷新/重建 微信聊天索引”

## Core Workflows

### 1. Refresh index

Default to asynchronous indexing unless the user explicitly asks to wait.

```bash
./.venv/bin/python examples/wechat_archive_index.py index \
  --source /home/nx/chat_archive \
  --export-root /home/nx/chat_archive/.openviking_export \
  --target viking://resources/wechat_archive
```

Synchronous run:

```bash
./.venv/bin/python examples/wechat_archive_index.py index \
  --source /home/nx/chat_archive \
  --export-root /home/nx/chat_archive/.openviking_export \
  --target viking://resources/wechat_archive \
  --wait --timeout 600
```

Notes:

- The export layer is rebuilt each run.
- OpenViking indexing is incremental because the same `target` is reused.
- If another embedded OpenViking job is already running, wait for it to finish or switch to HTTP mode with `--http-url`.

### 2. Semantic topic search

Use OpenViking semantic search first when the user is asking for concept or topic retrieval.

```bash
./.venv/bin/python examples/wechat_archive_index.py search "自动驾驶 测试" \
  --target viking://resources/wechat_archive
```

If semantic search is blocked because an indexing job is still holding the embedded service, fall back to file-level grep on the exported Markdown corpus:

```bash
./.venv/bin/python bot/workspace/skills/wechat-archive/scripts/archive_locator.py topic-grep "自动驾驶"
```

### 3. Daily summary

Locate all files for a date, read the matched daily Markdown files, then summarize by:

- major topics
- repeated stories across chats
- notable公众号/群聊
- links worth opening

Locate files:

```bash
./.venv/bin/python bot/workspace/skills/wechat-archive/scripts/archive_locator.py daily-files 2026-03-30
```

### 4. Single chat / official account analysis

Find the chat first, then read its `chat.md` and selected `days/*.md`.

```bash
./.venv/bin/python bot/workspace/skills/wechat-archive/scripts/archive_locator.py chat-files "动点科技"
```

Recommended output structure:

- time range covered
- main topics
- recurring themes
- representative messages or linked articles
- concise conclusion

### 5. Compare dates

Use the locator twice, one date each, then compare:

- new topics
- disappearing topics
- accounts that became more active
- overlapping stories

## File Discovery Rules

- Prefer the exported Markdown corpus for summaries and analysis.
- Use linked `document.md` files when a message points to a copied article and the article body is useful.
- Prefer `chat.md` for overview and `days/YYYY-MM-DD.md` for evidence.
- Use topic grep before reading large numbers of files.

## Operational Rules

- If `/home/nx/chat_archive/.openviking_export` does not exist or is clearly stale, run the index command first.
- For “today/yesterday” style requests, resolve the absolute date in the response.
- For specific chat analysis, include the exact matched chat name.
- When multiple chats match a keyword, present the candidate list and state which one you analyzed.
