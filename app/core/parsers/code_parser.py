"""代码解析器 - 解析游戏服务器代码目录，构建代码索引"""
from pathlib import Path
from langchain_core.documents import Document
from app.config import CODE_EXTENSIONS

# 需要排除的目录（编译产物、构建目录、依赖、IDE 配置等）
EXCLUDE_DIRS = {
    "target", "build", "out", "bin", "obj", "dist", "output",
    ".gradle", ".mvn", ".idea", ".vscode", ".git", ".svn",
    "node_modules", "__pycache__", ".cache", "logs", "log",
    "test", "tests", "doc", "docs",
}

# 需要排除的文件后缀（编译产物、二进制文件等）
EXCLUDE_EXTENSIONS = {
    ".class", ".jar", ".war", ".ear", ".pyc", ".pyo",
    ".o", ".obj", ".exe", ".dll", ".so", ".dylib",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".log", ".lock", ".map",
}


class CodeParser:
    """解析代码目录，提取源代码结构和内容"""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def _should_skip_dir(self, dir_path: Path) -> bool:
        """判断是否跳过该目录"""
        return dir_path.name.lower() in EXCLUDE_DIRS

    def _should_skip_file(self, file_path: Path) -> bool:
        """判断是否跳过该文件"""
        if file_path.suffix.lower() in EXCLUDE_EXTENSIONS:
            return True
        if file_path.suffix not in CODE_EXTENSIONS:
            return True
        # 跳过生成的代码文件（常见命名模式）
        name_lower = file_path.name.lower()
        if any(name_lower.endswith(s) for s in ["_generated.java", "_gen.go", ".g.dart", ".generated.ts"]):
            return True
        return False

    def parse_directory(self) -> list[Document]:
        """递归解析代码目录，自动排除编译产物和构建目录"""
        docs = []
        if not self.root_dir.exists():
            return docs
        self._walk_dir(self.root_dir, docs)
        return docs

    def _walk_dir(self, current_dir: Path, docs: list[Document]):
        """手动递归遍历，跳过排除目录"""
        try:
            for item in sorted(current_dir.iterdir()):
                if item.is_dir():
                    if not self._should_skip_dir(item):
                        self._walk_dir(item, docs)
                elif item.is_file():
                    if not self._should_skip_file(item):
                        doc = self._parse_file(item)
                        if doc:
                            docs.append(doc)
        except PermissionError:
            pass

    def _parse_file(self, file_path: Path) -> Document | None:
        """解析单个代码文件"""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                return None
            rel_path = file_path.relative_to(self.root_dir)
            # 提取代码结构摘要
            summary = self._extract_structure(content, file_path.suffix)
            enriched = f"# File: {rel_path}\n# Language: {file_path.suffix}\n{summary}\n\n{content}"
            return Document(
                page_content=enriched,
                metadata={
                    "source": str(rel_path),
                    "file_type": file_path.suffix,
                    "category": "code",
                    "module": self._detect_module(rel_path),
                },
            )
        except Exception:
            return None

    def _extract_structure(self, content: str, suffix: str) -> str:
        """提取代码结构（类名、方法名等）"""
        lines = content.split("\n")
        structures = []
        for line in lines:
            stripped = line.strip()
            # 通用的类/函数/方法检测
            if any(stripped.startswith(kw) for kw in [
                "class ", "def ", "func ", "function ", "public ", "private ",
                "protected ", "interface ", "struct ", "enum ", "abstract ",
            ]):
                structures.append(f"# Structure: {stripped[:120]}")
        return "\n".join(structures[:50])

    def _detect_module(self, rel_path: Path) -> str:
        """检测代码所属模块"""
        parts = rel_path.parts
        if len(parts) > 1:
            return parts[0]
        return "root"
