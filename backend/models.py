from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from database import Base, engine, SessionLocal
import re


class Skill(Base):
    __tablename__ = "skills"

    id             = Column(Integer, primary_key=True, index=True)
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
    # external import
    source_url     = Column(String(500), nullable=True)
    execute_url    = Column(String(500), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())


def slugify(text: str) -> str:
    s = re.sub(r'[^\w\s-]', '', text.lower())
    return re.sub(r'[\s_]+', '-', s).strip('-')


SEED_DATA = [
    {
        "name": "射频数据异常检测",
        "slug": "rf-anomaly-detection",
        "icon": "📡",
        "category": "射频/天线",
        "summary": "自动分析射频测试日志，定位异常频段与根因。",
        "description": (
            "## 射频数据异常检测\n\n"
            "输入一份 CSV 格式的射频扫描日志，Agent 将：\n\n"
            "1. 自动解析各频段 RSSI / SNR 数据\n"
            "2. 使用统计基线 + 规则引擎识别离群点\n"
            "3. 生成根因假设报告，包含建议复测方案\n\n"
            "> 支持频段：Sub-6G / mmWave / Wi-Fi 6E / BT5.3"
        ),
        "owner": "李雷",
        "input_schema": [
            {"key": "csv_data",   "label": "CSV 日志内容", "type": "textarea", "required": True,
             "placeholder": "粘贴射频扫描 CSV 数据..."},
            {"key": "freq_range", "label": "目标频段",     "type": "select",   "required": False,
             "options": ["全部","Sub-6G","mmWave","Wi-Fi 6E","BT5.3"], "default": "全部"},
            {"key": "threshold",  "label": "异常阈值 (dBm)","type": "number",  "required": False,
             "placeholder": "-85", "default": "-85"},
        ],
        "output_type": "markdown",
        "call_count": 142,
    },
    {
        "name": "竞品参数推演",
        "slug": "competitor-spec-inference",
        "icon": "🔍",
        "category": "竞品情报",
        "summary": "基于拆机 BOM 与公开基准推演竞品核心硬件参数。",
        "description": (
            "## 竞品参数推演\n\n"
            "输入竞品型号或已知规格片段，Agent 将：\n\n"
            "1. 检索内部拆机数据库与公开基准测试\n"
            "2. 利用 LLM 推理补全未知参数\n"
            "3. 输出结构化参数表 + 置信度评分\n\n"
            "> 数据源：极客湾 / 微机分 / AnandTech / TechInsights"
        ),
        "owner": "韩梅梅",
        "input_schema": [
            {"key": "model_name",   "label": "竞品型号",     "type": "text",   "required": True,
             "placeholder": "例：Samsung Galaxy S25 Ultra"},
            {"key": "known_specs",  "label": "已知规格片段", "type": "textarea","required": False,
             "placeholder": "可选：粘贴已知参数..."},
            {"key": "focus_area",   "label": "重点推演维度", "type": "select",  "required": False,
             "options": ["全维度","SoC/内存","相机系统","电池/充电","射频天线"], "default": "全维度"},
        ],
        "output_type": "json",
        "call_count": 87,
    },
    {
        "name": "电池客诉总结",
        "slug": "battery-complaint-summary",
        "icon": "🔋",
        "category": "质量/可靠性",
        "summary": "批量处理电池相关客诉工单，提炼高频问题与根因分布。",
        "description": (
            "## 电池客诉总结\n\n"
            "将多条客诉工单文本输入 Agent，它将：\n\n"
            "1. NLP 分类：识别发热 / 续航 / 鼓包 / 充电异常等子类别\n"
            "2. 频次统计与时间趋势分析\n"
            "3. 映射已知 DFMEA 条目，输出根因假设排序\n"
            "4. 生成可直接提交给品质委员会的摘要报告\n\n"
            "> 输入格式：换行分隔的工单文本（支持中英混合）"
        ),
        "owner": "张三",
        "input_schema": [
            {"key": "complaints",   "label": "客诉工单内容", "type": "textarea","required": True,
             "placeholder": "每条工单占一行，直接粘贴..."},
            {"key": "product_line", "label": "产品线",       "type": "select",  "required": False,
             "options": ["全部","旗舰系列","中端系列","折叠屏","平板"], "default": "全部"},
            {"key": "date_range",   "label": "时间范围",     "type": "text",    "required": False,
             "placeholder": "例：2025-01 ~ 2025-06"},
        ],
        "output_type": "markdown",
        "call_count": 203,
    },
    {
        "name": "天线仿真报告解析",
        "slug": "antenna-sim-parser",
        "icon": "🧲",
        "category": "射频/天线",
        "summary": "解析 HFSS/CST 仿真输出，自动标注关键指标并生成优化建议。",
        "description": (
            "## 天线仿真报告解析\n\n"
            "上传或粘贴仿真软件导出的 S 参数 / 方向图数据，Agent 将：\n\n"
            "1. 自动识别谐振频率、带宽、增益峰值\n"
            "2. 对比目标 spec，高亮不达标项\n"
            "3. 给出天线结构调整方向建议\n\n"
            "> 支持 Touchstone (.s1p/.s2p) 与 CSV 格式"
        ),
        "owner": "李雷",
        "input_schema": [
            {"key": "sim_data",    "label": "仿真数据",        "type": "textarea","required": True,
             "placeholder": "粘贴 S 参数或方向图 CSV..."},
            {"key": "target_freq", "label": "目标频率 (MHz)",  "type": "text",    "required": True,
             "placeholder": "例：2400,5800"},
            {"key": "target_gain", "label": "目标增益 (dBi)",  "type": "number",  "required": False,
             "placeholder": "3"},
        ],
        "output_type": "markdown",
        "call_count": 56,
    },
    {
        "name": "可靠性测试 Fail 分析",
        "slug": "reliability-fail-analysis",
        "icon": "🧪",
        "category": "质量/可靠性",
        "summary": "输入可靠性测试失效数据，自动输出 Fault Tree 与 8D 报告草稿。",
        "description": (
            "## 可靠性测试 Fail 分析\n\n"
            "输入测试项目名称、失效现象与环境条件，Agent 将：\n\n"
            "1. 构建初步故障树（FTA）\n"
            "2. 调用历史 DFMEA 数据库匹配相似案例\n"
            "3. 生成 8D 报告模板（D1-D4 自动填充）\n\n"
            "> 支持跌落 / 振动 / 温湿度 / ESD 等测试类型"
        ),
        "owner": "王芳",
        "input_schema": [
            {"key": "test_type",    "label": "测试类型",   "type": "select",  "required": True,
             "options": ["跌落测试","振动测试","温湿度循环","ESD","盐雾","其他"]},
            {"key": "failure_desc", "label": "失效现象描述","type": "textarea","required": True,
             "placeholder": "详细描述失效现象、发生批次、复现率..."},
            {"key": "sample_count", "label": "样品总数",   "type": "number",  "required": False,
             "placeholder": "50"},
            {"key": "fail_count",   "label": "失效数量",   "type": "number",  "required": False,
             "placeholder": "3"},
        ],
        "output_type": "markdown",
        "call_count": 31,
    },
    {
        "name": "供应链风险扫描",
        "slug": "supply-chain-risk-scan",
        "icon": "🌐",
        "category": "供应链",
        "summary": "输入 BOM 关键器件清单，扫描断供风险与备选方案。",
        "description": (
            "## 供应链风险扫描\n\n"
            "上传 BOM 中的关键器件，Agent 将：\n\n"
            "1. 查询供需动态\n"
            "2. 评估单一来源风险\n"
            "3. 推荐 Pin-to-Pin 兼容备选料\n\n"
            "> 每次最多分析 50 颗关键器件"
        ),
        "owner": "韩梅梅",
        "input_schema": [
            {"key": "bom_items",  "label": "器件清单", "type": "textarea","required": True,
             "placeholder": "每行一条：料号, 描述, 供应商"},
            {"key": "risk_level", "label": "扫描深度", "type": "select",  "required": False,
             "options": ["快速扫描","标准分析","深度审查"], "default": "标准分析"},
        ],
        "output_type": "json",
        "call_count": 19,
    },
]


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(Skill).count() == 0:
        for data in SEED_DATA:
            db.add(Skill(**data))
        db.commit()
    db.close()
