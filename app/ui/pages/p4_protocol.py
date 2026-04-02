"""页面4: 加载协议 - 轻量索引，支持关键词搜索，自动检测文件变化"""
import streamlit as st
from pathlib import Path
from app.core.protocol_index import ProtocolIndex


def render():
    st.header("🔌 加载协议")
    st.caption("基于关键词 + 结构解析，秒级完成，自动检测文件变化")

    project_name = st.session_state.get("project_name", "default")
    idx = ProtocolIndex(project_name)

    # 读取上次保存的路径作为默认值
    saved_dir = idx.get_saved_dir()
    if "proto_dir" not in st.session_state and saved_dir:
        st.session_state["proto_dir"] = saved_dir

    # 目录输入（保留上次路径）
    proto_dir = st.text_input(
        "协议文件目录",
        key="proto_dir",
        placeholder=r"输入协议文件所在目录，如 D:\game-server\proto",
    )

    if proto_dir and not Path(proto_dir).is_dir():
        st.warning(f"⚠️ 目录不存在: {proto_dir}")
        return

    # 构建索引按钮 + 自动检测变化
    if proto_dir:
        col1, col2 = st.columns([3, 1])
        with col1:
            has_changes = idx.check_changes() if idx.get_stats()["files"] > 0 else True
            if has_changes:
                st.warning("⚡ 检测到文件变化，建议重新构建索引")
            else:
                st.success(f"✅ 索引已是最新")
        with col2:
            if st.button("⚡ 构建索引", use_container_width=True, type="primary"):
                progress = st.progress(0, text="正在索引协议文件...")

                def on_progress(current, total):
                    progress.progress(current / total if total > 0 else 1.0,
                                      text=f"索引中... {current}/{total}")

                count = idx.build_index(proto_dir, on_progress=on_progress)
                progress.progress(1.0, text="✅ 索引完成")
                stats = idx.get_stats()
                st.success(f"索引完成: {stats['files']} 个文件, {stats['symbols']} 个符号")
                st.rerun()

    st.divider()

    # ========== 索引状态 + 搜索 ==========
    stats = idx.get_stats()
    if stats["files"] == 0:
        st.info("💡 请输入协议文件目录并点击「构建索引」")
        return

    st.info(f"📊 协议索引: {stats['files']} 个文件, {stats['symbols']} 个符号")

    st.subheader("🔍 协议搜索")
    query = st.text_input("搜索关键词", placeholder="输入 message 名、rpc 名、字段名...", key="proto_search")

    if query:
        results = idx.search(query, k=15)
        if not results:
            st.warning(f"未找到与「{query}」相关的协议")
        else:
            st.caption(f"找到 {len(results)} 条结果")

            for r in results:
                if r["type"] == "symbol":
                    kind_icon = {"message": "📦", "service": "🔧", "enum": "📋",
                                 "rpc": "📡", "field": "📎", "element": "🏷️"}.get(r["kind"], "🔹")
                    parent_info = f" (in {r['parent']})" if r.get("parent") else ""
                    with st.expander(f"{kind_icon} [{r['kind']}] {r['name']}{parent_info} — {r['file']}:{r['line']}"):
                        st.code(r["content"])
                        # 显示文件完整内容
                        if st.button(f"查看完整文件", key=f"view_{r['file']}_{r['line']}"):
                            content = idx.get_file_content(r["file"])
                            if content:
                                st.code(content, language=_guess_lang(r["file"]))
                else:
                    with st.expander(f"📄 {r['file']} ({r['format']}, {r['symbols_count']} 个符号)"):
                        content = idx.get_file_content(r["file"])
                        if content:
                            st.code(content[:2000], language=_guess_lang(r["file"]))
    else:
        # 没有搜索时，显示文件列表概览
        st.subheader("📁 协议文件列表")
        for path, file_idx in sorted(idx._file_indices.items()):
            sym_count = len(file_idx.symbols)
            msgs = [s for s in file_idx.symbols if s.kind in ("message", "service", "enum")]
            summary = ", ".join(s.name for s in msgs[:5])
            if len(msgs) > 5:
                summary += f" ... (+{len(msgs) - 5})"
            with st.expander(f"📄 {path} — {sym_count} 个符号"):
                if summary:
                    st.caption(f"主要定义: {summary}")
                content = idx.get_file_content(path)
                if content:
                    st.code(content[:2000], language=_guess_lang(path))


def _guess_lang(file_path: str) -> str:
    ext_map = {".proto": "protobuf", ".json": "json", ".yaml": "yaml",
               ".yml": "yaml", ".xml": "xml", ".thrift": "thrift"}
    return ext_map.get(Path(file_path).suffix.lower(), "text")
