"""轻量协议索引 - 基于关键词 + 结构解析，不依赖 Embedding"""
import re
import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from app.config import DATA_DIR

PROTOCOL_EXTENSIONS = {".proto", ".json", ".yaml", ".yml", ".xml", ".thrift", ".fbs"}


@dataclass
class ProtoSymbol:
    """协议符号（message, service, enum, rpc 等）"""
    name: str
    kind: str  # message, service, enum, rpc, field
    file_path: str
    line_start: int
    content: str = ""  # 完整定义内容
    parent: str = ""
    fields: list[str] = field(default_factory=list)


@dataclass
class ProtoFileIndex:
    """单个协议文件的索引"""
    path: str
    format: str  # proto, json, yaml, xml
    size: int
    mtime: float  # 文件修改时间，用于增量更新
    symbols: list[ProtoSymbol] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


class ProtocolIndex:
    """轻量协议索引器"""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.index_dir = DATA_DIR / "proto_index" / project_name
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._file_indices: dict[str, ProtoFileIndex] = {}
        self._symbol_map: dict[str, list[ProtoSymbol]] = {}
        self._root_dir: str = ""
        self._load_index()

    def get_saved_dir(self) -> str:
        """获取上次保存的目录路径"""
        meta = self.index_dir / "meta.json"
        if meta.exists():
            try:
                return json.loads(meta.read_text(encoding="utf-8")).get("root_dir", "")
            except Exception:
                pass
        return ""

    def build_index(self, root_dir: str, on_progress=None) -> int:
        """构建协议索引"""
        root = Path(root_dir)
        if not root.exists():
            return 0

        self._root_dir = root_dir
        files = self._collect_files(root)
        total = len(files)
        updated = 0

        for i, file_path in enumerate(files):
            rel = str(file_path.relative_to(root))
            mtime = file_path.stat().st_mtime

            # 增量：只处理新增或修改的文件
            existing = self._file_indices.get(rel)
            if existing and existing.mtime == mtime:
                continue

            idx = self._index_file(file_path, root)
            if idx:
                self._file_indices[rel] = idx
                for sym in idx.symbols:
                    key = sym.name.lower()
                    if key not in self._symbol_map:
                        self._symbol_map[key] = []
                    self._symbol_map[key].append(sym)
                updated += 1

            if on_progress and (i + 1) % 20 == 0:
                on_progress(i + 1, total)

        if on_progress:
            on_progress(total, total)

        # 清理已删除的文件
        current_files = {str(f.relative_to(root)) for f in files}
        for old_path in list(self._file_indices.keys()):
            if old_path not in current_files:
                del self._file_indices[old_path]

        self._rebuild_symbol_map()
        self._save_index()
        return total

    def _collect_files(self, root: Path) -> list[Path]:
        files = []
        for f in sorted(root.rglob("*")):
            if f.is_file() and f.suffix.lower() in PROTOCOL_EXTENSIONS:
                files.append(f)
        return files

    def _index_file(self, file_path: Path, root: Path) -> Optional[ProtoFileIndex]:
        """索引单个协议文件"""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
        if not content.strip():
            return None

        rel = str(file_path.relative_to(root))
        symbols = self._extract_symbols(content, rel, file_path.suffix.lower())
        keywords = self._extract_keywords(content, rel)

        return ProtoFileIndex(
            path=rel,
            format=file_path.suffix.lower(),
            size=len(content),
            mtime=file_path.stat().st_mtime,
            symbols=symbols,
            keywords=keywords,
        )

    def _extract_symbols(self, content: str, file_path: str, fmt: str) -> list[ProtoSymbol]:
        """提取协议符号"""
        symbols = []
        lines = content.split("\n")

        if fmt == ".proto":
            current_msg = ""
            msg_start = 0
            msg_lines = []
            for i, line in enumerate(lines):
                stripped = line.strip()
                # message / service / enum
                for kw in ["message", "service", "enum"]:
                    m = re.match(rf'^{kw}\s+(\w+)', stripped)
                    if m:
                        current_msg = m.group(1)
                        msg_start = i + 1
                        msg_lines = [stripped]
                        symbols.append(ProtoSymbol(
                            name=m.group(1), kind=kw, file_path=file_path,
                            line_start=i + 1, content=stripped,
                        ))
                # rpc
                m = re.match(r'rpc\s+(\w+)\s*\(', stripped)
                if m:
                    symbols.append(ProtoSymbol(
                        name=m.group(1), kind="rpc", file_path=file_path,
                        line_start=i + 1, content=stripped[:200], parent=current_msg,
                    ))
                # 字段
                m = re.match(r'(?:repeated\s+|optional\s+|required\s+)?(\w+)\s+(\w+)\s*=\s*(\d+)', stripped)
                if m and current_msg:
                    symbols.append(ProtoSymbol(
                        name=m.group(2), kind="field", file_path=file_path,
                        line_start=i + 1, content=stripped, parent=current_msg,
                    ))
        else:
            # JSON/YAML/XML: 提取顶层结构
            for i, line in enumerate(lines):
                stripped = line.strip()
                # 简单提取有意义的标签/key
                if fmt == ".xml":
                    m = re.match(r'<(\w+)[\s>]', stripped)
                    if m and m.group(1) not in ("xml", "?xml"):
                        symbols.append(ProtoSymbol(
                            name=m.group(1), kind="element", file_path=file_path,
                            line_start=i + 1, content=stripped[:150],
                        ))
                elif fmt in (".json", ".yaml", ".yml"):
                    m = re.match(r'"?(\w+)"?\s*:', stripped)
                    if m:
                        symbols.append(ProtoSymbol(
                            name=m.group(1), kind="field", file_path=file_path,
                            line_start=i + 1, content=stripped[:150],
                        ))
        return symbols

    def _extract_keywords(self, content: str, file_path: str) -> list[str]:
        keywords = set()
        name = Path(file_path).stem
        keywords.add(name.lower())
        for word in re.findall(r'[A-Z][a-z]+|[a-z]+', name):
            if len(word) > 2:
                keywords.add(word.lower())
        for m in re.findall(r'[\u4e00-\u9fff]+', content[:3000]):
            if len(m) >= 2:
                keywords.add(m)
        return list(keywords)[:30]

    # ========== 搜索 ==========

    def search(self, query: str, k: int = 10) -> list[dict]:
        """综合搜索"""
        results = []
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))

        # 符号匹配
        for sym_name, syms in self._symbol_map.items():
            if query_lower in sym_name or sym_name in query_lower:
                for sym in syms:
                    results.append({
                        "type": "symbol", "name": sym.name, "kind": sym.kind,
                        "file": sym.file_path, "line": sym.line_start,
                        "content": sym.content, "parent": sym.parent,
                        "score": 100 if query_lower == sym_name else 80,
                    })

        # 文件名和关键词匹配
        for path, idx in self._file_indices.items():
            score = 0
            if query_lower in path.lower():
                score += 60
            matched = query_words & set(kw.lower() for kw in idx.keywords)
            score += len(matched) * 20
            if score > 0:
                results.append({
                    "type": "file", "file": path, "format": idx.format,
                    "symbols_count": len(idx.symbols), "score": score,
                })

        results.sort(key=lambda x: -x["score"])
        seen = set()
        deduped = []
        for r in results:
            key = f"{r.get('name', '')}{r['file']}{r.get('line', '')}"
            if key not in seen:
                seen.add(key)
                deduped.append(r)
            if len(deduped) >= k:
                break
        return deduped

    def get_file_content(self, file_path: str) -> str:
        """读取协议文件原始内容"""
        root = Path(self._root_dir) if self._root_dir else None
        if not root:
            # 从 meta 读取
            root_dir = self.get_saved_dir()
            root = Path(root_dir) if root_dir else None
        if not root:
            return ""
        full = root / file_path
        try:
            return full.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def get_stats(self) -> dict:
        total_symbols = sum(len(idx.symbols) for idx in self._file_indices.values())
        return {
            "files": len(self._file_indices),
            "symbols": total_symbols,
            "root_dir": self._root_dir or self.get_saved_dir(),
        }

    def check_changes(self) -> bool:
        """检查目录是否有文件变化"""
        root_dir = self._root_dir or self.get_saved_dir()
        if not root_dir:
            return False
        root = Path(root_dir)
        if not root.exists():
            return False
        for f in root.rglob("*"):
            if f.is_file() and f.suffix.lower() in PROTOCOL_EXTENSIONS:
                rel = str(f.relative_to(root))
                existing = self._file_indices.get(rel)
                if not existing or existing.mtime != f.stat().st_mtime:
                    return True
        return False

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
                "path": idx.path, "format": idx.format, "size": idx.size, "mtime": idx.mtime,
                "symbols": [asdict(s) for s in idx.symbols],
                "keywords": idx.keywords,
            }
        (self.index_dir / "index.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        (self.index_dir / "meta.json").write_text(json.dumps({"root_dir": self._root_dir}, ensure_ascii=False), encoding="utf-8")

    def _load_index(self):
        index_file = self.index_dir / "index.json"
        if not index_file.exists():
            return
        try:
            data = json.loads(index_file.read_text(encoding="utf-8"))
            for path, info in data.items():
                symbols = [ProtoSymbol(**s) for s in info.get("symbols", [])]
                self._file_indices[path] = ProtoFileIndex(
                    path=info["path"], format=info["format"], size=info["size"],
                    mtime=info.get("mtime", 0), symbols=symbols, keywords=info.get("keywords", []),
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
