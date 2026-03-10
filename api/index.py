import sys
import os

# 将 backend 目录加入路径，确保能找到你的 main.py
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.backend.main import app

# Vercel 需要识别这个 app 对象
