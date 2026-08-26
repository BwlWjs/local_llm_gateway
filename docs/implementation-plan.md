# 编码计划

## 设计状态

设计层面已经闭环，可以开始编码。

## 当前进度

- 已完成：源码目录重命名为 `src/local_llm_gateway`
- 已完成：产品名统一为 `ModelRelay`
- 已完成：文档索引、详细设计、技术实现设计、mac 交付设计
- 已完成：后端骨架、路由、协议外壳、Ollama 链路、基础测试骨架
- 已完成：Ubuntu 24.04 LTS Server arm64 开发虚拟机已创建并启动
- 当前阻塞：本机缺少可用的 `git` / command line tools，无法直接完成远端提交
- 当前决定：后续开发环境迁移到 Ubuntu 24.04 LTS Server arm64 虚拟机，编辑器使用 VS Code

编码时以这些文档为准：

- [design-review.md](design-review.md)
- [detailed-design.md](detailed-design.md)
- [technical-implementation.md](technical-implementation.md)
- [performance.md](performance.md)

## 总体顺序

先做后端数据面，再做控制面后端，再做前端 UI，最后做 macOS 打包和升级。

理由：

- Claude Code 和其他智能体首先依赖 Gateway API。
- UI 的配置能力依赖后端已有 store、key、runtime snapshot。
- macOS 打包必须等后端和前端的运行边界稳定。

## 阶段 1：后端核心

目标：把当前骨架变成可测试的核心网关。

范围：

- canonical schema
- runtime snapshot
- model registry
- provider capability matrix
- unified error model
- shared httpx client

主要文件：

- `src/local_llm_gateway/models.py`
- `src/local_llm_gateway/router.py`
- `src/local_llm_gateway/config.py`
- `src/local_llm_gateway/providers/base.py`
- `src/local_llm_gateway/core/`

验收：

- `local-coder` 能解析到 `ollama / qwen2.5-coder:7b`
- 路由失败、能力不支持、provider 未知都有固定错误
- `GET /v1/models` 由 registry 输出

## 阶段 2：协议外壳

目标：Anthropic 和 OpenAI 入口并列接入同一核心。

范围：

- Anthropic messages facade
- OpenAI chat completions facade
- request -> canonical
- canonical -> response
- canonical stream event -> protocol stream event

主要文件：

- `src/local_llm_gateway/facades/anthropic.py`
- `src/local_llm_gateway/facades/openai.py`
- `src/local_llm_gateway/translator.py`
- `src/local_llm_gateway/main.py`

验收：

- Anthropic 和 OpenAI 请求不会互相转译
- 两个入口都进入同一个 router
- Anthropic stream 已接通，OpenAI stream 先显式返回 501，后续单独补齐

## 阶段 3：Ollama Provider

目标：完成首个真实模型链路。

默认链路：

```text
local-coder -> ollama -> qwen2.5-coder:7b
```

范围：

- Ollama request adapter
- Ollama stream adapter
- token count estimate
- timeout / cancel
- provider error mapping

主要文件：

- `src/local_llm_gateway/providers/ollama.py`
- `src/local_llm_gateway/streaming.py`
- `src/local_llm_gateway/protocols.py`

验收：

- `POST /v1/messages` 能真实调用 Ollama
- 流式响应不整包缓存
- provider 不可达返回 `502`
- provider 超时返回 `504`

## 阶段 4：key 与控制面后端

目标：让不同智能体可独立发 key，并通过 Admin API 管理。

范围：

- SQLite store
- key 生成、hash、prefix、scope
- Gateway API 鉴权
- Admin API
- runtime snapshot refresh

主要文件：

- `src/local_llm_gateway/security.py`
- `src/local_llm_gateway/storage/`
- `src/local_llm_gateway/admin/`
- `src/local_llm_gateway/core/runtime.py`

验收：

- UI 或 API 能创建 key
- key 明文只展示一次
- `x-api-key` 和 `Authorization: Bearer` 都能归一鉴权
- 吊销 key 后 Gateway 请求立即失败

## 阶段 5：前端 UI

目标：完成本地控制面。

页面：

- Models
- Keys
- Updates
- Logs / Status

推荐主体：

- `frontend/`
- TypeScript
- React
- Vite

约束：

- UI 只访问 Admin API
- UI 不调用 provider
- UI 不进入推理热路径
- 运行时不依赖 Node.js

验收：

- 能配置 `local-coder`
- 能生成 Claude Code 专用 key
- 能查看 gateway/provider 状态
- 能触发更新检查

## 阶段 6：vLLM Provider

目标：补第二个 provider，验证能力矩阵和路由抽象。

范围：

- vLLM OpenAI-compatible adapter
- stream adapter
- capability table
- provider selection

主要文件：

- `src/local_llm_gateway/providers/vllm.py`
- `src/local_llm_gateway/providers/registry.py`

验收：

- 同一 canonical request 可路由到 vLLM
- provider 能力差异不泄露到协议外壳

## 阶段 7：测试与性能

目标：防止实现偏离设计。

测试：

- router 单测
- translator 单测
- key 单测
- provider mock 集成测试
- stream 顺序与 cancel 测试
- benchmark 脚本

验收：

- 默认链路测试通过
- benchmark 能对比直连 Ollama 和经过网关
- p95 首 token 额外开销符合 [performance.md](performance.md)

## 阶段 8：macOS 交付

目标：把产品交付成 `ModelRelay.app`。

范围：

- app launcher
- 静态 UI 托管
- 后端进程启动
- LaunchAgent
- Sparkle update feed
- dmg 打包

主要目录：

- `deploy/mac/`
- `release/mac/`

验收：

- app 能启动本地服务
- UI 能打开
- Gateway API 可用
- 更新检查流程可跑通

## 不做

- 不先做复杂模型市场
- 不先做多租户
- 不先做远程控制台
- 不先做训练、微调、模型管理平台
- 不在 Anthropic 和 OpenAI 之间做链式转换
