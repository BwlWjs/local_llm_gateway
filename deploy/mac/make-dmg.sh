#!/bin/bash
# Build a ModelRelay.app bundle and a .dmg. Runs on macOS (requires hdiutil).
set -euo pipefail

APP_NAME="ModelRelay"
VERSION="${MODELRELAY_VERSION:-0.1.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${ROOT}/build"
APP="${BUILD_DIR}/${APP_NAME}.app"

rm -rf "${APP}"
mkdir -p "${APP}/Contents/MacOS" "${APP}/Contents/Resources"

cp "${ROOT}/launch.sh" "${APP}/Contents/MacOS/launcher"
chmod +x "${APP}/Contents/MacOS/launcher"

cat > "${APP}/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>ModelRelay</string>
  <key>CFBundleIdentifier</key><string>com.modelrelay.app</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundlePackageType</key><string>APPL</string>
</dict>
</plist>
PLIST

echo "Creating ${APP_NAME}-${VERSION}.dmg ..."
hdiutil create -volname "${APP_NAME}" -srcfolder "${APP}" -ov -format UDZO "${BUILD_DIR}/${APP_NAME}-${VERSION}.dmg"
echo "Done: ${BUILD_DIR}/${APP_NAME}-${VERSION}.dmg"
