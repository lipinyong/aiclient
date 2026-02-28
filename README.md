# FastAPI AI Client

基于 FastAPI 的 AI 命令行与 Web API 服务，集成 MCP（Model Context Protocol），支持多 AI 提供商与可扩展工具调用。

## 特性

- **多 AI 提供商**：DeepSeek、SiliconFlow 等
- **MCP 集成**：插件式 MCP 服务，启动时加载，提问时可按 skill 按需提交工具
- **双模式**：命令行交互 + Web API 服务
- **按需 Skills**：通过 `--skills`（CLI）或请求体 `skills`（API）指定本次可用的 MCP 能力
- **安全配置**：敏感信息使用环境变量与 `.env`
- **容器化**：支持 Docker / Docker Compose
- **丰富工具**：Git、MySQL、SSH、邮件、会议、项目管理、数据处理等

## 项目结构

```
aiclient/
├── app.py                 # FastAPI Web 服务入口
├── chat.py                # CLI 入口
├── config.yaml            # 主配置（AI、MCP、业务等）
├── .env                   # 环境变量（勿提交）
├── .env.example           # 环境变量示例
├── requirements.txt      # Python 依赖
├── mcp/                   # MCP 服务目录（每模块对应一个 skill）
│   ├── example.py
│   ├── file_manager.py
│   ├── data_processor.py
│   ├── mail.py
│   ├── xmgl.py
│   ├── establishments.py
│   └── ...
├── module/                # 核心模块
│   ├── aiagent.py        # AI Agent、工具按需提交
│   ├── mcpserver.py      # MCP 发现与加载
│   └── router.py         # Web 路由
└── web/                   # Web API 实现
    └── aichat/           # AI 聊天等
```

## 快速开始

### 环境要求

- Python 3.11+
- pip

### 安装

```bash
git clone https://github.com/lipinyong/aiclient.git
cd aiclient
pip install -r requirements.txt
```

### 配置

1. **环境变量**：在项目根目录创建 `.env`（可参考 `.env.example`），例如：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
SILICONFLOW_API_KEY=your_siliconflow_api_key
```

2. **主配置**：在项目根目录放置 `config.yaml`。主要项：
   - `ai`：provider、providers（base_url、model、api_key，可用 `${DEEPSEEK_API_KEY}`）
   - `mcp`：`services_path`（默认 `mcp`）、可选 `default_skills`

## 使用方式

### 命令行（CLI）

在**项目根目录**执行：

```bash
python chat.py
```

单次提问：

```bash
python chat.py -p "你的问题"
```

**按需指定 MCP 能力（skills）**：

```bash
# 仅使用 mail、data_processor
python chat.py --skills mail,data_processor

# 仅使用 xmgl
python chat.py --skills xmgl -p "查询本周日报"
```

不传 `--skills` 时使用**全部已加载的 MCP 工具**。

| 参数 | 说明 |
|------|------|
| `-p, --prompt` | 直接提问（非交互） |
| `--skills` | 按需启用的 MCP 能力，逗号分隔，如 `mail,data_processor,xmgl` |
| `-q, --quiet` | 静默模式 |
| `--no-typewriter` | 关闭打字机效果 |
| `--no-preprocess` | 关闭提示词预处理 |
| `--hot-reload` | 启用 MCP 热加载 |
| `--debug` | 开启 debug 日志 |

### Web API

启动 Web 服务：

```bash
python app.py
```

默认地址：`http://0.0.0.0:8000`。

**AI 聊天（按需 skills）**：

- **POST** `/api/aichat/deepseek`  
  请求体示例：

```json
{
  "prompt": "你的问题",
  "stream": true,
  "skills": ["mail", "data_processor"]
}
```

- 不传 `skills` 或传空数组：使用全部 MCP 能力；若配置了 `mcp.default_skills` 则使用该默认列表。

其他接口：

- `GET /api/aichat/deepseek` — 服务信息与可用 tools
- `POST /api/mail/send` — 邮件发送
- `GET /api/establishments/*` — 会议
- `GET /api/xmgl/*` — 项目管理

API 文档：`http://localhost:8000/docs`（Swagger）、`http://localhost:8000/redoc`（ReDoc）。

## 配置说明

### config.yaml 要点

- **ai**：`provider`、`providers`（base_url、model、api_key 等），api_key 支持 `${VAR}` 环境变量。
- **mcp**：`services_path`（默认 `mcp`）、可选 `default_skills`（默认启用的 skill 列表）。
- **lubanlou / chroma / logging**：业务与基础设施配置。

### 环境变量

- `CONFIG_PATH`：配置文件路径（默认 `config.yaml`）。
- `PORT` / `HOST`：服务端口与监听地址。
- `RELOAD`：是否热重载（如 `true`）。
- 各 API Key、令牌等建议放在 `.env`。

## MCP 与 Skills

- **加载**：启动时从 `mcp` 目录发现并加载所有 MCP 服务。
- **提交**：每次请求可指定 `skills`，仅对应工具提交给模型；未指定则提交全部已加载工具。
- **Skill 名称**：与 MCP 模块名一致（如 `mail`、`data_processor`、`xmgl`），启动时会打印已加载服务名。

开发新 MCP 可参考 `mcp/SKILL_DEVELOPMENT_GUIDE.md`。

## Docker

```bash
docker-compose up -d
```

或手动构建运行：

```bash
docker build -t aiclient:latest .
docker run -p 8000:8000 -v $(pwd)/config.yaml:/app/config.yaml aiclient:latest
```

## 打包为可执行文件

Windows：`build_exe.bat`  
Linux/Mac：`./build_exe.sh`  

输出在 `dist/`。需将 `config.yaml`、`mcp/`、`module/` 等与可执行文件同目录。详见 `BUILD.md`（若存在）。

## 许可证

Apache License 2.0，见 [LICENSE](LICENSE)。使用前请配置 `.env` 与 `config.yaml`（尤其是 AI API Key）。
