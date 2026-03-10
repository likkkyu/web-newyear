import sys
import os
from mangum import Mangum

# 确保能找到 backend 文件夹
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.backend.main import app

# 必须通过 Mangum 包装 FastAPI 实例
handler = Mangum(app)
