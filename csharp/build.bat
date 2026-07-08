@echo off
chcp 65001 >nul
title 防熄屏 C# 版 - 发布

echo === 防熄屏 C# 版发布 ===
echo.

where dotnet >nul 2>nul
if errorlevel 1 (
  echo [错误] 未检测到 dotnet。请先安装 .NET 10 SDK x64：
  echo        https://dotnet.microsoft.com/download/dotnet/10.0
  pause
  exit /b 1
)

REM ============================================================
REM 默认：framework-dependent（依赖框架）—— exe 约 260KB，启动快。
REM 代价：目标机需装 .NET 10 Desktop Runtime（本机已装 SDK 可直接跑；
REM       未装的机器双击 exe 会弹出微软官方引导，装一次即可）。
REM ============================================================
dotnet publish AntiLockScreen.csproj -c Release ^
  --self-contained false ^
  -p:PublishSingleFile=true ^
  -p:IncludeNativeLibrariesForSelfExtract=true ^
  -o ..\dist-csharp-fd

if errorlevel 1 (
  echo.
  echo [错误] 构建失败，请查看上方错误信息。
  pause
  exit /b 1
)

echo.
echo === 完成：..\dist-csharp-fd\AntiLockScreen.exe （约 260KB，依赖 .NET 10 Desktop Runtime）===
echo.
echo [可选] 若要「免安装」单文件（约 134MB，无需运行时），另开命令行执行：
echo   dotnet publish AntiLockScreen.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o ..\dist-csharp
echo.
pause
