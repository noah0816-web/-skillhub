import json
import os
import re
from datetime import datetime, timezone

import httpx
import yaml
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# ── Database setup ────────────────────────────────────────────────────────────

DB_PATH = os.environ.get("DB_PATH", "skillhub.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()


# ── Model ─────────────────────────────────────────────────────────────────────

class Skill(Base):
    __tablename__ = "skills"
    id             = Column(Integer, primary_key=True)
    name           = Column(String(100), nullable=False)
    slug           = Column(String(100), unique=True, nullable=False)
    icon           = Column(String(10),  default="⚡")
    category       = Column(String(50),  default="通用")
    summary        = Column(String(200), nullable=False)
    description    = Column(Text,        nullable=False)
    owner          = Column(String(50),  nullable=False)
    input_schema   = Column(JSON,        nullable=False, default=list)
    output_type    = Column(String(20),  default="markdown")
    call_count     = Column(Integer,     default=0)
    status         = Column(String(20),  default="active")
    source_url     = Column(String(500), nullable=True)
    execute_url    = Column(String(500), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", s).strip("-")


def _row_to_dict(s: Skill) -> dict:
    return {c.name: getattr(s, c.name) for c in s.__table__.columns}


# ── Seed data ─────────────────────────────────────────────────────────────────

SEEDS = [
    dict(name="Anthropic 官方 Claude Skills", slug="anthropics-skills",
         icon="🤖", category="AI 工具", owner="Anthropic", output_type="markdown",
         summary="Anthropic 官方发布的 Claude Skills 合集，覆盖代码、写作、分析等场景。",
         description="## Anthropic 官方 Claude Skills\n\n来源：[anthropics/skills](https://github.com/anthropics/skills)\n\n官方维护的 Claude 技能集合，包含：\n- 代码生成与调试\n- 文档写作与总结\n- 数据分析\n- 多轮对话管理\n\n> 从 GitHub 导入最新版本后可直接调用",
         source_url="https://github.com/anthropics/skills",
         input_schema=[{"key": "query", "label": "任务描述", "type": "textarea", "required": True, "placeholder": "描述你要完成的任务..."}]),

    dict(name="OpenAI Skills 合集", slug="openai-skills",
         icon="🧠", category="AI 工具", owner="OpenAI", output_type="markdown",
         summary="OpenAI 发布的官方 Skills 集合，适配 GPT 系列模型。",
         description="## OpenAI Skills 合集\n\n来源：[openai/skills](https://github.com/openai/skills)\n\nOpenAI 官方维护的技能库，包含工具调用、结构化输出、函数调用等最佳实践。",
         source_url="https://github.com/openai/skills",
         input_schema=[{"key": "task", "label": "任务", "type": "textarea", "required": True, "placeholder": "输入任务..."}]),

    dict(name="Claude 长期记忆管理", slug="claude-mem",
         icon="🧩", category="记忆管理", owner="社区", output_type="markdown",
         summary="为 Claude 提供跨会话长期记忆能力，支持存储与检索用户上下文。",
         description="## Claude 长期记忆管理\n\n来源：[claude-mem](https://github.com/search?q=claude-mem)\n\n让 Claude 具备持久化记忆能力：\n1. 自动提取对话中的关键信息\n2. 向量化存储，语义检索\n3. 注入历史上下文到新会话\n\n> 适合需要跨会话保持上下文的场景",
         source_url="https://github.com/search?q=claude-mem",
         input_schema=[
             {"key": "action",  "label": "操作", "type": "select", "required": True, "options": ["存储记忆","检索记忆","清空记忆"]},
             {"key": "content", "label": "内容", "type": "textarea", "required": False, "placeholder": "要存储或检索的内容..."},
         ]),

    dict(name="通用 AI Agents 工具集", slug="agents",
         icon="🕵️", category="AI 工具", owner="社区", output_type="markdown",
         summary="多种通用 AI Agent 实现，涵盖规划、执行、反思等核心能力。",
         description="## 通用 AI Agents 工具集\n\n来源：[agents](https://github.com/search?q=ai+agents+skills)\n\n包含 ReAct、CoT、Plan-and-Execute 等多种 Agent 模式的参考实现。",
         source_url="https://github.com/search?q=ai+agents+skills",
         input_schema=[
             {"key": "goal",    "label": "Agent 目标", "type": "textarea", "required": True, "placeholder": "描述 Agent 需要完成的目标..."},
             {"key": "mode",    "label": "执行模式",   "type": "select",   "required": False, "options": ["ReAct","CoT","Plan-and-Execute"], "default": "ReAct"},
         ]),

    dict(name="Awesome Agent Skills", slug="awesome-agent-skills",
         icon="⭐", category="AI 工具", owner="社区", output_type="markdown",
         summary="精选 Agent Skills 大全，社区协作维护的高质量技能合集。",
         description="## Awesome Agent Skills\n\n来源：[awesome-agent-skills](https://github.com/search?q=awesome-agent-skills)\n\n社区精选的 Agent 技能索引，覆盖：代码、写作、研究、数据、自动化等场景。",
         source_url="https://github.com/search?q=awesome-agent-skills",
         input_schema=[{"key": "keyword", "label": "搜索关键词", "type": "text", "required": True, "placeholder": "例：代码审查"}]),

    dict(name="Planning with Files", slug="planning-with-files",
         icon="📁", category="规划", owner="社区", output_type="markdown",
         summary="基于文件系统的 AI 规划 Agent，支持读写本地文件完成复杂任务。",
         description="## Planning with Files\n\n来源：[planning-with-files](https://github.com/search?q=planning-with-files)\n\n将文件系统作为 Agent 的外部记忆，实现：\n- 任务拆解与计划持久化\n- 进度跟踪\n- 多步骤执行",
         source_url="https://github.com/search?q=planning-with-files",
         input_schema=[
             {"key": "task",      "label": "任务描述", "type": "textarea", "required": True},
             {"key": "work_dir",  "label": "工作目录", "type": "text",     "required": False, "placeholder": "/tmp/workspace"},
         ]),

    dict(name="Scientific Agent Skills", slug="scientific-agent-skills",
         icon="🔬", category="研究助手", owner="社区", output_type="markdown",
         summary="面向科研场景的 Agent 技能集，支持文献检索、数据分析、假设生成。",
         description="## Scientific Agent Skills\n\n来源：[scientific-agent-skills](https://github.com/search?q=scientific-agent-skills)\n\n科研 AI 助手工具箱：\n1. 论文检索与摘要\n2. 实验数据分析\n3. 假设验证辅助\n4. 引用格式化",
         source_url="https://github.com/search?q=scientific-agent-skills",
         input_schema=[
             {"key": "research_q", "label": "研究问题", "type": "textarea", "required": True},
             {"key": "domain",     "label": "研究领域", "type": "select",   "required": False, "options": ["材料科学","生物医学","物理","工程","通用"], "default": "通用"},
         ]),

    dict(name="Claude Skills 社区库", slug="claude-skills",
         icon="💡", category="AI 工具", owner="社区", output_type="markdown",
         summary="社区共建的 Claude Skills 合集，涵盖日常办公、开发、创意等高频场景。",
         description="## Claude Skills 社区库\n\n来源：[claude-skills](https://github.com/search?q=claude-skills)\n\n由社区用户贡献和维护，包含各类实用技能模板，开箱即用。",
         source_url="https://github.com/search?q=claude-skills+yaml",
         input_schema=[{"key": "input", "label": "输入内容", "type": "textarea", "required": True}]),

    dict(name="Skill Seekers", slug="skill-seekers",
         icon="🔎", category="AI 工具", owner="社区", output_type="json",
         summary="AI 技能发现与推荐引擎，根据任务描述自动匹配最适合的 Skill。",
         description="## Skill Seekers\n\n来源：[Skill_Seekers](https://github.com/search?q=Skill_Seekers)\n\n输入你的任务，自动在技能库中匹配最合适的 Skill 并返回使用建议。",
         source_url="https://github.com/search?q=Skill_Seekers",
         input_schema=[{"key": "task_desc", "label": "任务描述", "type": "textarea", "required": True, "placeholder": "我想要..."}]),

    dict(name="Understand Anything", slug="understand-anything",
         icon="🌐", category="研究助手", owner="社区", output_type="markdown",
         summary="万物理解 Agent，输入任何文本、URL 或概念，输出深度解读与结构化分析。",
         description="## Understand Anything\n\n来源：[Understand-Anything](https://github.com/search?q=Understand-Anything)\n\n通用内容理解工具，支持：\n- 网页/文章深度解读\n- 技术概念解析\n- 多语言理解\n- 结构化知识提取",
         source_url="https://github.com/search?q=Understand-Anything",
         input_schema=[
             {"key": "content", "label": "内容（文本或 URL）", "type": "textarea", "required": True},
             {"key": "depth",   "label": "解读深度", "type": "select", "required": False, "options": ["概要","标准","深度"], "default": "标准"},
         ]),

    dict(name="NotebookLM Python 接口", slug="notebooklm-py",
         icon="📓", category="研究助手", owner="社区", output_type="markdown",
         summary="Google NotebookLM 的 Python 封装，支持上传文档、生成摘要与问答。",
         description="## NotebookLM Python 接口\n\n来源：[notebooklm-py](https://github.com/search?q=notebooklm-py)\n\n用 Python 调用 NotebookLM 的能力：\n1. 上传 PDF / 文档\n2. 自动生成播客式摘要\n3. 基于文档的问答",
         source_url="https://github.com/search?q=notebooklm-py",
         input_schema=[
             {"key": "doc_url",   "label": "文档 URL",  "type": "text",     "required": True},
             {"key": "question",  "label": "提问",      "type": "textarea", "required": False},
         ]),

    dict(name="Jeffallan Claude Skills", slug="jeffallan-claude-skills",
         icon="🛠️", category="AI 工具", owner="Jeffallan", output_type="markdown",
         summary="Jeffallan 整理的 Claude 实用技能包，覆盖开发、写作、数据处理。",
         description="## Jeffallan Claude Skills\n\n来源：[Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills)\n\n社区贡献者 Jeffallan 整理的实用 Claude 技能集，经过实际项目验证。",
         source_url="https://github.com/Jeffallan/claude-skills",
         input_schema=[{"key": "input", "label": "输入", "type": "textarea", "required": True}]),

    dict(name="AI Research Skills", slug="ai-research-skills",
         icon="📚", category="研究助手", owner="社区", output_type="markdown",
         summary="面向 AI 研究者的技能合集，包含论文阅读、实验设计、结果分析等工具。",
         description="## AI Research Skills\n\n来源：[AI-Research-SKILLs](https://github.com/search?q=AI-Research-SKILLs)\n\n专为 AI 研究人员设计：\n- arXiv 论文快速解读\n- 实验结果对比分析\n- 相关工作梳理\n- Baseline 复现指引",
         source_url="https://github.com/search?q=AI-Research-SKILLs",
         input_schema=[
             {"key": "paper_url", "label": "论文链接或摘要", "type": "textarea", "required": True},
             {"key": "focus",     "label": "关注点",        "type": "select",   "required": False, "options": ["方法","实验","贡献点","全文"], "default": "贡献点"},
         ]),

    dict(name="Prompt Master", slug="prompt-master",
         icon="✍️", category="AI 工具", owner="社区", output_type="markdown",
         summary="提示词工程专家，帮助优化和生成高质量 Prompt，提升 AI 输出效果。",
         description="## Prompt Master\n\n来源：[prompt-master](https://github.com/search?q=prompt-master+skill)\n\n提示词全流程工具：\n1. 分析现有 Prompt 的问题\n2. 自动优化重写\n3. A/B 测试版本生成\n4. 特定场景 Prompt 模板",
         source_url="https://github.com/search?q=prompt-master+skill",
         input_schema=[
             {"key": "prompt",  "label": "原始 Prompt",  "type": "textarea", "required": True},
             {"key": "goal",    "label": "优化目标",     "type": "select",   "required": False, "options": ["更精确","更简洁","更有创意","更专业"], "default": "更精确"},
         ]),

    dict(name="Product Manager Skills", slug="product-manager-skills",
         icon="📊", category="产品/规划", owner="社区", output_type="markdown",
         summary="产品经理 AI 技能集，覆盖需求分析、PRD 撰写、用户故事拆解等核心工作。",
         description="## Product Manager Skills\n\n来源：[Product-Manager-Skills](https://github.com/search?q=Product-Manager-Skills)\n\n为产品经理量身打造：\n1. 需求文档自动化生成\n2. 用户故事拆解\n3. 竞品分析框架\n4. OKR / KPI 制定辅助",
         source_url="https://github.com/search?q=Product-Manager-Skills",
         input_schema=[
             {"key": "requirement", "label": "需求描述", "type": "textarea", "required": True, "placeholder": "描述产品需求或功能点..."},
             {"key": "doc_type",    "label": "输出类型", "type": "select",   "required": False, "options": ["PRD","用户故事","竞品分析","OKR"], "default": "PRD"},
         ]),
]


# ── DB init ───────────────────────────────────────────────────────────────────

def init_db():
    Base.metadata.create_all(engine)
    _run_migrations()
    db = Session()
    if db.query(Skill).count() == 0:
        for d in SEEDS:
            db.add(Skill(**d))
        db.commit()
    db.close()


def _run_migrations():
    new_cols = [("source_url","TEXT"), ("execute_url","TEXT"), ("last_synced_at","DATETIME")]
    with engine.connect() as conn:
        existing = {r[1] for r in conn.execute(text("PRAGMA table_info(skills)"))}
        for col, typ in new_cols:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE skills ADD COLUMN {col} {typ}"))
        conn.commit()


# ── Queries ───────────────────────────────────────────────────────────────────

def get_all_skills(category=None, search=None) -> list[dict]:
    db = Session()
    q = db.query(Skill).filter(Skill.status == "active")
    if category:
        q = q.filter(Skill.category == category)
    rows = q.order_by(Skill.call_count.desc()).all()
    result = [_row_to_dict(r) for r in rows]
    db.close()
    if search:
        s = search.lower()
        result = [r for r in result if s in r["name"].lower() or s in r["summary"].lower() or s in r["owner"].lower()]
    return result


def get_categories() -> list[str]:
    db = Session()
    rows = db.query(Skill.category).distinct().filter(Skill.status == "active").all()
    db.close()
    return [r[0] for r in rows]


def get_skill(slug: str) -> dict | None:
    db = Session()
    row = db.query(Skill).filter(Skill.slug == slug).first()
    result = _row_to_dict(row) if row else None
    db.close()
    return result


def increment_calls(slug: str):
    db = Session()
    db.query(Skill).filter(Skill.slug == slug).update({"call_count": Skill.call_count + 1})
    db.commit()
    db.close()


# ── URL import ────────────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)", url)
    if m:
        u, r, b, p = m.groups()
        return f"https://raw.githubusercontent.com/{u}/{r}/{b}/{p}"
    m = re.match(r"https?://gist\.github\.com/([^/]+)/([a-f0-9]+)$", url)
    if m:
        return f"https://gist.githubusercontent.com/{m.group(1)}/{m.group(2)}/raw"
    return url


def _fetch(url: str) -> str:
    raw = _normalize_url(url)
    r = httpx.get(raw, follow_redirects=True, timeout=15)
    r.raise_for_status()
    return r.text


REQUIRED = {"name"}

def _parse(text: str) -> dict:
    """Parse YAML skill file OR SKILL.md with frontmatter."""
    # Markdown with YAML frontmatter (SKILL.md format)
    if text.lstrip().startswith("---"):
        parts = text.lstrip().split("---", 2)
        if len(parts) >= 3:
            try:
                fm   = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
            except yaml.YAMLError:
                fm, body = {}, text
        else:
            fm, body = {}, text

        data = {
            "name":        fm.get("name", ""),
            "summary":     fm.get("description", fm.get("summary", "")),
            "owner":       fm.get("origin", fm.get("author", fm.get("owner", "社区"))),
            "description": body or fm.get("description", ""),
            "category":    fm.get("category", "AI 工具"),
            "icon":        fm.get("icon", "⚡"),
            "output_type": fm.get("output_type", "markdown"),
            "input_schema":fm.get("input_schema", [
                {"key": "input", "label": "输入", "type": "textarea", "required": True}
            ]),
        }
    else:
        # Pure YAML
        try:
            data = yaml.safe_load(text)
            if not isinstance(data, dict):
                raise ValueError("根节点必须是 mapping")
        except yaml.YAMLError:
            data = json.loads(text)

    if not data.get("name"):
        raise ValueError("缺少必填字段: name")
    if not data.get("summary"):
        data["summary"] = data["description"][:80] if data.get("description") else data["name"]
    if not data.get("description"):
        data["description"] = data["summary"]
    if not data.get("owner"):
        data["owner"] = "社区"

    data.setdefault("slug",         slugify(data["name"]))
    data.setdefault("icon",         "⚡")
    data.setdefault("category",     "AI 工具")
    data.setdefault("output_type",  "markdown")
    data.setdefault("input_schema", [{"key": "input", "label": "输入", "type": "textarea", "required": True}])
    data.setdefault("status",       "active")
    data.setdefault("call_count",   0)
    return data


def preview_url(url: str) -> dict:
    return _parse(_fetch(url))


def scan_github_repo(repo_url: str) -> list[dict]:
    """Return list of importable skill files (SKILL.md, .md, .yaml) in a GitHub repo."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if not m:
        return []
    owner, repo = m.groups()
    meta = httpx.get(f"https://api.github.com/repos/{owner}/{repo}", timeout=10)
    meta.raise_for_status()
    branch = meta.json().get("default_branch", "main")
    tree = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
        timeout=15,
    )
    tree.raise_for_status()
    files = tree.json().get("tree", [])

    def is_skill_file(path: str) -> bool:
        lower = path.lower()
        fname = lower.split("/")[-1]
        return (
            fname == "skill.md"
            or lower.endswith(".yaml")
            or lower.endswith(".yml")
            or lower.endswith(".md")
        )

    return [
        {
            "path":    f["path"],
            "raw_url": f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{f['path']}",
            "type":    "SKILL.md" if f["path"].lower().endswith("skill.md")
                       else ("yaml" if f["path"].endswith((".yaml",".yml")) else "md"),
        }
        for f in files
        if f["type"] == "blob" and is_skill_file(f["path"])
    ]


def import_url(url: str) -> dict:
    data = _parse(_fetch(url))
    data["source_url"]     = url
    data["last_synced_at"] = datetime.now(timezone.utc)
    db = Session()
    existing = db.query(Skill).filter(Skill.slug == data["slug"]).first()
    if existing:
        for k, v in data.items():
            if k not in ("id", "created_at", "call_count"):
                setattr(existing, k, v)
    else:
        db.add(Skill(**{k: v for k, v in data.items() if hasattr(Skill, k)}))
    db.commit()
    db.close()
    return get_skill(data["slug"])


def sync_skill(slug: str) -> dict:
    skill = get_skill(slug)
    if not skill or not skill.get("source_url"):
        raise ValueError("该 Skill 没有 source_url")
    data = _parse(_fetch(skill["source_url"]))
    db = Session()
    row = db.query(Skill).filter(Skill.slug == slug).first()
    for k, v in data.items():
        if k not in ("id", "created_at", "call_count", "slug"):
            setattr(row, k, v)
    row.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    db.close()
    return get_skill(slug)


# ── Execute ───────────────────────────────────────────────────────────────────

def execute_skill(slug: str, payload: dict) -> tuple[str, str]:
    skill = get_skill(slug)
    if not skill:
        raise ValueError("Skill not found")
    increment_calls(slug)
    if skill.get("execute_url"):
        r = httpx.post(skill["execute_url"], json={"payload": payload}, timeout=60)
        r.raise_for_status()
        body = r.json()
        return skill["output_type"], body.get("result", body.get("output", str(body)))
    return skill["output_type"], _mock(slug, payload)


def _mock(slug: str, payload: dict) -> str:
    mocks = {
        "rf-anomaly-detection": (
            "## 射频异常检测报告\n\n**扫描完成 · 发现 2 处异常**\n\n"
            "| 频段 | 指标 | 测量值 | 基线 | 状态 |\n|------|------|--------|------|------|\n"
            "| 2400 MHz | RSSI | **-92 dBm** | ≥ -85 dBm | 🔴 异常 |\n"
            "| 5800 MHz | SNR  | **8.2 dB**  | ≥ 12 dB   | 🔴 异常 |\n"
            "| 3500 MHz | RSSI | -76 dBm     | ≥ -85 dBm | 🟢 正常 |\n\n"
            "### 根因假设\n1. **2.4 GHz 增益不足** — 建议检查 PA 偏置\n"
            "2. **5.8 GHz SNR 劣化** — 疑似邻频干扰，建议屏蔽箱复测\n\n> 置信度：87%"
        ),
        "competitor-spec-inference": json.dumps({
            "model": payload.get("model_name", "Unknown"),
            "inferred_specs": {
                "SoC":     {"value": "Snapdragon 8 Elite",    "confidence": 0.95},
                "RAM":     {"value": "12 GB LPDDR5X",         "confidence": 0.88},
                "Storage": {"value": "256 GB UFS 4.0",        "confidence": 0.92},
                "Camera":  {"value": "200 MP, 1/1.3\" sensor","confidence": 0.79},
                "Battery": {"value": "5000 mAh, 65W",         "confidence": 0.83},
            },
            "overall_confidence": 0.88,
        }, ensure_ascii=False, indent=2),
        "battery-complaint-summary": (
            "## 电池客诉总结\n\n| 类别 | 占比 | 环比 |\n|------|------|------|\n"
            "| 续航缩短 | 41% | ↑8% |\n| 快充异常 | 28% | →持平 |\n"
            "| 机身发热 | 19% | ↓3% |\n| 鼓包/膨胀 | 12% | ↑2% |\n\n"
            "### 根因假设\n1. 电芯老化加速（38%）\n2. BMS 固件 SOC 估算偏差（21%）"
        ),
        "antenna-sim-parser": (
            "## 仿真解析结果\n\n| 指标 | 仿真值 | 目标 | 结果 |\n|------|--------|------|------|\n"
            "| S11 @ 2.4G | -18.3 dB | ≤ -10 dB | 🟢 |\n"
            "| 峰值增益   | 2.1 dBi  | ≥ 3 dBi  | 🔴 |\n"
            "| 效率       | 68%      | ≥ 70%    | 🟡 |\n\n"
            "**建议**：延长辐射枝节 1.5 mm，增益预计提升 0.8 dBi"
        ),
        "reliability-fail-analysis": (
            "## 8D 报告草稿\n\n**D3 临时措施：** 暂停当前批次出货\n\n"
            "**D4 根因 FTA Top 3：**\n1. 材料缺陷（45%）\n2. 工艺参数漂移（33%）\n3. 设计裕量不足（22%）"
        ),
        "supply-chain-risk-scan": json.dumps({
            "summary": {"high": 1, "medium": 1, "low": 1},
            "items": [{"part": "MT29F8G08", "risk": "HIGH", "reason": "单一来源，Q3 延期8周",
                        "alternatives": ["Samsung K9F8G08","SK Hynix H27UBG8T2"]}],
        }, ensure_ascii=False, indent=2),
    }
    return mocks.get(slug, f"## 执行完成 (Mock)\n\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```")
