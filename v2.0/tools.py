"""
可被 AI 调用的执行工具：仅保留基础占位，具体工具由各技能提供。
- SSH：skills/ssh/tools.py（启用 ssh 时加载）
- Shell：skills/shell/tools.py（启用 shell 时加载）
"""

# 无全局工具，全部由 skills/<name>/tools.py 按需加载
TOOLS: list = []
