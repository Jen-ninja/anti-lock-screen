# 防熄屏（C# / WPF 版）

`anti_lockscreen.py` 的 C# WPF 等价实现：**更轻量、启动更快、打包更小**，UI 与功能与 Python 版一致，且读写同一份配置（可无缝切换）。

## 前置（一次性）

1. 安装 **.NET 10 SDK**（x64）：<https://dotnet.microsoft.com/download/dotnet/10.0>
2. 验证：`dotnet --version`
   - 若你装的是 **.NET 8 LTS**，把 `AntiLockScreen.csproj` 里的 `<TargetFramework>` 改成 `net8.0-windows`。
3. 无需 Visual Studio；CLI 即可。VS Code + C# Dev Kit 可选。

## 构建（调试运行）

```bash
cd csharp
dotnet run -c Debug
```

## 发布为单文件 exe

⚠️ **WPF 的体积现实**：WPF 不支持裁剪（.NET SDK 在 `PublishTrimmed` 时直接报 NETSDK1168），所以体积只能二选一：

| 方式 | 体积 | 免安装 | 适用 |
|---|---|---|---|
| **framework-dependent**（推荐，默认） | **~260KB** | 否（需 .NET 10 Desktop Runtime） | 轻量分发；目标机已装/愿装 runtime |
| self-contained | ~134MB | 是 | 必须免安装、可接受大体积 |

> 想同时「几 MB + 免安装 + 保留这套 UI」做不到——需换 Rust / 原生 Win32 重写（UI 要重做）。

**framework-dependent（推荐，默认）**：

```bash
cd csharp
dotnet publish AntiLockScreen.csproj -c Release --self-contained false ^
  -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o ..\dist-csharp-fd
```

产物 `dist-csharp-fd\AntiLockScreen.exe`（~260KB）。本机已装 SDK 可直接双击运行；未装 .NET Desktop Runtime 的机器会弹出微软官方引导装一次。

**self-contained（免安装，~134MB）**：

```bash
cd csharp
dotnet publish AntiLockScreen.csproj -c Release -r win-x64 --self-contained true ^
  -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o ..\dist-csharp
```

产物 `dist-csharp\AntiLockScreen.exe`（~134MB，任何 Windows 10/11 双击即跑，无需预装）。

## 与 Python 版互通

两者读写同一份 `%APPDATA%\AntiLockScreen\config.json`（字段名完全一致）：

| 字段 | 含义 |
|---|---|
| `mode` | keyboard / mouse / api / hybrid |
| `interval` | 间隔（秒） |
| `autoon` / `jitter` / `notify` | 启动即开启 / 随机抖动 / 切换提示 |
| `last_session` | 上次会话时长（秒） |
| `hotkeys.show` / `hotkeys.run` | 显隐 / 开关 全局热键 `{mods, vk, label}` |

开机自启快捷方式也共用 `Startup\防熄屏.lnk`。两版可交替使用，配置自动延续。

## 文件结构

```
csharp/
├── AntiLockScreen.csproj        net10.0-windows / UseWPF / 嵌入 app.ico
├── App.xaml(.cs)                启动 + 配色资源字典
├── MainWindow.xaml(.cs)         全屏卡片 UI + 交互（状态机/mini/full/拖动/热键捕获/状态刷新）
├── app.ico                      应用图标（从根目录复用，嵌入资源）
├── build.bat                    一键发布脚本
├── Themes/Colors.xaml           配色（对应 Python 常量）
├── Models/
│   ├── AppMode.cs               模式枚举 + 中文标签 + 配置字符串映射
│   └── AppConfig.cs             配置 POCO（JSON 字段名对齐 Python）
├── Native/
│   └── NativeMethods.cs         P/Invoke 全集（防锁屏/SendInput/热键/托盘/菜单）
├── Services/
│   ├── AntiLockEngine.cs        后台循环（PeriodicTimer + 随机抖动）
│   ├── ConfigStore.cs           %APPDATA% 配置读写
│   ├── Autostart.cs             Startup .lnk 创建/删除
│   ├── GlobalHotkeyManager.cs   RegisterHotKey + WM_HOTKEY 分发
│   └── TrayIconController.cs    Shell_NotifyIconW + 右键菜单（零依赖）
└── Controls/
    └── LampControl.xaml(.cs)    矢量台灯（IsOn 切亮/灭，1:1 还原 make_lamp）
```

## 默认值

- 模式：键盘；间隔：60s；启动即开启 / 随机抖动 / 切换提示：开
- 热键：`Ctrl + Alt + S`（显隐窗口）、`Ctrl + Alt + D`（开关防锁屏）

## 许可

MIT（与根项目一致）。
