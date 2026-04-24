# 注册 Windows 定时任务脚本
# 使用方法：右键以管理员身份运行 PowerShell，然后执行此脚本

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = "$ProjectDir\venv\Scripts\python.exe"
$MainScript = "$ProjectDir\main.py"
$LogFile = "$ProjectDir\logs\task_runner.log"
$TaskName = "WechatAutoPublisher"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 注册微信公众号自动发布 Windows 定时任务" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查虚拟环境
if (-not (Test-Path $PythonExe)) {
    Write-Host "[错误] 请先运行 start.bat 安装依赖" -ForegroundColor Red
    exit 1
}

# 删除旧任务（如有）
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[信息] 已删除旧任务" -ForegroundColor Yellow
}

# 创建任务 Action
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $MainScript `
    -WorkingDirectory $ProjectDir

# 触发器：每天开机后自动启动，同时设置每天 07:50 启动（确保 08:00 爬取任务能执行）
$Trigger1 = New-ScheduledTaskTrigger -AtStartup
$Trigger2 = New-ScheduledTaskTrigger -Daily -At "07:50"

# 任务设置
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 23) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable

# 注册任务（使用当前用户）
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger1, $Trigger2 `
    -Settings $Settings `
    -RunLevel Highest `
    -Description "微信公众号自动爬取并发布资讯" `
    -Force

Write-Host "[成功] 定时任务已注册: $TaskName" -ForegroundColor Green
Write-Host "[信息] 每天 07:50 自动启动，开机时自动运行" -ForegroundColor Green
Write-Host "[信息] 可在任务计划程序中查看和管理" -ForegroundColor Gray
