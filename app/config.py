"""全局配置"""
from pathlib import Path

# 数据目录
DATA_DIR = Path("./data")
SKILLS_DIR = DATA_DIR / "skills"

# 确保目录存在
for d in [DATA_DIR, SKILLS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 支持的文件类型
CODE_EXTENSIONS = {".java", ".kt", ".go", ".py", ".ts", ".js", ".cs", ".cpp", ".h", ".lua"}
