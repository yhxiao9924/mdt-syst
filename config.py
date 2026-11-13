"""全局配置：环境变量、路径、模型参数。"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CASE_DIR = DATA_DIR / "cases"
KB_DIR = BASE_DIR / "kb"

# 模型配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat")
TEMPERATURE = 0.2

# 单个 Agent 最多进行几轮"思考-调用工具"
MAX_TOOL_ROUNDS = 5

DISCLAIMER = "本系统基于公开数据构造的虚拟病例，仅供教学演示，不构成任何医疗建议。"
