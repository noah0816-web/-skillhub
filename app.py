import json
import re
import yaml
import httpx
import streamlit as st
from db import (
    init_db, get_all_skills, get_categories,
    get_skill, preview_url, import_url, sync_skill,
    scan_github_repo, reseed,
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
.installable-badge {
  position: absolute; top: .75rem; right: .75rem;
  font-size: .62rem; font-weight: 600;
  background: rgba(52,211,153,.12); color: #34d399;
  border: 1px solid rgba(52,211,153,.3);
  border-radius: 4px; padding: .1rem .45rem;
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


@st.cache_data(ttl=3600)
def fetch_github_stars(source_url: str) -> int | None:
    if not source_url:
        return None
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git|/.*)?$", source_url)
    if not m:
        return None
    owner, repo = m.groups()
    try:
        r = httpx.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            timeout=5,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if r.status_code == 200:
            return r.json().get("stargazers_count")
    except Exception:
        pass
    return None


# ── Import dialog ─────────────────────────────────────────────────────────────

@st.dialog("从 URL 导入 Skill", width="large")
def import_dialog():
    import re
    st.caption("支持 GitHub 仓库链接、单个文件链接、Gist 或任意公网 `skill.yaml`")

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

    url = st.text_input(
        "GitHub 仓库或文件 URL",
        placeholder="https://github.com/owner/repo  或  https://github.com/owner/repo/blob/main/skill.yaml",
    )

    is_repo = bool(url and re.match(r"https?://github\.com/[^/]+/[^/]+/?$", url.strip()))

    # ── Repo URL: scan & pick ──────────────────────────────────────────────────
    if is_repo:
        if st.button("🔍 扫描仓库 yaml 文件", use_container_width=True):
            with st.spinner("正在扫描 GitHub 仓库…"):
                try:
                    files = scan_github_repo(url.strip())
                    st.session_state["_repo_files"] = files
                    st.session_state["_repo_url"]   = url.strip()
                except Exception as e:
                    st.error(f"扫描失败：{e}")

        if "_repo_files" in st.session_state and st.session_state.get("_repo_url") == url.strip():
            files = st.session_state["_repo_files"]
            if not files:
                st.warning("该仓库中未找到 .yaml / .yml 文件")
            else:
                st.success(f"找到 {len(files)} 个 yaml 文件，选择要导入的：")
                options = {f"{f['path']}  [{f['type']}]": f["raw_url"] for f in files}
                selected = st.multiselect("选择文件", list(options.keys()))

                if selected and st.button(f"✓ 导入选中的 {len(selected)} 个文件", type="primary", use_container_width=True):
                    ok, fail = 0, []
                    for path in selected:
                        try:
                            import_url(options[path])
                            ok += 1
                        except Exception as e:
                            fail.append(f"{path}: {e}")
                    if ok:
                        st.success(f"✓ 成功导入 {ok} 个 Skill")
                    if fail:
                        st.warning("以下文件格式不兼容（缺少必填字段）：\n" + "\n".join(fail))
                    if ok:
                        for k in ("_repo_files", "_repo_url", "_preview", "_preview_url"):
                            st.session_state.pop(k, None)
                        st.rerun()

    # ── File URL: preview & import ─────────────────────────────────────────────
    else:
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("预览", use_container_width=True) and url:
                with st.spinner("获取中…"):
                    try:
                        st.session_state["_preview"]     = preview_url(url.strip())
                        st.session_state["_preview_url"] = url.strip()
                    except Exception as e:
                        st.error(f"获取失败：{e}")

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
                            st.session_state.pop("_preview", None)
                            st.session_state.pop("_preview_url", None)
                            st.success("导入成功！")
                            st.rerun()
                        except Exception as e:
                            st.error(f"导入失败：{e}")


# ── Grid view ─────────────────────────────────────────────────────────────────

def show_grid():
    # Header
    h1, h2, h3 = st.columns([6, 1, 0.4])
    with h1:
        st.markdown("# 硬件工程 skillhub")
        st.caption("集中展示团队外部精选的通用skills。支持从Github&任意公共网站一键引入外部Skill")
    with h2:
        st.write("")
        if st.button("＋ 导入 Skill", type="primary", use_container_width=True):
            import_dialog()
    with h3:
        st.write("")
        if st.button("⚙", use_container_width=True, help="管理员操作"):
            admin_dialog()

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
        st.markdown("""
<div style="text-align:center;padding:3rem 1rem">
  <div style="font-size:3rem;margin-bottom:1rem">📭</div>
  <h3 style="color:#e2e8f0;margin-bottom:.5rem">还没有任何 Skill</h3>
  <p style="color:#64748b;margin-bottom:2rem">点击右上角「＋ 导入 Skill」，粘贴 GitHub 上任意 skill.yaml 文件的链接即可引入。</p>
</div>
""", unsafe_allow_html=True)

        st.markdown("**可以去这些 GitHub 仓库搜索 Skill 文件：**")
        repos = [
            ("anthropics/skills",         "https://github.com/anthropics/skills"),
            ("openai/skills",             "https://github.com/openai/skills"),
            ("Jeffallan/claude-skills",   "https://github.com/Jeffallan/claude-skills"),
            ("awesome-agent-skills",      "https://github.com/search?q=awesome-agent-skills"),
            ("AI-Research-SKILLs",        "https://github.com/search?q=AI-Research-SKILLs"),
            ("claude-skills",             "https://github.com/search?q=claude-skills+skill.yaml"),
            ("claude-mem",                "https://github.com/search?q=claude-mem"),
            ("prompt-master",             "https://github.com/search?q=prompt-master+skill"),
        ]
        cols = st.columns(4)
        for i, (name, url) in enumerate(repos):
            cols[i % 4].markdown(f"[🔗 {name}]({url})")

        st.info("💡 找到 skill.yaml 文件后，复制它在 GitHub 上的链接，粘贴到「导入 Skill」对话框即可。", icon=None)
        return

    st.caption(f"{len(skills)} 个技能")

    # Build card HTML
    cards_html = '<div class="skill-grid">'
    for s in skills:
        if s.get("raw_content"):
            badge = '<span class="installable-badge">可安装</span>'
        elif s.get("source_url"):
            badge = '<span class="ext-badge">外部引入</span>'
        else:
            badge = ""
        cards_html += f"""
        <a class="skill-card" href="?skill={s['slug']}">
          {badge}
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

    st.markdown(f'<div class="back-btn"><a href="/">← 返回广场</a></div>', unsafe_allow_html=True)
    st.write("")

    # ── Header ──────────────────────────────────────────────────────────────────
    _cc = cat_class(skill["category"])
    stars = fetch_github_stars(skill.get("source_url") or "")
    star_str = f"  ·  ⭐ {stars:,}" if stars is not None else ""
    has_real_file = bool(skill.get("raw_content"))

    st.markdown(f'<span class="card-cat {_cc}">{skill["category"]}</span>', unsafe_allow_html=True)
    st.markdown(f"## {skill['icon']} {skill['name']}")
    st.markdown(
        f'<p style="color:#94a3b8;font-size:1rem;margin:-.5rem 0 .5rem">{skill["summary"]}</p>',
        unsafe_allow_html=True,
    )
    install_label = (
        '<span style="color:#34d399;font-size:.8rem">✅ 可安装</span>'
        if has_real_file else
        '<span style="color:#94a3b8;font-size:.8rem">📄 仅描述</span>'
    )
    st.markdown(
        f'👤 {skill["owner"]}  ·  {skill["output_type"].upper()}  ·  '
        f'{skill["call_count"]:,} 次下载{star_str}  ·  {install_label}',
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Main layout: description (left) | get & use (right) ─────────────────────
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown("#### 技能说明")
        st.markdown(skill["description"])

        schema = skill.get("input_schema") or []
        if schema:
            st.divider()
            st.markdown("#### 输入参数")
            for field in schema:
                req_badge = " `必填`" if field.get("required") else ""
                ftype = field.get("type", "text")
                parts = [f"类型：`{ftype}`"]
                if field.get("placeholder"):
                    parts.append(f"示例：`{field['placeholder']}`")
                if field.get("options"):
                    parts.append("选项：" + " / ".join(f"`{o}`" for o in field["options"]))
                if field.get("default") not in (None, ""):
                    parts.append(f"默认：`{field['default']}`")
                st.markdown(f"**{field['label']}**{req_badge}　　{'　　'.join(parts)}")

    with right:
        st.markdown("#### 获取与使用")

        # Download data
        _dl_keys = ["name", "slug", "icon", "category", "summary", "description",
                    "owner", "input_schema", "output_type", "execute_url", "source_url"]
        _dl_data = {k: skill[k] for k in _dl_keys if skill.get(k) not in (None, "", [])}

        col_a, col_b = st.columns(2)
        with col_a:
            st.download_button(
                "⬇ YAML（目录格式）",
                data=yaml.dump(_dl_data, allow_unicode=True, sort_keys=False),
                file_name=f"{skill['slug']}.yaml",
                mime="text/yaml",
                use_container_width=True,
            )
        with col_b:
            if has_real_file:
                st.download_button(
                    "⬇ SKILL.md（可安装）",
                    data=skill["raw_content"],
                    file_name=f"{skill['slug']}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            else:
                st.button(
                    "⬇ SKILL.md（暂无）",
                    disabled=True,
                    use_container_width=True,
                    help="此条目无真实实现文件。请点击下方来源链接前往 GitHub 查找原始 SKILL.md。",
                )

        if has_real_file:
            st.markdown("""
<div style="background:#161b27;border:1px solid #1e2535;border-radius:12px;padding:1.1rem 1.25rem;margin-top:.75rem">
<p style="color:#64748b;font-size:.75rem;margin:0 0 .9rem;font-weight:600;letter-spacing:.07em;text-transform:uppercase">在 Claude Code 中使用</p>
""", unsafe_allow_html=True)
            st.markdown("**Step 1** — 下载 `SKILL.md` 文件")
            st.markdown("**Step 2** — 安装到 Skills 目录")
            st.code(f"mv ~/Downloads/{skill['slug']}.md ~/.claude/skills/{skill['slug']}.md", language="bash")
            st.markdown("**Step 3** — 在 Claude Code 中调用")
            st.code(f"/{skill['slug']}", language="bash")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("此条目为描述性卡片，暂无可安装实现。点击下方来源链接前往 GitHub 查找真实 SKILL.md 文件。", icon="ℹ️")

        # ── Source ──────────────────────────────────────────────────────────────
        if skill.get("source_url"):
            st.divider()
            st.markdown("#### 来源")
            url_display = skill["source_url"].replace("https://", "").replace("http://", "")
            st.markdown(
                f'🔗 <a href="{skill["source_url"]}" target="_blank" '
                f'style="font-size:.85rem;color:#a5b4fc;font-family:monospace">{url_display}</a>',
                unsafe_allow_html=True,
            )
            if stars is not None:
                st.markdown(
                    f'<span style="font-size:.85rem;color:#fbbf24">⭐ {stars:,} stars on GitHub</span>',
                    unsafe_allow_html=True,
                )
            if skill.get("last_synced_at"):
                st.caption(f"上次同步：{str(skill['last_synced_at'])[:16]}")
            if st.button("🔄 同步更新", use_container_width=True):
                with st.spinner("同步中…"):
                    try:
                        sync_skill(slug)
                        st.success("同步完成")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))



# ── Admin panel ──────────────────────────────────────────────────────────────

@st.dialog("管理员操作", width="small")
def admin_dialog():
    pwd = st.text_input("管理员密码", type="password", placeholder="输入密码后操作")
    ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "hw2025admin")

    if pwd and pwd != ADMIN_PWD:
        st.error("密码错误")
        return
    if not pwd:
        return

    st.success("已验证")
    st.divider()

    st.markdown("**重新 Seed**　清空现有数据，从所有仓库重新导入")
    st.caption(f"共 {len(__import__('db').SEED_REPOS)} 个仓库，并发扫描，约 30-60 秒")

    if st.button("🔄 清空并重新导入", type="primary", use_container_width=True):
        status_text = st.empty()
        progress_bar = st.progress(0)
        total_repos = len(__import__('db').SEED_REPOS)
        state = {"scanned": 0, "imported": 0, "total_files": 0}

        def on_progress(phase, name, count):
            if phase == "scan":
                state["scanned"] += 1
                state["total_files"] = count
                pct = int(state["scanned"] / total_repos * 40)
                progress_bar.progress(pct)
                status_text.caption(f"🔍 扫描仓库 {state['scanned']}/{total_repos}，找到 {count} 个文件…")
            else:
                state["imported"] = count
                total = max(state["total_files"], 1)
                pct = 40 + int(count / total * 60)
                progress_bar.progress(min(pct, 99))
                status_text.caption(f"⬇ 导入中 {count}/{state['total_files']}…")

        try:
            n = reseed(clear_existing=True, on_progress=on_progress)
            progress_bar.progress(100)
            status_text.empty()
            st.success(f"✅ 完成！共导入 {n} 个 Skill")
            st.rerun()
        except Exception as e:
            st.error(f"失败：{e}")


# ── Router ────────────────────────────────────────────────────────────────────

slug = st.query_params.get("skill", "")
if slug:
    show_detail(slug)
else:
    show_grid()
