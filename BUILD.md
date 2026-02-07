# 打包说明文档

本项目支持两种打包方式：打包成EXE可执行文件和打包成Docker镜像。

## 一、打包成EXE

### 前置要求

1. Python 3.11+
2. 安装PyInstaller：
   ```bash
   pip install pyinstaller
   ```

### Windows系统

运行批处理脚本：
```bash
build_exe.bat
```

### Linux/Mac系统

运行shell脚本：
```bash
chmod +x build_exe.sh
./build_exe.sh
```

### 手动打包

如果需要单独打包某个应用：

**打包CLI工具（chat.py）：**
```bash
pyinstaller chat.spec --clean
```

**打包Web服务（app.py）：**
```bash
pyinstaller app.spec --clean
```

### 输出文件

打包完成后，可执行文件位于 `dist` 目录：
- `dist/chat/chat.exe` (Windows) 或 `dist/chat/chat` (Linux/Mac) - CLI工具
- `dist/app/app.exe` (Windows) 或 `dist/app/app` (Linux/Mac) - Web服务

### 注意事项

1. 打包后的exe文件需要与以下文件/目录放在同一目录：
   - `config.yaml` - 配置文件
   - `git.yaml` - Git配置
   - `mcp/` - MCP服务目录
   - `module/` - 模块目录
   - `web/` - Web目录
   - `data/` - 数据目录（可选）

2. 首次运行可能需要较长时间加载依赖

3. 如果遇到缺少模块的错误，可以在 `.spec` 文件的 `hiddenimports` 中添加

## 二、打包成Docker镜像

### 前置要求

1. Docker已安装并运行
2. 确保Docker有足够的磁盘空间

### 构建镜像

**Linux/Mac：**
```bash
chmod +x build_docker.sh
./build_docker.sh
```

**Windows：**
```bash
build_docker.bat
```

### 自定义镜像名称和标签

```bash
# Linux/Mac
IMAGE_NAME=my-app IMAGE_TAG=v1.0 ./build_docker.sh

# Windows
set IMAGE_NAME=my-app
set IMAGE_TAG=v1.0
build_docker.bat
```

### 运行镜像

**基本运行：**
```bash
docker run -p 8000:8000 fastapi-ai-cli:latest
```

**带环境变量：**
```bash
docker run -p 8000:8000 \
  -e DEEPSEEK_API_KEY=your_api_key \
  -e CONFIG_PATH=/app/config.yaml \
  fastapi-ai-cli:latest
```

**挂载配置文件：**
```bash
docker run -p 8000:8000 \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v $(pwd)/git.yaml:/app/git.yaml \
  -v $(pwd)/data:/app/data \
  fastapi-ai-cli:latest
```

**后台运行：**
```bash
docker run -d -p 8000:8000 --name ai-cli fastapi-ai-cli:latest
```

### 环境变量

- `HOST`: 服务监听地址（默认：0.0.0.0）
- `PORT`: 服务端口（默认：8000）
- `RELOAD`: 是否启用热重载（默认：false）
- `CONFIG_PATH`: 配置文件路径（默认：config.yaml）
- `DEEPSEEK_API_KEY`: DeepSeek API密钥
- `SILICONFLOW_API_KEY`: SiliconFlow API密钥

### 健康检查

镜像包含健康检查，可以通过以下命令查看：
```bash
docker inspect --format='{{.State.Health.Status}}' <container_id>
```

## 三、使用docker-compose（可选）

创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  ai-cli:
    build: .
    image: fastapi-ai-cli:latest
    ports:
      - "8000:8000"
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - HOST=0.0.0.0
      - PORT=8000
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./git.yaml:/app/git.yaml
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
```

运行：
```bash
docker-compose up -d
```

## 四、常见问题

### EXE打包问题

1. **缺少模块错误**
   - 在对应的 `.spec` 文件的 `hiddenimports` 中添加缺失的模块

2. **文件过大**
   - 使用 `--onefile` 模式（已在spec文件中配置）
   - 考虑使用虚拟环境减少依赖

3. **运行时错误**
   - 确保所有必要的文件都在exe同目录
   - 检查配置文件路径是否正确

### Docker打包问题

1. **构建失败**
   - 检查Docker是否有足够空间
   - 查看Docker日志：`docker build --no-cache -t fastapi-ai-cli .`

2. **运行时连接问题**
   - 检查端口是否被占用
   - 确认防火墙设置

3. **配置文件找不到**
   - 使用 `-v` 挂载配置文件
   - 或使用环境变量 `CONFIG_PATH`

## 五、开发模式

### 本地开发（不打包）

**运行CLI工具：**
```bash
python chat.py
```

**运行Web服务：**
```bash
python app.py
```

或使用uvicorn：
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```
