# 微信归档跨设备部署

本文档说明如何把当前仓库里的微信归档能力部署成一台服务机、多台客户端复用的模式。

适用场景：

- 微信归档和索引只保存在一台机器上
- Embedding / Rerank 模型只跑在一台 GPU 机器上
- 其他电脑、平板或终端只想复用检索和分析能力

## 推荐架构

推荐采用“一台服务机 + 多台客户端”的结构：

- 服务机：
  - 保存微信归档原始目录
  - 保存 OpenViking workspace 和导出 Markdown
  - 运行本地 embedding 服务
  - 运行本地 rerank 服务
  - 运行 OpenViking HTTP 服务
- 客户端：
  - 不保存索引
  - 不运行 embedding / rerank 模型
  - 只通过 `--http-url` 访问服务机上的 OpenViking HTTP 服务

## 端口职责

当前这条链路涉及三个端口：

- `8766`：本地 embedding 服务
- `8765`：本地 rerank 服务
- `1934`：OpenViking HTTP 服务

默认代码里，这三个服务都监听 `127.0.0.1`，因此别的设备不能直接访问。跨设备使用时，通常只需要把 `1934` 对外开放；`8766` 和 `8765` 仍然保持本机可见即可。

原因很简单：

- `1934` 是客户端真正访问的入口
- `8766` 和 `8765` 只是服务机内部被 OpenViking 调用

## 服务机部署

### 1. 准备代码和 Python 环境

建议保持当前仓库的默认路径，避免修改现有脚本和 systemd 单元中的硬编码路径：

```bash
mkdir -p "$HOME/github"
cd "$HOME/github"
git clone https://github.com/redyuan43/OpenViking.git
cd OpenViking

python3 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -e ".[bot]"
```

### 2. 准备本地 embedding / rerank 运行环境

```bash
cd "$HOME/github/OpenViking"
./scripts/setup_local_rerank_env.sh
```

这个脚本会在 `~/.local/share/wechat-rerank/.venv` 下准备模型服务所需环境。

### 3. 准备配置文件

需要至少准备两份配置：

- `~/.openviking/ov.conf`
- `~/.openviking/wechat_archive_local_gpu_server.conf`

建议从当前机器的工作版本拷贝，再按目标机器调整。

#### `ov.conf`

这份配置主要用于本地 CLI 和嵌入式模式。关键点：

- `embedding.dense.api_base` 指向 `http://127.0.0.1:8766/v1`
- `rerank.api_base` 指向 `http://127.0.0.1:8765/v1/rerank`
- `storage.workspace` 指向你的默认 OpenViking workspace

#### `wechat_archive_local_gpu_server.conf`

这份配置是 `1934` HTTP 服务使用的专用配置。关键点：

- `embedding.dense.api_base` 仍然指向 `http://127.0.0.1:8766/v1`
- `rerank.api_base` 仍然指向 `http://127.0.0.1:8765/v1/rerank`
- `storage.workspace` 指向微信归档专用 workspace
- `server.port` 设为 `1934`
- `server.host` 设为服务机的局域网 IP 或 `0.0.0.0`

如果 embedding / rerank 和 OpenViking HTTP 服务都在同一台机器上，不需要把 `8765` / `8766` 改成外网地址。

### 4. 启动三个服务

#### embedding

```bash
cd "$HOME/github/OpenViking"
./scripts/run_local_embedding_service.sh
```

#### rerank

```bash
cd "$HOME/github/OpenViking"
./scripts/run_local_rerank_service.sh
```

#### OpenViking HTTP

```bash
cd "$HOME/github/OpenViking"
OPENVIKING_SERVER_HOST=0.0.0.0 ./scripts/run_wechat_archive_http_service.sh
```

### 5. 用 systemd 持久化运行

Linux 推荐直接使用仓库内已有的用户级服务：

- `systemd/user/openviking-local-embed.service`
- `systemd/user/openviking-local-rerank.service`
- `systemd/user/openviking-wechat-archive-server.service`

复制到用户目录后重载并启用：

```bash
mkdir -p "$HOME/.config/systemd/user"
cp systemd/user/openviking-local-embed.service "$HOME/.config/systemd/user/"
cp systemd/user/openviking-local-rerank.service "$HOME/.config/systemd/user/"
cp systemd/user/openviking-wechat-archive-server.service "$HOME/.config/systemd/user/"

systemctl --user daemon-reload
systemctl --user enable --now openviking-local-embed.service
systemctl --user enable --now openviking-local-rerank.service
systemctl --user enable --now openviking-wechat-archive-server.service
```

由于 `openviking-wechat-archive-server.service` 默认使用 `127.0.0.1`，跨设备部署时建议加一个 override：

```bash
systemctl --user edit openviking-wechat-archive-server.service
```

写入：

```ini
[Service]
Environment=OPENVIKING_SERVER_HOST=0.0.0.0
Environment=OPENVIKING_SERVER_PORT=1934
```

然后重启服务：

```bash
systemctl --user daemon-reload
systemctl --user restart openviking-wechat-archive-server.service
```

### 6. 构建索引

增量索引：

```bash
./.venv/bin/python examples/wechat_archive_agent.py index
```

如果 embedding 规则、workspace 或摘要策略发生变化，需要做一次全量重建。推荐做法是先删除旧目标，再重新执行索引。

阻塞等待到队列完成的完整命令示例：

```bash
./.venv/bin/python examples/wechat_archive_agent.py index \
  --wait --timeout 7200 \
  --embedding-text-source content_only \
  --semantic-concurrency 2 \
  --embedding-concurrency 4 \
  --semantic-llm-timeout 180
```

### 7. 服务机健康检查

```bash
curl "http://127.0.0.1:8766/healthz"
curl "http://127.0.0.1:8765/healthz"
curl "http://127.0.0.1:1934/health"
```

如果要从其他设备测试，把最后一个地址改成服务机局域网 IP：

```bash
curl "http://<服务机IP>:1934/health"
```

## 客户端接入

客户端不需要本地部署 embedding / rerank，也不需要微信归档源目录。

### 1. 准备最小运行环境

最省事的方式仍然是克隆同一份仓库并安装依赖：

```bash
mkdir -p "$HOME/github"
cd "$HOME/github"
git clone https://github.com/redyuan43/OpenViking.git
cd OpenViking

python3 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -e ".[bot]"
```

### 2. 显式指定远程 HTTP 服务

跨设备使用时，不要依赖默认本地自动拉起逻辑，直接显式传 `--http-url`：

```bash
./.venv/bin/python examples/wechat_archive_agent.py \
  search "自动驾驶" \
  --limit 5 \
  --http-url "http://<服务机IP>:1934"
```

其他读操作也是一样：

```bash
./.venv/bin/python examples/wechat_archive_agent.py \
  daily-summary "2026-04-01" \
  --http-url "http://<服务机IP>:1934"

./.venv/bin/python examples/wechat_archive_agent.py \
  topic-report "机器人" \
  --http-url "http://<服务机IP>:1934"
```

### 3. 不要在客户端跑的命令

下面这些命令应该只在服务机上执行：

- `index`
- 任何依赖服务机本地微信归档目录的导出流程

原因是默认路径仍然是本地路径，例如：

- `--source`
- `--export-root`
- `--workspace`

这些路径默认都指向服务机本地文件系统，而不是客户端。

## 常见问题

### 为什么客户端不直接访问 `8765` 和 `8766`？

因为客户端只需要访问 OpenViking HTTP 服务。由 `1934` 去协调 embedding、rerank 和 workspace，更符合当前代码结构，也更容易控制权限和网络暴露面。

### 为什么客户端必须加 `--http-url`？

当前 `wechat_archive_agent.py` 的自动本地服务逻辑只针对默认本地 workspace 做优化。跨设备访问时，显式传入 `--http-url` 更稳定，也能避免客户端误走本地嵌入式模式。

### 如果服务机路径和当前项目不同怎么办？

可以，但你需要同步改掉以下位置中的路径或环境变量：

- `scripts/run_wechat_archive_http_service.sh`
- `bot/workspace/skills/wechat-archive/scripts/run_wechat_archive_agent.sh`
- `systemd/user/*.service`
- `OPENVIKING_REPO_DIR`
- `OPENVIKING_PYTHON_BIN`
- `OPENVIKING_SERVER_CONFIG`

如果没有特殊原因，建议直接沿用：

- `~/github/OpenViking`
- `~/.openviking`

这样最省事。

### 能不能直接暴露到公网？

不建议。当前这套默认更适合：

- 局域网
- Tailscale
- WireGuard
- SSH 隧道

如果确实要暴露到公网，至少要补齐认证、反向代理和访问控制，不要直接把默认配置裸露出去。

## 推荐最小方案

如果你的目标只是“让别的设备也能查微信归档”，最小可用方案是：

1. 在一台 GPU 机器上跑好 `8766`、`8765`、`1934`
2. 只把 `1934` 暴露给局域网或内网 VPN
3. 所有客户端统一执行：

```bash
./.venv/bin/python examples/wechat_archive_agent.py \
  search "自动驾驶" \
  --limit 5 \
  --http-url "http://<服务机IP>:1934"
```

这样维护成本最低，也最符合当前仓库已有脚本和服务单元的设计。
