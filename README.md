# 防熄屏 · AntiLockScreen

![Platform](https://img.shields.io/badge/platform-Windows-0078D4)
![Python](https://img.shields.io/badge/python-3.12-3776AB)
![License](https://img.shields.io/badge/license-MIT-green)

一个轻量的 Windows 桌面小工具，**防止电脑熄屏 / 锁屏**。现代化白色悬浮卡片 + 系统托盘 + 全局热键 + 可折叠的「台灯」迷你球，纯本地运行、零联网、单文件 exe 即用。

A lightweight Windows tool that **keeps your screen awake / prevents idle lock-screen**. Modern floating card UI + system tray + global hotkeys + a foldable mini "desk lamp" widget. Fully local, no network, ships as a single zero-install `.exe`.

> 📷 _可自行在 `docs/` 放界面截图后取消下面注释 / Drop screenshots into `docs/` and uncomment:_
> `<!-- ![main](docs/main.png) -->`

---

## 🇨🇳 中文文档

### ✨ 功能特性
- **一键开关**防锁屏，状态实时可见（绿/红状态点 + 计时）
- **四种防熄机制**，可随时切换：键盘 / 鼠标 / API / 组合
- **间隔自定义**（默认 60s，运行中可改）
- **两个全局热键**（Windows 原生 `RegisterHotKey`，不走键盘钩子，对管控软件更友好）
- **mini 台灯**：标题栏「缩小」折叠成透明镂空台灯；**开灯=亮灯+暖色光束，关灯=熄灯**；单击开关、拖动移动、右键还原
- **系统托盘**：最小化到托盘；左键显隐、右键菜单开关/退出
- **附加功能**（卡片「设置」区）：
  - 🔌 开机自启（往「启动」目录放/删快捷方式）
  - ⚡ 启动即开启（开机后自动防锁屏）
  - 🎲 间隔随机抖动（`60s × 0.8~1.2`，**反机器人检测**）
  - 🖱️ 鼠标模式不抢操作（你在动鼠标时先不抖）
  - 🔔 切换提示（气泡 + 蜂鸣）
- **会话计时 + 上次时长历史**：开启后显示已运行时长，关闭重置，并记录最近一次
- **配置自动持久化**，重启保留

### ⚙️ 工作原理（四种机制）
| 模式 | 原理 | 适用 / 说明 |
|---|---|---|
| 键盘 | 定时按 `F15`（无副作用），重置系统空闲计时器 | **默认，最稳**，对策略型屏保锁定最有效 |
| 鼠标 | 光标微移 1px 再移回（你正在动鼠标时自动跳过） | 可见，但不会干扰操作 |
| API | `SetThreadExecutionState` 请求显示/系统保持唤醒 | 主要防显示器/系统休眠；对**策略型屏保锁定可能无效** |
| 组合 | 键盘 + API 双保险 | 最稳 |

### 🚀 下载与使用（零安装）
1. 到 [Releases](../../releases) 下载 `AntiLockScreen.exe`
2. 双击运行 → 右上角出现悬浮卡片 + 右下角托盘图标
3. 点大按钮「开启防锁屏」即可

> 想要中文文件名可重命名为 `防熄屏.exe`。

### 🧑‍💻 开发运行
```bash
pip install -r requirements.txt
python anti_lockscreen.py
```

### 📦 自行打包成单文件 exe
直接双击 `build.bat`（会自动装依赖 + 生成图标 + 打包）：
```bash
build.bat
# 或手动：
python make_ico.py
pyinstaller --noconfirm --clean --onefile --noconsole --collect-all customtkinter --icon app.ico --name AntiLockScreen anti_lockscreen.py
```
产物：`dist\AntiLockScreen.exe`

### ⌨️ 快捷操作
| 操作 | 方式 |
|---|---|
| 开关防锁屏 | 大按钮 / `Ctrl+Alt+D` / 托盘菜单 / 台灯单击 |
| 显示/隐藏窗口 | `Ctrl+Alt+S` / 托盘左键 |
| 折叠成台灯 | 标题栏「缩小」按钮 |
| 移动窗口 | 拖动标题栏 / 拖动台灯 |
| 还原大卡片 | 台灯右键 |
| 自定义热键 | 卡片里点对应「热键」按钮，按下新组合（须含 Ctrl/Alt/Win，Esc 取消） |

### 🔒 配置与隐私
- 全部本地运行，**不联网、不上传任何数据**
- 配置文件：`%APPDATA%\AntiLockScreen\config.json`
- 开机自启快捷方式：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\防熄屏.lnk`

### 📁 文件结构
```
.
├── anti_lockscreen.py   # 主程序 / main app
├── make_ico.py          # 生成 app.ico / generate exe icon
├── app.ico              # exe 图标（自动生成）/ exe icon (generated)
├── requirements.txt     # 依赖 / dependencies
├── build.bat            # 一键打包 / one-click build
├── .gitignore
└── README.md
```

### ❓ 常见问题
- **还是被锁屏到登录？** → 用「键盘」或「组合」模式，间隔 ≤ 30–60s；纯 API 对策略型屏保锁定常无效。
- **被公司管控拦截/识别？** → 用「键盘 + 随机抖动」；自写小工具比知名软件（Caffeine/Move Mouse）更不易被特征识别。
- **开机不自启？** → 检查启动目录快捷方式是否存在；部分公司禁用「启动」目录，可改用「任务计划程序」触发。
- **托盘图标看不到？** → Windows 会折叠图标，点托盘区向上箭头展开，或拖到常驻区。

### ⚠️ 重要提醒
本工具仅供**合法的个人防熄屏场景**（演示、长编译、监控面板、长时间阅读等）。请遵守贵公司 IT 与安全政策；**对滥用或由此产生的任何后果，作者不承担责任**。建议优先向 IT 申请放宽锁屏策略。

### 🛠 技术栈
Python · customtkinter · pystray · Pillow · ctypes (Win32 API) · PyInstaller

---

## 🇬🇧 English

### ✨ Features
- One-click **anti-lock toggle**, live status (green/red dot + session timer)
- **Four keep-awake mechanisms**, switchable anytime: Keyboard / Mouse / API / Hybrid
- **Custom interval** (default 60s, editable while running)
- **Two global hotkeys** (native `RegisterHotKey`, no keyboard hook — friendlier to corporate monitoring tools)
- **Mini desk-lamp**: header "shrink" folds into a transparent cut-out lamp; **on = lit + warm light beam, off = unlit**; click to toggle, drag to move, right-click to restore
- **System tray**: minimize to tray; left-click toggle visibility, right-click menu for on/off & quit
- **Extras** (card "Settings" area):
  - 🔌 Run at startup (creates/removes a shortcut in the Windows Startup folder)
  - ⚡ Auto-enable on launch
  - 🎲 Randomized interval jitter (`60s × 0.8~1.2`, **anti-bot detection**)
  - 🖱️ Mouse mode respects real activity (skips jiggle while you move the mouse)
  - 🔔 Toggle feedback (balloon + beep)
- **Session timer + last-session history**: shows elapsed time while on, resets on off, remembers the most recent run
- **Auto-persisted config**, restored on restart

### ⚙️ How it works
| Mode | Mechanism | Note |
|---|---|---|
| Keyboard | Presses `F15` (no side effects), resets the idle timer | **Default, most reliable** for policy-based screen-lock |
| Mouse | 1px jiggle then back (auto-skips while you're moving the mouse) | Visible but non-intrusive |
| API | `SetThreadExecutionState` keeps display/system awake | Mainly for display/system sleep; **may not stop policy-based lock** |
| Hybrid | Keyboard + API | Most robust |

### 🚀 Download & Run (zero-install)
1. Grab `AntiLockScreen.exe` from [Releases](../../releases)
2. Double-click → floating card (top-right) + tray icon appear
3. Click "开启防锁屏" to enable

### 🧑‍💻 Run from source
```bash
pip install -r requirements.txt
python anti_lockscreen.py
```

### 📦 Build a single-file exe
Double-click `build.bat` (installs deps + generates icon + packages):
```bash
build.bat
# or manually:
python make_ico.py
pyinstaller --noconfirm --clean --onefile --noconsole --collect-all customtkinter --icon app.ico --name AntiLockScreen anti_lockscreen.py
```
Output: `dist\AntiLockScreen.exe`

### ⌨️ Shortcuts
| Action | How |
|---|---|
| Toggle anti-lock | Big button / `Ctrl+Alt+D` / tray menu / click the lamp |
| Show/hide window | `Ctrl+Alt+S` / left-click tray |
| Fold to lamp | Header "shrink" button |
| Move window | Drag header / drag lamp |
| Restore card | Right-click lamp |
| Customize hotkey | Click the "热键" button, press a new combo (must include Ctrl/Alt/Win, Esc to cancel) |

### 🔒 Privacy
- 100% local, **no network, no telemetry**
- Config: `%APPDATA%\AntiLockScreen\config.json`
- Startup shortcut: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\防熄屏.lnk`

### ❓ FAQ
- **Still gets locked?** → Use "Keyboard" or "Hybrid", interval ≤ 30–60s; pure API often can't stop a policy-based lock.
- **Blocked/flagged by corporate tools?** → Use "Keyboard + random jitter"; a custom tool is less likely to be signature-detected than well-known apps.
- **Doesn't auto-start?** → Check the Startup shortcut; some companies disable the Startup folder — use Task Scheduler instead.
- **No tray icon?** → Windows hides it — click the `^` arrow, or drag it to the always-shown area.

### ⚠️ Disclaimer
For **legitimate personal use only** (presentations, long builds, dashboards, reading). Follow your organization's IT/security policies. **The author is not liable for any misuse or consequences.** Prefer asking IT to relax the lock policy.

### 📝 License
MIT License — see [LICENSE](LICENSE).
