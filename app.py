import json
import streamlit as st
from db import (
    init_db, get_all_skills, get_categories,
    get_skill, execute_skill, preview_url, import_url, sync_skill,
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SkillHub · 硬工技能中心",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_db()

# ── Global CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 2rem; padding-bottom: 2rem; }

/* Card grid */
.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1rem;
  margin-top: 1.5rem;
}
.skill-card {
  background: #161b27;
  border: 1px solid #1e2535;
  border-radius: 14px;
  padding: 1.25rem;
  text-decoration: none !important;
  display: block;
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
  position: relative;
}
.skill-card:hover {
  border-color: #3b82f6;
  transform: translateY(-3px);
  box-shadow: 0 8px 32px rgba(59,130,246,.18);
}
.card-icon   { font-size: 1.8rem; margin-bottom: .5rem; display: block; }
.card-cat    { font-size: .65rem; letter-spacing: .08em; text-transform: uppercase;
               border: 1px solid; border-radius: 999px; padding: .15rem .6rem;
               display: inline-block; margin-bottom: .6rem; }
.card-name   { font-size: .95rem; font-weight: 700; color: #e2e8f0; margin: 0 0 .35rem; }
.card-summary{ font-size: .78rem; color: #94a3b8; line-height: 1.6;
               margin: 0 0 1rem; display: -webkit-box;
               -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.card-footer { display: flex; justify-content: space-between;
               font-size: .72rem; color: #64748b; }
.ext-badge   { position: absolute; top: .75rem; right: .75rem;
               font-size: .62rem; font-family: monospace;
               background: rgba(99,102,241,.12); color: #a5b4fc;
               border: 1px solid rgba(99,102,241,.25);
               border-radius: 4px; padding: .1rem .4rem; }

/* Category colors */
.cat-rf      { color: #22d3ee; border-color: rgba(34,211,238,.3); background: rgba(34,211,238,.08); }
.cat-comp    { color: #c084fc; border-color: rgba(192,132,252,.3); background: rgba(192,132,252,.08); }
.cat-qa      { color: #fbbf24; border-color: rgba(251,191,36,.3);  background: rgba(251,191,36,.08); }
.cat-supply  { color: #34d399; border-color: rgba(52,211,153,.3);  background: rgba(52,211,153,.08); }
.cat-default { color: #60a5fa; border-color: rgba(96,165,250,.3);  background: rgba(96,165,250,.08); }

/* Back button */
.back-btn a { font-size: .85rem; color: #60a5fa !important; text-decoration: none !important; }
.back-btn a:hover { color: #93c5fd !important; }

/* Output area */
.output-box {
  background: #161b27; border: 1px solid #1e2535;
  border-radius: 12px; padding: 1.25rem; min-height: 200px;
}
</style>
""", unsafe_allow_html=True)

# ── Category → CSS class ──────────────────────────────────────────────────────

CAT_CLASS = {
    "射频/天线": "cat-rf",
    "竞品情报":  "cat-comp",
    "质量/可靠性": "cat-qa",
    "供应链":    "cat-supply",
}

def cat_class(c): return CAT_CLASS.get(c, "cat-default")


# ── Import dialog ─────────────────────────────────────────────────────────────

@st.dialog("从 URL 导入 Skill", width="large")
def import_dialog():
    st.caption("支持 GitHub 文件链接、Gist、或任意公网 `skill.yaml` 文件")

    with st.expander("查看 skill.yaml 格式规范"):
        st.code("""name: "我的 Skill"
slug: "my-skill"           # 可选，自动生成
icon: "🚀"
category: "通用"
summary: "一句话描述"
owner: "张三"
output_type: "markdown"    # markdown | json
execute_url: "https://..." # 可选：真实执行端点
description: |
  ## Markdown 详细说明

input_schema:
  - key: query
    label: 查询内容
    type: textarea          # text|textarea|number|select
    required: true
    placeholder: "输入..."
  - key: mode
    label: 模式
    type: select
    options: ["快速", "精准"]
    default: "快速"
""", language="yaml")

    url = st.text_input("Skill YAML 文件 URL", placeholder="https://github.com/your-org/skills/blob/main/my-skill.yaml")

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("预览", use_container_width=True) and url:
            with st.spinner("获取中…"):
                try:
                    st.session_state["_preview"] = preview_url(url.strip())
                    st.session_state["_preview_url"] = url.strip()
                except Exception as e:
                    st.error(f"获取失败：{e}")

    # Show preview
    if "_preview" in st.session_state:
        p = st.session_state["_preview"]
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("名称", f"{p.get('icon','⚡')} {p.get('name','')}")
        c2.metric("分类", p.get("category", "通用"))
        c3.metric("输入字段", len(p.get("input_schema", [])))
        if p.get("execute_url"):
            st.success("✓ 包含真实执行端点，Skill 将实际运行 Agent")
        else:
            st.warning("ℹ 无 execute_url，将使用 Mock 模式执行")

        with col2:
            if st.button("✓ 确认导入", type="primary", use_container_width=True):
                with st.spinner("导入中…"):
                    try:
                        import_url(st.session_state["_preview_url"])
                        del st.session_state["_preview"]
                        del st.session_state["_preview_url"]
                        st.success("导入成功！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"导入失败：{e}")


# ── Grid view ─────────────────────────────────────────────────────────────────

def show_grid():
    # Header
    h1, h2 = st.columns([6, 1])
    with h1:
        st.markdown("# ⚡ SkillHub · AI 技能广场")
        st.caption("集中展示与调用团队内部所有 AI Agent 技能。支持从 GitHub / 任意公网 URL 一键引入外部 Skill。")
    with h2:
        st.write("")
        if st.button("＋ 导入 Skill", type="primary", use_container_width=True):
            import_dialog()

    st.divider()

    # Search + category filter
    col_s, col_c = st.columns([2, 5])
    with col_s:
        search = st.text_input("🔍", placeholder="搜索技能…", label_visibility="collapsed")
    with col_c:
        cats = ["全部"] + get_categories()
        sel = st.pills("分类", cats, default="全部", label_visibility="collapsed")
        active_cat = None if sel == "全部" else sel

    # Load skills
    skills = get_all_skills(category=active_cat, search=search or None)

    if not skills:
        st.info("没有找到匹配的技能")
        return

    st.caption(f"{len(skills)} 个技能")

    # Build card HTML
    cards_html = '<div class="skill-grid">'
    for s in skills:
        ext = '<span class="ext-badge">外部引入</span>' if s.get("source_url") else ""
        cards_html += f"""
        <a class="skill-card" href="?skill={s['slug']}">
          {ext}
          <span class="card-icon">{s['icon']}</span>
          <span class="card-cat {cat_class(s['category'])}">{s['category']}</span>
          <p class="card-name">{s['name']}</p>
          <p class="card-summary">{s['summary']}</p>
          <div class="card-footer">
            <span>👤 {s['owner']}</span>
            <span>{s['call_count']:,} calls</span>
          </div>
        </a>"""
    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)


# ── Detail view ───────────────────────────────────────────────────────────────

def show_detail(slug: str):
    skill = get_skill(slug)
    if not skill:
        st.error("Skill 不存在")
        st.query_params.clear()
        return

    # Back + header
    st.markdown(f'<div class="back-btn"><a href="/">← 返回广场</a></div>', unsafe_allow_html=True)
    st.write("")

    # Title row
    t1, t2 = st.columns([5, 2])
    with t1:
        st.markdown(f"## {skill['icon']} {skill['name']}")
        _cc = cat_class(skill["category"])
        _cn = skill["category"]
        st.markdown(f'<span class="card-cat {_cc}">{_cn}</span>', unsafe_allow_html=True)
        st.caption(skill["summary"])
    with t2:
        st.metric("调用次数", f"{skill['call_count']:,}")
        st.caption(f"👤 {skill['owner']}  ·  {skill['output_type'].upper()}")

    # Source row for external skills
    if skill.get("source_url"):
        sc1, sc2 = st.columns([5, 1])
        with sc1:
            url_display = skill["source_url"].replace("https://","").replace("http://","")
            st.markdown(f'🔗 <a href="{skill["source_url"]}" target="_blank" style="font-size:.8rem;color:#a5b4fc;font-family:monospace">{url_display}</a>', unsafe_allow_html=True)
            if skill.get("last_synced_at"):
                synced = str(skill["last_synced_at"])[:16]
                st.caption(f"上次同步：{synced}")
        with sc2:
            if st.button("🔄 同步更新", use_container_width=True):
                with st.spinner("同步中…"):
                    try:
                        sync_skill(slug)
                        st.success("同步完成")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    st.divider()

    # Two-column layout: form | output
    left, right = st.columns([1, 1], gap="large")

    with left:
        st.markdown("**技能说明**")
        st.markdown(skill["description"])

        st.divider()
        st.markdown("**输入参数**")

        schema = skill.get("input_schema") or []
        payload = {}

        with st.form("exec_form"):
            for field in schema:
                key   = field["key"]
                label = field["label"] + (" *" if field.get("required") else "")
                ph    = field.get("placeholder", "")
                ftype = field.get("type", "text")

                if ftype == "textarea":
                    payload[key] = st.text_area(label, placeholder=ph, height=120)
                elif ftype == "select":
                    opts = field.get("options", [])
                    default_val = field.get("default", opts[0] if opts else "")
                    idx = opts.index(default_val) if default_val in opts else 0
                    payload[key] = st.selectbox(label, opts, index=idx)
                elif ftype == "number":
                    payload[key] = st.text_input(label, value=str(field.get("default", "")), placeholder=ph)
                else:
                    payload[key] = st.text_input(label, placeholder=ph)

            submitted = st.form_submit_button("▶  执行 Skill", type="primary", use_container_width=True)

    with right:
        st.markdown("**执行结果**")

        if submitted:
            clean = {k: v for k, v in payload.items() if v}
            with st.spinner("Agent 执行中…"):
                try:
                    out_type, result = execute_skill(slug, clean)
                    st.session_state[f"result_{slug}"] = (out_type, result)
                except Exception as e:
                    st.session_state[f"result_{slug}"] = ("error", str(e))
            st.rerun()

        if f"result_{slug}" in st.session_state:
            out_type, result = st.session_state[f"result_{slug}"]
            if out_type == "error":
                st.error(result)
            elif out_type == "json":
                try:
                    st.json(json.loads(result))
                except Exception:
                    st.code(result, language="json")
            else:
                st.markdown(result)

            if st.button("复制结果", use_container_width=True):
                st.code(result)
        else:
            st.markdown('<div class="output-box"><p style="color:#475569;text-align:center;padding-top:4rem">填写参数后点击执行</p></div>', unsafe_allow_html=True)


# ── Router ────────────────────────────────────────────────────────────────────

slug = st.query_params.get("skill", "")
if slug:
    show_detail(slug)
else:
    show_grid()
