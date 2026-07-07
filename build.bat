@echo off
chcp 65001 >nul
echo ========================================
echo   防熄屏 - 打包脚本
echo ========================================
echo.
echo [1/3] 安装依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo 依赖安装失败，请检查 pip / 网络。
    pause
    exit /b 1
)
echo.
echo [2/3] 生成 exe 图标 app.ico...
python make_ico.py
echo.
echo [3/3] 打包为单文件 exe...
pyinstaller --noconfirm --clean --onefile --noconsole --collect-all customtkinter --icon app.ico --name AntiLockScreen anti_lockscreen.py
if errorlevel 1 (
    echo 打包失败。
    pause
    exit /b 1
)
echo.
echo ========================================
echo  完成！产物： dist\AntiLockScreen.exe
echo  （可重命名为 防熄屏.exe，或拖到桌面/开机启动项）
echo ========================================
pause
