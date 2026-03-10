import sys
import os
from mangum import Mangum

# 获取项目根目录（requirements.txt 所在的目录）
path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.insert(0, path)

# 确保导入路径正确：backend文件夹 -> backend文件夹 -> main.py
from backend.backend.main import app

handler = Mangum(app)
