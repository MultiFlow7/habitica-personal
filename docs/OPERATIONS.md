# 个人版本的开发、升级和部署

源码仓库：`MultiFlow7/habitica-personal`。经所有者授权公开源码；运行数据保持私密。
官方来源：`HabitRPG/habitica`。首次基线为官方 5.50.2 开发线提交
`fb6de8f`；完整编号可从首次个人提交的父提交查到。

## 分支和版本

首次克隆后启用本地隐私检查（Git 不会自动安装 hooks）：

```sh
git config core.hooksPath scripts/githooks
```

- `origin/main`：个人稳定版本。
- `feature/名称`：单项功能，通过 PR 的 Personal release 检查后合入 main。
- `upgrade/官方版本`：官方升级候选，先验证再合入。
- `personal-vX.Y.Z`：经过验证的个人发布标签。
- `upstream`：只用于获取官方更新，本机已禁用向它推送。

日常修改：

```sh
git switch main
git pull --ff-only origin main
git switch -c feature/my-change
# 修改代码；配置、界面、游戏逻辑分别提交
git add <具体文件>
git commit -m "Describe the behavior change"
git push -u origin HEAD
gh pr create --base main
```

PR 的 Personal release 检查会构建 Linux 生产镜像，运行共享游戏逻辑测试，
并在 GitHub Actions 临时数据库上验证页面资源、注册、登录、任务创建、打卡、经验和金币。
上游完整测试工作流保留为手动触发，较大改造应额外运行相关测试。
CI 不保存服务器 SSH 密钥，也不会自动部署。

## 数据与公开仓库的边界

账号、密码哈希、任务、习惯、历史记录等仅存于服务器 MongoDB 的独立 Docker 卷。
运行配置只在服务器 `config.json`，数据库备份只在服务器 `backups/`。
服务器运行目录不是 Git 仓库；`ops` 只上传固定程序包，没有将数据库同步到 GitHub 的命令。
GitHub Actions 使用随机生成的配置和临时测试账号，不能连接正式数据库。
公开镜像使用显式文件清单复制程序，不包含运行配置、数据库卷或备份。

`.gitignore` 与 `.dockerignore` 排除常见私密路径；本地提交和推送 hook 检查文件路径与常见密钥，
PR 在云端重复检查个人提交历史。使用 GitHub 的密钥扫描与推送保护作为补充。
新增功能时不要把真实用户数据写进源码、测试 fixture、截图、Issues、PR、日志或发布说明；
需要示例时使用合成数据。GitHub 同步只同步已提交文件，不会自行读取服务器数据库。

这些检查降低误提交风险，不能识别任意格式的日记或个人信息，也不能保证从不泄露。
`git add -f`、`--no-verify` 或更改检查可绕过本机保护；因此仍需检查 PR diff，
不要给 CI 添加服务器密钥。若密钥误公开，立即撤销和轮换；仅删除文件无法清除历史。

## 获取官方更新

```sh
git fetch upstream --tags
git switch main
git switch -c upgrade/selected-version
git merge <明确选择的官方标签或提交>
```

阅读官方变更和 `migrations/`，处理冲突，检查依赖、配置和数据结构变化。
先在测试数据库上验证，禁止把集成测试指向正式数据库。PR 通过检查后再合入 main。
不要在服务器直接拉取 upstream/develop，不要自动执行迁移目录中的脚本。
首次基线来自 develop，后续官方标签需要包含或正确兼容该基线，不能盲目向后合并旧版本。

## 发布和部署

在 main 手动运行 Personal release，成功后给同一提交打标签。标签构建也可用于后续发布。

```sh
gh workflow run personal-release.yml --ref main
gh run list --workflow personal-release.yml
./ops deploy <成功的运行ID>
```

`./ops deploy` 检查构建结果，下载带 SHA256 校验的固定镜像，通过 SSH 上传服务器，
先备份数据库，再切换版本并执行应用冒烟验证。失败时恢复先前的应用镜像和 Compose 配置。
镜像标签使用完整提交 SHA，服务器不构建源码、不追踪 latest。
云端构建产物默认保留 7 天；正式版本应同时保存到 GitHub Release 和服务器 releases 目录。

服务器布局：

```text
/srv/habitica-personal/
  config.json          私密运行配置
  .env                 当前镜像版本
  compose.yml          当前运行配置
  manage.sh            运维入口
  releases/<commit>/   固定部署包和校验清单
  backups/             MongoDB 备份
  deployments.log      版本切换记录
```

默认内存上限：应用 768MiB，MongoDB 512MiB（WiredTiger 缓存 256MiB）。
应用单进程运行，Node 堆上限 512MiB；数据库只接入专用 Docker 网络。
网页端口只绑定服务器 `127.0.0.1:8317`。未配置邮件、推送、第三方登录和支付。
无邮件时不能通过邮件找回密码；账号注销依赖的上游后台 worker 也未部署。

## 本机操作

私密连接配置 `.habitica-server.json`（已被 Git 忽略）：

```json
{
  "host": "user@your-server",
  "identity": "~/.ssh/your-key",
  "directory": "/srv/habitica-personal"
}
```

```sh
./ops status
./ops logs
./ops backup
./ops tunnel
./ops close-tunnel
```

隧道运行期间访问 http://127.0.0.1:8317 。隧道在后台运行，通过 `./ops close-tunnel` 关闭。
后续可独立配置 HTTPS 域名和反向代理；无需修改现有网站的入口。

如需本机完整调试环境：`./dev install`，然后 `./dev start`；结束后 `./dev stop`。
此步骤会重新下载 Node、依赖，并需要 Docker；平时只编辑源码或运行 `ops` 不需要它们。

## 回滚与数据恢复

```sh
./ops rollback <服务器上保留的旧提交完整SHA>
```

这只切换应用版本，并会先另做数据库备份。若升级涉及数据迁移，需确认旧版本兼容迁移后的数据。
数据库恢复必须单独执行，恢复前停止写入并再做备份；恢复旧快照可能丢失快照之后的记录。
当前脚本不会自动迁移或回退数据库。

备份默认保留在服务器，同机备份不能防止整台服务器丢失；需要时通过 SCP 另存一份。
脚本不会自动清理历史发布和备份，磁盘空间不足时根据版本记录人工选择清理。
