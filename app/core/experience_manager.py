"""经验管理 - AI 学习业务模块代码，总结开发经验"""
import json
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel
from app.config import DATA_DIR

EXPERIENCE_DIR = DATA_DIR / "experiences"
EXPERIENCE_DIR.mkdir(parents=True, exist_ok=True)


class Experience(BaseModel):
    """一条开发经验"""
    name: str  # 经验名称（通常是模块名）
    source_dir: str  # 来源代码目录
    summary: str  # AI 总结的经验内容
    patterns: list[str] = []  # 提炼的开发模式
    file_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class ExperienceManager:
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.project_dir = EXPERIENCE_DIR / project_name
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def list_experiences(self) -> list[Experience]:
        exps = []
        for f in sorted(self.project_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                exps.append(Experience(**json.loads(f.read_text(encoding="utf-8"))))
            except Exception:
                pass
        return exps

    def save_experience(self, exp: Experience):
        now = datetime.now().isoformat()
        if not exp.created_at:
            exp.created_at = now
        exp.updated_at = now
        import re
        safe = re.sub(r'[<>:"/\\|?*]', '_', exp.name)
        (self.project_dir / f"{safe}.json").write_text(
            exp.model_dump_json(indent=2), encoding="utf-8")

    def delete_experience(self, name: str):
        import re
        safe = re.sub(r'[<>:"/\\|?*]', '_', name)
        f = self.project_dir / f"{safe}.json"
        if f.exists():
            f.unlink()

    def get_all_summaries(self) -> str:
        """获取综合总结（供其他模块使用）"""
        combined = self.project_dir / "_combined_summary.md"
        if combined.exists():
            return combined.read_text(encoding="utf-8")
        return ""

    def save_combined_summary(self, summary: str):
        """保存综合总结"""
        (self.project_dir / "_combined_summary.md").write_text(summary, encoding="utf-8")

    def get_combined_summary(self) -> str:
        """获取综合总结"""
        f = self.project_dir / "_combined_summary.md"
        return f.read_text(encoding="utf-8") if f.exists() else ""
