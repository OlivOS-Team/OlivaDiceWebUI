# OlivaDiceWebUI

青果骰的跨平台浏览器管理界面，作为 OlivOS 插件与 OlivaDiceCore 在同一进程中运行。它覆盖 OlivaDiceNativeGUI 的主要管理流程，无需 Tk 窗口。仓库内包含完整的 React、Vite、Tailwind 前端源码、Python 插件、测试和构建脚本。

## 仓库结构

| 路径 | 用途 |
| --- | --- |
| `frontend/` | 可独立安装依赖并构建的前端源码 |
| `OlivaDiceWebUI/` | OlivOS 插件与已构建的静态页面，可直接复制到 `plugin/app/` |
| `tests/` | 后端接口与页面服务测试、无需真实账号的演示服务 |
| `scripts/package.py` | 从当前源码生成 OlivOS 安装 ZIP |
| `scripts/publish_release.py` | 为通过验证的 `main` 构建编号并发布 Release |
| [Releases](https://github.com/ShiaNyaa/OlivaDiceWebUI/releases/latest) | 自动构建的安装 ZIP 下载页 |

## 管理范围

| 页面 | 功能 |
| --- | --- |
| 工作台 | 账号概况、配置及回复数量、牌堆索引、复制 `.master` 认证指令 |
| 账号与骰主 | 切换账号、管理骰主、建立及解除主从关系、账号数据复制、ZIP 导入导出 |
| 核心配置 | Core 固定配置和运行时扩展整数配置、通知群与心跳地址列表、单项恢复或删除、JSON 导入导出、磁盘刷新、恢复默认 |
| 回复词 | 搜索、编辑、新增及删除自定义键、单项恢复、恢复模块列表、JSON 导入导出、磁盘刷新、批量恢复 |
| 帮助文档 | 搜索、编辑、新增及删除自定义词条 |
| 牌堆管理 | 已加载牌堆与分组、本地文件安装及删除、重新加载；安装 OlivaDiceOdyssey 后可浏览及安装 Extiverse 牌堆 |
| 自动备份 | 安装 OlivaDiceMaster 后编辑计划、JSON 导入导出、磁盘刷新、单项及全部恢复 |

账号关系、数据迁移和备份需要 OlivaDiceMaster；牌堆市场需要 OlivaDiceOdyssey。缺少可选插件时，相应页面会显示原因。WebUI 管理的是青果骰插件数据，不提供 OlivOS 自身的机器人登录和宿主进程控制。

## 安装与打开

1. 在目标机器的 OlivOS 中安装 OlivaDiceCore；需要账号迁移、备份或市场时，再安装对应的 OlivaDiceMaster / OlivaDiceOdyssey。
2. 从 [最新 Release](https://github.com/ShiaNyaa/OlivaDiceWebUI/releases/latest) 下载 `OlivaDiceWebUI-<版本号>.zip`，解压到 OlivOS 的 `plugin/app/`。开发调试时也可以先构建前端，再复制本仓库的 `OlivaDiceWebUI/` 目录。安装结果应是 `plugin/app/OlivaDiceWebUI/app.json`，并包含 Python 文件、说明 JSON 和 `web/` 构建产物。
3. 启动 OlivOS，默认在运行 OlivOS 的机器上访问 `http://127.0.0.1:8765/`。远程访问见下一节。若宿主菜单可用，也可点击“打开青果骰 WebUI”。
4. 首次启动会生成 `plugin/data/OlivaDiceWebUI/admin-token.txt`，把其中的令牌输入页面。令牌只存在当前浏览器标签页的 `sessionStorage` 中，关闭标签页后需重新输入。

所有 API 都需要令牌；请勿将令牌文件加入版本库或公开目录。WebUI 可以在支持 OlivOS 和 Core 的 Windows、macOS 或 Linux 环境中使用；实际宿主兼容性仍取决于所安装的 OlivOS 发行版及其他插件。

如需更换端口，在启动 OlivOS 前设置环境变量 `OLIVADICE_WEBUI_PORT`，例如 `OLIVADICE_WEBUI_PORT=8766 python main.py`。

## 远程访问

WebUI 使用当前浏览器地址访问同源 API。默认监听 `127.0.0.1`，避免未配置访问地址时意外对外开放。局域网或 VPN 中直接访问时，在启动 OlivOS 前设置监听地址和浏览器实际使用的来源地址：

```sh
OLIVADICE_WEBUI_BIND=0.0.0.0 \
OLIVADICE_WEBUI_PUBLIC_ORIGIN=http://192.168.1.10:8765 \
python main.py
```

把示例 IP 换成 OlivOS 主机的地址，然后从其他设备打开该 URL。`OLIVADICE_WEBUI_PUBLIC_ORIGIN` 必须与浏览器地址栏里的协议、域名/IP、端口一致，不含路径。服务端会校验 `Host` 与写入请求的 `Origin`，不匹配时拒绝访问。

通过 HTTPS 反向代理公开时，保留默认的本机监听，并设置 `OLIVADICE_WEBUI_PUBLIC_ORIGIN=https://dice.example.com`；代理转发到 `127.0.0.1:8765`，且保留原始 `Host` 头。公网访问应使用 HTTPS 或 VPN，避免管理令牌通过明文 HTTP 传输。也可以通过 SSH 端口转发访问本机监听的服务：`ssh -L 8765:127.0.0.1:8765 user@server`。

直接打开 `index.html` 只是静态外观预览；`file://` 无法连接本机 API。

## 开发和验证

前端源码在 `frontend/src/olivadice/`，入口与 Vite 配置分别是 `frontend/olivadice.html` 和 `frontend/vite.config.ts`。项目 logo 来自用户提供的 `olivos.svg`，原文件副本保存在 `assets/olivos.svg`，前端使用的副本在 `frontend/src/olivadice/assets/olivos.svg`。构建时会自动复制到插件的 `web/assets/` 并用作页面品牌标记与 favicon。

```sh
cd frontend
npm ci
npm run lint
npm run build
cd ..
python3 -m unittest discover -s tests -v
python3 scripts/package.py
```

构建结果写入 `OlivaDiceWebUI/web/`。`python3 scripts/package.py` 会在本地生成 `dist/` 安装包；该目录不提交到 Git。无需真实账号的演示服务：

```sh
python3 tests/demo_server.py
```

访问 `http://127.0.0.1:8765/`，测试令牌为 `oliva-demo-2026`。演示数据只保存在测试进程内，重启后复原。

## 版本与自动发布

推送到 `main` 后，GitHub Actions 会构建前端、运行测试并打包。成功后按北京时间当天已有的发布标签递增编号，从 `1` 开始，例如当天的第一版为 `v20260918(1)`。CI 会把安装 ZIP 中 `app.json` 的版本写成 `20260918(1)`，并在 Release 附上同名 ZIP。PR 和手动运行只生成工作流附件，不占发布编号。仓库里的 `app.json` 保留源码版本；安装包内的版本以对应 Release 为准。

## 真实 OlivOS 联调

在 macOS 上使用真实 OlivOS 0.11.90、OlivaDiceCore 3.4.81、OlivaDiceMaster、OlivaDiceOdyssey 和此 WebUI 安装包启动了隔离测试实例。运行目录为本地的 `integration-real/`，端口是 `127.0.0.1:8766`；两个 `virtualTerminal` 测试账号没有平台凭据，不会连接聊天平台。该目录包含自动生成的管理令牌和测试数据，已加入 `.gitignore`，不随仓库发布。

联调已确认：四个插件加载；页面令牌登录；账号、配置、回复、帮助、内置牌堆与市场目录读取；开关、回复词、帮助词条、牌堆文件、骰主、主从关系、备份设置和恢复模块写入及恢复；账号 ZIP 导出；重启后配置继续可读。通过浏览器保存开关与回复词后，也核对了 Core 的磁盘文件。Core 的 67 个内置牌堆分组现会显示在工作台和牌堆页面。

账号数据复制及 ZIP 导入会整体覆盖目标账号，此次未做真实写入联调。实际聊天平台账号的登录、消息收发，以及 Windows/Linux 上的宿主运行也仍需在相应环境验证。

## 实现说明

WebUI 调用 Core 和 Master 已有的内存对象与保存函数，配置仍存放在原来的数据目录中，不修改 Core、Master 或 OlivOS 源码。WebUI 自身的写入由同一把锁串行化。JSON 请求上限为 4 MiB，牌堆文件为 12 MiB，账号 ZIP 为 100 MiB；文件路径和扩展名在服务端校验。跨插件线程同时修改同一份 Core 数据，以及不同 OlivOS 发行版的实际加载行为，仍需用真实账号回归验证。部分 Core 设置的运行效果取决于相应模块的重载时机。

## 致谢与许可

本项目复用了 AGPL-3.0 系列项目的代码与资源：[Dice!Next WebUI](https://github.com/DiceZone/Dice-Next-WebUI) 的部分前端组件、样式、构建配置和字体资源，以及 OlivaDiceNativeGUI 的回复词、配置项说明文本。本仓库附有 AGPL-3.0 许可证。
