"""页面6: Skill 管理 - 左侧对话生成，右侧 Skill 列表"""
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.core.llm_settings import get_llm_config
from app.core.skill_manager import (
    SkillManager, Skill, _collect_project_context,
    parse_skill_json_from_response, save_skills_from_json,
)

CAT_LABELS = {
    "protocol": "🔌 协议相关",
    "business": "⚙️ 业务逻辑",
    "config": "📊 配置相关",
    "framework": "🏗️ 框架相关",
    "custom": "🎨 自定义",
}
CAT_OPTIONS = list(CAT_LABELS.keys())


def _build_system_prompt(project_name: str, modules: list[str]) -> str:
    mgr = SkillManager(project_name)
    existing_skills = mgr.list_skills()
    project_ctx = _collect_project_context(project_name, modules or None)

    # 已有 Skill
    skills_desc = ""
    if existing_skills:
        parts = []
        for s in existing_skills:
            parts.append(f"- {s.name} [{s.category}]: {s.description}")
        skills_desc = "当前已有的 Skill:\n" + "\n".join(parts)

    # AI 学习的经验
    from app.core.experience_manager import ExperienceManager
    exp_mgr = ExperienceManager(project_name)
    experience_ctx = exp_mgr.get_all_summaries()
    experience_section = ""
    if experience_ctx:
        experience_section = f"""
## AI 学习的开发经验（生成 Skill 时必须参考这些经验）
{experience_ctx[:3000]}
"""

    return f"""你是一个游戏服务器开发专家，负责管理代码生成 Skill 模板。

## 项目代码上下文
{project_ctx[:4000]}
{experience_section}
{skills_desc}

你的职责：
1. 理解用户意图：判断用户是要「全部重新生成」还是「修改某几个 Skill」
2. 如果用户要全部重新生成，输出所有 Skill 的 JSON 数组
3. 如果用户要修改某个/某几个 Skill，只输出需要修改的 Skill 的 JSON 数组
4. 如果用户只是在讨论或提问，正常回复即可

重要规则：
- 如果项目代码上下文为空或信息不足，你必须要求用户先完成「加载框架代码」构建代码索引
- 如果用户没有选择参考模块，你必须提醒用户先选择参考模块
- 如果用户的请求缺少关键信息，你必须主动追问
- 不要在信息不足时凭空编造模板

当需要输出 Skill 时，使用 ```json 代码块：
```json
[{{"name": "skill名", "description": "描述", "category": "protocol/business/config/custom",
   "template": "模板内容，用 {{{{var}}}} 作为变量", "variables": ["var1"]}}]
```

常见 Skill 类型：protocol_code, controller_entry, business_service, data_table_loader, db_dao, data_table_create"""


def render():
    st.header("🧩 Skill 管理")

    project_name = st.session_state.get("project_name", "default")
    mgr = SkillManager(project_name)

    if "skill_messages" not in st.session_state:
        st.session_state["skill_messages"] = []

    # 模块选择
    from app.core.code_index import CodeIndex
    code_idx = CodeIndex(project_name)
    available_modules = code_idx.get_stats().get("module_list", [])

    selected_modules = st.multiselect(
        "参考模块",
        options=available_modules,
        default=available_modules[:5] if len(available_modules) > 5 else available_modules,
        key="skill_ref_modules",
    ) if available_modules else []

    st.divider()

    # ========== 左右布局：左边对话，右边 Skill 列表 ==========
    col_chat, col_skills = st.columns([3, 2])

    with col_chat:
        st.subheader("💬 对话生成 Skill")

        # 对话历史
        chat_container = st.container(height=450)
        with chat_container:
            for i, msg in enumerate(st.session_state["skill_messages"]):
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg["role"] == "assistant" and "saved_skills" in msg:
                        saved = msg["saved_skills"]
                        st.success(f"✅ 已保存 {len(saved)} 个: {', '.join(s['name'] for s in saved)}")

        # 输入
        if prompt := st.chat_input("如「全部重新生成」「修改 controller_entry」...", key="skill_chat"):
            # 显示用户消息
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
            st.session_state["skill_messages"].append({"role": "user", "content": prompt})

            # 构建 LLM 消息
            cfg = get_llm_config()
            if not cfg["api_key"]:
                st.error("⚠️ 请先在侧边栏配置大模型 API Key")
            else:
                try:
                    llm = ChatOpenAI(
                        model=cfg["model"], openai_api_key=cfg["api_key"],
                        openai_api_base=cfg["base_url"], temperature=0.1, streaming=True,
                    )
                    sys_prompt = _build_system_prompt(project_name, selected_modules)
                    messages = [SystemMessage(content=sys_prompt)]
                    for msg in st.session_state["skill_messages"][-16:]:
                        if msg["role"] == "user":
                            messages.append(HumanMessage(content=msg["content"]))
                        else:
                            messages.append(AIMessage(content=msg["content"]))

                    # 流式输出
                    with chat_container:
                        with st.chat_message("assistant"):
                            placeholder = st.empty()
                            full_response = ""
                            for chunk in llm.stream(messages):
                                if chunk.content:
                                    full_response += chunk.content
                                    placeholder.markdown(full_response + "▌")
                            placeholder.markdown(full_response)

                    # 检查并保存 JSON Skill
                    msg_data = {"role": "assistant", "content": full_response}
                    items = parse_skill_json_from_response(full_response)
                    if items:
                        saved = save_skills_from_json(project_name, items)
                        if saved:
                            msg_data["saved_skills"] = [{"name": s.name} for s in saved]
                            st.success(f"✅ 已保存 {len(saved)} 个 Skill")

                    st.session_state["skill_messages"].append(msg_data)
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ 调用大模型出错: {str(e)}")

        # 清空对话
        if st.button("🗑️ 清空对话", key="clear_skill_chat"):
            st.session_state["skill_messages"] = []
            st.rerun()

    with col_skills:
        st.subheader("📋 已有 Skill")
        skills = mgr.list_skills()
        if not skills:
            st.info("暂无 Skill，通过左侧对话生成")
        else:
            for skill in skills:
                source_badge = "🤖" if skill.source == "auto_generated" else "✏️"
                with st.expander(f"{source_badge} {skill.name} — {skill.description}"):
                    with st.form(key=f"edit_{skill.name}"):
                        desc = st.text_input("描述", value=skill.description, key=f"d_{skill.name}")
                        cat_idx = CAT_OPTIONS.index(skill.category) if skill.category in CAT_OPTIONS else 0
                        cat = st.selectbox("类别", CAT_OPTIONS, index=cat_idx, key=f"c_{skill.name}",
                                           format_func=lambda x: CAT_LABELS.get(x, x))
                        tpl = st.text_area("模板", value=skill.template, height=180, key=f"t_{skill.name}")
                        vrs = st.text_input("变量", value=", ".join(skill.variables), key=f"v_{skill.name}")

                        c1, c2 = st.columns([3, 1])
                        with c1:
                            save_ok = st.form_submit_button("💾 保存", use_container_width=True, type="primary")
                        with c2:
                            del_ok = st.form_submit_button("🗑️", use_container_width=True)

                    if save_ok:
                        mgr.save_skill(Skill(
                            name=skill.name, description=desc, category=cat, template=tpl,
                            variables=[v.strip() for v in vrs.split(",") if v.strip()], source="manual",
                        ))
                        st.rerun()
                    if del_ok:
                        mgr.delete_skill(skill.name)
                        st.rerun()


