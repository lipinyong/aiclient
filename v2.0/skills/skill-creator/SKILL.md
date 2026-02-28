---
name: skill-creator
description: 在线创建、管理、安装与删除 Agent Skills。根据用户描述生成新技能、从本地目录或 GitHub 安装技能、列出/删除已有技能。
triggers: [创建技能, 管理技能, 安装技能, 删除技能, 列出技能, 所有技能, 当前技能, 从github安装, 技能管理, skill创建, 生成skill, 写一个skill]
---

# 技能创建与管理

当用户要求**创建新技能**、**管理/列出/删除技能**、**从本地目录或 GitHub 安装技能**时，使用本技能提供的工具完成操作。

## 能力

1. **列出技能**：`skill_list` — 列出当前已发现的所有技能（含名称、描述、路径）。
2. **创建技能**：`skill_create` — 根据用户描述生成一个完整的技能目录与 SKILL.md，写入项目 `skills/<name>/`，之后系统即可按需加载并调用。
3. **删除技能**：`skill_delete` — 按名称删除一个技能目录（不可恢复）。
4. **从本地安装**：`skill_install_path` — 从用户指定的本地目录安装技能（复制到 `skills/`）。
5. **从 GitHub 安装**：`skill_install_github` — 从 GitHub 仓库安装技能（支持指定子目录，如 `owner/repo` 下的 `skills/xxx`）。

## 使用规范

- 创建技能时：先根据用户需求确定 `name`（小写、连字符）、`description`、`triggers`（触发词列表），再生成清晰的 Markdown 正文（步骤、示例、注意事项），最后调用 `skill_create` 写入。创建完成后告知用户技能名与触发词，并说明「下次对话中说出触发词即可自动启用该技能」。
- 删除前：用 `skill_list` 确认名称，再调用 `skill_delete`，并确认操作不可恢复。
- 从 GitHub 安装时：若仓库内技能在子目录（如 `skills/my-skill`），使用参数 `subdir` 指定；安装完成后列出新技能并说明用法。
- 所有路径以当前工作目录（运行 chat 的目录）为项目根；如需指定其他项目根，可传 `project_root` 参数。

## 说明

- 新创建的技能仅包含 `SKILL.md`；若用户需要可执行工具（如调用 API、读文件），需在技能目录下手动添加 `tools.py`（或后续由你生成模板）。
- 从 GitHub 安装时需本机已安装 `git` 且可访问网络。
