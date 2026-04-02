@echo off
chcp 65001 >nul
echo 正在打包 game-ai-workflow...
echo.
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 请先运行 start.bat 安装好环境，再执行打包
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
python pack.py
pause
