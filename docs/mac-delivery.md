# macOS 交付与升级设计

## 目标

- 开发代码和产品交付产物不混在同一目录
- macOS 上以一个稳定的产品包交付 UI + 本地网关
- 升级只替换产品包，不覆盖用户数据和 key
- 控制面 UI 可以管理模型、key、更新和状态

## 目录边界

开发态只保留源码和设计文档：

- `src/` 运行时代码
- `docs/` 设计文档
- `deploy/mac/` macOS 打包、签名、发布脚本

交付态产物放到独立目录，且不进入源码提交：

- `release/mac/` 打包输出
- `release/mac/appcast.xml` 更新索引
- `release/mac/*.dmg` 或 `*.pkg` 安装包

运行态数据放在用户目录：

- `~/Library/Application Support/ModelRelay/`
- `~/Library/Logs/ModelRelay/`
- `~/Library/Keychains/` 或系统 Keychain

## 产品形态

v1 推荐一个统一发行单元：

- `ModelRelay.app` 作为唯一分发入口
- App 内包含控制面 UI
- App 内包含本地网关服务或其启动器
- UI 和网关按同一版本升级

这样可以避免 UI 升级了、网关没升级，或反过来的版本漂移。

## macOS 安装包

主方案采用 notarized `dmg`：

- `ModelRelay.app` 放在磁盘映像中
- 同时放一个 `/Applications` symlink
- App 和 DMG 都要签名
- 发布前完成 notarization 和 staple

这是最适合直接分发给本机开发者的形态。

## 什么时候用 pkg

只有在下面场景才考虑 `pkg`：

- 需要安装 privileged helper
- 需要写入系统级位置
- 需要额外组件由安装器负责落地

如果只是普通 `.app` 和本地网关，优先继续用 `dmg`，不要把升级复杂化。

## 升级机制

推荐使用 `Sparkle` 作为 UI 更新框架：

- UI 通过更新 feed 拉取版本信息
- feed 指向 `dmg` 产物
- UI 负责下载、校验、安装和重启
- 版本号和 build number 要单调递增

升级包中应包含：

- 安装包文件
- release notes
- 签名信息
- 最低系统版本
- 架构信息，例如 `arm64` / `universal2`

## 升级 UI

控制面 UI 的更新页建议包含：

- 当前版本
- 最新版本
- 上次检查时间
- 自动检查开关
- 发布说明
- 立即更新
- 稍后提醒

UI 只做展示和触发，不直接处理包文件细节。

## key 与配置

key 不放进安装包。

- key 在控制面 UI 中创建
- 每个智能体单独发一个 key
- key 只在创建时明文展示一次
- 服务端只保存 hash 或受保护密文
- 轮换和吊销都走控制面

## 更新接口

控制面和本地网关之间建议保留一组本地接口：

- `GET /api/v1/version`
- `GET /api/v1/update/status`
- `POST /api/v1/update/check`
- `POST /api/v1/update/restart`
- `POST /api/v1/keys`
- `DELETE /api/v1/keys/{id}`

这些接口只服务本机控制面，不对外暴露。

## 发布流程

1. 构建 app
2. 签名
3. notarize
4. 打包成 dmg
5. 生成更新 feed
6. 发布 release notes
7. 客户端拉取更新

## 设计原则

- 数据面和控制面分离
- 交付产物和源码分离
- key、配置、日志和 app bundle 分离
- 升级单位尽量只有一个
- 不把更新逻辑塞进推理热路径
