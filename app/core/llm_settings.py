"""LLM 设置管理 - 持久化保存到本地"""
import json
from pathlib import Path
from app.config import DATA_DIR

SETTINGS_FILE = DATA_DIR / "llm_settings.json"

# 预定义的大模型提供商
PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "default_model": "gpt-4o",
    },
    "zhipu": {
        "name": "智谱 AI (GLM)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "glm-4", "glm-4-flash"],
        "default_model": "glm-4-plus",
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
        "default_model": "qwen-max",
    },
    "custom": {
        "name": "自定义（OpenAI 兼容）",
        "base_url": "",
        "models": [],
        "default_model": "",
    },
}


def load_settings() -> dict:
    """加载 LLM 设置"""
    defaults = {
        "provider": "deepseek",
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    }
    if SETTINGS_FILE.exists():
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_settings(provider: str, api_key: str, base_url: str, model: str):
    """保存 LLM 设置"""
    data = {"provider": provider, "api_key": api_key, "base_url": base_url, "model": model}
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_llm_config() -> dict:
    """获取当前 LLM 配置（供其他模块使用）"""
    s = load_settings()
    return {
        "api_key": s["api_key"],
        "base_url": s["base_url"],
        "model": s["model"],
    }
