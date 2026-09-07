# 按需启用本地开发环境

正式版本部署在服务器，本机默认只保留源码、Git 历史和远程运维入口。
开发、官方升级、发布、备份和回滚说明见 [操作指南](docs/OPERATIONS.md)。

需要完整本地调试时，在项目目录执行：

```sh
./dev install
./dev start
```

`install` 会重新下载项目专用 Node 20、安装依赖和初始化图片子模块；
`start` 会打开 Docker Desktop、启动本项目 MongoDB，并启动前后端热更新。
访问 http://127.0.0.1:5173 。本地账号和服务器账号互相独立。

```sh
./dev status
./dev logs
./dev restart
./dev stop
```

`stop` 保留本地数据库数据。日志、运行时和缓存位于被 Git 忽略的 `work/`。
只访问服务器时使用 `./ops tunnel`，不需要 Node、npm 或本地 Docker 数据库。
