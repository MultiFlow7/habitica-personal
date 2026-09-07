# Habitica 本地改造环境

源码基于官方 `HabitRPG/habitica` 的 `develop` 分支，当前工作分支是 `local-dev`。
`upstream` 指向官方仓库。首次拉取为浅克隆，图片子模块已初始化。

## 日常使用

在项目目录打开终端：

```sh
./dev start
./dev status
./dev logs
./dev stop
```

- 网页：http://127.0.0.1:5173
- 后端：http://127.0.0.1:3000/api/v3/status
- 首次使用请在本地网页注册账号；账号与官方 Habitica 不互通。
- 前端、后端和 MongoDB 只绑定本机地址。
- `start` 会按需打开 Docker Desktop，并在后台启动服务。关闭终端不会停止服务。
- `stop` 会停止本项目的前后端进程和数据库容器，保留数据库数据。
- 电脑重启后运行 `./dev start`。

## 修改代码

| 目录 | 用途 |
|---|---|
| `website/client/src` | Vue 页面、组件、样式 |
| `website/server` | 后端接口、数据库模型 |
| `website/common/script` | 任务计分、经验、金币、装备等共享逻辑 |
| `website/common/locales` | 多语言文案 |
| `habitica-images` | 官方图片资源子模块 |

前端使用 Vite 热更新，后端使用 Node 的 watch 模式。修改共享逻辑或配置后，
如果没有自动生效，运行 `./dev restart`。修改图片后运行 `./dev sprites` 重新生成精灵图。

## 运行环境和依赖

- Node 20 位于 `work/runtime/node`，脚本自动使用它，不修改系统 Node。
- 当前安装的 Node 包为 macOS Apple Silicon 版本，换平台时需更换此运行时。
- 前后端依赖使用各自的 `package-lock.json` 安装。
- npm 使用 `work/npm-cache` 独立缓存，避开系统缓存权限问题。
- MongoDB 7.0 由 `compose.local.yml` 管理，本地端口 27017。
- 重新安装依赖并生成图片：`./dev install`。
- `./dev install` 对 git:// 依赖使用当前进程内的 HTTPS 重写，不修改全局 Git 配置。
- 本地配置在 `config.json`，会被 Git 忽略。它包含随机生成的会话密钥。
- 当前是开发环境：邮件、推送、第三方登录和支付未配置。日常使用本地用户名和密码登录。

## 数据与备份

数据库为 `habitica-local`，数据存放在 Docker 命名卷 `habitica-local_mongo-data`。
源码目录和数据库数据分开保存；不要删除该卷，或执行带 `-v` 的 Compose down。

数据库运行时执行：

```sh
./dev backup
```

备份保存到 `work/backups/时间.archive.gz`，此目录不会提交到 Git。
如需恢复，先停止前后端、启动 MongoDB，并使用 `mongorestore --archive --gzip` 导入备份。
恢复到已有数据前，应先另做备份并确认覆盖范围。

## 本地适配

1. 新增 `compose.local.yml`，隔离数据库卷并限制本机访问。
2. 后端监听地址支持 `HOST` 配置，本地设为 `127.0.0.1`。
3. 根目录安装脚本不再修改全局 Git 配置；前端依赖改用锁文件安装。
4. 新增 `dev` 和 `scripts/local-dev.py`，管理服务、日志、图片生成和备份。

这次只配置开发环境；角色数值、付费道具规则等仍采用官方源码逻辑，可在后续按需要修改。
