"""Excel 解析器 - 解析游戏配置表，学习配置结构"""
from pathlib import Path
import pandas as pd
from langchain_core.documents import Document


class ExcelParser:
    """解析 Excel 配置表，提取表结构和数据样例"""

    def parse_files(self, file_paths: list[str]) -> list[Document]:
        """解析多个 Excel 文件"""
        docs = []
        for fp in file_paths:
            docs.extend(self._parse_single(Path(fp)))
        return docs

    def _parse_single(self, file_path: Path) -> list[Document]:
        """解析单个 Excel 文件的所有 sheet"""
        docs = []
        try:
            xls = pd.ExcelFile(file_path)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                doc = self._dataframe_to_doc(df, file_path.name, sheet_name)
                if doc:
                    docs.append(doc)
        except Exception as e:
            docs.append(Document(
                page_content=f"解析失败: {file_path.name} - {str(e)}",
                metadata={"source": file_path.name, "category": "excel_error"},
            ))
        return docs

    def _dataframe_to_doc(self, df: pd.DataFrame, filename: str, sheet: str) -> Document | None:
        """将 DataFrame 转为文档"""
        if df.empty:
            return None
        # 提取列信息
        columns_info = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            sample_values = df[col].dropna().head(3).tolist()
            columns_info.append(f"  - {col} (类型: {dtype}, 示例: {sample_values})")

        # 构建描述
        content = f"""# Excel配置表: {filename} / Sheet: {sheet}
## 表结构
- 总行数: {len(df)}
- 总列数: {len(df.columns)}
- 列定义:
{chr(10).join(columns_info)}

## 数据样例 (前5行)
{df.head(5).to_markdown(index=False)}

## 配置表分析
该配置表包含 {len(df.columns)} 个字段，{len(df)} 条数据记录。
字段名列表: {list(df.columns)}
"""
        return Document(
            page_content=content,
            metadata={
                "source": filename,
                "sheet": sheet,
                "category": "excel_config",
                "columns": list(df.columns),
                "row_count": len(df),
            },
        )

    def to_markdown(self, file_path: str) -> str:
        """将 Excel 转为 Markdown 格式"""
        result = []
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            result.append(f"## Sheet: {sheet_name}\n")
            result.append(df.to_markdown(index=False))
            result.append("\n")
        return "\n".join(result)
