"""可复用的 UI 组件 - 基于本地文件系统"""
import os
import streamlit as st
from pathlib import Path


def directory_input(label: str, key: str) -> str:
    """目录路径输入组件"""
    path = st.text_input(label, key=key, placeholder=r"输入本地目录路径，如 D:\game-server\src")
    if path and not Path(path).exists():
        st.warning(f"⚠️ 目录不存在: {path}")
    return path


def directory_browser(label: str, key: str, root: str = "") -> str:
    """目录浏览器 - 输入路径后可展开浏览子目录"""
    path = st.text_input(label, value=root, key=key, placeholder=r"输入目录路径")
    if not path or not Path(path).is_dir():
        return path

    # 显示子目录列表，方便用户确认
    try:
        items = sorted(Path(path).iterdir())
        dirs = [p for p in items if p.is_dir() and not p.name.startswith(".")]
        files_count = sum(1 for p in items if p.is_file())
        st.caption(f"📁 {len(dirs)} 个子目录, 📄 {files_count} 个文件")
        if dirs:
            with st.expander("查看子目录", expanded=False):
                for d in dirs[:30]:
                    st.text(f"  📁 {d.name}")
    except PermissionError:
        st.warning("⚠️ 无权限访问该目录")
    return path


def file_picker(label: str, key: str, extensions: list[str] = None, base_dir: str = "") -> list[str]:
    """本地文件选择器 - 输入目录后列出文件供勾选"""
    dir_path = st.text_input(f"{label} - 文件所在目录", value=base_dir, key=f"{key}_dir",
                              placeholder=r"输入文件所在目录路径")
    if not dir_path or not Path(dir_path).is_dir():
        return []

    # 扫描目录下的匹配文件
    target_dir = Path(dir_path)
    all_files = []
    try:
        for f in sorted(target_dir.rglob("*")):
            if not f.is_file():
                continue
            if extensions:
                if f.suffix.lstrip(".").lower() in [e.lower() for e in extensions]:
                    all_files.append(f)
            else:
                all_files.append(f)
    except PermissionError:
        st.warning("⚠️ 无权限访问部分目录")

    if not all_files:
        st.info("该目录下没有找到匹配的文件")
        return []

    # 限制显示数量
    display_files = all_files[:200]
    if len(all_files) > 200:
        st.warning(f"文件过多，仅显示前 200 个（共 {len(all_files)} 个）")

    st.caption(f"找到 {len(display_files)} 个文件")

    # 生成每个文件的 checkbox key
    file_keys = []
    for f in display_files:
        rel = f.relative_to(target_dir)
        file_keys.append((f, str(rel), f"{key}_{rel}"))

    # 全选/取消全选 — 点击时主动更新所有文件的 session_state
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("✅ 全选", key=f"{key}_select_all"):
            for _, _, fk in file_keys:
                st.session_state[fk] = True
            st.rerun()
    with col2:
        if st.button("❎ 取消全选", key=f"{key}_deselect_all"):
            for _, _, fk in file_keys:
                st.session_state[fk] = False
            st.rerun()

    # 文件列表勾选
    selected = []
    with st.expander(f"选择文件 ({len(display_files)} 个)", expanded=True):
        for f, rel, fk in file_keys:
            if st.checkbox(rel, key=fk):
                selected.append(str(f))

    return selected


def step_checkbox(steps: dict[str, str], default_on: list[str] = None) -> list[str]:
    """工作流步骤选择器"""
    if default_on is None:
        default_on = list(steps.keys())
    selected = []
    cols = st.columns(3)
    for i, (key, label) in enumerate(steps.items()):
        with cols[i % 3]:
            if st.checkbox(label, value=key in default_on, key=f"step_{key}"):
                selected.append(key)
    return selected
