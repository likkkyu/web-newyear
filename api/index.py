import sys
import os
from mangum import Mangum
# 确保路径指向你真正的 FastAPI 入口
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from backend.backend.main import app 

handler = Mangum(app) # 这一行是 Vercel 运行 Python 后端的生命线
