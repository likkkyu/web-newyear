import sys
import os
from mangum import Mangum

# 将 backend 所在的根目录加入 Python 路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 这里的导入路径必须和你 GitHub 上的 backend/backend/main.py 一致
from backend.backend.main import app

handler = Mangum(app)
