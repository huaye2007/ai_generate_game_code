@echo off
chcp 65001 >nul
title 游戏服务器业务代码开发
echo.
echo  ========================================
echo    游戏服务器业务代码开发 - 启动中...
echo  ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.11+
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

:: 如果旧的 venv 损坏，先清理
if exist "venv" (
    if not exist "venv\Scripts\activate.bat" (
        echo [提示] 检测到损坏的虚拟环境，正在清理...
        rmdir /s /q venv
    )
)

:: 首次运行：创建虚拟环境 + 安装依赖
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] 创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo [错误] 创建虚拟环境失败！可能的原因：
        echo   - Python 版本过低，需要 3.11+
        echo   - 路径包含中文或空格
        echo   - 缺少 venv 模块（Ubuntu 需要 apt install python3-venv）
        echo.
        if exist "venv" rmdir /s /q venv
        pause
        exit /b 1
    )

    echo [2/3] 安装依赖...
    call venv\Scripts\activate.bat
    if errorlevel 1 (
        echo [错误] 激活虚拟环境失败！
        pause
        exit /b 1
    )
    if exist "vendor" (
        echo      （使用离线包，速度很快）
        xcopy /s /e /q /y vendor venv\Lib\site-packages\ >nul
        pip install -e . --no-deps -q
    ) else (
        echo      （首次联网下载，请耐心等待）
        pip install -e . -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    )
    if errorlevel 1 (
        echo.
        echo [错误] 安装依赖失败！
        if not exist "vendor" echo 可尝试使用国内镜像：pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
        pause
        exit /b 1
    )
    echo [3/3] 安装完成
) else (
    call venv\Scripts\activate.bat
)

echo.
echo  浏览器将自动打开 http://localhost:8501
echo  按 Ctrl+C 停止服务
echo.
streamlit run app/main.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
if errorlevel 1 (
    echo.
    echo [错误] 启动失败！尝试重新安装依赖...
    pip install -e . -q
    streamlit run app/main.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
)
pause
