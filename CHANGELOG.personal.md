# 个人版本变更

## personal-v0.1.0

- 建立个人 Git 仓库、官方 upstream 和受控发布流程。
- GitHub Actions 构建固定提交的 Linux 生产镜像，并进行游戏逻辑和端到端 API 验证。
- 独立的 MongoDB 数据卷、资源上限、数据库备份及应用版本回退脚本。
- 本机通过 SSH 隧道使用服务器部署，按需重建本地开发环境。
- 新增 HOST 和 DISABLE_EMAILS 配置以适配个人部署。
- 未改动任务奖励、装备或其他核心游戏规则。
