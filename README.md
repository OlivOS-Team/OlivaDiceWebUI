# OlivaDiceWebUI

青果骰管理页面，以插件页面方式接入 OlivOS 官方 WebUI。插件与 OlivaDiceCore 在同一进程中运行，由 OlivOS 负责页面挂载、登录认证和消息转发；本插件不再启动独立 HTTP 服务，也不会接触 OlivOS WebUI 的令牌。

当前接入方式面向 OlivOS `0.11.90-alpha.2` 及更新版本，依据官方的 [WebUI 使用文档](https://doc.olivos.wiki/User/WebUI/) 和 [插件 WebUI 开发文档](https://doc.olivos.wiki/DevPlugin/WebUI/)。

## 仓库结构

| 路径 | 用途 |
| --- | --- |
| `frontend/` | React、Vite、Tailwind 前端源码 |
| `OlivaDiceWebUI/` | OlivOS 插件及已构建的单文件 `webui/` 页面 |
| `OlivaDiceWebUI/bridge.py` | 官方 WebUI 消息桥的请求分发及分块文件传输 |
| `tests/` | 后端服务、桥接和打包测试 |
| `scripts/package.py` | 生成 OlivOS 安装 ZIP |
| [Releases](https://github.com/ShiaNyaa/OlivaDiceWebUI/releases/latest) | 自动构建的安装 ZIP |

## 管理范围

| 页面 | 功能 |
| --- | --- |
| 工作台 | 账号概况、配置及回复数量、牌堆索引、复制 `.master` 认证指令 |
| 账号与骰主 | 切换账号、管理骰主、建立及解除主从关系、账号数据复制、ZIP 导入导出 |
| 核心配置 | Core 固定配置和运行时扩展整数配置、JSON 导入导出、磁盘刷新、恢复默认 |
| 回复词 | 全量搜索与分页、编辑、新增及删除自定义键、JSON 导入导出、批量恢复 |
| 帮助文档 | 搜索、编辑、新增及删除自定义词条 |
| 牌堆管理 | 查看已加载牌堆、安装及删除本地文件、重新加载；可选接入 Extiverse 市场 |
| 自动备份 | 编辑计划、JSON 导入导出、磁盘刷新、单项及全部恢复 |

账号关系、数据迁移和备份需要 OlivaDiceMaster；牌堆市场需要 OlivaDiceOdyssey。缺少可选插件时，相应页面会显示原因。

## 安装与打开

1. 安装 OlivOS `0.11.90-alpha.2` 或更新版本以及 OlivaDiceCore。需要账号迁移、备份或牌堆市场时，再安装 OlivaDiceMaster / OlivaDiceOdyssey。
2. 从 [最新 Release](https://github.com/ShiaNyaa/OlivaDiceWebUI/releases/latest) 下载 `OlivaDiceWebUI-YYYYMMDD.N.zip`，解压到 OlivOS 的 `plugin/app/`。安装结果应包含 `plugin/app/OlivaDiceWebUI/app.json` 和 `plugin/app/OlivaDiceWebUI/webui/olivadice.html`。
3. 启动或重载插件，登录 OlivOS WebUI；默认地址为 `http://127.0.0.1:20480`，认证令牌由 OlivOS 保存在 `conf/webui_token.txt`。
4. 从 OlivOS WebUI 侧栏的“插件页面”打开“青果骰管理”。不要单独打开插件 HTML；脱离宿主 iframe 时没有消息桥。

远程访问、端口和认证均由 OlivOS WebUI 统一配置。插件页面运行在无同源权限的沙箱中，不能读取父页面 DOM、存储或令牌，也不直接使用 `fetch`、XHR 或 WebSocket。

## 接入实现

`app.json.webui_config` 注册 `webui/olivadice.html`。前端使用 `window.parent.postMessage` 发送带唯一 `request_id` 的插件事件；Python 在 `Event.menu` 中校验命名空间和 WebUI 上下文，调用现有 Core/Master 服务后以 `plugin_event.send('webui', ...)` 回包。

OlivOS 对单个桥接 HTTP 请求限制为 1 MiB。项目对大 JSON、牌堆文件和账号 ZIP 使用 256 KiB 分块顺序传输，并将传输绑定到当前宿主会话。原有上限保持不变：JSON 4 MiB、牌堆 12 MiB、账号 ZIP 100 MiB。中断的临时传输会在十分钟后清理。

## 开发和验证

```sh
npm ci --prefix frontend
npm run lint --prefix frontend
npm run build --prefix frontend
python3 -m unittest discover -s tests -v
python3 scripts/package.py
```

构建结果写入 `OlivaDiceWebUI/webui/olivadice.html`，JavaScript、CSS 和 Logo 全部内联且不依赖外部资源，以兼容 OlivOS 的无同源插件沙箱。安装包写入 `dist/`。浏览器直接预览只能检查静态布局；完整通信必须在 OlivOS WebUI 的插件 iframe 中验证。

## 版本与自动发布

推送到 `main` 后，GitHub Actions 会构建前端、运行测试并打包。成功后按北京时间当天已有标签递增编号，例如 `v20260919(2)`；Release ZIP 使用点号兼容文件名，例如 `OlivaDiceWebUI-20260919.2.zip`。

## 许可与致谢

本项目复用了 AGPL-3.0 系列项目的代码与资源，包括 Dice!Next WebUI 的部分前端组件、样式、构建配置和字体资源，以及 OlivaDiceNativeGUI 的说明文本。本仓库采用 AGPL-3.0 许可证。
