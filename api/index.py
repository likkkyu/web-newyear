# api/index.py
from backend.backend.main import app  # 复用你现有的 FastAPI app

# Vercel 的 Python Runtime 会自动识别模块里的 `app` 作为入口（ASGI）
