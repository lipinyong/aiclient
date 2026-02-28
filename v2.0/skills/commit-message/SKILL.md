---
name: commit-message
description: 根据代码变更或用户描述生成规范的 Git 提交信息。当用户要求写 commit message、提交说明、或提供 diff/变更描述时使用。
triggers: [commit, 提交, 提交说明, diff, 变更描述, commit message, 写提交]
---

# Git 提交信息生成

## 规范

- 使用 **约定式提交**（Conventional Commits）：`<type>(<scope>): <subject>`
- type 取：`feat`（新功能）、`fix`（修复）、`docs`、`style`、`refactor`、`test`、`chore`
- subject 使用祈使句、首字母小写、结尾不加句号，长度建议 50 字以内
- 可选第二行空行后写详细说明（body）

## 输出格式

```
<type>(<scope>): <subject>

[空行]
[可选的 body，说明动机或变更细节]
```

## 示例

- 输入：添加用户登录接口  
  输出：`feat(auth): add user login endpoint`

- 输入：修复列表页在空数据时崩溃  
  输出：`fix(list): handle empty data to prevent crash`

- 输入：更新 README 安装步骤  
  输出：`docs(readme): update installation steps`

请根据用户提供的变更描述或 diff 内容，生成一条符合上述规范的提交信息；若用户使用中文描述，subject 可用中文。
