# 🎮 游戏服务器业务代码开发

AI 辅助游戏服务器业务代码开发工具。通过学习已有项目代码、配置表、协议文件，自动提炼开发经验和代码生成模板（Skill），帮助开发者快速生成需求文档和业务代码。

基于 Streamlit 构建，数据全部存储在本地，支持多项目管理。

## 快速开始

### 环境要求

- Python 3.11+（安装时勾选 "Add Python to PATH"）

### Windows 一键启动

双击 `start.bat` 即可。首次运行会自动创建虚拟环境并安装依赖，之后秒启动。

启动后浏览器自动打开 `http://localhost:8501`。

### 手动运行

```bash
python -m venv venv
venv\Scripts\activate     # Windows
# source venv/bin/activate  # Mac/Linux
pip install -e .
streamlit run app/main.py
```

## 功能模块

### 🏗️ 加载框架代码

扫描项目代码目录，基于关键词 + AST 结构构建轻量代码索引（不依赖 Embedding 向量化）。

- 支持增量索引，仅重新索引变更文件
- 支持语言：Java、Kotlin、Go、Python、TypeScript、JavaScript、C#、C++、Lua
- 提取类、方法、函数、接口、枚举等符号信息
- 支持关键词搜索和符号搜索

### 📊 加载配置表

解析 Excel/CSV 配置表，提取列定义和数据样本，构建配置索引。

- 自动识别表头和数据类型
- 支持多 Sheet 解析
- 支持关键词搜索

### 🔌 加载协议

解析协议文件，提取消息、服务、枚举、RPC 定义。

- 支持格式：Protobuf、JSON、YAML、XML
- 自动提取协议结构
- 支持关键词搜索

### 📝 需求文档生成

对话式 AI 生成游戏功能需求文档。

- 自动检索项目代码、配置表、协议作为上下文
- 参考已学习的开发经验和 Skill 模板
- 自动保存文档，支持迭代修改
- 输出标准 Markdown 格式（功能概述、数据结构、接口设计、业务流程等）
- 支持对话中自动修正 Skill 模板

### 🧠 AI 学习

让 AI 学习项目中的业务模块代码，提炼开发经验。

- 选择代码目录，AI 自动分析架构模式、命名规范、业务处理流程
- 生成模块级开发经验总结
- 支持生成跨模块的综合开发经验

### 🧩 Skill 管理

管理代码生成模板（Skill），支持 AI 自动提炼和手动编辑。

- 从项目代码/配置/协议自动生成 Skill
- 内置类型：协议处理、Controller 入口、业务 Service、配置表加载、数据库 DAO、数据表定义
- 需求文档生成时自动引用对应 Skill，确保代码风格一致

## 大模型配置

启动后点击侧边栏的设置按钮配置大模型。支持以下提供商：

| 提供商 | 模型 |
|--------|------|
| DeepSeek | deepseek-chat, deepseek-coder, deepseek-reasoner |
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo |
| 智谱 AI | glm-4-plus, glm-4, glm-4-flash |
| 通义千问 | qwen-max, qwen-plus, qwen-turbo |
| 自定义 | 任意 OpenAI 兼容 API |

## 数据存储

所有数据存储在项目 `data/` 目录下：

```
data/
├── code_index/{项目名}/     # 代码索引
├── config_index/{项目名}/   # 配置表索引
├── proto_index/{项目名}/    # 协议索引
├── skills/{项目名}/         # Skill 模板
├── experiences/{项目名}/    # 学习经验
├── requirements/{项目名}/   # 需求文档
└── llm_settings.json        # 大模型设置
```

## 分发打包

项目提供离线打包功能，打包后的压缩包包含所有依赖，别人解压后双击 `start.bat` 即可使用，无需联网安装依赖。

```bash
# 1. 先确保本地环境正常（运行过 start.bat）
# 2. 双击 pack.bat 生成压缩包
pack.bat
```

生成的 `game-ai-workflow-dist.zip` 在上级目录，包含 `vendor/` 离线依赖包。

## 技术栈

- [Streamlit](https://streamlit.io/) - Web UI
- [LangChain](https://www.langchain.com/) - LLM 集成（OpenAI 兼容接口）
- [Pydantic](https://docs.pydantic.dev/) - 数据模型
- [openpyxl](https://openpyxl.readthedocs.io/) / [pandas](https://pandas.pydata.org/) - Excel 解析
- [python-docx](https://python-docx.readthedocs.io/) - Word 文档解析
