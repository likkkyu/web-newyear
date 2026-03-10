import sys
import os
from mangum import Mangum

# 1. 获取 api 文件夹的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
# 2. 获取项目真正的根目录（web-newyear 这一层）
project_root = os.path.dirname(current_dir)

# 3. 核心修复：必须把根目录加入 sys.path
# 只有这样，main.py 里的 from backend.providers... 才能在顶级找到 backend 文件夹
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 4. 导入路径必须与你的目录结构完全一致
# 结构：根目录 -> backend 文件夹 -> backend 文件夹 -> main.py
try:
    from backend.backend.main import app
except ImportError as e:
    # 打印详细错误到 Vercel 日志，方便我们查看它到底在找哪里
    print(f"Import failed. project_root: {project_root}")
    print(f"sys.path: {sys.path}")
    raise e

handler = Mangum(app)
