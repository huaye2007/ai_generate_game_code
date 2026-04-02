"""页面7: AI 学习 - 学习模块代码 + 对话生成综合总结"""
import streamlit as st
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.core.llm_settings import get_llm_config
from app.core.code_index import CodeIndex, CodeSymbol
from app.core.experience_manager import ExperienceManager, Experience
from app.config import CODE_EXTENSIONS


def _read_module_code(code_dir: str, module_path: str, max_files: int = 20) -> str:
    root = Path(code_dir) / module_path
    if not root.is_dir():
        root = Path(module_path)
    if not root.is_dir():
        return ""
    parts = []
    count = 0
    for f in sorted(root.rglob("*")):
        if f.is_file() and f.suffix in CODE_EXTENSIONS and count < max_files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                rel = f.relative_to(root)
                parts.append(f"### {rel}\n```\n{content[:2000]}\n```")
                count += 1
            except Exception:
                pass
    return "\n\n".join(parts)


def _build_summary_system_prompt(project_name: str) -> str:
    """构建综合总结对话的 system prompt"""
    exp_mgr = ExperienceManager(project_name)
    experiences = exp_mgr.list_experiences()
    combined = exp_mgr.get_combined_summary()

    exp_text = ""
    if experiences:
        parts = []
        for e in experiences:
            parts.append(f"## 模块: {e.name}\n{e.summary[:2000]}")
        exp_text = "\n\n".join(parts)

    current_summary = ""
    if combined:
        current_summary = f"\n\n## 当前综合总结（用户可能要求在此基础上修改）\n{combined}"

    return f"""你是一个游戏服务器开发专家。你的任务是根据已学习的各业务模块开发经验，生成或更新一份综合的游戏服务器业务开发经验总结。

## 已学习的模块经验
{exp_text if exp_text else "（尚未学习任何模块）"}
{current_summary}

## 综合总结应包含
1. 通用架构模式（分层结构、类的职责划分）
2. 命名规范（类名、方法名、变量名）
3. 数据库操作规范（ORM 用法、事务、缓存）
4. 协议处理规范（请求/响应流程）
5. 配置表使用规范（加载和使用方式）
6. 业务逻辑编写规范（校验、流程、错误处理）
7. 其他项目特有的开发规范

## 规则
- 讨论时正常回复
- 当用户要求生成或更新综合总结时，输出完整的 Markdown 文档
- 修改时只更新改动部分，保留其余内容
- 总结必须基于实际学习到的模块经验，不要凭空编造"""


def render():
    st.header("🧠 AI 学习")

    project_name = st.session_state.get("project_name", "default")
    exp_mgr = ExperienceManager(project_name)
    code_idx = CodeIndex(project_name)
    stats = code_idx.get_stats()

    if "learn_messages" not in st.session_state:
        st.session_state["learn_messages"] = []

    # ========== 三栏布局：学习 | 对话 | 经验列表 ==========
    col_learn, col_chat, col_exp = st.columns([2, 3, 2])

    # ========== 左栏：学习新模块 ==========
    with col_learn:
        st.subheader("📚 学习模块")

        code_dir = stats.get("root_dir", "") or st.session_state.get("code_dir", "")
        if not code_dir or stats["files"] == 0:
            st.warning("请先在「加载框架代码」中构建索引")
        else:
            modules = stats.get("module_list", [])
            selected = st.multiselect("选择模块", modules, key="learn_modules")
            custom_dir = st.text_input("或输入目录", placeholder="自定义代码目录", key="learn_custom")

            if st.button("🧠 开始学习", type="primary", use_container_width=True,
                          disabled=(not selected and not custom_dir)):
                cfg = get_llm_config()
                if not cfg["api_key"]:
                    st.error("⚠️ 请先配置 API Key")
                else:
                    all_code = ""
                    learn_name = ""
                    if selected:
                        code_parts = []
                        for mod in selected:
                            mc = _read_module_code(code_dir, mod)
                            if mc:
                                code_parts.append(f"## 模块: {mod}\n{mc}")
                        all_code = "\n\n".join(code_parts)
                        learn_name = "_".join(selected[:3])
                    elif custom_dir:
                        all_code = _read_module_code("", custom_dir)
                        learn_name = Path(custom_dir).name

                    if not all_code:
                        st.error("未读取到代码")
                    else:
                        try:
                            llm = ChatOpenAI(model=cfg["model"], openai_api_key=cfg["api_key"],
                                             openai_api_base=cfg["base_url"], temperature=0.1, streaming=True)
                            placeholder = st.empty()
                            full = ""
                            for chunk in llm.stream([
                                SystemMessage(content="你是游戏服务器开发专家。阅读代码后总结开发经验：架构模式、命名规范、数据库操作、协议处理、配置表使用、业务逻辑、错误处理。用 Markdown 输出。"),
                                HumanMessage(content=all_code[:15000]),
                            ]):
                                if chunk.content:
                                    full += chunk.content
                                    placeholder.markdown(full[:500] + "▌")
                            placeholder.markdown(f"✅ 已学习 {learn_name}")

                            exp_mgr.save_experience(Experience(
                                name=learn_name, source_dir=custom_dir or code_dir,
                                summary=full, file_count=all_code.count("###"),
                            ))
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {str(e)}")

        # 已学习的模块列表
        st.divider()
        experiences = exp_mgr.list_experiences()
        if experiences:
            st.caption(f"已学习 {len(experiences)} 个模块")
            for exp in experiences:
                with st.expander(f"🧠 {exp.name}"):
                    st.markdown(exp.summary[:800])
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🔄", key=f"re_{exp.name}"):
                            exp_mgr.delete_experience(exp.name)
                            st.rerun()
                    with c2:
                        if st.button("🗑️", key=f"del_{exp.name}"):
                            exp_mgr.delete_experience(exp.name)
                            st.rerun()

    # ========== 中栏：对话生成综合总结 ==========
    with col_chat:
        st.subheader("💬 综合总结对话")

        # 当前综合总结预览
        combined = exp_mgr.get_combined_summary()
        if combined:
            with st.expander("⭐ 当前综合总结", expanded=False):
                st.markdown(combined[:2000])

        # 对话历史
        chat_container = st.container(height=400)
        with chat_container:
            for msg in st.session_state["learn_messages"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        # 对话输入
        if prompt := st.chat_input("如「生成综合总结」「补充错误处理规范」...", key="learn_chat"):
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
            st.session_state["learn_messages"].append({"role": "user", "content": prompt})

            cfg = get_llm_config()
            if not cfg["api_key"]:
                st.error("⚠️ 请先配置 API Key")
            else:
                try:
                    llm = ChatOpenAI(model=cfg["model"], openai_api_key=cfg["api_key"],
                                     openai_api_base=cfg["base_url"], temperature=0.2, streaming=True)

                    sys_prompt = _build_summary_system_prompt(project_name)
                    messages = [SystemMessage(content=sys_prompt)]
                    for msg in st.session_state["learn_messages"][-16:]:
                        if msg["role"] == "user":
                            messages.append(HumanMessage(content=msg["content"]))
                        else:
                            messages.append(AIMessage(content=msg["content"]))

                    with chat_container:
                        with st.chat_message("assistant"):
                            placeholder = st.empty()
                            full_response = ""
                            for chunk in llm.stream(messages):
                                if chunk.content:
                                    full_response += chunk.content
                                    placeholder.markdown(full_response + "▌")
                            placeholder.markdown(full_response)

                    st.session_state["learn_messages"].append({"role": "assistant", "content": full_response})

                    # 自动保存：如果回复是文档格式（综合总结）
                    if full_response.count("#") >= 3 and len(full_response) > 300:
                        exp_mgr.save_combined_summary(full_response)
                        st.toast("✅ 综合总结已自动保存")

                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {str(e)}")

        if st.button("🗑️ 清空对话", key="clear_learn_chat"):
            st.session_state["learn_messages"] = []
            st.rerun()

    # ========== 右栏：综合总结完整内容 ==========
    with col_exp:
        st.subheader("📝 综合总结")
        combined = exp_mgr.get_combined_summary()
        if combined:
            st.markdown(combined[:5000])
            if len(combined) > 5000:
                st.caption(f"... 共 {len(combined)} 字符")
            st.download_button("📥 下载", combined, file_name="development_experience.md", mime="text/markdown")
        else:
            st.info("通过中间的对话生成综合总结，如输入「生成综合总结」")
