---
name: wechat-archive
description: Reindex, search, summarize, and analyze the WeChat chat archive under /home/nx/chat_archive. Use when the user asks to summarize one day, analyze a specific 公众号/微信群/聊天对象, search topics like 自动驾驶/FSD/机器人, compare dates, build a topic memory card, generate watchlist alerts, or refresh the OpenViking archive index.
---

# WeChat Archive

Use this skill for the unified WeChat archive workflow backed by OpenViking.

## Scope

- Source archive: `/home/nx/chat_archive`
- Exported Markdown corpus: `/home/nx/chat_archive/.openviking_export`
- OpenViking target URI: `viking://resources/wechat_archive`
- Embedded workspace: `/home/nx/.openviking-wechat-archive-local-gpu`
- HTTP search endpoint: `http://127.0.0.1:1934`
- Local embedding endpoint: `http://127.0.0.1:8766/v1`
- Local rerank endpoint: `http://127.0.0.1:8765/v1/rerank`
- Main entrypoint: [examples/wechat_archive_agent.py](/home/nx/github/OpenViking/examples/wechat_archive_agent.py)
- Wrapper: [run_wechat_archive_agent.sh](/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh)
- File locator helper: [archive_locator.py](/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/scripts/archive_locator.py)

## Trigger Phrases

Use this skill immediately when the user asks any of:

- “总结 2026-03-30 的微信内容”
- “分析 动点科技/人民日报/某个公众号 最近发了什么”
- “检索聊天归档里关于自动驾驶/机器人/SOTIF 的内容”
- “比较 3 月 30 号和 3 月 31 号的新增信息”
- “刷新/重建 微信聊天索引”
- “做一个 topic memory card / watchlist alert”

## Project Capabilities

- Build/rebuild export + semantic index (`index`)
- Semantic search and query routing (`search`)
- Daily summary and single-chat deep analysis
- Topic analysis, hotspot mining, timeline analysis
- Day compare, sender distribution, linked-article ranking
- Topic memory card / watchlist alert generation with durable report indexing
- Read-only analysis over an explicit OpenViking HTTP endpoint (`--http-url`) for cross-device usage
- Auto-start the default local OpenViking HTTP server for read-only commands when no explicit `--http-url` is provided
- Service-oriented deployment with local embed (`8766`), rerank (`8765`), and archive HTTP (`1934`) processes
- File-level discovery via locator helper for fallback and fast operations

## WeChat Data Model and Coverage

Current project reads WeChat archive input from:

- `/home/nx/chat_archive/chats/<chat>/chat_meta.json`
- `/home/nx/chat_archive/chats/<chat>/messages/*.jsonl`

Export artifacts used by downstream search and analysis:

- Root export summary: `README.md`
- Per-chat overview: `chats/<chat>/chat.md`
- Per-day evidence files: `chats/<chat>/days/YYYY-MM-DD.md`
- Copied linked articles as local `document.md` files

Chat-level metadata retained in the export:

- `chat_id`
- `chat_type`
- `aliases`
- `first_seen_ts`
- `last_seen_ts`
- `message_count`

Per-message fields retained or rendered into the exported Markdown:

- Timestamp
- Sender
- `type_label (base_type/sub_type)`
- `message_key`
- `event_kind`
- `first_seen_ts`
- `processed_ts`
- Primary `url`
- `analysis`
- `linked_doc_summary`
- `linked_doc`

Current high-confidence coverage:

- Text messages
- Shared links with copied `document.md`
- Voice messages as typed message records
- System notices as typed message records

Current limits and boundaries:

- Remote HTTP mode is mainly for read operations; `index` remains a service-machine workflow
- High-level analysis is strongest on exported text and linked article content
- Image, video, and generic file messages may be preserved through type labels and raw content fields, but they do not currently have equally strong specialized analysis logic

## Operator Playbook

Start by choosing the execution mode:

- Service machine / local archive workflow: use the wrapper without `--http-url`; this is the only place that should run `index`
- Remote client / cross-device workflow: always pass explicit `--http-url`; do not run `index`
- Requests using relative dates like `today` or `yesterday` should be resolved to absolute dates before running commands

Choose the command by user intent:

- Rebuild export and semantic index: `index`
- Quickly find whether a topic appears in the archive: `search`
- Summarize one day: `daily-summary`
- Summarize one chat, group, or official account: `chat-summary`
- Analyze one topic in depth: `topic-report`
- Identify recurring hot themes: `hotspots`
- Compare two dates: `compare-days`
- Build a topic evolution timeline: `timeline-report`
- Inspect who is contributing content in one chat: `sender-report`
- Rank the most worthwhile linked articles: `top-articles`
- Save durable derived reports back into OpenViking: `topic-memory-card` and `watchlist-alerts`

Use evidence and fallback helpers when needed:

- `archive_locator.py chats`: list exported chats
- `archive_locator.py chat-files <query>`: resolve ambiguous chat names
- `archive_locator.py daily-files <date> [--chat]`: inspect concrete daily evidence files
- `archive_locator.py topic-grep <query> [--date] [--chat]`: fallback when semantic search is sparse or unavailable

Run health checks before blaming the archive data:

```bash
curl "http://127.0.0.1:8766/healthz"
curl "http://127.0.0.1:8765/healthz"
curl "http://127.0.0.1:1934/health"
```

## Command Recipes

### 1. Refresh index

Default to incremental indexing into the same target URI.

```bash
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh index
```

Common index args:

- `--source` (default `/home/nx/chat_archive`)
- `--export-root` (default `/home/nx/chat_archive/.openviking_export`)
- `--target` (default `viking://resources/wechat_archive`)
- `--workspace` (default `/home/nx/.openviking-wechat-archive-local-gpu`)
- `--http-url` (explicit endpoint override)
- `--reason` (resource add reason)
- `--timeout` (default `300.0`)
- `--wait`
- `--watch-interval`
- `--semantic-concurrency` (default `2`)
- `--embedding-concurrency` (default `4`)
- `--semantic-llm-timeout` (default `180`)
- `--embedding-text-source` (`summary_first` / `summary_only` / `content_only`, default `content_only`)

Block until queue completion when the user explicitly asks to wait:

```bash
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh index   --wait --timeout 7200   --embedding-text-source content_only   --semantic-concurrency 2   --embedding-concurrency 4   --semantic-llm-timeout 180
```

If embedding rules changed and user wants full rebuild, remove the target first, then re-run `index`.

### 2. Semantic topic search

```bash
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh search "自动驾驶" --limit 5
```

Search args:

- `--limit` (default `5`)
- `--text-fallback` (default true)
- inherits storage flags (`--source`, `--export-root`, `--target`, `--workspace`, `--http-url`)

The preferred path is local HTTP on `127.0.0.1:1934`; if unavailable, it can still run in embedded mode for non-read-only commands.

If semantic search is blocked or only file hits are needed, use locator helper:

```bash
python3 bot/workspace/skills/wechat-archive/scripts/archive_locator.py topic-grep "自动驾驶"
```

### 3. Daily summary

```bash
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh daily-summary "2026-03-30"
```

Optional: `--chat`, `--output`, `--analysis-backend`, `--codex-model`, `--analysis-timeout`

### 4. Single chat / official account analysis

```bash
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh chat-summary "动点科技" --date "2026-03-30"
```

Required: `chat_query`; optional: `--date`, `--start-date`, `--end-date`, `--output`, analysis options above.

### 5. Topic analysis and comparisons

```bash
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh topic-report "FSD 特斯拉"
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh hotspots --start-date "2026-03-30" --end-date "2026-03-31"
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh compare-days "2026-03-30" "2026-03-31"
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh timeline-report "自动驾驶" --start-date "2026-03-30" --end-date "2026-03-31"
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh sender-report "新技术讨论" --date "2026-03-31"
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh top-articles --date "2026-03-31" --limit 5
```

Common flags by command:

- topic-report: `<query> [--limit 8] [--date] [--chat] [--output]`
- hotspots: `[--date] [--start-date] [--end-date] [--chat] [--output]`
- compare-days: `<day1> <day2> [--chat] [--output]`
- timeline-report: `<query> [--limit 10] [--date] [--start-date] [--end-date] [--chat] [--output]`
- sender-report: `<chat_query> [--date] [--start-date] [--end-date] [--query] [--output]`
- top-articles: `[--date] [--start-date] [--end-date] [--chat] [--query] [--limit 5] [--output]`

All analysis commands also support:

- `--analysis-backend` (`codex` / `vlm` / `auto`, default `codex`)
- `--codex-model` (default `gpt-5.1-codex-mini`)
- `--analysis-timeout` (seconds)

### 6. Durable outputs

```bash
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh topic-memory-card "自动驾驶"
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh watchlist-alerts
```

Persistent flags:

- `topic-memory-card <query> [--limit 8] [--date|--start-date|--end-date] [--chat] [--slug] [--output] [--report-root] [--report-target] [--sync/--no-sync]`
- `watchlist-alerts [topic1 topic2...] [--watchlist-file] [--date|--start-date|--end-date] [--chat] [--limit-per-topic] [--output] [--report-root] [--report-target] [--sync/--no-sync]`

Defaults: derived report root `/home/nx/chat_archive/index/derived`, derived target `viking://resources/wechat_archive_reports`.


### 7. HTTP server mode and cross-device access

Read-only analysis commands can run against an explicit remote or local OpenViking HTTP endpoint:

```bash
bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh search "自动驾驶" --limit 5 --http-url "http://127.0.0.1:1934"
```

Use explicit `--http-url` whenever the client machine is different from the service machine. Current project behavior:

- Client machines only need the repo checkout plus Python environment; they do not need local embedding, rerank, or the WeChat source archive
- `search`, `daily-summary`, `chat-summary`, `topic-report`, `hotspots`, `compare-days`, `timeline-report`, `sender-report`, `top-articles`, `topic-memory-card`, and `watchlist-alerts` can run over HTTP
- `index` should stay on the service machine because it depends on local archive paths such as `--source`, `--export-root`, and `--workspace`
- When `--http-url` is not passed, `wechat_archive_agent.py` may auto-start the default local HTTP service for read-only commands and falls back to embedded mode if startup fails

### 8. Service deployment and health checks

Current project deployment expects three local services on the service machine:

- `/home/nx/github/OpenViking/systemd/user/openviking-local-embed.service`
- `/home/nx/github/OpenViking/systemd/user/openviking-local-rerank.service`
- `/home/nx/github/OpenViking/systemd/user/openviking-wechat-archive-server.service`

Health checks:

```bash
curl "http://127.0.0.1:8766/healthz"
curl "http://127.0.0.1:8765/healthz"
curl "http://127.0.0.1:1934/health"
```

Cross-device deployment notes:

- The server service depends on embed and rerank services
- To expose archive search to LAN or VPN clients, override `OPENVIKING_SERVER_HOST=0.0.0.0` and keep the client pointed at `--http-url "http://<server-ip>:1934"`
- Do not expose `8765` or `8766` directly to clients; the HTTP server on `1934` is the project entrypoint

### 9. Config files, logs, and environment overrides

Current project behavior also depends on these local artifacts:

- Auto-generated local HTTP server config: `/home/nx/.openviking/wechat_archive_local_gpu_server.conf`
- Auto-start server log: `/home/nx/.openviking/log/wechat_archive_local_gpu_server.log`

Important environment variables used by the bundled scripts:

- `OPENVIKING_REPO_DIR`: repo root used by `run_wechat_archive_agent.sh` and the skill-level HTTP wrapper
- `OPENVIKING_PYTHON_BIN`: Python interpreter used by `run_wechat_archive_agent.sh`
- `OPENVIKING_SERVER_PYTHON`: Python interpreter used by `run_wechat_archive_http_service.sh`
- `OPENVIKING_SERVER_CONFIG`: explicit config path for the HTTP server bootstrap script
- `OPENVIKING_SERVER_HOST`: bind host for the archive HTTP service
- `OPENVIKING_SERVER_PORT`: bind port for the archive HTTP service

Behavior details worth knowing when adapting this skill to another machine:

- Explicit `--http-url` requires the target server to already be healthy; it does not auto-fallback
- When `--http-url` is omitted on read-only commands under the default workspace, `wechat_archive_agent.py` may generate the local server config automatically and try to boot the local HTTP server
- If the repo path or Python path changes on another machine, update these environment variables or the corresponding service unit files instead of editing every command example

## File Discovery Rules

- Prefer the exported Markdown corpus for summaries and analysis.
- Use linked `document.md` files when a message points to a copied article and article body is useful.
- Prefer `chat.md` for overview and `days/YYYY-MM-DD.md` for evidence.
- Use topic grep before reading large numbers of files.

`archive_locator.py` commands:

- `chats`
- `daily-files <date> [--chat]`
- `chat-files <query>`
- `topic-grep <query> [--date YYYY-MM-DD] [--chat]`

## Operations

- If `/home/nx/chat_archive/.openviking_export` does not exist or is clearly stale, run `index` first.
- For “today/yesterday” style requests, resolve the absolute date in the response.
- For specific chat analysis, include the exact matched chat name.
- When multiple chats match keyword, present candidates and state which chat was analyzed.
- When search cold-start latency matters, keep `openviking-wechat-archive-server.service` enabled.
- Daily auto-refresh and HTTP service assets are bundled under `systemd/user/` in this skill.

### Deployment and cross-platform sync notes

When the skill code moves to a different workspace path (for example switching between `OpenViking` and a cloned `wechat-archive` layout), update only the service unit files that are copied into user systemd.

- Source unit files (authoritative):
  - `/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/systemd/user/openviking-wechat-archive-server.service`
  - `/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/systemd/user/openviking-wechat-archive-index.service`
  - `/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/systemd/user/openviking-wechat-archive-index.timer`
- User-level links expected by systemd:
  - `/home/nx/.config/systemd/user/openviking-wechat-archive-server.service`
  - `/home/nx/.config/systemd/user/openviking-wechat-archive-index.service`
  - `/home/nx/.config/systemd/user/openviking-wechat-archive-index.timer`

```bash
ln -sf /home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/systemd/user/openviking-wechat-archive-server.service \
  /home/nx/.config/systemd/user/openviking-wechat-archive-server.service
ln -sf /home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/systemd/user/openviking-wechat-archive-index.service \
  /home/nx/.config/systemd/user/openviking-wechat-archive-index.service
ln -sf /home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/systemd/user/openviking-wechat-archive-index.timer \
  /home/nx/.config/systemd/user/openviking-wechat-archive-index.timer
```

On Linux desktop sessions with user systemd available, run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now openviking-wechat-archive-server.service
systemctl --user enable --now openviking-wechat-archive-index.timer
```

## Bundled Assets

- [run_wechat_archive_agent.sh](/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh): wrapper for `examples/wechat_archive_agent.py`
- [run_wechat_archive_daily_index.sh](/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_daily_index.sh): daily incremental index wrapper
- [run_wechat_archive_http_service.sh](/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_http_service.sh): `1934` HTTP service wrapper
- [openviking-wechat-archive-index.service](/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/systemd/user/openviking-wechat-archive-index.service): user service for daily index refresh
- [openviking-wechat-archive-index.timer](/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/systemd/user/openviking-wechat-archive-index.timer): user timer for daily index refresh
- [openviking-wechat-archive-server.service](/home/nx/github/OpenViking/bot/workspace/skills/wechat-archive/systemd/user/openviking-wechat-archive-server.service): user service for local HTTP search
