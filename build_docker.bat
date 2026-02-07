@echo off
REM Windows批处理脚本 - 构建Docker镜像

echo ========================================
echo 开始构建Docker镜像
echo ========================================

REM 镜像名称和标签
if "%IMAGE_NAME%"=="" set IMAGE_NAME=fastapi-ai-cli
if "%IMAGE_TAG%"=="" set IMAGE_TAG=latest

REM 完整镜像名称
set FULL_IMAGE_NAME=%IMAGE_NAME%:%IMAGE_TAG%

echo 镜像名称: %FULL_IMAGE_NAME%
echo.

REM 构建Docker镜像
docker build -t %FULL_IMAGE_NAME% .

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo Docker镜像构建成功！
    echo 镜像名称: %FULL_IMAGE_NAME%
    echo.
    echo 运行镜像：
    echo   docker run -p 8000:8000 %FULL_IMAGE_NAME%
    echo.
    echo 运行镜像（带环境变量）：
    echo   docker run -p 8000:8000 -e DEEPSEEK_API_KEY=your_key %FULL_IMAGE_NAME%
    echo.
    echo 运行镜像（挂载配置文件）：
    echo   docker run -p 8000:8000 -v %cd%\config.yaml:/app/config.yaml %FULL_IMAGE_NAME%
    echo ========================================
) else (
    echo.
    echo ========================================
    echo Docker镜像构建失败！
    echo ========================================
    exit /b 1
)

pause
