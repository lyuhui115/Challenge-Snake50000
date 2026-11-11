@echo off
setlocal
rem ============================================================
rem  SNAKE-500 一键导出脚本
rem  用法: tools\build.bat [Godot可执行文件路径]
rem  示例: tools\build.bat C:\Tools\Godot_v4.3-stable_win64_console.exe
rem        (不加参数则假定 godot 已在 PATH 里)
rem ============================================================
set GODOT=%~1
if "%GODOT%"=="" set GODOT=godot

where %GODOT% >nul 2>nul
if errorlevel 1 (
    echo [X] 找不到 Godot: %GODOT%
    echo     用法: tools\build.bat C:\path\to\Godot_console.exe
    exit /b 1
)

echo [*] 正在导出（headless，自动导入资源）...
%GODOT% --headless --path game --export-release "Windows Desktop"
if errorlevel 1 (
    echo [X] 导出失败。最常见原因: 未安装导出模板
    echo     (进编辑器 -^> 管理导出模板 -^> 下载安装，版本需与编辑器一致)
    exit /b 1
)

if not exist "game\build\snake50000.exe" (
    echo [X] 导出命令成功但未找到产物 game\build\snake50000.exe
    exit /b 1
)

echo [*] 明文泄露检查（必须为 False，连诱饵都搜不到才算加密生效）:
python -X utf8 -c "d=open(r'game\build\snake50000.exe','rb').read(); print('flag{ in exe:', b'flag{' in d)"

echo [*] SHA256（写进题目描述，供玩家校验）:
python -X utf8 -c "import hashlib; print(hashlib.sha256(open(r'game\build\snake50000.exe','rb').read()).hexdigest())"

echo [OK] 产物: game\build\snake50000.exe
endlocal
