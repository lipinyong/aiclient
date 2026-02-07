@echo off
REM Windows批处理脚本 - 打包成exe
echo ========================================
echo 开始打包为EXE文件
echo ========================================

REM 检查PyInstaller是否安装
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller未安装，正在安装...
    pip install pyinstaller
)

REM 清理之前的构建
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo 正在打包chat.py (CLI工具)...
pyinstaller chat.spec --clean

echo.
echo 正在打包app.py (Web服务)...
pyinstaller app.spec --clean

echo.
echo ========================================
echo 打包完成！
echo 输出文件位于 dist 目录：
echo   - dist\chat\chat.exe (CLI工具)
echo   - dist\app\app.exe (Web服务)
echo ========================================
pause
