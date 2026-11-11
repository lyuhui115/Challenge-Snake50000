@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  SNAKE-50000 自定义加密导出模板一键编译脚本
rem
rem  作用: 编译带内嵌 AES 密钥的 Godot 4.5.1 导出模板
rem        (官方模板不含密钥 -> 全加密 PCK 的游戏无法启动)
rem
rem  用法: tools\build_template.bat [源码目录]
rem        默认源码目录 C:\Users\djkl1\godot-4.5.1
rem
rem  前置: gcc (scoop install mingw) + python + git
rem  耗时: 首次编译约 20-60 分钟, 磁盘约 3-4 GB
rem ============================================================
set "SRC=%~1"
if "%SRC%"=="" set "SRC=C:\Users\djkl1\godot-4.5.1"
set "KEY=f956ea30749ff095e35fcf5cb074d6e821782ca8072568624d9d3cb595564ce8"

echo [1/4] 检查工具链...
where gcc >nul 2>nul || (echo [X] 找不到 gcc ^(需要 mingw: scoop install mingw^) & exit /b 1)
gcc --version | findstr /i "gcc"
python --version
python -m pip show scons >nul 2>nul || (echo 安装 scons... & python -m pip install scons || exit /b 1)

echo [2/4] 获取 Godot 4.5.1 源码...
if exist "%SRC%\SConstruct" (
    echo     源码已存在: %SRC%
) else (
    git clone --depth 1 --branch 4.5.1-stable https://github.com/godotengine/godot.git "%SRC%" || (echo [X] clone 失败, 检查网络/代理 & exit /b 1)
)

echo [3/4] 编译模板 (密钥经环境变量注入, 预计 20-60 分钟)...
cd /d "%SRC%"
set "SCRIPT_AES256_ENCRYPTION_KEY=%KEY%"
scons platform=windows target=template_release arch=x86_64 use_mingw=yes -j%NUMBER_OF_PROCESSORS%
if errorlevel 1 (echo [X] 编译失败, 把上面的报错发我 & exit /b 1)

echo.
echo [4/4] 编译产出:
if not exist "bin\godot.windows.template_release.x86_64.exe" (echo [X] 未找到产物 & exit /b 1)
dir "bin\godot.windows.template_release.x86_64.exe"

echo.
echo ============================================================
echo  下一步: 把 game\export_presets.cfg 改为:
echo    custom_template/release="%SRC:\=/%/bin/godot.windows.template_release.x86_64.exe"
echo    encrypt_pck=true
echo    encrypt_directory=true
echo    encryption_include_filters="*"
echo  然后重新导出并冒烟测试。
echo ============================================================
endlocal
