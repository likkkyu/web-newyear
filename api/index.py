import sys
import os
from mangum import Mangum

# 定位到最内层的 backend/backend 目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
# 必须准确指向 main.py 所在的文件夹
inner_backend = os.path.join(project_root, "backend", "backend")

if inner_backend not in sys.path:
    sys.path.insert(0, inner_backend)

try:
    from main import app
except ImportError:
    # 备选路径：如果 backend 只有一层
    from backend.main import app

handler = Mangum(app)
