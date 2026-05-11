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
    dict(name="射频数据异常检测", slug="rf-anomaly-detection", icon="📡",
         category="射频/天线", owner="李雷", output_type="markdown",
         call_count=142,
         summary="自动分析射频测试日志，定位异常频段与根因。",
         description="## 射频数据异常检测\n\n输入 CSV 格式的射频扫描日志，Agent 将：\n\n1. 自动解析各频段 RSSI / SNR 数据\n2. 使用统计基线 + 规则引擎识别离群点\n3. 生成根因假设报告，包含建议复测方案\n\n> 支持频段：Sub-6G / mmWave / Wi-Fi 6E / BT5.3",
         input_schema=[
             {"key": "csv_data",   "label": "CSV 日志内容",  "type": "textarea", "required": True,  "placeholder": "粘贴射频扫描 CSV 数据..."},
             {"key": "freq_range", "label": "目标频段",      "type": "select",   "required": False, "options": ["全部","Sub-6G","mmWave","Wi-Fi 6E","BT5.3"], "default": "全部"},
             {"key": "threshold",  "label": "异常阈值 (dBm)","type": "number",   "required": False, "placeholder": "-85"},
         ]),
    dict(name="竞品参数推演", slug="competitor-spec-inference", icon="🔍",
         category="竞品情报", owner="韩梅梅", output_type="json",
         call_count=87,
         summary="基于拆机 BOM 与公开基准推演竞品核心硬件参数。",
         description="## 竞品参数推演\n\n输入竞品型号，Agent 将推理补全未知参数并输出置信度评分。\n\n> 数据源：极客湾 / 微机分 / AnandTech / TechInsights",
         input_schema=[
             {"key": "model_name",  "label": "竞品型号",     "type": "text",     "required": True,  "placeholder": "例：Samsung Galaxy S25 Ultra"},
             {"key": "known_specs", "label": "已知规格片段", "type": "textarea", "required": False, "placeholder": "可选：粘贴已知参数..."},
             {"key": "focus_area",  "label": "重点推演维度", "type": "select",   "required": False, "options": ["全维度","SoC/内存","相机系统","电池/充电","射频天线"], "default": "全维度"},
         ]),
    dict(name="电池客诉总结", slug="battery-complaint-summary", icon="🔋",
         category="质量/可靠性", owner="张三", output_type="markdown",
         call_count=203,
         summary="批量处理电池相关客诉工单，提炼高频问题与根因分布。",
         description="## 电池客诉总结\n\n将多条客诉工单文本输入 Agent，输出分类统计 + 根因假设排序 + 品质委员会摘要报告。\n\n> 支持中英混合输入，换行分隔工单",
         input_schema=[
             {"key": "complaints",   "label": "客诉工单内容", "type": "textarea", "required": True,  "placeholder": "每条工单占一行..."},
             {"key": "product_line", "label": "产品线",       "type": "select",   "required": False, "options": ["全部","旗舰系列","中端系列","折叠屏","平板"], "default": "全部"},
             {"key": "date_range",   "label": "时间范围",     "type": "text",     "required": False, "placeholder": "例：2025-01 ~ 2025-06"},
         ]),
    dict(name="天线仿真报告解析", slug="antenna-sim-parser", icon="🧲",
         category="射频/天线", owner="李雷", output_type="markdown",
         call_count=56,
         summary="解析 HFSS/CST 仿真输出，自动标注关键指标并生成优化建议。",
         description="## 天线仿真报告解析\n\n粘贴仿真软件导出的 S 参数 / 方向图数据，Agent 识别谐振频率、带宽、增益，对比目标 spec，给出结构调整建议。\n\n> 支持 Touchstone (.s1p/.s2p) 与 CSV",
         input_schema=[
             {"key": "sim_data",    "label": "仿真数据",       "type": "textarea", "required": True, "placeholder": "粘贴 S 参数或方向图 CSV..."},
             {"key": "target_freq", "label": "目标频率 (MHz)", "type": "text",     "required": True, "placeholder": "例：2400,5800"},
             {"key": "target_gain", "label": "目标增益 (dBi)", "type": "number",   "required": False,"placeholder": "3"},
         ]),
    dict(name="可靠性测试 Fail 分析", slug="reliability-fail-analysis", icon="🧪",
         category="质量/可靠性", owner="王芳", output_type="markdown",
         call_count=31,
         summary="输入可靠性测试失效数据，自动输出 Fault Tree 与 8D 报告草稿。",
         description="## 可靠性测试 Fail 分析\n\n输入测试类型与失效现象，Agent 构建初步 FTA，匹配历史 DFMEA 案例，生成 8D 报告模板（D1-D4 自动填充）。",
         input_schema=[
             {"key": "test_type",    "label": "测试类型",    "type": "select",   "required": True,  "options": ["跌落测试","振动测试","温湿度循环","ESD","盐雾","其他"]},
             {"key": "failure_desc", "label": "失效现象描述","type": "textarea", "required": True,  "placeholder": "详细描述失效现象、批次、复现率..."},
             {"key": "sample_count", "label": "样品总数",    "type": "number",   "required": False, "placeholder": "50"},
             {"key": "fail_count",   "label": "失效数量",    "type": "number",   "required": False, "placeholder": "3"},
         ]),
    dict(name="供应链风险扫描", slug="supply-chain-risk-scan", icon="🌐",
         category="供应链", owner="韩梅梅", output_type="json",
         call_count=19,
         summary="输入 BOM 关键器件清单，扫描断供风险与备选方案。",
         description="## 供应链风险扫描\n\n输入关键器件，Agent 查询供需动态，评估单一来源风险，推荐 Pin-to-Pin 兼容备选料。\n\n> 每次最多 50 颗关键器件",
         input_schema=[
             {"key": "bom_items",  "label": "器件清单", "type": "textarea","required": True,  "placeholder": "每行一条：料号, 描述, 供应商"},
             {"key": "risk_level", "label": "扫描深度", "type": "select",  "required": False, "options": ["快速扫描","标准分析","深度审查"], "default": "标准分析"},
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


REQUIRED = {"name", "summary", "owner", "description"}

def _parse(text: str) -> dict:
    try:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("根节点必须是 mapping")
    except yaml.YAMLError:
        data = json.loads(text)
    missing = REQUIRED - data.keys()
    if missing:
        raise ValueError(f"缺少必填字段: {', '.join(sorted(missing))}")
    data.setdefault("slug",         slugify(data["name"]))
    data.setdefault("icon",         "⚡")
    data.setdefault("category",     "通用")
    data.setdefault("output_type",  "markdown")
    data.setdefault("input_schema", [])
    data.setdefault("status",       "active")
    data.setdefault("call_count",   0)
    return data


def preview_url(url: str) -> dict:
    return _parse(_fetch(url))


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
