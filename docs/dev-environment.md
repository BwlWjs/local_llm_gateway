# 开发与运行环境

> 本文档是当前环境的权威说明，与代码、架构、部署现状保持一致。如环境变更，先改本文件。

## 拓扑总览

ModelRelay 跨两台机器协作：宿主机负责跑模型（Ollama）和上层智能体（Claude Code），UTM 虚拟机负责跑网关与源码构建。

```text
宿主机 macOS (Apple M4 Pro, 24GB)
├── Claude Code          上层智能体，发 Anthropic-compatible 请求
├── Ollama 守护进程       127.0.0.1:11434（仅本地监听）
│   └── qwen2.5-coder:7b / qwen3:8b（GGUF 4-bit，原生 tools）
└── UTM 桥接网段地址      192.168.64.1（VM 经此访问宿主 Ollama）
        │
        ▼
UTM 虚拟机 Ubuntu 24.04.4 LTS (arm64)
├── ModelRelay 网关      192.168.64.5:8000（uvicorn，systemd 自启）
│   └── 源码构建 + .venv，GATEWAY_OLLAMA_BASE_URL=http://192.168.64.1:11434
├── 仓库                 /home/jingshuo/modelrelay
└── 别名                 local-coder → ollama/qwen2.5-coder:7b
                         qwen3-8b    → ollama/qwen3:8b
```

## 宿主机

- 机器：MacBook Pro，Apple M4 Pro，24GB 统一内存，arm64
- 角色：跑 Ollama（本地模型推理）、跑 Claude Code、做 macOS 打包交付
- Ollama：`127.0.0.1:11434`，仅本地监听。已装 `qwen2.5-coder:7b`、`qwen3:8b`（Q4_K_M，能力含 `completion`+`tools`+`thinking`）
- UTM 桥接：宿主机在该网段地址为 `192.168.64.1`，VM 经 `http://192.168.64.1:11434` 访问宿主 Ollama
- 本机仓库副本：`/Users/lucas/mac_self`，仅作本地参考与 macOS 打包用，**不是正式网关实例**

## UTM 虚拟机

- 镜像：`ubuntu-24.04.4-live-server-arm64.iso`，架构 arm64（aarch64）
- VM 包：`~/Library/Containers/com.utmapp.UTM/Data/Documents/Linux.utm`
  - UTM 配置：4GB 内存、virtio-net `Shared` 模式（即 192.168.64.x 网段）、VirtFS 共享开启、UEFI 启动
- IP：`192.168.64.5`（DHCP，网卡 `enp0s1`）
- 登录：用户 `jingshuo`（密码在 Ubuntu 安装时设置，不写入仓库；由用户持有）
- 角色：ModelRelay 网关正式运行环境 + 源码构建环境
- 仓库：`/home/jingshuo/modelrelay`，远程 `git@github.com:BwlWjs/local_llm_gateway.git`
- Python：系统 3.12.3，项目 `.venv`（可编辑安装，import 直接解析到 `src/local_llm_gateway`）

> 历史说明：早期文档曾把 VM 包记为 `ModelRelay Ubuntu 24.04.utm`，实际建好后命名为 `Linux.utm`，以本文件为准。

## 网关运行

- 进程：由 systemd 单元 `modelrelay-gateway.service` 管理（`enabled`，开机自启，`Restart=on-failure`）
- 单元定义：`/etc/systemd/system/modelrelay-gateway.service`，`ExecStart=/bin/bash /home/jingshuo/modelrelay/scripts/run_gateway.sh`
- 启动脚本：`scripts/run_gateway.sh`，`source .env` 后用 `.venv/bin/python -m uvicorn local_llm_gateway.main:app --host 0.0.0.0 --port 8000`
- 配置文件：`~/modelrelay/.env`
  - `GATEWAY_OLLAMA_BASE_URL=http://192.168.64.1:11434`（指向宿主）
  - `GATEWAY_MODEL_MAP`：含 `local-coder` 与 `qwen3-8b` 两个别名
  - `GATEWAY_PROVIDER_CAPS`：ollama/vllm 均 `supports_tools=true`
- 数据库：`~/modelrelay/modelrelay.db`（SQLite，存 API key 的 SHA-256 哈希；跨重启持久）
- 健康检查：`GET /healthz` → `{"status":"ok"}`

常用运维（在 VM 内）：

```bash
systemctl status modelrelay-gateway     # 状态
systemctl restart modelrelay-gateway    # 重启
journalctl -u modelrelay-gateway -f      # 日志
tail -f /tmp/gateway.log                # 启动脚本重定向日志
```

## 代码状态

- 当前 HEAD：`c9ce98a feat(tools): bidirectional tool_use conversion for Claude Code compatibility`
- 宿主与 VM 两个仓库均已同步到 `origin/main` 的 `c9ce98a`
- 关键能力已实现并端到端验证：双向 tool_use 转换（Anthropic 工具 schema ↔ Ollama tool_calls，含流式）、流式 input_tokens 真实上报、key 过期校验、lifespan 迁移、GitHub Actions CI

## 模型别名

| 别名 | provider | 真实模型 | 说明 |
|---|---|---|---|
| `local-coder` | ollama | qwen2.5-coder:7b | 默认 coding 模型 |
| `qwen3-8b` | ollama | qwen3:8b | 原生 function calling + thinking，Claude Code 主用 |

新增模型：编辑 `~/modelrelay/.env` 的 `GATEWAY_MODEL_MAP` 后 `systemctl restart modelrelay-gateway`。

## Claude Code 接入

宿主机 Claude Code 的 `~/.claude/settings.json`：

```json
{
    "env": {
        "ANTHROPIC_AUTH_TOKEN": "mr_<在 VM 网关 admin API 创建的 key>",
        "ANTHROPIC_BASE_URL": "http://192.168.64.5:8000",
        "ANTHROPIC_MODEL": "qwen3-8b",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "qwen3-8b",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "qwen3-8b",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "qwen3-8b",
        "CLAUDE_CODE_SUBAGENT_MODEL": "qwen3-8b",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
    }
}
```

创建 API key：访问 `http://192.168.64.5:8000`（管理 UI）或 `POST /api/v1/keys`（`admin_token` 为空时本地放行）。

## 端到端验证

链路 `Claude Code (宿主) → VM 网关 (192.168.64.5:8000) → 宿主 Ollama (192.168.64.1:11434) → qwen3:8b` 已验证：

- 非流式：`stop_reason=tool_use`，返回 `tool_use` block（`get_weather` / `{city: Beijing}`）
- 流式：SSE 发出 `content_block_start(tool_use)` → `input_json_delta` → `stop_reason: tool_use`
- `usage.input_tokens` 真实上报（非 0）

验证脚本：`scripts/test_tool_call.sh`（宿主机执行，`stream:false` 拿 JSON，exit 0 表示 tool_use 往返成功）。

## 环境边界约束

- 网关在 VM，**不要**在宿主机本地起网关当作正式实例（宿主副本仅用于打包/本地参考）
- VM 网关连 Ollama 必须用 `192.168.64.1:11434`，不能用 `127.0.0.1`（VM 内无 Ollama）
- Claude Code 的 `ANTHROPIC_BASE_URL` 用 `http://192.168.64.5:8000`
- 安装本包**必须**用可编辑安装 `pip install -e .`，否则 site-packages 存旧副本、网关跑陈旧代码
