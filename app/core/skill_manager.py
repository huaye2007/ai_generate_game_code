"""Skill 管理器 - 根据项目代码/配置/协议自动提炼 Skill"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.config import SKILLS_DIR


class Skill(BaseModel):
    """Skill 定义"""
    name: str
    description: str
    category: str  # framework, config, protocol, business, custom
    template: str  # 提示词模板
    variables: list[str] = []
    dependencies: list[str] = []
    project: str = "default"
    source: str = "manual"  # manual / auto_generated
    created_at: str = ""
    updated_at: str = ""


# Skill 类型定义（用于自动生成时的分类指导）
SKILL_TYPES = {
    "protocol_code": {"category": "protocol", "desc": "协议处理代码生成"},
    "controller_entry": {"category": "business", "desc": "协议入口 Controller 生成"},
    "business_service": {"category": "business", "desc": "业务逻辑 Service 生成"},
    "data_table_loader": {"category": "config", "desc": "配置表加载类生成"},
    "db_dao": {"category": "business", "desc": "数据库 DAO 操作类生成"},
    "data_table_create": {"category": "business", "desc": "数据表定义/建表生成"},
}


class SkillManager:
    """Skill 管理器"""

    def __init__(self, project_name: str = "default"):
        self.project_name = project_name
        self.project_dir = SKILLS_DIR / project_name
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def list_skills(self) -> list[Skill]:
        """列出所有已保存的 Skill"""
        skills = {}
        for f in sorted(self.project_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                s = Skill(**data)
                skills[s.name] = s
            except Exception:
                continue
        return list(skills.values())

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定 Skill"""
        skill_file = self.project_dir / f"{name}.json"
        if skill_file.exists():
            try:
                data = json.loads(skill_file.read_text(encoding="utf-8"))
                return Skill(**data)
            except Exception:
                pass
        return None

    def save_skill(self, skill: Skill):
        """保存 Skill"""
        now = datetime.now().isoformat()
        skill.project = self.project_name
        if not skill.created_at:
            skill.created_at = now
        skill.updated_at = now
        path = self.project_dir / f"{skill.name}.json"
        path.write_text(skill.model_dump_json(indent=2), encoding="utf-8")

    def delete_skill(self, name: str) -> bool:
        path = self.project_dir / f"{name}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def has_skills(self) -> bool:
        """是否已有生成的 Skill"""
        return any(self.project_dir.glob("*.json"))


def _collect_project_context(project_name: str, modules: list[str] = None) -> str:
    """收集项目上下文（代码索引 + 配置表 + 协议）"""
    from app.core.code_index import CodeIndex

    parts = []

    # 代码索引
    code_idx = CodeIndex(project_name)
    if code_idx.get_stats()["files"] > 0:
        keywords = ["Controller", "Service", "Handler", "Manager", "Dao", "Repository", "Config", "Loader"]
        if modules:
            keywords.extend(modules)
        for kw in keywords:
            for r in code_idx.search(kw, k=3):
                if modules and r.get("module") and r["module"] not in modules:
                    continue
                if r["type"] == "symbol":
                    parts.append(f"[{r['kind']}] {r['name']} in {r['file']}:{r['line']}\n  {r['signature']}")
                else:
                    parts.append(f"[file] {r['file']} (module: {r['module']})")

        # 读取指定模块的代码片段
        if modules:
            import streamlit as st
            code_dir = st.session_state.get("code_dir", "")
            if code_dir:
                from app.core.code_index import CodeSymbol
                for mod in modules[:3]:
                    for r in code_idx.search(mod, k=3):
                        if r["type"] == "symbol":
                            sym = CodeSymbol(name=r["name"], kind=r["kind"], file_path=r["file"],
                                             line_start=r["line"], signature=r["signature"])
                            ctx = code_idx.get_symbol_context(sym, code_dir, context_lines=40)
                            if ctx:
                                parts.append(f"[代码] {r['file']}:{r['line']}\n```\n{ctx[:600]}\n```")

    # 配置表（使用 ConfigIndex）
    from app.core.config_index import ConfigIndex
    config_idx = ConfigIndex(project_name)
    if config_idx.get_stats()["files"] > 0:
        for s in config_idx.get_all_sheets()[:3]:
            detail = config_idx.get_sheet_detail(s["file"], s["sheet"])
            if detail:
                parts.append(f"[配置表] {detail[:400]}")

    # 协议（使用 ProtocolIndex）
    from app.core.protocol_index import ProtocolIndex
    proto_idx = ProtocolIndex(project_name)
    if proto_idx.get_stats()["files"] > 0:
        for r in proto_idx.search("message", k=3):
            if r["type"] == "symbol":
                parts.append(f"[协议 {r['kind']}] {r['name']} — {r['content']}")

    return "\n\n".join(parts[:40])


def parse_skill_json_from_response(content: str) -> list[dict]:
    """从 LLM 回复中提取 JSON 数组"""
    content = content.strip()
    # 去掉 markdown 代码块
    if "```" in content:
        # 找到第一个 [ 和最后一个 ]
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end != -1:
            content = content[start:end + 1]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return []


def save_skills_from_json(project_name: str, items: list[dict]) -> list[Skill]:
    """将 JSON 数据保存为 Skill"""
    mgr = SkillManager(project_name)
    skills = []
    for item in items:
        template = item.get("template", "")
        template = template.replace("{{", "{").replace("}}", "}")
        skill = Skill(
            name=item.get("name", "unnamed"),
            description=item.get("description", ""),
            category=item.get("category", "business"),
            template=template,
            variables=item.get("variables", []),
            source="auto_generated",
        )
        mgr.save_skill(skill)
        skills.append(skill)
    return skills
