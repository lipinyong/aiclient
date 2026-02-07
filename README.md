# FastAPI AI CLI

一个基于 FastAPI 的 AI 命令行工具和 Web API 服务，集成了 MCP (Model Context Protocol) 服务，支持多种 AI 提供商和丰富的工具调用能力。

## ✨ 特性

- 🤖 **多 AI 提供商支持**：支持 DeepSeek、SiliconFlow 等 AI 服务
- 🔌 **MCP 服务集成**：可扩展的插件式架构，支持多种工具和服务
- 💬 **双模式运行**：支持命令行交互模式和 Web API 服务模式
- 🔐 **安全配置**：敏感信息通过环境变量管理，支持 `.env` 文件
- 🐳 **容器化支持**：提供 Docker 镜像和 Docker Compose 配置
- 📦 **可执行文件打包**：支持打包成独立的 EXE 可执行文件
- 🛠️ **丰富的工具集**：Git、MySQL、SSH、邮件、会议管理等

## 📋 目录结构

```
aiclient/
├── app.py                 # FastAPI Web 服务入口
├── chat.py                # CLI 命令行工具入口
├── config.yaml            # 主配置文件
├── git.yaml               # GitLab 配置（使用环境变量）
├── requirements.txt       # Python 依赖
├── Dockerfile             # Docker 镜像构建文件
├── docker-compose.yml     # Docker Compose 配置
├── mcp/                   # MCP 服务模块
│   ├── git.py            # GitLab API 集成
│   ├── mysql.py          # MySQL 数据库操作
│   ├── ssh.py            # SSH 远程执行
│   ├── mail.py           # 邮件发送
│   ├── establishments.py  # 会议管理
│   ├── xmgl.py           # 项目管理
│   └── ...
├── module/                # 核心模块
│   ├── aiagent.py        # AI Agent 核心
│   ├── mcpserver.py      # MCP 服务管理器
│   ├── config_manager.py # 配置管理
│   └── ...
└── web/                   # Web API 路由
    ├── aichat/           # AI 聊天 API
    ├── mail/             # 邮件 API
    └── ...
```

## 🚀 快速开始

### 环境要求

- Python 3.11+
- pip

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/lipinyong/aiclient.git
cd aiclient
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **配置环境变量**

复制 `.env.example` 为 `.env` 并填入配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下内容：

```env
# AI API 密钥
DEEPSEEK_API_KEY=your_deepseek_api_key
SILICONFLOW_API_KEY=your_siliconflow_api_key

# 邮件配置
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_email_password

# GitLab 令牌（如果使用 Git 相关功能）
GITLAB_TOKEN_LUBANLOU=your_token_here
GITLAB_TOKEN_PRODUCTION_DOCUMENT=your_token_here
GITLAB_TOKEN_PROJECT_DOCUMENT=your_token_here
GITLAB_TOKEN_SERVICE_ISSUES=your_token_here
GITLAB_TOKEN_C_ENGINEER=your_token_here
GITLAB_TOKEN_GVSUNSCRIPT=your_token_here
```

4. **配置 GitLab（可选）**

如果使用 GitLab 相关功能，需要配置 `git.yaml` 文件。令牌会从 `.env` 文件中的环境变量读取。

## 💻 使用方法

### 命令行模式（CLI）

启动交互式命令行工具：

```bash
python chat.py
```

或直接提问（非交互模式）：

```bash
python chat.py -p "你好，请介绍一下这个项目"
```

**命令行参数：**

- `-p, --prompt`: 直接提问（非交互模式）
- `-d, --delay`: 打字机效果延迟（秒，默认 0.02）
- `--no-typewriter`: 禁用打字机效果
- `--no-preprocess`: 禁用提示词预处理
- `-q, --quiet`: 静默模式，减少输出信息
- `--debug`: 启用 debug 模式，打印 info 级别日志
- `--hot-reload`: 启用 MCP 服务热加载
- `--hot-reload-interval`: 热加载检查间隔（秒，默认 2.0）

### Web API 模式

启动 FastAPI Web 服务：

```bash
python app.py
```

服务默认运行在 `http://0.0.0.0:8000`

**主要 API 端点：**

- `POST /api/aichat/deepseek` - AI 聊天接口（支持工具调用）
- `GET /api/aichat/topology` - 系统拓扑图生成
- `POST /api/mail/send` - 邮件发送
- `GET /api/establishments/*` - 会议管理相关接口
- `GET /api/xmgl/*` - 项目管理相关接口

**API 文档：**

启动服务后，访问以下地址查看自动生成的 API 文档：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 环境变量配置

可以通过环境变量覆盖默认配置：

```bash
# 设置服务端口
export PORT=8080

# 设置主机地址
export HOST=127.0.0.1

# 启用热重载
export RELOAD=true

# 设置配置文件路径
export CONFIG_PATH=/path/to/config.yaml
```

## 🐳 Docker 部署

### 使用 Docker Compose（推荐）

```bash
docker-compose up -d
```

### 手动构建和运行

```bash
# 构建镜像
docker build -t aiclient:latest .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/data:/app/data \
  --name aiclient \
  aiclient:latest
```

更多 Docker 相关说明请参考 `BUILD.md`。

## 📦 打包成可执行文件

### Windows

```bash
build_exe.bat
```

### Linux/Mac

```bash
chmod +x build_exe.sh
./build_exe.sh
```

打包完成后，可执行文件位于 `dist` 目录。

详细打包说明请参考 `BUILD.md`。

## 🔧 配置说明

### 主配置文件 (config.yaml)

主要配置项：

- `ai`: AI 提供商配置（DeepSeek、SiliconFlow 等）
- `mcp`: MCP 服务配置
- `lubanlou`: 业务系统 API 配置
- `logging`: 日志配置
- `chroma`: ChromaDB 向量数据库配置

### GitLab 配置 (git.yaml)

GitLab 相关配置，令牌从环境变量读取。支持配置多个 GitLab 仓库。

### 环境变量 (.env)

所有敏感信息（API 密钥、令牌、密码等）都应配置在 `.env` 文件中，该文件不会被提交到版本库。

## 🛠️ MCP 服务

项目支持以下 MCP 服务：

| 服务 | 功能 | 文件 |
|------|------|------|
| Git | GitLab API 集成，支持 issues、commits、MR 等 | `mcp/git.py` |
| MySQL | MySQL 数据库连接和查询 | `mcp/mysql.py` |
| SSH | SSH 远程命令执行 | `mcp/ssh.py` |
| Mail | SMTP 邮件发送 | `mcp/mail.py` |
| Establishments | 会议管理集成 | `mcp/establishments.py` |
| XMGL | 项目管理相关功能 | `mcp/xmgl.py` |
| Common | 通用文件操作和工具 | `mcp/common.py` |
| Data Processor | 大数据分块处理（Map-Reduce 模式） | `mcp/data_processor.py` |
| Chroma | ChromaDB 向量数据库集成 | `mcp/chroma.py` |

## 📝 开发指南

### 添加新的 MCP 服务

1. 在 `mcp/` 目录下创建新的服务文件
2. 实现服务类，注册工具函数
3. 服务会自动被发现和加载

### 代码结构

- `module/aiagent.py`: AI Agent 核心，处理 AI 交互和工具调用
- `module/mcpserver.py`: MCP 服务管理器，负责服务的发现、加载和管理
- `module/config_manager.py`: 配置管理器，支持热重载和环境变量替换
- `web/`: Web API 路由处理

## 🔒 安全说明

- **敏感信息管理**：所有敏感信息（API 密钥、令牌、密码）都通过 `.env` 文件管理
- **环境变量替换**：配置文件支持 `${VAR_NAME}` 语法引用环境变量
- **Git 推送保护**：GitHub 已启用推送保护，防止敏感信息泄露

## 📄 许可证

本项目采用 Apache License 2.0 许可证。详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

- 项目地址: https://github.com/lipinyong/aiclient
- 作者: lipinyong

## 🙏 致谢

感谢所有为本项目做出贡献的开发者！

---

**注意**：使用前请确保已正确配置 `.env` 文件，特别是 AI API 密钥等必要配置。
