---
name: shell
description: 生成或解释本地 Shell 命令。当用户要执行命令、查看目录、跑脚本、环境变量、管道、批处理或询问 Windows/Linux/macOS 命令行时使用。
triggers: [命令, 终端, shell, 执行命令, 脚本, 目录, ls, dir, powershell, bash, cmd, 环境变量, 管道, 批处理, 命令行]
---

# 本地 Shell 技能

## 使用场景

- 用户要求「执行命令」「在终端运行」「列出目录」「查进程」「写个脚本」等
- 涉及：文件操作、环境变量、管道、重定向、后台任务、PowerShell / CMD / bash / zsh

## 行为规范

1. **脚本位置**：**禁止在当前目录或用户目录下生成脚本文件**。需要生成并执行脚本时，必须使用 **run_script** 工具，脚本会统一写入项目根下的 **data/temp** 目录并在此目录执行，便于后期统一清除；不得用 run_shell 执行“在当前目录写文件再执行”的命令。
2. **平台区分**：若未说明，Windows 下优先给出 **PowerShell** 命令，Linux/macOS 给出 **bash**；必要时同时给出两种。
3. **安全**：对 `rm -rf`、`del /s`、格式化、覆盖系统文件等危险操作给出明确警告，并建议先备份或 dry-run。
4. **可执行性**：给出的命令应可直接复制到终端运行；若有占位符（如路径、变量），用 `<路径>` 等标出并说明替换方式。
4. **输出形式**：用代码块包裹命令，并注明 shell 类型，例如：
   ```powershell
   # PowerShell
   Get-ChildItem -Recurse -Filter "*.py"
   ```
   ```bash
   # bash
   find . -name "*.py"
   ```

## 常用对照（示例）

| 需求       | PowerShell (Windows)     | bash (Linux/macOS)   |
|------------|--------------------------|----------------------|
| 列目录     | `Get-ChildItem` / `dir`  | `ls -la`             |
| 当前路径   | `Get-Location` / `pwd`   | `pwd`                |
| 环境变量   | `$env:VAR`               | `$VAR` / `echo $VAR` |
| 递归查找   | `Get-ChildItem -Recurse` | `find . -name "..."`  |
| 进程/端口  | `Get-Process` / `netstat`| `ps aux` / `ss -tlnp`|

## 说明

- **当启用本技能且用户要求执行本地命令时**：单条命令用 **run_shell**；**需要生成并运行脚本时**必须用 **run_script**，将脚本内容传入，工具会写入 data/temp 并执行，不得在当前目录创建脚本。
- 涉及路径时使用正斜杠或平台惯用写法，避免硬编码用户机器上的绝对路径。
- data/temp 由 run_script 自动创建，可定期手动清空以清理临时脚本。
