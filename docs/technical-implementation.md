# 技术实现设计

## 目标

- 路由单内核
- 协议多外壳
- 控制面和数据面分离
- UI、更新、配置、key 管理不进入推理热路径
- 代码实现可分层、可测试、可替换

## 总体分层

### 1. 控制面

负责本地产品 UI、模型配置、key 管理、更新检查、日志查看和运行状态。

推荐形态：

- 本地 Web UI
- 本地 Admin API
- 可选桌面壳

控制面只访问本地接口，不直接触碰 provider。

### 2. 数据面

负责 Anthropic / OpenAI 等协议入口、模型路由、provider 适配、流式转发和 token 统计。

数据面只关心：

- 请求是否合法
- 路由到哪个 provider
- 如何把上游字节流直通回去

### 3. Provider 面

负责对接 Ollama、vLLM-Metal 以及后续 provider。

provider 适配器只处理：

- 协议字段转换
- 请求 URL 和 header 组装
- stream / non-stream 的上游调用
- provider 特有错误映射

## 前后端配合

### 前端

前端是本地 Web UI，建议只做三类页面：

- Models: 配置本地模型和路由别名
- Keys: 创建、吊销、轮换智能体 key
- Updates: 版本检查、升级和重启

前端职责：

- 表单校验
- 状态展示
- 触发 admin API
- 展示失败原因

前端不做：

- 路由决策
- token 统计
- provider 调用

### 后端

后端分成两个服务域：

- `Admin API`: 给前端用
- `Gateway API`: 给 Claude Code 和其他智能体用

两者共享同一份运行时配置快照和存储层，但权限不同。

### 中间件

推荐的系统中间件：

- `SQLite`：保存模型配置、key 元数据、审计记录、更新记录
- `Keychain`：保存敏感密钥或本机根密钥
- `LaunchAgent`：负责自启动和后台守护
- `Sparkle`：负责 macOS 更新检查和升级
- `Reverse Proxy`：可选，用于本地域名、TLS 和入口整形

## 请求路径

### 数据面请求

```text
client -> protocol facade -> canonical request -> router snapshot -> provider adapter
       -> upstream stream -> translator -> client
```

执行步骤：

1. 入口协议层解析请求。
2. 校验字段并转成 canonical request。
3. 读取当前配置快照。
4. 做一次模型路由。
5. 选择 provider adapter。
6. 通过 httpx 连接池访问上游。
7. 流式场景边收边发。
8. 结束后回写 usage、日志和指标。

### 控制面请求

```text
ui -> admin api -> store/config service -> runtime snapshot -> ui
```

执行步骤：

1. UI 拉取当前状态。
2. 用户修改模型、key 或更新设置。
3. Admin API 写入持久层。
4. 发布新的只读运行时快照。
5. UI 刷新页面状态。

## 代码实现逻辑

### `main.py`

负责应用组装，不放业务规则。

职责：

- 注册路由
- 装载依赖
- 挂载 app state
- 初始化共享 http client、store、logger、metrics

### `models.py`

负责 canonical schema。

职责：

- 定义请求/响应模型
- 定义 provider target
- 定义 admin side 的配置结构

### `router.py`

负责逻辑模型名到 provider target 的解析。

推荐实现：

- 运行时只读快照
- model alias 映射表
- provider capability table

### `translator.py`

负责协议翻译。

职责：

- Anthropic / OpenAI -> canonical request
- canonical response -> protocol response
- 统一 message、tool、usage 和 error 格式

### `streaming.py`

负责流式转发。

职责：

- 直通上游 chunk
- 控制 backpressure
- 不做整包缓冲
- 需要时做 event 级轻量转换

### `providers/*`

负责 provider 具体实现。

职责：

- 请求组装
- 上游调用
- 错误映射
- token 计数

## 设计模式

### Facade

Anthropic、OpenAI、Admin UI 都是 facade，只负责入口和出口。

### Adapter

provider 适配器把 canonical request 翻成 Ollama / vLLM 的调用格式。

### Strategy

路由策略、provider 选择策略、限流策略都做成可替换策略对象。

### Registry

模型、provider、能力、key 都通过 registry 管理，而不是散在代码里。

### Snapshot

运行时配置采用只读快照，避免热路径加锁和反复读库。

### Pipeline

请求处理拆成校验、路由、适配、流式、审计几个稳定步骤。

### Soft Circuit Breaker

对连续失败的 provider 做冷却，不要把失败请求持续打进上游。

## 性能优化

### 热路径原则

- 一次解析
- 一次路由
- 一次序列化
- 一次上游调用

### 具体措施

- 复用 `httpx.AsyncClient`
- 连接池长驻
- stream 直通，不拼大包
- token count 结果做短 TTL 缓存
- 模型配置预计算成内存表
- 结构化日志延后到请求结束
- 统计和审计异步化
- 控制面和数据面分端口，避免 admin 流量挤占推理流量

### 避免的开销

- 每个 token 打同步日志
- 每次请求都读配置文件
- 反复 JSON parse/stringify
- 在适配器里再套协议转换
- 在 gateway 内部再发一个 gateway 请求

## 存储设计

- 配置类数据：SQLite
- key 材料：Keychain 或加密后落盘
- 审计日志：SQLite 或独立 log 文件
- 更新元数据：本地缓存 + feed

存储访问原则：

- 写入发生在控制面
- 读取优先走内存快照
- 数据面不直接访问慢存储

## middleware 协作

### TLS / 域名

如果需要稳定域名，建议在本机用 reverse proxy 或 app 内部 listener 处理。

### 更新

Sparkle 负责检测和下载升级包，UI 负责展示和触发。

### 本地启动

LaunchAgent 负责开机自启和后台拉起。

### Key 管理

敏感 key 不进入前端状态树，只返回最小必要信息。

## 测试策略

### 单元测试

- 路由解析
- 协议翻译
- token 估算
- key 校验

### 集成测试

- 数据面请求流
- 控制面配置更新流
- provider mock 回包

### 流式测试

- chunk 顺序
- 断流恢复
- cancel 传播

### 性能测试

- 首 token 延迟
- 网关额外开销
- 上下文变长退化
- provider 切换成本

## 落地顺序

1. 先冻结 canonical schema 和协议 facade。
2. 再做 router snapshot 和 provider adapter。
3. 然后补控制面 admin API、store 和 key 管理。
4. 最后补更新、指标和本地 UI 细节。
