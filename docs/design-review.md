# 设计评审

## 结论

当前工程的目标已经明确，设计已经闭环，可以进入编码阶段。

## 已明确

- 目标用户：本机开发者和 Claude Code
- 核心价值：一个入口，多后端，逻辑模型名隔离实现细节
- 技术边界：Anthropic-compatible 网关，不做训练平台和复杂控制台
- 性能原则：流式优先，网关开销尽量接近零

## 已闭环

下面这些决策已经冻结，后续编码按这里执行。

| 优先级 | 决策主题 | 最终决议 | 实现依据 |
| --- | --- | --- | --- |
| P0 | 协议契约 | canonical request / response / stream event 作为核心 schema；Anthropic 和 OpenAI 只做一次入口/出口转换；未知字段不进入核心路由。 | [docs/detailed-design.md](detailed-design.md) |
| P0 | 路由与 provider 能力矩阵 | 逻辑模型名用显式 registry 做 exact match；`local-coder -> ollama -> qwen2.5-coder:7b` 是默认路径；能力缺口按矩阵处理，不靠隐式分支。 | [docs/detailed-design.md](detailed-design.md) |
| P0 | key / 权限 / 鉴权 | 每个智能体一个 key；Bearer / x-api-key 都归一；key 只显示一次明文，服务端只存 hash 和元数据；Admin 和 Gateway 权限分离。 | [docs/detailed-design.md](detailed-design.md) |
| P1 | 观测与稳定性 | 结构化日志、基础 metrics、超时、取消传播、限流和软熔断都纳入设计；生成路径不做自动重试。 | [docs/technical-implementation.md](technical-implementation.md) |
| P1 | 性能与 benchmark | 对照组固定为“直连 provider vs 经过网关”；测首 token 延迟、p95 和网关额外开销；脚本可重复。 | [docs/performance.md](performance.md) |
| P2 | 进程与部署拓扑 | v1 采用单 App Bundle、单后端进程、双 API 分区；UI 通过本地 Admin API 管理配置和升级。 | [docs/mac-delivery.md](mac-delivery.md) |

## 主要优化点

1. 先冻结 canonical schema，再写 provider 适配。
2. 把模型路由、能力矩阵、错误映射拆成独立契约。
3. 流式路径只做直通，不做整包缓冲和重复序列化。
4. token 统计放到独立路径，不进入消息生成热路径。
5. 补齐观测、超时、取消和测试基线，再进入稳定实现。
6. 对外协议层保持并列，不要让 Anthropic 或 OpenAI 成为内核依赖。
7. 进程和部署拓扑要先定清，再写启动器和更新逻辑。

## 设计完成标准

- 详细设计、架构设计、交付设计、性能设计对同一套决策无冲突
- `POST /v1/messages` 和 `POST /v1/messages/count_tokens` 的行为和错误码固定
- 至少一个 provider 的真实转发链路可用
- `GET /v1/models` 由 registry 驱动，而不是手写常量
- 关键配置有明确优先级和校验规则
- 有可重复的本地 benchmark 和最小测试集
