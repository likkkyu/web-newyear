import sys
import os
from mangum import Mangum

# 获取项目根目录并加入搜索路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# 导入路径：文件夹backend / 文件夹backend / 文件main.py
try:
    from backend.backend.main import app
except ImportError:
    # 兼容备选路径
    from backend.main import app

handler = Mangum(app)
