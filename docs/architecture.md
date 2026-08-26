# 技术架构

## 链路

```text
Claude Code
  -> Anthropic/OpenAI-compatible Gateway
  -> Model Router
  -> Provider Adapter
  -> Ollama / vLLM-Metal
  -> Local Model
```

## 模块

### Gateway

负责协议入口、鉴权、限流、日志和健康检查。

### Router

负责把逻辑模型名映射到 provider 和真实模型名。

### Adapter

负责协议转换：

- Claude Messages -> Ollama API
- Claude Messages -> vLLM OpenAI-compatible API

### Streaming

负责边收边发，尽量不拼整包响应。

## 协议外壳策略

推荐做法是“单路由核心，多协议外壳”。

- 核心只认一份 canonical request / response / stream event
- Anthropic 和 OpenAI 只是入口适配层，不进入核心语义
- 任何协议差异只在 ingress / egress 做一次转换
- 不允许 Anthropic -> OpenAI -> core 这种链式翻译

这样做的原因是：

- 路由逻辑只保留一份
- provider 适配只写一份
- 共享流式、错误和观测逻辑
- 减少 token 回复路径上的重复解析和序列化

实现细节见 [technical-implementation.md](technical-implementation.md)。

## 当前实现状态

- 已有：FastAPI 入口、健康检查、模型列表、模型路由、基础配置和 token 估算
- 代码实现层未完成：真实 provider 转发、流式代理、错误标准化、鉴权、限流、审计和 metrics

设计闭环结果以 [design-review.md](design-review.md) 的冻结决策表为准。P0 包括协议契约、路由能力矩阵、key 与权限契约，已经冻结并作为实现依据。

## 部署分层

- **开发态**: `src/` 和 `docs/`
- **打包态**: `deploy/mac/`
- **交付态**: `release/mac/`，只存生成物，不存源码
- **运行态**: `ModelRelay.app`、本地网关进程、Application Support 数据

## 接口契约

### 外部

- `POST /v1/messages`
- `POST /v1/messages/count_tokens`
- `GET /v1/models`
- `GET /healthz`

### 约束

- 单次请求只做一次路由决策
- 逻辑模型名先进入 Router，再进入 Provider Adapter
- 流式路径不做整包缓冲，不重复序列化
- count_tokens 可以独立于消息生成路径执行

### 错误约定

- 请求校验失败返回 `400`
- 上游超时返回 `504`
- 上游协议或网络失败返回 `502`
- 能力不支持返回 `501`

### 内部

- `resolve(model_name) -> provider_target`
- `stream(request) -> async byte stream`
- `count_tokens(request) -> int`

## 配置与映射

- `GATEWAY_MODEL_MAP` 负责逻辑模型名到 provider/model 的映射
- `GATEWAY_PROVIDER_DEFAULT` 负责映射缺失时的默认 provider
- `GATEWAY_OLLAMA_BASE_URL` 和 `GATEWAY_VLLM_BASE_URL` 负责 provider 地址

## 能力边界

- 先支持消息生成、流式转发和 token 计数
- 不把 provider 差异藏成隐式行为，应该显式记录在能力矩阵里
- 任何新增能力都要先补接口契约，再进入实现
- 优先把 Anthropic 和 OpenAI 做成平行外壳，而不是互相转译

## 设计约束

- 单次请求只做一次路由决策
- 热路径不落盘
- 热路径不做同步阻塞 IO
- 热路径不重复序列化
