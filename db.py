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
    raw_content    = Column(Text,        nullable=True)   # original fetched file
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", s).strip("-")


def _row_to_dict(s: Skill) -> dict:
    return {c.name: getattr(s, c.name) for c in s.__table__.columns}


# ── DB init ───────────────────────────────────────────────────────────────────

SEED_REPOS = [
    "https://github.com/anthropics/skills",
    "https://github.com/openai/skills",
    "https://github.com/thedotmack/claude-mem",
    "https://github.com/wshobson/agents",
    "https://github.com/VoltAgent/awesome-agent-skills",
    "https://github.com/OthmanAdi/planning-with-files",
    "https://github.com/K-Dense-AI/scientific-agent-skills",
    "https://github.com/alirezarezvani/claude-skills",
    "https://github.com/yusufkaraaslan/Skill_Seekers",
    "https://github.com/Lum1104/Understand-Anything",
    "https://github.com/teng-lin/notebooklm-py",
    "https://github.com/Orchestra-Research/AI-Research-SKILLs",
]


def init_db():
    Base.metadata.create_all(engine)
    _run_migrations()
    db = Session()
    is_empty = db.query(Skill).count() == 0
    db.close()
    if is_empty:
        _seed_from_repos()


def _seed_from_repos():
    """Scan SEED_REPOS, import every SKILL.md / .yaml / .yml found. Skip on any error."""
    for repo_url in SEED_REPOS:
        try:
            files = scan_github_repo(repo_url)
        except Exception:
            continue
        # Prioritise SKILL.md and yaml; skip plain .md files (likely READMEs)
        installable = [
            f for f in files
            if f["path"].lower().endswith(("skill.md", ".yaml", ".yml"))
        ]
        for f in installable:
            try:
                import_url(f["raw_url"])
            except Exception:
                continue


def _run_migrations():
    new_cols = [
        ("source_url",     "TEXT"),
        ("execute_url",    "TEXT"),
        ("last_synced_at", "DATETIME"),
        ("raw_content",    "TEXT"),
    ]
    with engine.connect() as conn:
        existing = {r[1] for r in conn.execute(text("PRAGMA table_info(skills)"))}
        for col, typ in new_cols:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE skills ADD COLUMN {col} {typ}"))
        # Remove description-only entries that have no real installable file
        conn.execute(text(
            "DELETE FROM skills WHERE source_url IS NOT NULL AND (raw_content IS NULL OR raw_content = '')"
        ))
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
            "name":         fm.get("name", ""),
            "summary":      fm.get("description", fm.get("summary", "")),
            "owner":        fm.get("origin", fm.get("author", fm.get("owner", "社区"))),
            "description":  body or fm.get("description", ""),
            "category":     fm.get("category", "AI 工具"),
            "icon":         fm.get("icon", "⚡"),
            "output_type":  fm.get("output_type", "markdown"),
            "input_schema": fm.get("input_schema", [
                {"key": "input", "label": "输入", "type": "textarea", "required": True}
            ]),
        }
    else:
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
                       else ("yaml" if f["path"].endswith((".yaml", ".yml")) else "md"),
        }
        for f in files
        if f["type"] == "blob" and is_skill_file(f["path"])
    ]


def import_url(url: str) -> dict:
    raw = _fetch(url)
    data = _parse(raw)
    data["source_url"]     = url
    data["last_synced_at"] = datetime.now(timezone.utc)
    data["raw_content"]    = raw
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
    raw = _fetch(skill["source_url"])
    data = _parse(raw)
    db = Session()
    row = db.query(Skill).filter(Skill.slug == slug).first()
    for k, v in data.items():
        if k not in ("id", "created_at", "call_count", "slug"):
            setattr(row, k, v)
    row.raw_content    = raw
    row.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    db.close()
    return get_skill(slug)
