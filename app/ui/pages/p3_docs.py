"""页面3: 需求文档生成 - 对话式，自动保存，自动标题"""
import json
import re
from datetime import datetime
import streamlit as st
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.core.llm_settings import get_llm_config
from app.config import DATA_DIR
from app.core.parsers.doc_parser import DocParser
from app.core.parsers.excel_parser import ExcelParser

REQUIREMENTS_DIR = DATA_DIR / "requirements"
REQUIREMENTS_DIR.mkdir(parents=True, exist_ok=True)


def _get_system_prompt(project_name: str, project_context: str, saved_doc: str = "") -> str:
    skills_info, skills_rules = _collect_skills_context(project_name)
    experience_info = _collect_experience_context(project_name)

    base = f"""你是一个资深游戏策划和服务器开发专家。根据用户描述生成或修改游戏功能需求文档。

## 项目相关代码/配置/协议（根据用户需求动态检索）
{project_context}

## AI 学习的开发经验（必须参考这些经验来设计）
{experience_info}

## Skill 模板（需求文档必须遵循这些规范）
{skills_info}

## 文档格式（Markdown）
1. 功能概述  2. 功能详细描述  3. 数据结构设计（遵循对应 Skill 代码风格和开发经验）
4. 接口设计（遵循对应协议 Skill）  5. 业务流程  6. 异常处理
7. 配置表需求（遵循对应配置表 Skill）  8. 测试要点

## 规则
{skills_rules}
- 必须参考 AI 学习的开发经验中的架构模式、命名规范、业务处理流程
- 讨论时正常回复，要求生成文档时输出完整 Markdown
- 修改时只更新改动部分，保留其余内容
- 需求文档中涉及的每个技术设计，都必须找到对应类别的 Skill 并严格遵循其模板规范

## Skill 自动修正
当用户指出代码格式、风格、规范有问题时（如"Controller 不应该这样写"、"数据库注解格式不对"、"协议定义方式错了"），你需要：
1. 先修正需求文档中的相关内容
2. 然后在回复末尾追加一个 ```skill_update 代码块，包含需要修改的 Skill JSON：
```skill_update
[{{"name": "要修改的skill名", "description": "更新后的描述", "category": "类别", "template": "修正后的模板", "variables": ["var1"]}}]
```
这样对应的 Skill 会被自动更新，后续生成的文档就会遵循新的规范。
只有用户明确指出格式/风格问题时才输出 skill_update 块，正常对话不要输出。"""
    if saved_doc:
        base += f"\n\n## 当前文档（在此基础上修改）\n{saved_doc}"
    return base


def _collect_experience_context(project_name: str) -> str:
    """收集 AI 学习的开发经验"""
    from app.core.experience_manager import ExperienceManager
    mgr = ExperienceManager(project_name)
    summaries = mgr.get_all_summaries()
    return summaries if summaries else "（尚未生成综合总结，可在「AI 学习」模块中学习后点击生成综合总结）"


def _collect_skills_context(project_name: str) -> tuple[str, str]:
    """收集 Skill 信息，返回 (skill详情, 动态生成的规则)"""
    from app.core.skill_manager import SkillManager
    mgr = SkillManager(project_name)
    skills = mgr.list_skills()
    if not skills:
        return "（尚未生成 Skill）", "- 尚未配置 Skill，请先在 Skill 管理中生成"

    # Skill 详情
    details = []
    for s in skills:
        details.append(f"### {s.name} ({s.category}) - {s.description}\n模板:\n{s.template}")
    skills_info = "\n\n".join(details)

    # 动态生成规则：按类别分组，自动关联
    category_map = {
        "protocol": "协议设计",
        "business": "业务逻辑和代码结构设计",
        "config": "配置表设计",
        "framework": "框架和架构设计",
        "custom": "相关设计",
    }
    rules = []
    for s in skills:
        cat_desc = category_map.get(s.category, "相关设计")
        rules.append(f"- {cat_desc}必须遵循「{s.name}」Skill 的规范（{s.description}）")

    return skills_info, "\n".join(rules)


def _extract_search_keywords(user_input: str, chat_history: list) -> list[str]:
    """第一轮：让 LLM 分析用户需求，提取搜索关键词"""
    cfg = get_llm_config()
    llm = ChatOpenAI(model=cfg["model"], openai_api_key=cfg["api_key"],
                     openai_api_base=cfg["base_url"], temperature=0)

    # 收集最近的对话上下文
    recent = ""
    for msg in chat_history[-6:]:
        recent += f"{msg['role']}: {msg['content'][:200]}\n"

    resp = llm.invoke([
        SystemMessage(content="""你是一个关键词提取器。根据用户的游戏开发需求描述，提取用于搜索代码库、配置表、协议文件的关键词。
输出 JSON 格式：{"code": ["关键词1", ...], "config": ["关键词1", ...], "protocol": ["关键词1", ...]}
- code: 用于搜索代码的关键词（类名、模块名、功能名，如 Shop, Item, Controller, Service）
- config: 用于搜索配置表的关键词（表名、字段名，如 item, reward, price, 道具）
- protocol: 用于搜索协议的关键词（消息名、接口名，如 BuyItem, ShopList, request）
每类最多5个关键词。只输出 JSON，不要其他内容。"""),
        HumanMessage(content=f"对话上下文:\n{recent}\n\n当前用户输入: {user_input}"),
    ])

    try:
        content = resp.content.strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except Exception:
        # 回退：从用户输入中简单提取
        words = re.findall(r'[a-zA-Z]\w+|[\u4e00-\u9fff]+', user_input)
        return {"code": words[:3], "config": words[:3], "protocol": words[:3]}


def _search_project_context(project_name: str, keywords: dict) -> str:
    """第二轮准备：根据提取的关键词搜索项目索引"""
    parts = []

    # 搜索代码索引
    from app.core.code_index import CodeIndex, CodeSymbol
    code_idx = CodeIndex(project_name)
    if code_idx.get_stats()["files"] > 0:
        parts.append(f"项目: {code_idx.get_stats()['files']} 文件")
        seen = set()
        for kw in keywords.get("code", []):
            for r in code_idx.search(kw, k=3):
                key = f"{r.get('name', '')}{r['file']}"
                if key in seen:
                    continue
                seen.add(key)
                if r["type"] == "symbol":
                    parts.append(f"[{r['kind']}] {r['name']} — {r['signature']}")
                    # 读取代码上下文
                    sym = CodeSymbol(name=r["name"], kind=r["kind"], file_path=r["file"],
                                     line_start=r["line"], signature=r["signature"])
                    ctx = code_idx.get_symbol_context(sym, context_lines=25)
                    if ctx:
                        parts.append(f"```\n{ctx[:400]}\n```")

    # 搜索配置表索引
    from app.core.config_index import ConfigIndex
    cfg_idx = ConfigIndex(project_name)
    if cfg_idx.get_stats()["files"] > 0:
        seen_cfg = set()
        for kw in keywords.get("config", []):
            for r in cfg_idx.search(kw, k=2):
                key = f"{r['file']}/{r['sheet']}"
                if key in seen_cfg:
                    continue
                seen_cfg.add(key)
                parts.append(f"[配置表 {r['file']}/{r['sheet']}]\n{r['sample_text'][:400]}")

    # 搜索协议索引
    from app.core.protocol_index import ProtocolIndex
    proto_idx = ProtocolIndex(project_name)
    if proto_idx.get_stats()["files"] > 0:
        seen_proto = set()
        for kw in keywords.get("protocol", []):
            for r in proto_idx.search(kw, k=3):
                key = f"{r.get('name', '')}{r['file']}"
                if key in seen_proto:
                    continue
                seen_proto.add(key)
                if r["type"] == "symbol":
                    parts.append(f"[协议 {r['kind']}] {r['name']} — {r['content']}")

    return "\n\n".join(parts) if parts else "（未找到相关项目数据）"


def _parse_uploaded_files(uploaded_files) -> str:
    if not uploaded_files:
        return ""
    doc_parser, excel_parser = DocParser(), ExcelParser()
    parts = []
    for f in uploaded_files:
        tmp = Path("data/uploads") / f.name
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(f.getvalue())
        md = excel_parser.to_markdown(str(tmp)) if f.name.endswith((".xlsx", ".xls")) else doc_parser.to_markdown(str(tmp))
        parts.append(f"**📄 {f.name}**\n\n{md}")
    return "\n\n---\n\n".join(parts)


def _list_saved_docs(project_name: str) -> list[dict]:
    d = REQUIREMENTS_DIR / project_name
    if not d.exists():
        return []
    docs = []
    for f in sorted(d.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            docs.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return docs


def _save_doc(project_name: str, doc_name: str, content: str, chat_history: list):
    d = REQUIREMENTS_DIR / project_name
    d.mkdir(parents=True, exist_ok=True)
    # 文件名安全处理
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', doc_name)
    f = d / f"{safe_name}.json"
    data = {"name": doc_name, "content": content, "chat_history": chat_history,
            "updated_at": datetime.now().isoformat(), "created_at": datetime.now().isoformat()}
    if f.exists():
        try:
            old = json.loads(f.read_text(encoding="utf-8"))
            data["created_at"] = old.get("created_at", data["created_at"])
        except Exception:
            pass
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _delete_doc(project_name: str, doc_name: str):
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', doc_name)
    f = REQUIREMENTS_DIR / project_name / f"{safe_name}.json"
    if f.exists():
        f.unlink()


def _auto_title(content: str) -> str:
    """从文档内容提取第一个标题作为文档名"""
    for line in content.split("\n"):
        stripped = line.strip().lstrip("#").strip()
        if stripped and len(stripped) >= 2 and not stripped.startswith("```"):
            return stripped[:30]
    return f"需求文档_{datetime.now().strftime('%m%d_%H%M')}"


def _strip_skill_update_block(content: str) -> str:
    """从回复中去掉 skill_update 代码块，返回干净的文档内容"""
    return re.sub(r'```skill_update\s*\n.*?```', '', content, flags=re.DOTALL).strip()


def _auto_update_skills(project_name: str, response: str):
    """检测回复中的 skill_update 块，自动更新对应 Skill"""
    match = re.search(r'```skill_update\s*\n(.*?)```', response, flags=re.DOTALL)
    if not match:
        return

    try:
        items = json.loads(match.group(1).strip())
        from app.core.skill_manager import SkillManager, Skill
        mgr = SkillManager(project_name)
        updated = []
        for item in items:
            template = item.get("template", "")
            template = template.replace("{{", "{").replace("}}", "}")
            skill = Skill(
                name=item.get("name", ""),
                description=item.get("description", ""),
                category=item.get("category", "business"),
                template=template,
                variables=item.get("variables", []),
                source="auto_updated",
            )
            if skill.name:
                mgr.save_skill(skill)
                updated.append(skill.name)
        if updated:
            st.toast(f"🔧 已自动更新 Skill: {', '.join(updated)}")
    except (json.JSONDecodeError, Exception):
        pass


def render():
    st.header("📝 需求文档生成")
    project_name = st.session_state.get("project_name", "default")

    if "doc_messages" not in st.session_state:
        st.session_state["doc_messages"] = []
    if "current_req_doc" not in st.session_state:
        st.session_state["current_req_doc"] = ""
    if "current_req_name" not in st.session_state:
        st.session_state["current_req_name"] = ""

    # ========== 顶部：文档选择 ==========
    saved_docs = _list_saved_docs(project_name)
    doc_names = [d["name"] for d in saved_docs]
    options = ["📄 新建文档"] + doc_names

    # 确保 doc_selector 的值在 options 里（防止删除后残留旧值）
    if "doc_selector" in st.session_state and st.session_state["doc_selector"] not in options:
        st.session_state["doc_selector"] = "📄 新建文档"

    # 自动保存后同步 selectbox
    if st.session_state["current_req_name"] in doc_names:
        st.session_state["doc_selector"] = st.session_state["current_req_name"]

    # 处理待删除标记（在 selectbox 渲染前处理）
    if st.session_state.get("_pending_delete"):
        doc_to_del = st.session_state.pop("_pending_delete")
        _delete_doc(project_name, doc_to_del)
        st.session_state["current_req_doc"] = ""
        st.session_state["current_req_name"] = ""
        st.session_state["doc_messages"] = []
        st.session_state["doc_selector"] = "📄 新建文档"
        st.rerun()

    col_sel, col_del = st.columns([5, 1])
    with col_sel:
        selected = st.selectbox("需求文档", options, key="doc_selector")
    with col_del:
        st.write("")
        st.write("")
        if st.button("🗑️ 删除", disabled=(selected == "📄 新建文档"), use_container_width=True):
            # 标记待删除，下次 rerun 时在 selectbox 渲染前处理
            st.session_state["_pending_delete"] = selected
            st.rerun()

    # 切换文档：只在用户主动选择「新建文档」时才清空
    if selected == "📄 新建文档" and st.session_state["current_req_name"]:
        # 检查是不是用户主动切换的（而不是 rerun 后的默认值）
        if st.session_state.get("_prev_doc_selection") != "📄 新建文档":
            st.session_state["doc_messages"] = []
            st.session_state["current_req_doc"] = ""
            st.session_state["current_req_name"] = ""
    elif selected != "📄 新建文档" and selected != st.session_state.get("current_req_name"):
        doc_data = next((d for d in saved_docs if d["name"] == selected), None)
        if doc_data:
            st.session_state["current_req_name"] = doc_data["name"]
            st.session_state["current_req_doc"] = doc_data["content"]
            st.session_state["doc_messages"] = doc_data.get("chat_history", [])
            st.rerun()
    st.session_state["_prev_doc_selection"] = selected

    # 上传参考文档
    uploaded = st.file_uploader("📎 上传参考文档（可选）", type=["docx", "xlsx", "xls", "txt", "md"],
                                 accept_multiple_files=True, key="doc_uploader")
    if uploaded:
        fk = ",".join(sorted(f.name for f in uploaded))
        if st.session_state.get("_last_upload_key") != fk:
            content = _parse_uploaded_files(uploaded)
            if content:
                st.session_state["doc_messages"].append({"role": "user", "content": f"参考文档：\n\n{content[:6000]}", "is_doc": True})
                st.session_state["doc_messages"].append({"role": "assistant", "content": f"已阅读 {len(uploaded)} 个文档，请描述需求。", "is_doc": True})
                st.session_state["_last_upload_key"] = fk
                st.rerun()

    # 当前文档预览
    if st.session_state["current_req_doc"]:
        with st.expander(f"📄 {st.session_state['current_req_name']}", expanded=False):
            st.markdown(st.session_state["current_req_doc"])
            st.download_button("📥 下载", st.session_state["current_req_doc"],
                               file_name=f"{st.session_state['current_req_name']}.md", mime="text/markdown")

    st.divider()

    # ========== 对话区域 ==========
    for msg in st.session_state["doc_messages"]:
        with st.chat_message(msg["role"]):
            if msg.get("is_doc") and msg["role"] == "user":
                with st.expander("📎 参考文档", expanded=False):
                    st.markdown(msg["content"][:3000])
            else:
                st.markdown(msg["content"])

    # ========== 输入 ==========
    if prompt := st.chat_input("描述需求，文档自动保存..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state["doc_messages"].append({"role": "user", "content": prompt})

        cfg = get_llm_config()

        # 第一轮：提取搜索关键词
        with st.spinner("🔍 分析需求，检索项目相关代码..."):
            keywords = _extract_search_keywords(prompt, st.session_state["doc_messages"])
            project_context = _search_project_context(project_name, keywords)

        # 第二轮：带搜索结果生成回复
        llm = ChatOpenAI(model=cfg["model"], openai_api_key=cfg["api_key"],
                         openai_api_base=cfg["base_url"], temperature=0.3, streaming=True)

        sys_prompt = _get_system_prompt(project_name, project_context,
                                         st.session_state.get("current_req_doc", ""))
        messages = [SystemMessage(content=sys_prompt)]
        for msg in st.session_state["doc_messages"][-20:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            for chunk in llm.stream(messages):
                if chunk.content:
                    full_response += chunk.content
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)

        st.session_state["doc_messages"].append({"role": "assistant", "content": full_response})

        # 检测并自动更新 Skill
        _auto_update_skills(project_name, full_response)

        # 自动保存文档（去掉 skill_update 块后保存）
        clean_response = _strip_skill_update_block(full_response)
        if clean_response.count("#") >= 3 and len(clean_response) > 500:
            if st.session_state["current_req_name"]:
                doc_name = st.session_state["current_req_name"]
            else:
                doc_name = _auto_title(clean_response)
            _save_doc(project_name, doc_name, clean_response, st.session_state["doc_messages"])
            st.session_state["current_req_name"] = doc_name
            st.session_state["current_req_doc"] = clean_response

        st.rerun()
