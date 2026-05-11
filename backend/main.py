import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
import yaml
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, run_migrations
from models import Skill, init_db, slugify

app = FastAPI(title="SkillHub API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    run_migrations()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SkillOut(BaseModel):
    id: int
    name: str
    slug: str
    icon: str
    category: str
    summary: str
    description: str
    owner: str
    input_schema: list
    output_type: str
    call_count: int
    status: str
    source_url: str | None
    execute_url: str | None
    last_synced_at: datetime | None

    class Config:
        from_attributes = True


class ExecuteRequest(BaseModel):
    payload: dict[str, Any]


class ImportRequest(BaseModel):
    url: str


# ── URL helpers ───────────────────────────────────────────────────────────────

def normalize_to_raw(url: str) -> str:
    """Convert github.com/…/blob/… URLs to raw.githubusercontent.com."""
    # github blob URL
    m = re.match(
        r'https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)',
        url
    )
    if m:
        user, repo, branch, path = m.groups()
        return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}"

    # gist: convert to raw (first file)
    m = re.match(r'https?://gist\.github\.com/([^/]+)/([a-f0-9]+)$', url)
    if m:
        return f"https://gist.githubusercontent.com/{m.group(1)}/{m.group(2)}/raw"

    return url  # already raw or other host


async def fetch_raw(url: str) -> str:
    raw_url = normalize_to_raw(url)
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        r = await client.get(raw_url)
        r.raise_for_status()
        return r.text


# ── Skill manifest parser ─────────────────────────────────────────────────────

REQUIRED = {"name", "summary", "owner", "description"}

def parse_manifest(text: str) -> dict:
    """Parse YAML or JSON skill manifest. Returns validated dict."""
    try:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("Manifest root must be a mapping")
    except yaml.YAMLError:
        data = json.loads(text)  # fallback to JSON

    missing = REQUIRED - data.keys()
    if missing:
        raise ValueError(f"Manifest missing required fields: {', '.join(sorted(missing))}")

    if "slug" not in data:
        data["slug"] = slugify(data["name"])

    data.setdefault("icon",         "⚡")
    data.setdefault("category",     "通用")
    data.setdefault("output_type",  "markdown")
    data.setdefault("input_schema", [])
    data.setdefault("status",       "active")
    data.setdefault("call_count",   0)

    return data


# ── API: CRUD ─────────────────────────────────────────────────────────────────

@app.get("/api/skills", response_model=list[SkillOut])
def list_skills(category: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Skill).filter(Skill.status == "active")
    if category:
        q = q.filter(Skill.category == category)
    return q.order_by(Skill.call_count.desc()).all()


@app.get("/api/skills/{slug}", response_model=SkillOut)
def get_skill(slug: str, db: Session = Depends(get_db)):
    skill = db.query(Skill).filter(Skill.slug == slug).first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    return skill


@app.get("/api/categories")
def list_categories(db: Session = Depends(get_db)):
    rows = db.query(Skill.category).distinct().filter(Skill.status == "active").all()
    return [r[0] for r in rows]


# ── API: Execute ──────────────────────────────────────────────────────────────

@app.post("/api/skills/{slug}/execute")
async def execute_skill(slug: str, req: ExecuteRequest, db: Session = Depends(get_db)):
    skill = db.query(Skill).filter(Skill.slug == slug).first()
    if not skill:
        raise HTTPException(404, "Skill not found")

    skill.call_count += 1
    db.commit()

    if skill.execute_url:
        # Forward to the external Agent endpoint
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(skill.execute_url, json={"payload": req.payload})
                resp.raise_for_status()
                body = resp.json()
                result = body.get("result", body.get("output", str(body)))
        except Exception as e:
            raise HTTPException(502, f"External Agent error: {e}")
    else:
        result = _mock_execute(skill.slug, req.payload)

    return {"skill": slug, "output_type": skill.output_type, "result": result}


# ── API: Import from URL ──────────────────────────────────────────────────────

@app.post("/api/import/preview")
async def preview_import(req: ImportRequest):
    """Fetch and parse a skill manifest without saving it."""
    try:
        text = await fetch_raw(req.url)
        data = parse_manifest(text)
    except httpx.HTTPStatusError as e:
        raise HTTPException(400, f"无法获取 URL ({e.response.status_code}): {req.url}")
    except Exception as e:
        raise HTTPException(400, f"解析失败: {e}")
    return data


@app.post("/api/import", response_model=SkillOut)
async def import_skill(req: ImportRequest, db: Session = Depends(get_db)):
    """Import (or update) a skill from an external URL."""
    try:
        text = await fetch_raw(req.url)
        data = parse_manifest(text)
    except httpx.HTTPStatusError as e:
        raise HTTPException(400, f"无法获取 URL ({e.response.status_code}): {req.url}")
    except Exception as e:
        raise HTTPException(400, f"解析失败: {e}")

    data["source_url"]     = req.url
    data["last_synced_at"] = datetime.now(timezone.utc)

    existing = db.query(Skill).filter(Skill.slug == data["slug"]).first()
    if existing:
        for k, v in data.items():
            if k not in ("id", "created_at", "call_count"):
                setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        skill = Skill(**{k: v for k, v in data.items() if hasattr(Skill, k)})
        db.add(skill)
        db.commit()
        db.refresh(skill)
        return skill


@app.post("/api/skills/{slug}/sync", response_model=SkillOut)
async def sync_skill(slug: str, db: Session = Depends(get_db)):
    """Re-fetch and update a skill from its source_url."""
    skill = db.query(Skill).filter(Skill.slug == slug).first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    if not skill.source_url:
        raise HTTPException(400, "This skill has no source_url to sync from")

    try:
        text  = await fetch_raw(skill.source_url)
        data  = parse_manifest(text)
    except Exception as e:
        raise HTTPException(400, f"Sync failed: {e}")

    for k, v in data.items():
        if k not in ("id", "created_at", "call_count", "slug"):
            setattr(skill, k, v)
    skill.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(skill)
    return skill


# ── Mock execution (fallback when no execute_url) ─────────────────────────────

def _mock_execute(slug: str, payload: dict) -> str:
    mocks = {
        "rf-anomaly-detection": (
            "## 射频异常检测报告\n\n"
            "**扫描完成 · 发现 2 处异常**\n\n"
            "| 频段 | 指标 | 测量值 | 基线 | 状态 |\n"
            "|------|------|--------|------|------|\n"
            "| 2400 MHz | RSSI | **-92 dBm** | ≥ -85 dBm | 🔴 异常 |\n"
            "| 5800 MHz | SNR | **8.2 dB** | ≥ 12 dB | 🔴 异常 |\n"
            "| 3500 MHz | RSSI | -76 dBm | ≥ -85 dBm | 🟢 正常 |\n\n"
            "### 根因假设\n"
            "1. **2.4 GHz 链路增益不足** — 建议检查 PA 偏置电压与匹配网络\n"
            "2. **5.8 GHz SNR 劣化** — 疑似邻频干扰，建议在屏蔽箱内复测\n\n"
            "> 置信度：87% | 建议复测批次：≥ 5 台"
        ),
        "competitor-spec-inference": json.dumps({
            "model": payload.get("model_name", "Unknown"),
            "inferred_specs": {
                "SoC":     {"value": "Snapdragon 8 Elite",       "confidence": 0.95},
                "RAM":     {"value": "12 GB LPDDR5X",            "confidence": 0.88},
                "Storage": {"value": "256 GB UFS 4.0",           "confidence": 0.92},
                "Camera":  {"value": "200 MP, 1/1.3\" sensor",   "confidence": 0.79},
                "Battery": {"value": "5000 mAh, 65W",            "confidence": 0.83},
            },
            "overall_confidence": 0.88,
        }, ensure_ascii=False, indent=2),
        "battery-complaint-summary": (
            "## 电池客诉总结报告\n\n"
            "### 问题分布\n"
            "| 类别 | 占比 | 环比 |\n|------|------|------|\n"
            "| 续航缩短 | 41% | ↑ 8% |\n| 快充异常 | 28% | → 持平 |\n"
            "| 机身发热 | 19% | ↓ 3% |\n| 鼓包/膨胀 | 12% | ↑ 2% |\n\n"
            "### 根因假设\n"
            "1. 电芯老化加速（38%）\n2. BMS 固件 SOC 估算偏差（21%）\n"
            "3. 充电 IC 过温保护阈值偏低（17%）"
        ),
        "antenna-sim-parser": (
            "## 天线仿真解析结果\n\n"
            "| 指标 | 仿真值 | 目标 | 结果 |\n|------|--------|------|------|\n"
            "| S11 @ 2.4G | -18.3 dB | ≤ -10 dB | 🟢 |\n"
            "| 峰值增益 | 2.1 dBi | ≥ 3 dBi | 🔴 |\n"
            "| 效率 | 68% | ≥ 70% | 🟡 |\n\n"
            "**建议**：延长辐射枝节 1.5 mm，预计增益提升 0.8 dBi"
        ),
        "reliability-fail-analysis": (
            "## 8D 报告草稿\n\n"
            "**D3 临时措施：** 暂停当前批次出货\n\n"
            "**D4 根因 FTA Top 3：**\n"
            "1. 材料缺陷（45%）\n2. 工艺参数漂移（33%）\n3. 设计裕量不足（22%）"
        ),
        "supply-chain-risk-scan": json.dumps({
            "high_risk": 1, "medium_risk": 1, "low_risk": 1,
            "items": [
                {"part": "MT29F8G08", "risk": "HIGH", "reason": "单一来源，Q3 延期 8 周",
                 "alternatives": ["Samsung K9F8G08", "SK Hynix H27UBG8T2"]},
            ],
        }, ensure_ascii=False, indent=2),
    }
    return mocks.get(
        slug,
        f"## 执行完成 (Mock)\n\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )


# ── Static frontend ───────────────────────────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/skill/{slug}")
def serve_skill(slug: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "skill.html"))
