# AI Client v2.0

支持 **Agent Skills** 的 AI 命令行客户端。从项目或用户目录加载 Cursor 风格的技能（`SKILL.md`），并注入到模型上下文中。

## 功能

- **Agent Skills**：从项目根 **`skills/`** 目录（以及可选的 `.cursor/skills`、`~/.cursor/skills`）加载 `skills/<skill-name>/SKILL.md`，不加载 `~/.cursor/skills-cursor/`。
- **技能注入**：将选中技能的说明注入系统提示，模型按技能指引回答。
- **按需加载**：不指定 `--skills` 时，根据用户输入**自动选择**相关技能（匹配技能的 `triggers` 或 description），只注入匹配到的技能，减少无关上下文。
- **显式指定**：`--skills name1,name2` 时仅启用指定技能。
- **列出技能**：`--list-skills` 列出当前发现的技能及触发词说明。
- **技能工具**：技能目录下可放置 **`tools.py`**，定义 `TOOLS`（OpenAI 格式）和 `execute_tool(name, args)`；仅在**启用该技能**时加载并注入 API。例如 `skills/ssh/tools.py` 的 `ssh_run`、`skills/shell/tools.py` 的 `run_shell`（支持 Windows PowerShell/CMD 与 Linux bash）均在对应技能启用时生效。

## 环境准备

```bash
cd v2.0
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 或相应 API Key
```

## 配置

- `config.yaml`：AI 提供商与 `skills.paths`（如 `skills`、`project`、`personal`）。默认优先从项目根 **`skills/`** 加载。
- `.env`：API Key 等环境变量，支持在 config 中用 `${VAR}` 引用。

## 使用

```bash
# 交互模式（按需自动选择技能，无需指定 --skills）
python chat.py

# 单次提问（例如包含「提交说明」会自动启用 commit-message）
python chat.py -p "帮我写提交说明：修复了登录超时"

# 包含「ssh」「传文件」会自动启用 ssh 技能
python chat.py -p "用 scp 把本机文件传到服务器"

# 显式指定只用某几个技能
python chat.py --skills commit-message -p "写一条 commit"

# 列出已发现的 Agent Skills
python chat.py --list-skills
```

## Agent Skill 格式

每个技能是一个目录，内含 `SKILL.md`：

```markdown
---
name: my-skill
description: 简短描述，说明何时使用本技能（用于匹配与展示）
triggers: [关键词1, 关键词2, 英文关键词]   # 可选，用户输入包含任一词时自动启用
---

# 技能标题

此处写具体指引：步骤、示例、模板等。会原样注入系统提示。
```

- **name**：技能唯一标识，建议小写、连字符。
- **description**：一句话说明用途与触发场景；未配置 `triggers` 时会从 description 中抽取关键词做匹配。
- **triggers**（可选）：字符串列表。用户输入（小写）包含任一触发词时，该技能会被自动注入；不写则用 description/name 做简单关键词匹配。

技能目录可放在（按 `config.yaml` 中 `skills.paths` 顺序，后者覆盖同名）：

- **`skills/`**：项目根下的 `skills/<skill-name>/SKILL.md`（推荐部署）
- 项目：`<项目根>/.cursor/skills/<skill-name>/SKILL.md`
- 用户：`~/.cursor/skills/<skill-name>/SKILL.md`

## 内置技能（`skills/` 目录）

| 技能名 | 说明 |
|--------|------|
| `example-skill` | 示例格式与回复模板，用户说「举例」「示例」时可用 |
| `commit-message` | 按约定式提交规范生成 Git 提交信息，用户提供变更描述或 diff 时使用 |
| `shell` | 生成或解释本地 Shell 命令（PowerShell/bash），执行脚本、目录、环境变量等 |
| `ssh` | 生成或解释 SSH/SCP/SFTP 命令与配置，远程连接、传文件、密钥、跳板机 |

使用示例：不指定 `--skills` 时，问「帮我写提交说明」会自动启用 `commit-message`；问「用 ssh 连接服务器」会自动启用 `ssh`。回答结束后会打印本次使用的技能名。

## 与 v1 的区别

- v2 专注 **Agent Skills**（SKILL.md 说明注入），不包含 MCP 工具与 Web 服务。
- 需要 MCP/工具或 Web API 时请使用 v1.0。
