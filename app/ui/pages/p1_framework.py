"""页面1: 加载框架代码 - 轻量索引，自动检测变化，支持搜索"""
import streamlit as st
from pathlib import Path
from app.core.code_index import CodeIndex


def render():
    st.header("🏗️ 加载框架代码")
    st.caption("基于关键词 + AST 结构解析，秒级完成，自动检测文件变化")

    project_name = st.session_state.get("project_name", "default")
    idx = CodeIndex(project_name)

    # 读取上次保存的路径
    saved_dir = idx.get_saved_dir()
    if "code_dir" not in st.session_state and saved_dir:
        st.session_state["code_dir"] = saved_dir

    # 目录输入
    code_dir = st.text_input(
        "游戏服务器代码目录",
        key="code_dir",
        placeholder=r"输入代码目录路径，如 D:\game-server\src",
    )

    if code_dir and not Path(code_dir).is_dir():
        st.warning(f"⚠️ 目录不存在: {code_dir}")
        return

    # 构建索引 + 变化检测
    if code_dir:
        col1, col2 = st.columns([3, 1])
        with col1:
            stats = idx.get_stats()
            if stats["files"] > 0:
                has_changes = idx.check_changes()
                if has_changes:
                    st.warning("⚡ 检测到文件变化，建议重新构建索引")
                else:
                    st.success("✅ 索引已是最新")
            else:
                st.info("💡 首次使用，请点击构建索引")
        with col2:
            if st.button("⚡ 构建索引", use_container_width=True, type="primary"):
                progress = st.progress(0, text="正在索引代码文件...")

                def on_progress(current, total):
                    progress.progress(current / total if total > 0 else 1.0,
                                      text=f"索引中... {current}/{total}")

                count = idx.build_index(code_dir, on_progress=on_progress)
                progress.progress(1.0, text="✅ 索引完成")
                stats = idx.get_stats()
                st.success(f"索引完成: {stats['files']} 文件, {stats['symbols']} 符号, {stats['modules']} 模块")
                st.rerun()

    st.divider()

    # ========== 索引状态 + 搜索 ==========
    stats = idx.get_stats()
    if stats["files"] == 0:
        st.info("💡 请输入代码目录并点击「构建索引」")
        return

    st.info(f"📊 代码索引: {stats['files']} 文件 / {stats['symbols']} 符号 / {stats['modules']} 模块")

    # 模块概览
    with st.expander("📁 模块列表"):
        for mod in stats["module_list"]:
            mod_files = sum(1 for f in idx._file_indices.values() if f.module == mod)
            mod_syms = sum(len(f.symbols) for f in idx._file_indices.values() if f.module == mod)
            st.text(f"  📁 {mod} — {mod_files} 文件, {mod_syms} 符号")

    # 搜索
    st.subheader("🔍 代码搜索")
    query = st.text_input("搜索关键词", placeholder="输入类名、方法名、模块名...", key="code_search")

    if query:
        results = idx.search(query, k=15)
        if not results:
            st.warning(f"未找到与「{query}」相关的代码")
        else:
            st.caption(f"找到 {len(results)} 条结果")
            for r in results:
                if r["type"] == "symbol":
                    kind_icon = {"class": "🔷", "interface": "🔶", "enum": "📋",
                                 "method": "⚙️", "function": "🔧"}.get(r["kind"], "🔹")
                    parent = f" (in {r['parent']})" if r.get("parent") else ""
                    with st.expander(f"{kind_icon} [{r['kind']}] {r['name']}{parent} — {r['file']}:{r['line']}"):
                        st.code(r["signature"])
                        from app.core.code_index import CodeSymbol
                        sym = CodeSymbol(name=r["name"], kind=r["kind"], file_path=r["file"],
                                         line_start=r["line"], signature=r["signature"], parent=r.get("parent", ""))
                        ctx = idx.get_symbol_context(sym, context_lines=30)
                        if ctx:
                            st.code(ctx, language=_guess_lang(r["file"]))
                else:
                    with st.expander(f"📄 {r['file']} ({r['module']}, {r['symbols_count']} 符号)"):
                        content = idx.get_file_content(r["file"])
                        if content:
                            st.code(content[:2000], language=_guess_lang(r["file"]))


def _guess_lang(file_path: str) -> str:
    ext_map = {
        ".java": "java", ".kt": "kotlin", ".go": "go", ".py": "python",
        ".ts": "typescript", ".js": "javascript", ".cs": "csharp",
        ".cpp": "cpp", ".h": "cpp", ".lua": "lua",
    }
    return ext_map.get(Path(file_path).suffix, "text")
