@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo  公众号内容自动发布系统
echo ========================================
echo.

cd /d "%~dp0"

:: 检测 Python（优先使用已知路径，再自动查找）
set PYTHON_EXE=

:: 优先检查已知路径（Python 3.14）
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe
    goto :found_python
)

:: 其次从PATH查找
for %%p in (python python3) do (
    where %%p >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_EXE=%%p
        goto :found_python
    )
)

:: 查找其他常见安装位置
for %%d in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python314\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
) do (
    if exist %%d (
        set PYTHON_EXE=%%d
        goto :found_python
    )
)

echo [错误] 未找到 Python！请安装 Python 3.10 或更高版本
echo 下载地址: https://www.python.org/downloads/
pause
exit /b 1

:found_python
echo [信息] 使用 Python: %PYTHON_EXE%
%PYTHON_EXE% --version

:: 安装依赖（直接安装到Python本体，避免venv兼容问题）
echo [信息] 安装/更新依赖...
%PYTHON_EXE% -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --prefer-binary --no-warn-script-location --quiet
if errorlevel 1 (
    echo [警告] 部分依赖安装可能失败，尝试继续...
)

:: 检查配置文件
if not exist ".env" (
    echo.
    echo [重要] 首次运行！请配置公众号信息
    echo --------------------------------------------------
    copy .env.example .env >nul
    echo .env 文件已创建，请填入以下信息：
    echo   WECHAT_APP_ID    - 你的公众号 AppID
    echo   WECHAT_APP_SECRET - 你的公众号 AppSecret
    echo --------------------------------------------------
    echo 正在打开配置文件，请编辑后保存，然后关闭记事本继续...
    notepad .env
    echo.
    echo 配置完成后按任意键启动程序...
    pause >nul
)

:: 创建必要目录
if not exist "data" mkdir data
if not exist "logs" mkdir logs

:: 启动
echo.
echo [信息] 启动程序...
echo [信息] Web 管理界面: http://127.0.0.1:5000
echo [信息] 默认登录: admin / admin123
echo [信息] 按 Ctrl+C 停止程序
echo.

%PYTHON_EXE% main.py

echo.
echo 程序已退出
pause
