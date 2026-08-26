# 文档索引

这个目录是 `README.md` 的展开版。

- `README.md` 是项目入口页，负责一句话说明、当前状态、启动方式和总链接。
- `docs/README.md` 是文档地图，负责告诉你每份文档该什么时候读。
- `docs/detailed-design.md` 是落代码前的详细设计基线。

## 推荐阅读顺序

1. [README.md](../README.md)
2. [docs/design-review.md](design-review.md)
3. [docs/product-design.md](product-design.md)
4. [docs/architecture.md](architecture.md)
5. [docs/detailed-design.md](detailed-design.md)
6. [docs/technical-implementation.md](technical-implementation.md)
7. [docs/implementation-plan.md](implementation-plan.md)
8. [docs/dev-environment.md](dev-environment.md)
9. [docs/mac-delivery.md](mac-delivery.md)
10. [docs/performance.md](performance.md)
11. [deploy/mac/README.md](../deploy/mac/README.md)

## 文档层级

- 项目入口：`README.md`
- 文档索引：`docs/README.md`
- 产品设计：`docs/product-design.md`
- 系统设计：`docs/architecture.md`
- 详细设计：`docs/detailed-design.md`
- 代码实现设计：`docs/technical-implementation.md`
- 编码计划：`docs/implementation-plan.md`
- 开发环境：`docs/dev-environment.md`
- 交付部署设计：`docs/mac-delivery.md` 和 `deploy/mac/README.md`
- 性能与测试约束：`docs/performance.md`

## 文档职责

| 文档 | 作用 | 和 README 的关系 |
| --- | --- | --- |
| [README.md](../README.md) | 项目入口、快速启动、当前阶段结论 | 主入口 |
| [design-review.md](design-review.md) | 设计闭环、决策、完成标准 | README 的状态依据 |
| [product-design.md](product-design.md) | 产品目标、用户、边界、体验 | README 的上层定义 |
| [architecture.md](architecture.md) | 系统分层、模块协同、接口契约 | README 的系统展开 |
| [detailed-design.md](detailed-design.md) | 详细实现设计、数据流、接口、存储、模型选择 | README 的落代码基线 |
| [technical-implementation.md](technical-implementation.md) | 代码组织、设计模式、性能优化、测试策略 | 详细设计的实现补充 |
| [implementation-plan.md](implementation-plan.md) | 前后端工程主体和实现顺序 | 编码入口 |
| [mac-delivery.md](mac-delivery.md) | macOS 部署、升级、打包、UI 更新 | 产品交付补充 |
| [performance.md](performance.md) | 性能目标、评测方法、优化约束 | 非功能约束补充 |
| [deploy/mac/README.md](../deploy/mac/README.md) | macOS 打包脚本目录说明 | mac-delivery 的脚本入口 |

## 约定

- 先改 `README.md`，再改这里，再改细分文档。
- 如果产品名、模型默认值、接口边界变化，必须先同步索引。
- 如果实现和文档冲突，以索引和详细设计为准，再回写 README。
- 默认模型路径以 `local-coder -> ollama -> qwen2.5-coder:7b` 为准。
