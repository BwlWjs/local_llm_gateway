#!/bin/bash
# 在 macOS 宿主机上安装 Ollama 并拉取本地模型（无需 Homebrew）。
# 通过 Clash 代理下载，解决 GitHub release CDN 直连慢/被墙的问题。
set -euo pipefail

MODEL="${1:-qwen2.5-coder:7b}"
INSTALL_BIN="${HOME}/bin/ollama"
OLLAMA_HOST_ENV="${OLLAMA_HOST:-0.0.0.0:11434}"
PROXY="${PROXY:-http://127.0.0.1:7897}"   # Clash/Mihomo 代理端口

# 代理可用则走代理（github release CDN 直连太慢）
if curl -s -o /dev/null --max-time 5 -x "${PROXY}" https://github.com 2>/dev/null; then
  echo "==> 使用代理 ${PROXY}"
  CURL_ARGS=(-x "${PROXY}")
  export HTTPS_PROXY="${PROXY}" HTTP_PROXY="${PROXY}"
else
  echo "==> 代理不可用，改直连"
  CURL_ARGS=()
fi

echo "==> 下载 Ollama (macOS) ..."
WORK="$(mktemp -d)"
curl -fL --retry 3 "${CURL_ARGS[@]}" "https://ollama.com/download/Ollama-darwin.zip" -o "${WORK}/ollama.zip"

echo "==> 解压 ..."
unzip -q "${WORK}/ollama.zip" -d "${WORK}/app"

# 在 .app 包里定位 ollama CLI 二进制（优先 Contents/Resources）
BIN="$(find "${WORK}/app" -type f -name ollama -path "*Resources*" | head -1)"
[ -z "${BIN}" ] && BIN="$(find "${WORK}/app" -type f -name ollama | head -1)"
[ -z "${BIN}" ] && { echo "错误：未找到 ollama 二进制" >&2; exit 1; }

mkdir -p "$(dirname "${INSTALL_BIN}")"
cp "${BIN}" "${INSTALL_BIN}"
chmod +x "${INSTALL_BIN}"
echo "==> 已安装到 ${INSTALL_BIN}"

echo "==> 启动 ollama serve（OLLAMA_HOST=${OLLAMA_HOST_ENV}）..."
OLLAMA_HOST="${OLLAMA_HOST_ENV}" nohup "${INSTALL_BIN}" serve > /tmp/ollama-serve.log 2>&1 &
sleep 4
curl -s -o /dev/null "http://127.0.0.1:11434/" || echo "警告：serve 未起来，看 /tmp/ollama-serve.log"

echo "==> 拉取模型 ${MODEL}（约 4.7GB，可能较久）..."
"${INSTALL_BIN}" pull "${MODEL}"

echo ""
echo "==> 完成。ollama 二进制: ${INSTALL_BIN}"
echo "    服务: http://127.0.0.1:11434 (宿主机) / http://192.168.64.1:11434 (VM 访问)"
echo "    PATH: export PATH=\"\$HOME/bin:\$PATH\""
echo "    注意：以后手动重启服务要带 OLLAMA_HOST=0.0.0.0:11434"
