"""轻量代码索引 - 基于关键词 + AST 结构，不依赖 Embedding 向量化
参考 Claude Code 的思路：文本搜索 + 结构提取 + 按需读取
"""
import re
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from app.config import DATA_DIR, CODE_EXTENSIONS


@dataclass
class CodeSymbol:
    """代码符号（类、方法、函数等）"""
    name: str
    kind: str  # class, method, function, interface, enum
    file_path: str
    line_start: int
    line_end: int = 0
    parent: str = ""  # 所属类名
    signature: str = ""  # 完整签名


@dataclass
class CodeFileIndex:
    """单个文件的索引"""
    path: str
    module: str
    language: str
    size: int
    mtime: float = 0
    symbols: list[CodeSymbol] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)  # 提取的关键词


class CodeIndex:
    """轻量代码索引器"""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.index_dir = DATA_DIR / "code_index" / project_name
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._file_indices: dict[str, CodeFileIndex] = {}
        self._symbol_map: dict[str, list[CodeSymbol]] = {}  # name -> symbols
        self._root_dir: str = ""
        self._load_index()

    def get_saved_dir(self) -> str:
        meta = self.index_dir / "meta.json"
        if meta.exists():
            try:
                return json.loads(meta.read_text(encoding="utf-8")).get("root_dir", "")
            except Exception:
                pass
        return ""

    def check_changes(self) -> bool:
        """检查目录是否有文件变化"""
        root_dir = self._root_dir or self.get_saved_dir()
        if not root_dir:
            return False
        root = Path(root_dir)
        if not root.exists():
            return False
        from app.core.parsers.code_parser import EXCLUDE_DIRS, EXCLUDE_EXTENSIONS
        current_files = set()
        for f in self._collect_files(root, EXCLUDE_DIRS, EXCLUDE_EXTENSIONS):
            rel = str(f.relative_to(root))
            current_files.add(rel)
            existing = self._file_indices.get(rel)
            if not existing or existing.mtime != f.stat().st_mtime:
                return True
        if set(self._file_indices.keys()) != current_files:
            return True
        return False

    def build_index(self, root_dir: str, on_progress=None) -> int:
        """构建代码索引（增量：只处理新增/修改的文件）"""
        from app.core.parsers.code_parser import EXCLUDE_DIRS, EXCLUDE_EXTENSIONS
        root = Path(root_dir)
        if not root.exists():
            return 0

        self._root_dir = root_dir
        files = self._collect_files(root, EXCLUDE_DIRS, EXCLUDE_EXTENSIONS)
        total = len(files)
        updated = 0

        current_files = set()
        for i, file_path in enumerate(files):
            rel = str(file_path.relative_to(root))
            current_files.add(rel)
            mtime = file_path.stat().st_mtime

            # 增量：跳过未修改的文件
            existing = self._file_indices.get(rel)
            if existing and existing.mtime == mtime:
                continue

            try:
                idx = self._index_file(file_path, root)
                if idx:
                    idx.mtime = mtime
                    self._file_indices[idx.path] = idx
                    updated += 1
            except Exception:
                pass
            if on_progress and (i + 1) % 50 == 0:
                on_progress(i + 1, total)

        # 清理已删除的文件
        for old in list(self._file_indices.keys()):
            if old not in current_files:
                del self._file_indices[old]

        if on_progress:
            on_progress(total, total)

        self._rebuild_symbol_map()
        self._save_index()
        return total

    def _collect_files(self, root: Path, exclude_dirs: set, exclude_exts: set) -> list[Path]:
        """收集所有源代码文件"""
        files = []
        def walk(d: Path):
            try:
                for item in sorted(d.iterdir()):
                    if item.is_dir():
                        if item.name.lower() not in exclude_dirs:
                            walk(item)
                    elif item.is_file():
                        if item.suffix in CODE_EXTENSIONS and item.suffix.lower() not in exclude_exts:
                            files.append(item)
            except PermissionError:
                pass
        walk(root)
        return files

    def _index_file(self, file_path: Path, root: Path) -> Optional[CodeFileIndex]:
        """索引单个文件：提取符号、import、关键词"""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
        if not content.strip():
            return None

        rel_path = str(file_path.relative_to(root))
        parts = Path(rel_path).parts
        module = parts[0] if len(parts) > 1 else "root"

        symbols = self._extract_symbols(content, rel_path)
        imports = self._extract_imports(content)
        keywords = self._extract_keywords(content, rel_path)

        return CodeFileIndex(
            path=rel_path,
            module=module,
            language=file_path.suffix,
            size=len(content),
            symbols=symbols,
            imports=imports,
            keywords=keywords,
        )

    def _extract_symbols(self, content: str, file_path: str) -> list[CodeSymbol]:
        """提取代码符号（类、方法、函数）"""
        symbols = []
        lines = content.split("\n")
        current_class = ""

        patterns = [
            (r'^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:abstract\s+)?class\s+(\w+)', 'class'),
            (r'^\s*(?:public|private|protected)?\s*(?:static\s+)?interface\s+(\w+)', 'interface'),
            (r'^\s*(?:public|private|protected)?\s*(?:static\s+)?enum\s+(\w+)', 'enum'),
            (r'^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:\w+(?:<[^>]*>)?)\s+(\w+)\s*\(', 'method'),
            (r'^\s*def\s+(\w+)\s*\(', 'function'),
            (r'^\s*func\s+(\w+)\s*\(', 'function'),
            (r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)', 'function'),
        ]

        for line_num, line in enumerate(lines):
            stripped = line.strip()
            # 跟踪当前类
            for pattern, kind in patterns:
                m = re.match(pattern, line)
                if m:
                    name = m.group(1)
                    if kind == 'class':
                        current_class = name
                    symbols.append(CodeSymbol(
                        name=name,
                        kind=kind,
                        file_path=file_path,
                        line_start=line_num + 1,
                        parent=current_class if kind == 'method' else "",
                        signature=stripped[:150],
                    ))
                    break
        return symbols

    def _extract_imports(self, content: str) -> list[str]:
        """提取 import 语句"""
        imports = []
        for line in content.split("\n")[:50]:  # 只看前50行
            stripped = line.strip()
            if stripped.startswith(("import ", "from ", "require(", "#include", "using ")):
                imports.append(stripped[:200])
        return imports

    def _extract_keywords(self, content: str, file_path: str) -> list[str]:
        """提取关键词（文件名、类名、方法名等）"""
        keywords = set()
        # 文件名关键词
        name = Path(file_path).stem
        keywords.add(name.lower())
        # 驼峰拆分
        for word in re.findall(r'[A-Z][a-z]+|[a-z]+', name):
            if len(word) > 2:
                keywords.add(word.lower())
        # 注释中的中文关键词
        for m in re.findall(r'[\u4e00-\u9fff]+', content[:3000]):
            if len(m) >= 2:
                keywords.add(m)
        return list(keywords)[:30]

    # ========== 搜索方法 ==========

    def search(self, query: str, k: int = 10) -> list[dict]:
        """综合搜索：关键词匹配 + 符号匹配"""
        results = []
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))

        # 1. 符号名精确/模糊匹配
        for sym_name, syms in self._symbol_map.items():
            if query_lower in sym_name or sym_name in query_lower:
                for sym in syms:
                    results.append({
                        "type": "symbol",
                        "name": sym.name,
                        "kind": sym.kind,
                        "file": sym.file_path,
                        "line": sym.line_start,
                        "signature": sym.signature,
                        "parent": sym.parent,
                        "score": 100 if query_lower == sym_name else 80,
                    })

        # 2. 文件名和关键词匹配
        for path, idx in self._file_indices.items():
            score = 0
            path_lower = path.lower()
            # 文件路径匹配
            if query_lower in path_lower:
                score += 60
            # 关键词匹配
            matched_kw = query_words & set(kw.lower() for kw in idx.keywords)
            score += len(matched_kw) * 20
            # 模块名匹配
            if query_lower in idx.module.lower():
                score += 40

            if score > 0:
                results.append({
                    "type": "file",
                    "file": path,
                    "module": idx.module,
                    "language": idx.language,
                    "symbols_count": len(idx.symbols),
                    "score": score,
                })

        # 按分数排序，去重
        results.sort(key=lambda x: -x["score"])
        seen_files = set()
        deduped = []
        for r in results:
            f = r["file"]
            if f not in seen_files:
                seen_files.add(f)
                deduped.append(r)
            if len(deduped) >= k:
                break
        return deduped

    def get_file_content(self, file_path: str, root_dir: str, max_lines: int = 200) -> str:
        """按需读取文件内容（不预加载，用时再读）"""
        full_path = Path(root_dir) / file_path
        try:
            lines = full_path.read_text(encoding="utf-8", errors="ignore").split("\n")
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + f"\n... (共 {len(lines)} 行，已截断)"
            return "\n".join(lines)
        except Exception:
            return ""

    def get_symbol_context(self, symbol: CodeSymbol, root_dir: str, context_lines: int = 50) -> str:
        """获取符号周围的代码上下文"""
        full_path = Path(root_dir) / symbol.file_path
        try:
            lines = full_path.read_text(encoding="utf-8", errors="ignore").split("\n")
            start = max(0, symbol.line_start - 3)
            end = min(len(lines), symbol.line_start + context_lines)
            return "\n".join(lines[start:end])
        except Exception:
            return ""

    def get_stats(self) -> dict:
        """获取索引统计"""
        total_symbols = sum(len(idx.symbols) for idx in self._file_indices.values())
        modules = set(idx.module for idx in self._file_indices.values())
        return {
            "files": len(self._file_indices),
            "symbols": total_symbols,
            "modules": len(modules),
            "module_list": sorted(modules),
            "root_dir": self._root_dir or self.get_saved_dir(),
        }

    def get_file_content(self, file_path: str, root_dir: str = "", max_lines: int = 200) -> str:
        """按需读取文件内容"""
        rd = root_dir or self._root_dir or self.get_saved_dir()
        if not rd:
            return ""
        full_path = Path(rd) / file_path
        try:
            lines = full_path.read_text(encoding="utf-8", errors="ignore").split("\n")
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + f"\n... (共 {len(lines)} 行，已截断)"
            return "\n".join(lines)
        except Exception:
            return ""

    def get_symbol_context(self, symbol: CodeSymbol, root_dir: str = "", context_lines: int = 50) -> str:
        """获取符号周围的代码上下文"""
        rd = root_dir or self._root_dir or self.get_saved_dir()
        if not rd:
            return ""
        full_path = Path(rd) / symbol.file_path
        try:
            lines = full_path.read_text(encoding="utf-8", errors="ignore").split("\n")
            start = max(0, symbol.line_start - 3)
            end = min(len(lines), symbol.line_start + context_lines)
            return "\n".join(lines[start:end])
        except Exception:
            return ""

    # ========== 持久化 ==========

    def _rebuild_symbol_map(self):
        self._symbol_map.clear()
        for idx in self._file_indices.values():
            for sym in idx.symbols:
                key = sym.name.lower()
                if key not in self._symbol_map:
                    self._symbol_map[key] = []
                self._symbol_map[key].append(sym)

    def _save_index(self):
        data = {}
        for path, idx in self._file_indices.items():
            data[path] = {
                "path": idx.path, "module": idx.module, "language": idx.language,
                "size": idx.size, "mtime": idx.mtime,
                "symbols": [asdict(s) for s in idx.symbols],
                "imports": idx.imports, "keywords": idx.keywords,
            }
        (self.index_dir / "index.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        (self.index_dir / "meta.json").write_text(
            json.dumps({"root_dir": self._root_dir}, ensure_ascii=False), encoding="utf-8")

    def _load_index(self):
        index_file = self.index_dir / "index.json"
        if not index_file.exists():
            return
        try:
            data = json.loads(index_file.read_text(encoding="utf-8"))
            for path, info in data.items():
                symbols = [CodeSymbol(**s) for s in info.get("symbols", [])]
                self._file_indices[path] = CodeFileIndex(
                    path=info["path"], module=info["module"], language=info["language"],
                    size=info["size"], mtime=info.get("mtime", 0),
                    symbols=symbols, imports=info.get("imports", []),
                    keywords=info.get("keywords", []),
                )
            self._rebuild_symbol_map()
        except Exception:
            pass
        meta = self.index_dir / "meta.json"
        if meta.exists():
            try:
                self._root_dir = json.loads(meta.read_text(encoding="utf-8")).get("root_dir", "")
            except Exception:
                pass
