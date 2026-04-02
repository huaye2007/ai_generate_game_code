"""轻量配置表索引 - 基于关键词 + 文本解析，不依赖 Embedding"""
import re
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
import pandas as pd
from app.config import DATA_DIR

CONFIG_EXTENSIONS = {".xlsx", ".xls", ".csv"}


@dataclass
class ConfigSheet:
    """单个 Sheet 的索引"""
    file_name: str
    sheet_name: str
    columns: list[str] = field(default_factory=list)
    dtypes: dict = field(default_factory=dict)  # 列名 -> 类型
    row_count: int = 0
    sample_text: str = ""  # 前几行的文本表示
    keywords: list[str] = field(default_factory=list)


@dataclass
class ConfigFileIndex:
    """单个配置文件的索引"""
    path: str
    file_name: str
    mtime: float = 0
    sheets: list[ConfigSheet] = field(default_factory=list)


class ConfigIndex:
    """轻量配置表索引器"""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.index_dir = DATA_DIR / "config_index" / project_name
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._file_indices: dict[str, ConfigFileIndex] = {}
        self._sheet_map: dict[str, list[ConfigSheet]] = {}  # keyword -> sheets
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
        current_files = set()
        for f in self._collect_files(root):
            rel = str(f.relative_to(root))
            current_files.add(rel)
            existing = self._file_indices.get(rel)
            if not existing or existing.mtime != f.stat().st_mtime:
                return True
        if set(self._file_indices.keys()) != current_files:
            return True
        return False

    def build_index(self, root_dir: str, on_progress=None) -> int:
        """构建配置表索引（增量）"""
        root = Path(root_dir)
        if not root.exists():
            return 0
        self._root_dir = root_dir
        files = self._collect_files(root)
        total = len(files)
        updated = 0

        current_files = set()
        for i, file_path in enumerate(files):
            rel = str(file_path.relative_to(root))
            current_files.add(rel)
            mtime = file_path.stat().st_mtime

            existing = self._file_indices.get(rel)
            if existing and existing.mtime == mtime:
                continue

            idx = self._index_file(file_path, root)
            if idx:
                idx.mtime = mtime
                self._file_indices[rel] = idx
                updated += 1

            if on_progress:
                on_progress(i + 1, total)

        # 清理已删除的文件
        for old in list(self._file_indices.keys()):
            if old not in current_files:
                del self._file_indices[old]

        if on_progress:
            on_progress(total, total)

        self._rebuild_sheet_map()
        self._save_index()
        return total

    def _collect_files(self, root: Path) -> list[Path]:
        files = []
        for f in sorted(root.rglob("*")):
            if f.is_file() and f.suffix.lower() in CONFIG_EXTENSIONS and not f.name.startswith("~"):
                files.append(f)
        return files

    def _index_file(self, file_path: Path, root: Path) -> Optional[ConfigFileIndex]:
        """索引单个配置文件"""
        rel = str(file_path.relative_to(root))
        sheets = []
        try:
            if file_path.suffix.lower() == ".csv":
                df = pd.read_csv(file_path, encoding="utf-8", errors="ignore", nrows=100)
                sheet = self._df_to_sheet(df, file_path.name, "Sheet1")
                if sheet:
                    sheets.append(sheet)
            else:
                xls = pd.ExcelFile(file_path)
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet_name, nrows=100)
                    sheet = self._df_to_sheet(df, file_path.name, sheet_name)
                    if sheet:
                        sheets.append(sheet)
        except Exception:
            pass

        if not sheets:
            return None

        return ConfigFileIndex(path=rel, file_name=file_path.name, sheets=sheets)

    def _df_to_sheet(self, df: pd.DataFrame, file_name: str, sheet_name: str) -> Optional[ConfigSheet]:
        """将 DataFrame 转为 ConfigSheet 索引"""
        if df.empty or len(df.columns) == 0:
            return None

        columns = [str(c) for c in df.columns]
        dtypes = {str(c): str(df[c].dtype) for c in df.columns}

        # 生成文本样例（前5行转为可读文本）
        sample_lines = []
        sample_lines.append(f"# 配置表: {file_name} / Sheet: {sheet_name}")
        sample_lines.append(f"# 列数: {len(columns)}, 行数: {len(df)}")
        sample_lines.append(f"# 列定义:")
        for col in columns:
            sample_vals = df[col].dropna().head(3).tolist()
            sample_lines.append(f"#   {col} ({dtypes.get(col, '?')}): {sample_vals}")
        sample_lines.append("")
        try:
            sample_lines.append(df.head(5).to_markdown(index=False))
        except Exception:
            sample_lines.append(df.head(5).to_string(index=False))

        sample_text = "\n".join(sample_lines)

        # 提取关键词
        keywords = set()
        # 文件名
        stem = Path(file_name).stem.lower()
        keywords.add(stem)
        for w in re.findall(r'[A-Z][a-z]+|[a-z]+', Path(file_name).stem):
            if len(w) > 2:
                keywords.add(w.lower())
        # sheet 名
        keywords.add(sheet_name.lower())
        # 列名
        for col in columns:
            keywords.add(col.lower())
            for w in re.findall(r'[A-Z][a-z]+|[a-z]+', col):
                if len(w) > 2:
                    keywords.add(w.lower())
        # 中文关键词
        for col in columns:
            for m in re.findall(r'[\u4e00-\u9fff]+', col):
                if len(m) >= 2:
                    keywords.add(m)

        return ConfigSheet(
            file_name=file_name, sheet_name=sheet_name,
            columns=columns, dtypes=dtypes, row_count=len(df),
            sample_text=sample_text, keywords=list(keywords)[:50],
        )

    # ========== 搜索 ==========

    def search(self, query: str, k: int = 10) -> list[dict]:
        """关键词搜索配置表"""
        results = []
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))
        # 中文也拆出来
        for m in re.findall(r'[\u4e00-\u9fff]+', query):
            query_words.add(m)

        for path, file_idx in self._file_indices.items():
            for sheet in file_idx.sheets:
                score = 0
                # 文件名匹配
                if query_lower in sheet.file_name.lower():
                    score += 60
                # sheet 名匹配
                if query_lower in sheet.sheet_name.lower():
                    score += 50
                # 列名精确匹配
                for col in sheet.columns:
                    if query_lower in col.lower():
                        score += 40
                        break
                # 关键词匹配
                matched = query_words & set(sheet.keywords)
                score += len(matched) * 20

                if score > 0:
                    results.append({
                        "file": sheet.file_name,
                        "sheet": sheet.sheet_name,
                        "path": path,
                        "columns": sheet.columns,
                        "row_count": sheet.row_count,
                        "sample_text": sheet.sample_text,
                        "score": score,
                    })

        results.sort(key=lambda x: -x["score"])
        return results[:k]

    def get_all_sheets(self) -> list[dict]:
        """获取所有配置表概览"""
        sheets = []
        for path, file_idx in sorted(self._file_indices.items()):
            for sheet in file_idx.sheets:
                sheets.append({
                    "file": sheet.file_name, "sheet": sheet.sheet_name,
                    "columns": len(sheet.columns), "rows": sheet.row_count,
                    "col_names": sheet.columns,
                })
        return sheets

    def get_sheet_detail(self, file_name: str, sheet_name: str) -> str:
        """获取指定 sheet 的详细文本"""
        for file_idx in self._file_indices.values():
            for sheet in file_idx.sheets:
                if sheet.file_name == file_name and sheet.sheet_name == sheet_name:
                    return sheet.sample_text
        return ""

    def get_stats(self) -> dict:
        total_sheets = sum(len(f.sheets) for f in self._file_indices.values())
        return {
            "files": len(self._file_indices),
            "sheets": total_sheets,
            "root_dir": self._root_dir or self.get_saved_dir(),
        }

    # ========== 持久化 ==========

    def _rebuild_sheet_map(self):
        self._sheet_map.clear()
        for file_idx in self._file_indices.values():
            for sheet in file_idx.sheets:
                for kw in sheet.keywords:
                    if kw not in self._sheet_map:
                        self._sheet_map[kw] = []
                    self._sheet_map[kw].append(sheet)

    def _save_index(self):
        data = {}
        for path, idx in self._file_indices.items():
            data[path] = {
                "path": idx.path, "file_name": idx.file_name, "mtime": idx.mtime,
                "sheets": [asdict(s) for s in idx.sheets],
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
                sheets = [ConfigSheet(**s) for s in info.get("sheets", [])]
                self._file_indices[path] = ConfigFileIndex(
                    path=info["path"], file_name=info["file_name"],
                    mtime=info.get("mtime", 0), sheets=sheets,
                )
            self._rebuild_sheet_map()
        except Exception:
            pass
        meta = self.index_dir / "meta.json"
        if meta.exists():
            try:
                self._root_dir = json.loads(meta.read_text(encoding="utf-8")).get("root_dir", "")
            except Exception:
                pass
