#!/bin/bash
# Linux/Mac shell脚本 - 打包成exe

echo "========================================"
echo "开始打包为EXE文件"
echo "========================================"

# 检查PyInstaller是否安装
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "PyInstaller未安装，正在安装..."
    pip install pyinstaller
fi

# 清理之前的构建
rm -rf build dist

echo ""
echo "正在打包chat.py (CLI工具)..."
pyinstaller chat.spec --clean

echo ""
echo "正在打包app.py (Web服务)..."
pyinstaller app.spec --clean

echo ""
echo "========================================"
echo "打包完成！"
echo "输出文件位于 dist 目录："
echo "  - dist/chat/chat (CLI工具)"
echo "  - dist/app/app (Web服务)"
echo "========================================"
