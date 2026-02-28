"""
项目根工具定义。基础工具列表为空，具体工具由各技能在 skills/<name>/tools.py 中提供。
agent 会合并 BASE_TOOLS 与当前启用技能的工具后注入 API。
"""

# 基础工具列表（空）；SSH、Shell、PDF、OCR、skill-creator 等由对应技能提供
TOOLS: list = []
