"""Game AI Workflow - 主入口"""
import streamlit as st

st.set_page_config(
    page_title="🎮 游戏服务器业务代码开发",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.dialog("⚙️ 大模型设置", width="large")
def _open_llm_dialog():
    from app.core.llm_settings import PROVIDERS, load_settings, save_settings
    settings = load_settings()

    provider_keys = list(PROVIDERS.keys())
    current_idx = provider_keys.index(settings["provider"]) if settings["provider"] in provider_keys else 0

    provider = st.selectbox("提供商", provider_keys, index=current_idx,
                             format_func=lambda k: PROVIDERS[k]["name"], key="dlg_provider")
    provider_info = PROVIDERS[provider]

    api_key = st.text_input("API Key", value=settings["api_key"], type="password", key="dlg_api_key")

    if provider == "custom":
        base_url = st.text_input("Base URL", value=settings["base_url"], key="dlg_base_url",
                                  placeholder="https://your-api.com/v1")
        model = st.text_input("模型名称", value=settings["model"], key="dlg_model_input")
    else:
        base_url = provider_info["base_url"]
        models = provider_info["models"]
        current_model = settings["model"] if settings["model"] in models else provider_info["default_model"]
        model_idx = models.index(current_model) if current_model in models else 0
        model = st.selectbox("模型", models, index=model_idx, key="dlg_model_select")

    if not api_key:
        st.warning("⚠️ 请填入 API Key")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 保存", use_container_width=True, type="primary"):
            save_settings(provider, api_key, base_url, model)
            st.rerun()
    with col2:
        if st.button("取消", use_container_width=True):
            st.rerun()


def main():
    # 侧边栏
    with st.sidebar:
        st.title("🎮 游戏服务器业务代码开发")
        st.caption("游戏服务器业务代码开发工具")

        st.divider()

        # 项目选择
        project_name = st.text_input("项目名称", value="my_game", key="project_name_input")
        if project_name != st.session_state.get("project_name", ""):
            st.session_state["project_name"] = project_name

        if "project_name" not in st.session_state:
            st.session_state["project_name"] = project_name

        st.divider()

        # 导航
        page = st.radio(
            "功能模块",
            [
                "🏗️ 加载框架代码",
                "📊 加载配置表",
                "🔌 加载协议",
                "📝 需求文档生成",
                "🧠 AI 学习",
                "🧩 Skill 管理",
            ],
            key="nav_page",
        )

        st.divider()

        # LLM 设置按钮
        from app.core.llm_settings import load_settings
        settings = load_settings()
        provider_label = settings.get("model", "未配置")
        has_key = bool(settings.get("api_key"))
        status = f"✅ {provider_label}" if has_key else "⚠️ 未配置"
        if st.button(f"⚙️ 大模型设置 ({status})", use_container_width=True):
            _open_llm_dialog()

        st.caption("v0.1.0")

    # 页面路由
    if page == "🏗️ 加载框架代码":
        from app.ui.pages.p1_framework import render
        render()
    elif page == "📊 加载配置表":
        from app.ui.pages.p2_config import render
        render()
    elif page == "🔌 加载协议":
        from app.ui.pages.p4_protocol import render
        render()
    elif page == "📝 需求文档生成":
        from app.ui.pages.p3_docs import render
        render()
    elif page == "🧠 AI 学习":
        from app.ui.pages.p7_learning import render
        render()
    elif page == "🧩 Skill 管理":
        from app.ui.pages.p6_skills import render
        render()


if __name__ == "__main__":
    main()
