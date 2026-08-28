# ModelRelay

一个把 `Claude Code` 接到本地模型的中间层工程。

对上层暴露一个稳定域名，并通过 Anthropic-compatible、OpenAI-compatible 等协议外壳接入；对下层通过适配器屏蔽 `Ollama` / `vLLM-Metal` 的差异。目标不是再造一个模型平台，而是把本地模型接入 Claude Code 和其他智能体的链路做薄、做稳、做快。

当前仓库的 Python import 包名已统一为 `local_llm_gateway`，发行包名为 `modelrelay`。

## 设计评审结论

当前工程的方向已经明确，设计已闭环，已经进入编码阶段。

- 已冻结：目标用户、单入口多后端、Anthropic-compatible / OpenAI-compatible 外壳、流式优先
- 已冻结：协议契约、provider 能力矩阵、key / 权限 / 鉴权、观测、benchmark、部署拓扑

详细 review 见 [docs/design-review.md](docs/design-review.md)。

## 产品交付

macOS 的部署和升级设计见 [docs/mac-delivery.md](docs/mac-delivery.md)。核心原则是源码、打包脚本和发布产物分开，产品以一个统一发行单元交付，控制面 UI 只负责管理配置、key 和更新。

技术实现细节见 [docs/technical-implementation.md](docs/technical-implementation.md)。

编码计划见 [docs/implementation-plan.md](docs/implementation-plan.md)。

文档入口见 [docs/README.md](docs/README.md)。

## 目标

- Claude Code 只看到一个域名，不感知后端是 Ollama 还是 vLLM
- 统一模型路由，模型名做逻辑隔离
- 保持流式输出，避免在网关层堆积 token
- 为二次开发留接口，但不在热路径加重逻辑
- 适配本地小模型场景，接受 token 速度不高这个现实
- 默认本地模型路径先按 `ollama + qwen2.5-coder:7b` 设计

## 产品设计

### 使用场景

- 本机开发
- Claude Code 调本地 coding 模型
- 需要随时切换 `Ollama` 和 `vLLM-Metal`
- 需要统一鉴权、日志、路由和性能控制

### 用户体验

1. 用户只配置一个网关域名，例如 `https://llm-gw.local`
2. Claude Code 通过这个域名发起请求
3. 网关按模型名映射到对应 provider
4. provider 可以是 Ollama，也可以是 vLLM-Metal
5. 上层不改使用方式，只换后端能力

### 产品边界

- 不做训练平台
- 不做模型管理面板
- 不做复杂调参 UI
- 不在网关里复写模型能力

## 技术架构

```text
Claude Code
   |
   | Anthropic-compatible API
   v
Gateway / Domain Layer
   |
   +--> Auth / Rate Limit / Audit
   +--> Model Registry
   +--> Streaming Proxy
   +--> Token Meter
   |
   +--> Provider Adapter
           |                 |
           |                 |
        Ollama             vLLM-Metal
```

### 分层职责

- **Domain Layer**: 对外稳定域名和接口，保证 Claude Code 不感知后端变化
- **Router Layer**: 负责逻辑模型名到真实 provider/model 的映射
- **Adapter Layer**: 负责协议转换，屏蔽 Ollama 和 vLLM 的差异
- **Streaming Layer**: 负责 SSE / chunk 转发，尽量不改写 payload
- **Token Layer**: 负责 token 计数和性能观测

### 核心原则

- canonical schema 只保留一份
- 热路径只做必要转换
- 流式优先，不做整包缓冲
- 适配器无状态或尽量少状态
- 失败要尽早返回，避免白白消耗上下文时间

## 二次开发接口

本项目的二开重点不是再加一个业务层，而是保持接口薄且稳定。

### 推荐外部接口

- `POST /v1/messages`
- `POST /v1/messages/count_tokens`
- `GET /v1/models`
- `GET /healthz`
- `GET /metrics`（可选）

### 推荐内部接口

- `ProviderAdapter.stream_messages()`
- `ProviderAdapter.count_tokens()`
- `ModelRegistry.resolve()`
- `StreamTranslator.forward()`

### 注意事项

- 不要在流式输出路径里反复 `json parse/stringify`
- 不要在每个 token 上打同步日志
- 不要先收全响应再返回
- 不要在网关层重复做复杂推理
- 不要让模型选择逻辑散落到路由、适配器和配置三处

## 性能说明

这个工程的前提是：**本地 token 生成速度本来就不快**。因此网关的任务不是“提速”，而是“不要拖慢”。

建议的性能目标：

- 网关额外延迟尽量接近零
- 流式 chunk 直通，不做大段拼接
- Token 计数独立缓存，避免重复计算
- provider 连接复用
- 错误尽早返回，减少无效上下文占用

### 经验规则

- 7B 级模型优先
- 长上下文要谨慎
- 先保证稳定，再谈更复杂的路由策略
- 对本地机器来说，`vLLM-Metal` 和 `Ollama` 的差异通常小于模型大小和量化方式的差异

## 工程结构

```text
.
├── README.md
├── pyproject.toml
├── .env.example
├── docs/
│   ├── README.md
│   ├── architecture.md
│   ├── design-review.md
│   ├── detailed-design.md
│   ├── implementation-plan.md
│   ├── mac-delivery.md
│   ├── performance.md
│   ├── product-design.md
│   └── technical-implementation.md
├── deploy/
│   └── mac/
├── release/   # generated artifacts, gitignored
└── src/
    └── local_llm_gateway/
        ├── __init__.py
        ├── __main__.py
        ├── config.py
        ├── main.py
        ├── models.py
        ├── router.py
        ├── streaming.py
        ├── translator.py
        └── providers/
            ├── __init__.py
            ├── base.py
            ├── ollama.py
            └── vllm.py
```

## 快速启动

本地开发副本：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]          # 必须可编辑安装，否则 site-packages 存旧副本
cp .env.example .env
python -m local_llm_gateway
```

正式运行部署在 UTM 虚拟机，由 systemd 单元 `modelrelay-gateway.service` 自启，宿主机跑 Ollama 与 Claude Code。完整跨机拓扑、凭据与运维命令见 [docs/dev-environment.md](docs/dev-environment.md)。

## 下一步

阶段 1–6（后端核心、协议外壳、Ollama/vLLM provider、key/Admin、UI、双向 tool_use 转换）均已实现并端到端验证，代码 HEAD `c9ce98a`。剩余工作：

1. 限流、审计落盘、metrics 端点
2. vLLM-Metal 在 Apple Silicon 上的实际接入（当前生产用 Ollama + qwen3:8b）
3. macOS 交付（ModelRelay.app 打包、LaunchAgent、Sparkle 升级）

> 运行环境与跨机拓扑（宿主机跑 Ollama/Claude Code，UTM 虚拟机跑网关）见 [docs/dev-environment.md](docs/dev-environment.md)。
