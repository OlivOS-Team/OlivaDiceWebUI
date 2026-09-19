# OlivaDiceWebUI

青果骰管理页面在同一个 `main` 分支维护两种安装版本。两版共用前端页面、Core/Master 管理逻辑和测试，只保留各自很薄的通信适配层。

| 版本 | 插件名 / namespace | 打开方式 |
| --- | --- | --- |
| 官方接入版 | `OlivaDice WebUI（官方接入版）` / `OlivaDiceWebUI` | OlivOS WebUI 的“插件页面”，使用官方消息桥 |
| 独立服务版 | `OlivaDice WebUI（独立服务版）` / `OlivaDiceWebUIStandalone` | 自行监听端口，使用独立管理令牌 |

官方接入版面向 OlivOS `0.11.90-alpha.2` 及更新版本，依据官方的 [WebUI 使用文档](https://doc.olivos.wiki/User/WebUI/) 和 [插件 WebUI 开发文档](https://doc.olivos.wiki/DevPlugin/WebUI/)。

## 仓库结构

| 路径 | 用途 |
| --- | --- |
| `frontend/` | 两个版本共用的 React、Vite、Tailwind 前端源码 |
| `OlivaDiceWebUI/` | 官方接入适配器、共用后端逻辑及单文件 `webui/` 页面 |
| `OlivaDiceWebUIStandalone/` | 独立 HTTP 服务适配器及其构建页面 |
| `OlivaDiceWebUI/bridge.py` | 官方 WebUI 消息桥的请求分发及分块文件传输 |
| `tests/` | 后端服务、桥接和打包测试 |
| `scripts/package.py` | 生成 OlivOS 安装 ZIP |
| [Releases](https://github.com/ShiaNyaa/OlivaDiceWebUI/releases/latest) | 同时提供官方接入版和独立服务版安装 ZIP |

## 管理范围

| 页面 | 功能 |
| --- | --- |
| 工作台 | 账号概况、配置及回复数量、牌堆索引、复制 `.master` 认证指令 |
| 账号与骰主 | 切换账号、管理骰主、建立及解除主从关系、账号数据复制、ZIP 导入导出 |
| 核心配置 | Core 固定配置和运行时扩展整数配置、JSON 导入导出、磁盘刷新、恢复默认 |
| 回复词 | 按机器人账号搜索与分页、编辑、新增及删除自定义键、JSON 导入导出、批量恢复 |
| 帮助文档 | 按机器人账号搜索、编辑、新增及删除自定义词条 |
| 牌堆管理 | 查看已加载牌堆与文件加载状态、安装及删除本地文件、重新加载；可选接入 Extiverse 市场 |
| 自动备份 | 编辑计划、JSON 导入导出、磁盘刷新、单项及全部恢复 |

账号关系、数据迁移和备份需要 OlivaDiceMaster；牌堆市场需要 OlivaDiceOdyssey。缺少可选插件时，相应页面会显示原因。

两个版本共用同一套界面与主题逻辑：官方接入版默认顶部导航，独立服务版默认左侧导航；用户可在页面右上角切换导航方向及亮色/暗色主题。

## 安装与打开

1. 安装 OlivOS 和 OlivaDiceCore。需要账号迁移、备份或牌堆市场时，再安装 OlivaDiceMaster / OlivaDiceOdyssey。
2. 从 [最新 Release](https://github.com/ShiaNyaa/OlivaDiceWebUI/releases/latest) 选择下载：`OlivaDiceWebUI-YYYYMMDD.N.zip` 为官方接入版，`OlivaDiceWebUIStandalone-YYYYMMDD.N.zip` 为独立服务版。两者注册名、namespace、安装目录和自身数据目录均不同，可以同时安装。
3. 官方接入版：登录 OlivOS WebUI 后，从侧栏“插件页面”打开“青果骰管理”。不要单独打开插件 HTML；脱离宿主 iframe 时没有消息桥。
4. 独立服务版：默认访问 `http://127.0.0.1:8765/`，管理令牌位于 `plugin/data/OlivaDiceWebUIStandalone/admin-token.txt`；监听设置保存在同目录的 `network.json`。

官方接入版的远程访问、端口和认证均由 OlivOS WebUI 统一配置；它运行在无同源权限的插件沙箱中，不能读取父页面 DOM、存储或令牌，也不直接使用 `fetch`、XHR 或 WebSocket。独立服务版则只使用自己的监听设置和管理令牌，不依赖 OlivOS WebUI。

## 接入实现

官方版通过 `app.json.webui_config` 注册 `webui/olivadice.html`，使用 `window.parent.postMessage` 和 `plugin_event.send('webui', ...)` 通信。独立版通过同源 HTTP API 和 Bearer 令牌通信，并额外提供服务设置页面。账号、配置、回复词、帮助、牌堆、备份等代码全部共用。

OlivOS 对单个桥接 HTTP 请求限制为 1 MiB。项目对大 JSON、牌堆文件和账号 ZIP 使用 256 KiB 分块顺序传输，并将传输绑定到当前宿主会话。原有上限保持不变：JSON 4 MiB、牌堆 12 MiB、账号 ZIP 100 MiB。中断的临时传输会在十分钟后清理。

## 开发和验证

```sh
npm ci --prefix frontend
npm run lint --prefix frontend
npm run build --prefix frontend
python3 -m unittest discover -s tests -v
python3 scripts/package.py
```

一次前端构建会生成 `OlivaDiceWebUI/webui/olivadice.html` 和 `OlivaDiceWebUIStandalone/web/`；一次打包会在 `dist/` 生成两个 ZIP。官方版是无外部资源的单文件页面，以兼容 OlivOS 插件沙箱；独立版保留普通静态资源，交由自身 HTTP 服务提供。

## 版本与自动发布

推送到 `main` 后，GitHub Actions 会从同一份源码构建、测试并打包两个版本。成功后使用同一个北京时间版本号创建 Release，同时上传 `OlivaDiceWebUI-YYYYMMDD.N.zip` 和 `OlivaDiceWebUIStandalone-YYYYMMDD.N.zip`。

## 许可与致谢

本项目复用了 AGPL-3.0 系列项目的代码与资源，包括 Dice!Next WebUI 的部分前端组件、样式、构建配置和字体资源，以及 OlivaDiceNativeGUI 的说明文本。本仓库采用 AGPL-3.0 许可证。
