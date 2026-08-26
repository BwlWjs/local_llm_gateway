# macOS Deployment

ModelRelay 的 macOS 打包、自启动和更新脚本目录。产品级发布设计见 [docs/mac-delivery.md](../../docs/mac-delivery.md)。

## 文件说明

| 文件 | 用途 |
|------|------|
| `launch.sh` | 启动后端（`python3 -m local_llm_gateway`）并用浏览器打开控制 UI |
| `com.modelrelay.gateway.plist` | LaunchAgent 模板，登录自启动 + 崩溃自动拉起 |
| `make-dmg.sh` | 打包 `ModelRelay.app` + 生成 `.dmg`（依赖 macOS 自带 `hdiutil`） |
| `appcast.xml` | Sparkle 更新源模板（需替换 `REPLACE_*` 占位符并签名） |

## 本地快速启动

```bash
# 假设已经 pip install local_llm_gateway
chmod +x deploy/mac/launch.sh
MODELRELAY_PYTHON=/path/to/venv/bin/python deploy/mac/launch.sh
```

启动后打开 `http://127.0.0.1:8000`（控制 UI）。环境变量：

- `MODELRELAY_HOST` / `MODELRELAY_PORT`：默认 `127.0.0.1:8000`
- `MODELRELAY_PYTHON`：后端使用的 Python（默认 `python3`）

## 开机自启动（LaunchAgent）

```bash
cp deploy/mac/com.modelrelay.gateway.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.modelrelay.gateway.plist
```

## 打包 dmg

```bash
MODELRELAY_VERSION=0.1.0 deploy/mac/make-dmg.sh
```

产出 `deploy/mac/build/ModelRelay-0.1.0.dmg`。

## 待办（v1 之后）

- 代码签名 + 公证（`codesign` / `notarytool`），否则 macOS Gatekeeper 会拦截
- Sparkle 框架接入（`appcast.xml` 只是模板，需要 `sparkle:edSignature` 真签名）
- dmg 里带上 venv/依赖，避免依赖系统 `python3 -m local_llm_gateway` 已安装
