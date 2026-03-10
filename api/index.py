import sys
import os
from mangum import Mangum

# 这里的关键：让 Python 能够跨文件夹找到你的 main.py
# 路径必须对应 GitHub 上的 backend/backend/main.py
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from backend.backend.main import app

handler = Mangum(app)
