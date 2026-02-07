import platform
import sys

# 根据操作系统动态导入对应的模块
system = platform.system()

if system == "Windows":
    from .windows import handle
elif system == "Linux":
    from .linux import handle
else:
    # 其他操作系统默认使用linux实现
    from .linux import handle

# 导出handle函数
__all__ = ["handle"]