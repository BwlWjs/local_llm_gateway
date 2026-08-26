#!/bin/bash
# 在 macOS 宿主机上安装 Ollama 并拉取本地模型（无需 Homebrew）。
# 用法: ./install-ollama-macos.sh [模型名，默认 qwen2.5-coder:7b]
set -euo pipefail

MODEL="${1:-qwen2.5-coder:7b}"
INSTALL_BIN="${HOME}/bin/ollama"
OLLAMA_HOST_ENV="${OLLAMA_HOST:-0.0.0.0:11434}"

echo "==> 下载 Ollama (macOS) ..."
WORK="$(mktemp -d)"
curl -fL --retry 3 "https://ollama.com/download/Ollama-darwin.zip" -o "${WORK}/ollama.zip"

echo "==> 解压 ..."
unzip -q "${WORK}/ollama.zip" -d "${WORK}/app"

# 在 .app 包里定位 ollama CLI 二进制（优先 Contents/Resources）
BIN="$(find "${WORK}/app" -type f -name ollama -path "*Resources*" | head -1)"
[ -z "${BIN}" ] && BIN="$(find "${WORK}/app" -type f -name ollama | head -1)"
if [ -z "${BIN}" ]; then
  echo "错误：未在 app 包里找到 ollama 二进制" >&2
  exit 1
fi

mkdir -p "$(dirname "${INSTALL_BIN}")"
cp "${BIN}" "${INSTALL_BIN}"
chmod +x "${INSTALL_BIN}"
echo "==> 已安装到 ${INSTALL_BIN}"

# 启动服务，监听所有网卡，让 VM 里的网关能通过 192.168.64.1:11434 访问
echo "==> 启动 ollama serve（OLLAMA_HOST=${OLLAMA_HOST_ENV}）..."
OLLAMA_HOST="${OLLAMA_HOST_ENV}" nohup "${INSTALL_BIN}" serve > /tmp/ollama-serve.log 2>&1 &
sleep 4

if ! curl -s -o /dev/null "http://127.0.0.1:11434/"; then
  echo "警告：ollama serve 似乎没起来，看 /tmp/ollama-serve.log" >&2
fi

echo "==> 拉取模型 ${MODEL}（约 4.7GB，视网络可能较久）..."
"${INSTALL_BIN}" pull "${MODEL}"

echo ""
echo "==> 完成。"
echo "    ollama 二进制: ${INSTALL_BIN}"
echo "    模型: ${MODEL}"
echo "    服务地址: http://127.0.0.1:11434  (宿主机) / http://192.168.64.1:11434 (VM 访问)"
echo ""
echo "    把 ollama 加入 PATH:"
echo "    export PATH=\"\$HOME/bin:\$PATH\""
echo ""
echo "    注意：以后手动重启服务时也要带 OLLAMA_HOST=0.0.0.0:11434，否则 VM 连不上。"
