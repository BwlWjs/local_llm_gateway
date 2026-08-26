# 详细设计

## 目标

这份文档是 `README.md` 之后、落代码之前的实现基线。

它要回答四个问题：

1. 系统怎么拆。
2. 请求怎么走。
3. 模型怎么选。
4. 代码怎么落。

## 项目名

- 产品名：`ModelRelay`
- 当前仓库代码名：`local_llm_gateway`
- 代码名后续可以再统一，设计阶段先不阻塞实现

## 设计原则

- 单路由内核
- 多协议外壳
- 控制面和数据面分离
- 运行时配置只读快照
- 流式优先，少拷贝，少序列化
- key 和模型配置可管理、可审计、可轮换

## 默认模型选择

首个默认模型建议固定为本地 `qwen2.5-coder:7b`。

推荐映射：

- 逻辑模型名：`local-coder`
- provider：`ollama`
- 真实模型名：`qwen2.5-coder:7b`

示例：

```json
{
  "local-coder": {
    "provider": "ollama",
    "model": "qwen2.5-coder:7b"
  }
}
```

## 推荐技术栈

### 后端

- Python 3.11+
- FastAPI
- Pydantic v2
- httpx.AsyncClient
- uvicorn
- SQLite

当前代码已经采用这条路径，后续实现不需要重新选型。

### 前端

推荐本地 Web UI：

- TypeScript
- React 或轻量等价框架
- Vite 构建静态资源
- 构建产物由本地后端或 app bundle 托管

运行时不依赖 Node.js。

### macOS 壳

v1 推荐使用轻量 app launcher：

- 启动本地 gateway / admin server
- 打开内置或本地 Web UI
- 接 Sparkle 更新框架
- 不把推理逻辑放进 UI 进程

### 存储与系统能力

- SQLite 保存配置和元数据
- macOS Keychain 保存敏感材料
- LaunchAgent 负责自启动和守护
- Sparkle 负责 app 更新

## 总体结构

```text
Client / Agent
  -> Protocol Facade
  -> Canonical Request
  -> Router Snapshot
  -> Provider Adapter
  -> Local Provider
  -> Local Model
```

控制面：

```text
Web UI
  -> Admin API
  -> Store
  -> Runtime Snapshot
  -> Gateway / UI refresh
```

## 模块划分

### 1. 协议外壳

职责：

- 接 Anthropic compatible 请求
- 接 OpenAI compatible 请求
- 将不同协议转成 canonical request
- 将 canonical response 转回各自协议

规则：

- 入口只做一次转换
- 出口只做一次转换
- 不允许协议之间互相转译

### 2. 网关核心

职责：

- 模型路由
- provider 选择
- token 计数
- 流式转发
- 错误归一化

### 3. 路由器

职责：

- 读取逻辑模型名
- 命中模型映射表
- 返回 `provider + model + base_url`

默认逻辑：

1. 先查显式映射。
2. 命中则返回配置值。
3. 未命中则回退到默认 provider。
4. model 名默认沿用逻辑模型名。

### 4. Provider Adapter

职责：

- 构造上游请求
- 处理 Ollama / vLLM 差异
- 执行 stream 或 non-stream 请求
- 转成统一错误

### 5. Control Plane

职责：

- 配模型
- 发 key
- 看状态
- 管更新
- 查日志

### 6. Store

职责：

- 保存模型配置
- 保存 key 元数据
- 保存更新记录
- 保存最小审计信息

推荐：

- 配置与元数据用 SQLite
- root secret 或敏感材料放 Keychain
- runtime 侧只读快照

## 接口设计

### Gateway API

- `POST /v1/messages`
- `POST /v1/messages/count_tokens`
- `GET /v1/models`
- `GET /healthz`
- `GET /metrics`（可选）

### 协议契约基线

核心内部只认 canonical schema。

`CanonicalRequest` 固定包含：

- `request_id`
- `protocol`
- `api_key_id`
- `model`
- `messages`
- `system`
- `max_tokens`
- `stream`
- `temperature`
- `top_p`
- `top_k`
- `stop_sequences`
- `tools`
- `tool_choice`
- `metadata`
- `stream_options`

协议外壳负责把 Anthropic / OpenAI 的字段映射到这些结构，不允许在核心路由中读取协议私有字段。额外的协议私有字段只能进入 `metadata` 或被 facade 丢弃，不得污染 router 和 provider。

`CanonicalResponse` 固定包含：

- `id`
- `type`
- `model`
- `role`
- `content`
- `stop_reason`
- `usage`
- `stop_sequence`（可选）
- `created_at`（可选）

`CanonicalStreamEvent` 固定包含：

- `event_type`
- `index`
- `delta`
- `usage`
- `stop_reason`
- `raw_provider_event`（可选，仅调试使用）

### 路由失败语义

- 路由不存在或被禁用：`404`
- key 无效：`401`
- key 无权限：`403`
- provider 能力不支持：`501`
- provider 不可达或协议失败：`502`
- provider 超时：`504`

生成路径不做自动重试和跨 provider 迁移。若要切换 provider，必须由 router 预先选择，而不是在失败后现场跳转。

### Provider 能力矩阵

每个 provider 都必须声明能力，而不是由调用路径隐式判断。

基础能力字段：

- `supports_messages`
- `supports_stream`
- `supports_count_tokens`
- `supports_tools`
- `supports_system`
- `max_context_tokens`

首版能力建议：

| provider | messages | stream | count_tokens | tools | system |
| --- | --- | --- | --- | --- | --- |
| ollama | yes | yes | estimate | degraded | yes |
| vllm | yes | yes | estimate | provider-dependent | yes |

`estimate` 表示用网关估算，不调用 provider 原生 token count。
`vllm` 在首轮落地里先作为预留 provider，默认关闭，等 phase 6 再切到可用实现。

### key 与权限契约

key 用于区分不同智能体和权限范围。

约定：

- 每个智能体独立 key。
- key 明文只在创建时展示一次。
- 服务端只保存 hash、prefix 和元数据。
- Gateway API 必须校验 key。
- Admin API 使用本地管理权限，不复用智能体 key。

scope 建议：

- `messages:create`
- `tokens:count`
- `models:list`
- `admin:read`
- `admin:write`

鉴权 header：

- Anthropic compatible: `x-api-key`
- OpenAI compatible: `Authorization: Bearer <key>`

内部统一成 `api_key_id` 和 `scopes`。

### 观测契约

最小结构化日志字段：

- `request_id`
- `api_key_id`
- `protocol`
- `route_id`
- `provider`
- `model`
- `status_code`
- `latency_ms`
- `first_token_latency_ms`
- `stream_chunks`
- `error_code`

最小指标：

- `request_total`
- `request_failed_total`
- `request_duration_ms`
- `first_token_latency_ms`
- `provider_error_total`
- `route_miss_total`
- `auth_denied_total`
- `stream_cancel_total`

### Admin API

- `GET /api/v1/status`
- `GET /api/v1/settings`
- `PUT /api/v1/settings`
- `GET /api/v1/models`
- `POST /api/v1/models`
- `POST /api/v1/keys`
- `DELETE /api/v1/keys/{id}`
- `POST /api/v1/update/check`
- `POST /api/v1/update/install`

## 请求流

### Anthropic 请求流

```text
request -> Anthropic facade -> canonical request -> router -> adapter
        -> upstream stream -> canonical response -> Anthropic response
```

### OpenAI 请求流

```text
request -> OpenAI facade -> canonical request -> router -> adapter
        -> upstream stream -> canonical response -> OpenAI response
```

### Admin 请求流

```text
UI -> Admin API -> store write -> snapshot refresh -> UI
```

## 代码落点

### 当前模块的职责

- `main.py`: 组装应用和依赖
- `models.py`: canonical schema
- `router.py`: 路由解析
- `translator.py`: 协议翻译
- `streaming.py`: 流式直通
- `providers/*`: provider 适配器

### 下一阶段建议新增

- `admin.py` 或 `admin/`: 控制面 API
- `store.py`: SQLite 访问层
- `security.py`: key 生成、hash、轮换、吊销
- `runtime.py`: 只读配置快照
- `metrics.py`: 观测数据
- `updater.py`: 更新检查与安装状态

### 目标目录

```text
src/local_llm_gateway/
  app.py
  main.py
  models.py
  core/
    runtime.py
    service.py
    errors.py
  facades/
    anthropic.py
    openai.py
  admin/
    routes.py
    schemas.py
  providers/
    base.py
    ollama.py
    vllm.py
    registry.py
  storage/
    sqlite.py
    migrations.py
  security.py
  streaming.py
  translator.py
  metrics.py
```

这个目录是目标结构，不要求一次性重构完成。

## 运行时数据模型

### ModelRoute

- `logical_name`
- `provider`
- `model`
- `base_url`
- `enabled`
- `priority`

### ProviderConfig

- `name`
- `base_url`
- `timeout_s`
- `keepalive`
- `supports_stream`
- `supports_token_count`

### ApiKeyRecord

- `id`
- `name`
- `prefix`
- `hash`
- `scopes`
- `status`
- `created_at`
- `expires_at`
- `last_used_at`

### UpdateRecord

- `current_version`
- `latest_version`
- `feed_url`
- `last_check_at`
- `last_result`

## 错误设计

- `400`: 请求不合法
- `401`: key 无效
- `403`: key 无权限
- `404`: 资源不存在
- `429`: 限流
- `500`: 内部异常
- `502`: 上游协议或网络失败
- `504`: 上游超时
- `501`: 能力不支持

错误处理原则：

- 先归一化，再返回
- 不向上游直接泄露内部堆栈
- 流式中断要能回收连接

## 运行拓扑

v1 推荐同一个后端进程托管 Admin API 和 Gateway API，但分路径、分权限、分中间件。

```text
ModelRelay.app
  -> backend process
       -> Gateway API: /v1/*
       -> Admin API: /api/v1/*
       -> Static UI: /
```

约束：

- 允许后续拆成两个进程，但 v1 不强制。
- Gateway 热路径不能访问慢存储。
- Admin 写入配置后刷新 runtime snapshot。
- UI 只访问 Admin API，不直接访问 Gateway 内部对象。

## 性能预算

- 路由只做一次
- 配置只读快照，不落慢查询
- 流式不整包缓存
- token 统计短 TTL 缓存
- admin 请求不抢占推理热路径

## 测试矩阵

### 单元测试

- 路由映射
- 协议转换
- key 生成与校验
- token 估算

### 集成测试

- Anthropic 请求流
- OpenAI 请求流
- admin 配置变更
- provider mock 返回

### 性能测试

- 首 token 延迟
- 网关额外开销
- 请求放大后的退化

## 落地顺序

1. 先补 canonical schema。
2. 再补 protocol facade。
3. 再补 router snapshot 和 provider adapter。
4. 再补 store、key 和 admin API。
5. 最后补 UI、更新和打包。
