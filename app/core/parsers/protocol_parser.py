"""协议解析器 - 解析游戏通信协议文件（protobuf, json schema, 自定义协议等）"""
from pathlib import Path
from langchain_core.documents import Document
from app.config import CONFIG_EXTENSIONS


class ProtocolParser:
    """解析协议定义文件"""

    PROTOCOL_EXTENSIONS = {".proto", ".json", ".yaml", ".yml", ".xml", ".thrift", ".fbs"}

    def parse_files(self, file_paths: list[str]) -> list[Document]:
        """解析多个协议文件"""
        docs = []
        for fp in file_paths:
            p = Path(fp)
            doc = self._parse_single(p)
            if doc:
                docs.append(doc)
        return docs

    def _parse_single(self, file_path: Path) -> Document | None:
        """解析单个协议文件"""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                return None
            analysis = self._analyze_protocol(content, file_path.suffix)
            enriched = f"""# 协议文件: {file_path.name}
# 格式: {file_path.suffix}
{analysis}

## 原始内容
```
{content}
```
"""
            return Document(
                page_content=enriched,
                metadata={
                    "source": file_path.name,
                    "category": "protocol",
                    "format": file_path.suffix,
                },
            )
        except Exception:
            return None

    def _analyze_protocol(self, content: str, suffix: str) -> str:
        """分析协议结构"""
        lines = content.split("\n")
        structures = []
        if suffix == ".proto":
            for line in lines:
                stripped = line.strip()
                if any(stripped.startswith(kw) for kw in ["message ", "service ", "enum ", "rpc "]):
                    structures.append(f"- {stripped}")
        elif suffix in (".json", ".yaml", ".yml"):
            structures.append("- JSON/YAML 协议定义")
            # 提取顶层 key
            import json
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    for key in list(data.keys())[:20]:
                        structures.append(f"- 字段: {key}")
            except Exception:
                pass
        elif suffix == ".xml":
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("<") and not stripped.startswith("<?") and not stripped.startswith("<!"):
                    tag = stripped.split(">")[0].split(" ")[0].replace("<", "").replace("/", "")
                    if tag:
                        structures.append(f"- 标签: {tag}")

        if structures:
            return "## 协议结构\n" + "\n".join(structures[:30])
        return "## 协议结构\n- 自定义格式"
