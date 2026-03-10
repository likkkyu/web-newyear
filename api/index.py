import sys
import os
from mangum import Mangum

# 获取当前 api 文件夹的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录（即 backend 文件夹所在的目录）
project_root = os.path.dirname(current_dir)

# 核心修复：必须将根目录插入 sys.path 的最前面
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 确保 backend 文件夹本身也被视为一个包
backend_path = os.path.join(project_root, "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    # 按照你的结构：根目录/backend/backend/main.py
    from backend.backend.main import app
except ImportError:
    # 备选：如果结构是 根目录/backend/main.py
    from backend.main import app

handler = Mangum(app)
