"""页面2: 加载配置表 - 轻量索引，自动检测变化，支持搜索"""
import streamlit as st
from pathlib import Path
from app.core.config_index import ConfigIndex


def render():
    st.header("📊 加载配置表")
    st.caption("监控目录下 Excel 文件变化，自动构建索引，支持关键词搜索")

    project_name = st.session_state.get("project_name", "default")
    idx = ConfigIndex(project_name)

    # 读取上次保存的路径
    saved_dir = idx.get_saved_dir()
    if "config_dir" not in st.session_state and saved_dir:
        st.session_state["config_dir"] = saved_dir

    # 目录输入
    config_dir = st.text_input(
        "配置表目录",
        key="config_dir",
        placeholder=r"输入 Excel 配置表所在目录，如 D:\game-server\config",
    )

    if config_dir and not Path(config_dir).is_dir():
        st.warning(f"⚠️ 目录不存在: {config_dir}")
        return

    # 构建索引 + 变化检测
    if config_dir:
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
                progress = st.progress(0, text="正在索引配置表...")

                def on_progress(current, total):
                    progress.progress(current / total if total > 0 else 1.0,
                                      text=f"索引中... {current}/{total}")

                count = idx.build_index(config_dir, on_progress=on_progress)
                progress.progress(1.0, text="✅ 索引完成")
                stats = idx.get_stats()
                st.success(f"索引完成: {stats['files']} 个文件, {stats['sheets']} 个 Sheet")
                st.rerun()

    st.divider()

    # ========== 索引状态 + 搜索 ==========
    stats = idx.get_stats()
    if stats["files"] == 0:
        st.info("💡 请输入配置表目录并点击「构建索引」")
        return

    st.info(f"📊 配置表索引: {stats['files']} 个文件, {stats['sheets']} 个 Sheet")

    # 配置表概览
    all_sheets = idx.get_all_sheets()
    with st.expander(f"📁 配置表列表 ({len(all_sheets)} 个)"):
        for s in all_sheets:
            cols_preview = ", ".join(s["col_names"][:6])
            if len(s["col_names"]) > 6:
                cols_preview += f" ... (+{len(s['col_names']) - 6})"
            st.text(f"  📄 {s['file']} / {s['sheet']} — {s['rows']}行 {s['columns']}列 [{cols_preview}]")

    # 搜索
    st.subheader("🔍 配置表搜索")
    query = st.text_input("搜索关键词", placeholder="输入表名、列名、如 item、reward、等级...", key="config_search")

    if query:
        results = idx.search(query, k=10)
        if not results:
            st.warning(f"未找到与「{query}」相关的配置表")
        else:
            st.caption(f"找到 {len(results)} 条结果")
            for i, r in enumerate(results):
                cols_str = ", ".join(r["columns"][:8])
                if len(r["columns"]) > 8:
                    cols_str += f" ..."
                with st.expander(
                    f"📊 {r['file']} / {r['sheet']} — {r['row_count']}行 [{cols_str}]",
                    expanded=(i == 0),
                ):
                    st.markdown(r["sample_text"])
