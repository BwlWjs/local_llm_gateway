# 开发环境

## 当前状态

本机 macOS 环境可继续阅读和整理代码，但不适合作为当前主开发环境，因为系统缺少可直接使用的命令行工具链。
Ubuntu 开发虚拟机已经创建并启动，VM 包位于 `~/Library/Containers/com.utmapp.UTM/Data/Documents/ModelRelay Ubuntu 24.04.utm`。

## 迁移决策

- 主开发环境：Ubuntu 24.04 LTS Server 虚拟机
- 架构：arm64
- 镜像：`ubuntu-24.04.4-live-server-arm64.iso`
- 编辑器：VS Code
- macOS 保留用途：后续 `ModelRelay.app` 打包、签名、macOS 交付

## 迁移原因

- `git`、测试、Python 工具链在 Ubuntu 上更稳定
- 避免受 macOS 命令行工具链缺失影响
- 后续前后端开发、单测、提交都更顺畅
- Server 版镜像更轻，适合长期开发机
- ISO 已内置到 UTM 虚拟机包内，避免沙盒访问外部路径失败

## 保留事项

- 最终 macOS 安装包仍需要回到本机完成
- 代码仓库建议在 Ubuntu 虚拟机内重新 clone 一份
