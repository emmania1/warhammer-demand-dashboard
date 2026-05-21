"""
Warhammer Demand Intelligence — HTML Report Generator (Phase 3: Structural Growth)

Changes from Phase 2:
  - Removed: Google Trends section, chart, and all related stat cards
  - Added: YouTube Channel YoY Expansion section (with N/A placeholders while history builds)
  - Added: Trailer & Tentpole Reveals section
  - Added: New Player Funnel Signals section
  - Reframed: All sections for structural/YoY growth, not weekly noise
  - Updated: Reddit member table to show 1yr/2yr growth (no 7d deltas)
  - Updated: Steam table to show YoY player growth (no 7d deltas)
  - Updated: Data health to reflect new signal priorities
"""

import json, os, re, webbrowser
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

SUMMARY_FILE = "weekly_summary.json"
REPORT_FILE  = "demand_report.txt"
OUTPUT_FILE  = "demand_report.html"


# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_num(val):
    if val is None: return "—"
    try:
        v = float(val)
        if v >= 1_000_000: return f"{v/1_000_000:.2f}M"
        if v >= 1_000:     return f"{v/1_000:.1f}K"
        return str(int(v))
    except Exception:
        return str(val)

def fmt_pct(val, decimals=1):
    if val is None: return "—"
    try:
        v = float(val)
        arrow = "▲" if v > 0 else ("▼" if v < 0 else "—")
        color = "var(--green)" if v > 0 else ("var(--red)" if v < 0 else "inherit")
        return f'<span style="color:{color}">{arrow} {v:+.{decimals}f}%</span>'
    except Exception:
        return str(val)

def fmt_delta(val):
    if val is None: return "—"
    try:
        v = int(float(val))
        if v > 0: return f'<span style="color:var(--green)">▲ +{fmt_num(v)}</span>'
        elif v < 0: return f'<span style="color:var(--red)">▼ {fmt_num(v)}</span>'
        return "— 0"
    except Exception:
        return str(val)

def fmt_pct_or_na(val, na_text='<span style="color:var(--muted);font-size:11px">building…</span>'):
    """Render percentage or a 'building' placeholder if None."""
    if val is None:
        return na_text
    return fmt_pct(val)

def extract_analyst_narrative(report_text):
    marker = "RAW DATA TABLES"
    idx = report_text.find(marker)
    if idx == -1: return report_text
    start = report_text.find("ANALYST BRIEFING")
    if start != -1:
        start = report_text.find("\n", start) + 1
        dash_end = report_text.find("\n", start) + 1
        narrative = report_text[dash_end:idx].strip()
    else:
        narrative = report_text[:idx].strip()
    parts = re.split(r'\n(SECTION \d+[^\n]+)\n', narrative)
    html_parts = []
    for part in parts:
        if re.match(r'SECTION \d+', part):
            html_parts.append(f'<h3 class="section-heading">{part.strip()}</h3>')
        else:
            paras = [p.strip() for p in part.split('\n\n') if p.strip()]
            for para in paras:
                html_parts.append(f'<p>{para}</p>')
    return '\n'.join(html_parts)


# ── Data health checker ───────────────────────────────────────────────────────

def build_data_health(summary):
    checks = []
    def chk(metric, value, ok_fn, warn_note, ok_note="ok"):
        if value is None:
            checks.append({"metric": metric, "status": "missing", "note": warn_note})
        elif ok_fn(value):
            checks.append({"metric": metric, "status": "ok", "note": ok_note})
        else:
            checks.append({"metric": metric, "status": "warn", "note": warn_note})

    # Reddit
    re_ = summary.get("reddit_ecosystem", {})
    subs = re_.get("subreddits", [])
    m30 = [s for s in subs if s.get("structural_30d_comments_pct") is not None]
    checks.append({"metric": "Reddit — 30d structural engagement",
                   "status": "ok" if m30 else "warn",
                   "note": f"{len(m30)}/{len(subs)} subreddits have 30d data"})
    mc = re_.get("member_counts", [])
    checks.append({"metric": "Reddit — member counts (live API)",
                   "status": "ok" if mc else "missing",
                   "note": f"{len(mc)} subs tracked" if mc else "Run fetch_reddit_members.py"})
    checks.append({"metric": "Reddit — member history (charts)",
                   "status": "ok" if re_.get("member_history") else "warn",
                   "note": f"{len(re_.get('member_history',{}))} subs have time series"})
    mc_yoy = [m for m in mc if m.get("growth_1y_pct") is not None]
    checks.append({"metric": "Reddit — 1-year member growth",
                   "status": "ok" if mc_yoy else "warn",
                   "note": f"{len(mc_yoy)}/{len(mc)} subs have 1yr reference" if mc else "No member data yet"})

    # YouTube channels
    ytc = summary.get("youtube_channels", {})
    snaps_ytc = ytc.get("snapshots_available", 0)
    chk("YouTube — channel snapshots", snaps_ytc,
        lambda v: v >= 2, f"Only {snaps_ytc} snapshot(s) — need 2+ for deltas", f"{snaps_ytc} snapshots collected")
    yoy_avail = ytc.get("yoy_data_available", False)
    checks.append({"metric": "YouTube — YoY tracking readiness",
                   "status": "ok" if yoy_avail else "warn",
                   "note": "52+ snapshots — YoY live" if yoy_avail else f"{snaps_ytc}/52 weekly snapshots collected (building history)"})

    # YouTube videos
    ytv = summary.get("youtube_videos", {})
    snaps_ytv = ytv.get("snapshots_available", 0)
    chk("YouTube — video snapshots", snaps_ytv,
        lambda v: v >= 2, f"Only {snaps_ytv} snapshot — gainers N/A", f"{snaps_ytv} snapshots")
    trailer_count = ytv.get("trailers", {}).get("total_found", 0)
    checks.append({"metric": "YouTube — trailer / reveal signals",
                   "status": "ok" if trailer_count > 0 else "warn",
                   "note": f"{trailer_count} trailer/reveal videos detected" if trailer_count else "No trailer keywords matched in current video library"})
    beg_count = ytv.get("beginner_funnel", {}).get("total_videos", 0)
    checks.append({"metric": "YouTube — beginner funnel videos",
                   "status": "ok" if beg_count > 5 else ("warn" if beg_count > 0 else "missing"),
                   "note": f"{beg_count} beginner/starter videos in library" if beg_count else "No beginner keyword matches"})

    # Steam
    steam = summary.get("steam", {})
    games = steam.get("games", [])
    gp = [g for g in games if g.get("current_players") is not None]
    go = [g for g in games if g.get("owners_low") is not None]
    gy = [g for g in games if g.get("growth_1y_players_pct") is not None]
    checks.append({"metric": "Steam — player counts",
                   "status": "ok" if gp else "missing", "note": f"{len(gp)}/{len(games)} games"})
    checks.append({"metric": "Steam — YoY player growth",
                   "status": "ok" if gy else "warn",
                   "note": f"{len(gy)} games have YoY player data" if gy else "Need 12mo history — building"})
    checks.append({"metric": "Steam — owner estimates (SteamSpy)",
                   "status": "ok" if go else "warn",
                   "note": f"{len(go)} games" if go else "SteamSpy not returning data"})

    # WarCom
    wc = summary.get("warcom", {})
    chk("WarCom — 7d article count",  wc.get("articles_last_7d"),  lambda v: v > 0, "No data")
    chk("WarCom — 30d article count", wc.get("articles_last_30d"), lambda v: v > 0, "Homepage proxy (same as 7d)")
    if wc.get("method") == "homepage_links":
        checks.append({"metric": "WarCom — data quality", "status": "warn",
                       "note": "Homepage link proxy — not date-filtered. 7d ≈ 30d count is expected."})

    # Competitive & retail
    comp = summary.get("competitive_events", [])
    checks.append({"metric": "Competitive events",
                   "status": "ok" if comp else "missing",
                   "note": f"{len(comp)} events" if comp else "BCP/Longshanks not accessible — manual entry possible"})
    retail = summary.get("retail_signals", [])
    checks.append({"metric": "Retail signals",
                   "status": "ok" if retail else "warn",
                   "note": f"{len(retail)} signals" if retail else "No Warhammer keyword matches found"})
    return checks


# ── Main HTML builder ─────────────────────────────────────────────────────────

def build_html(summary, report_text):
    date_str  = summary.get("date", str(datetime.now().date()))
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    narrative = extract_analyst_narrative(report_text)
    dh        = build_data_health(summary)

    reddit  = summary.get("reddit_ecosystem", {})
    yt_ch   = summary.get("youtube_channels", {})
    yt_vid  = summary.get("youtube_videos", {})
    steam   = summary.get("steam", {})
    warcom  = summary.get("warcom", {})
    comp    = summary.get("competitive_events", [])
    retail  = summary.get("retail_signals", [])

    # ── Chart data (pre-computed JSON) ─────────────────────────────────────────

    # Reddit members bar (sorted desc, Sept 2025 vs Now)
    mc_list = sorted(reddit.get("member_counts", []), key=lambda x: -(x.get("members") or 0))
    mh      = reddit.get("member_history", {})
    j_rl   = json.dumps([f"r/{m['subreddit']}" for m in mc_list])
    j_rnow = json.dumps([m.get("members") or 0 for m in mc_list])
    sept25 = []
    for m in mc_list:
        hist = mh.get(m["subreddit"], [])
        hit  = next((h["members"] for h in hist if str(h.get("date",""))[:7] == "2025-09"), None)
        sept25.append(hit)
    j_rs25 = json.dumps(sept25)

    # r/Warhammer40k growth trajectory
    w40k_hist = mh.get("Warhammer40k", [])
    j_w40k_d  = json.dumps([h["date"] for h in w40k_hist])
    j_w40k_m  = json.dumps([h["members"] for h in w40k_hist])

    # YouTube channels bar (sorted by subs desc)
    yt_active = sorted([c for c in yt_ch.get("channels", []) if (c.get("subscribers") or 0) > 0],
                       key=lambda x: -(x.get("subscribers") or 0))
    j_ytl = json.dumps([c["label"].replace("_", " ") for c in yt_active])
    j_yts = json.dumps([c.get("subscribers", 0) or 0 for c in yt_active])
    j_ytv = json.dumps([round((c.get("total_views") or 0) / 1e6, 1) for c in yt_active])

    # Steam bar (non-zero, sorted)
    st_active = sorted([g for g in steam.get("games", []) if (g.get("current_players") or 0) > 0],
                       key=lambda x: -(x.get("current_players") or 0))
    j_stl = json.dumps([g["label"].replace("_", " ") for g in st_active])
    j_stp = json.dumps([g.get("current_players") or 0 for g in st_active])

    # ── Context callout strings ────────────────────────────────────────────────

    # Reddit context
    top_sub       = mc_list[0] if mc_list else {}
    total_members = sum(m.get("members") or 0 for m in mc_list)
    strong_growth = [m for m in mc_list if (m.get("growth_1y_pct") or 0) > 15]
    if top_sub.get("members"):
        reddit_ctx = (f"<strong>{len(mc_list)} Warhammer communities</strong> collectively hold "
                      f"<strong>{fmt_num(total_members)} members</strong>. "
                      f"r/{top_sub['subreddit']} leads at "
                      f"<strong>{fmt_num(top_sub['members'])} members</strong>, "
                      f"having surpassed 1M in October 2024.")
    else:
        reddit_ctx = ""

    # YouTube ecosystem context
    total_yt_subs  = yt_ch.get("total_ecosystem_subscribers") or sum(c.get("subscribers", 0) or 0 for c in yt_active)
    total_yt_views = yt_ch.get("total_ecosystem_views") or sum(c.get("total_views", 0) or 0 for c in yt_active)
    yoy_avail      = yt_ch.get("yoy_data_available", False)
    n_snaps        = yt_ch.get("snapshots_available", 0)
    yoy_status     = "YoY growth rates live" if yoy_avail else f"YoY rates building — {n_snaps}/52 weekly snapshots collected"
    if yt_active:
        yt_ctx = (f"<strong>{len(yt_active)} active channels</strong> tracked across the creator ecosystem — "
                  f"<strong>{fmt_num(total_yt_subs)} combined subscribers</strong> and "
                  f"<strong>{fmt_num(total_yt_views)} lifetime views</strong>. "
                  f"{yoy_status}.")
    else:
        yt_ctx = ""

    # Trailer context
    trailers_data  = yt_vid.get("trailers", {})
    trailer_count  = trailers_data.get("total_found", 0)
    if trailer_count:
        trailer_ctx = (f"<strong>{trailer_count} trailer, preview, or reveal videos</strong> detected in the tracked channel library. "
                       f"Top results ranked by total view count.")
    else:
        trailer_ctx = "No trailer or reveal keyword matches in the current video library. Content will appear as channels post trailers/previews."

    # Beginner funnel context
    beg      = yt_vid.get("beginner_funnel", {})
    beg_tot  = beg.get("total_videos", 0)
    beg_90d  = beg.get("last_90d_count", 0)
    beg_90v  = beg.get("last_90d_views", 0)
    beg_1yv  = beg.get("last_1y_views", 0)
    if beg_tot:
        beg_ctx = (f"<strong>{beg_tot} beginner/starter videos</strong> identified across tracked channels. "
                   f"<strong>{beg_90d} published in the last 90 days</strong>, accumulating "
                   f"<strong>{fmt_num(beg_90v)} views</strong>. "
                   f"Last 12 months: <strong>{fmt_num(beg_1yv)} views</strong> on new-player-focused content.")
    else:
        beg_ctx = "No beginner or starter keyword matches in current library. Funnel metrics will populate as content is indexed."

    # Steam context
    sm2         = next((g for g in steam.get("games", [])
                        if "space_marine" in g.get("label","").lower() or "Space_Marine" in g.get("label","")), None)
    total_pl    = steam.get("total_players", 0)
    if sm2 and sm2.get("owners_low"):
        steam_ctx = (f"<strong>{fmt_num(total_pl)} concurrent players</strong> across all tracked titles. "
                     f"Space Marine 2: <strong>{fmt_num(sm2.get('owners_low'))}–{fmt_num(sm2.get('owners_high'))} copies sold</strong> "
                     f"(SteamSpy est.) at <strong>{sm2.get('positive_pct', 0):.0f}% positive</strong> — "
                     f"the largest digital launch in franchise history.")
    else:
        steam_ctx = f"<strong>{fmt_num(total_pl)} concurrent players</strong> across all tracked titles."

    # ── Table row builders ─────────────────────────────────────────────────────

    # Reddit engagement (30d structural only)
    reddit_rows = ""
    for sub in sorted(reddit.get("subreddits", []), key=lambda x: x.get("subreddit", "")):
        reddit_rows += (f"<tr><td>r/{sub['subreddit']}</td>"
                        f"<td>{fmt_pct(sub.get('structural_30d_comments_pct'))}</td></tr>\n")

    # Reddit member platform note
    hist_ctx = reddit.get("history_context", {})
    platform_note_html = (f'<div class="callout callout-warn">⚠ {hist_ctx.get("platform_note","")}</div>'
                          if hist_ctx.get("platform_note") else "")

    # Reddit key takeaways
    takeaways = []
    if top_sub.get("members"):
        takeaways.append(f'✅ <strong>r/{top_sub["subreddit"]}</strong> leads at <strong>{fmt_num(top_sub["members"])}</strong> members — surpassed 1M in October 2024.')
    for m in strong_growth[:2]:
        if m.get("growth_1y_pct"):
            takeaways.append(f'✅ <strong>r/{m["subreddit"]}</strong> grew <strong>{m["growth_1y_pct"]:+.1f}%</strong> year-over-year — sustained structural expansion.')
    takeaways.append("⚠️ Reddit removed public subscriber counts from the web in <strong>September 2025</strong>. The API still returns live accurate values used here.")
    takeaways.append("ℹ️ Historical annual growth has ranged <strong>13–25%</strong> across major Warhammer subs. Weekly tracking began February 2026.")
    takeaways_html = "".join(f"<li>{t}</li>" for t in takeaways)

    # Reddit member table (new columns: since Sept 25, 1yr, 2yr growth)
    member_rows = ""
    for m in mc_list:
        oldest    = m.get("oldest_data_point") or {}
        oldest_str = f"{str(oldest.get('date',''))[:7]}: {fmt_num(oldest.get('members'))}" if oldest.get("members") else "—"
        member_rows += (f"<tr><td>r/{m['subreddit']}</td>"
                        f"<td><strong>{fmt_num(m.get('members'))}</strong></td>"
                        f"<td>{fmt_pct_or_na(m.get('growth_5m_pct'))}</td>"
                        f"<td>{fmt_pct_or_na(m.get('growth_1y_pct'))}</td>"
                        f"<td>{fmt_pct_or_na(m.get('growth_2y_pct'))}</td>"
                        f"<td style='color:var(--muted);font-size:12px'>{oldest_str}</td>"
                        f"</tr>\n")

    # YouTube channel rows (YoY growth columns)
    na_label = '<span style="color:var(--muted);font-size:11px">building…</span>'
    yt_ch_rows = ""
    for ch in yt_active:
        yt_ch_rows += (f"<tr><td>{ch['label'].replace('_',' ')}</td>"
                       f"<td>{fmt_num(ch['subscribers'])}</td>"
                       f"<td>{fmt_num(ch['total_views'])}</td>"
                       f"<td>{fmt_pct_or_na(ch.get('growth_1y_subs_pct'), na_label)}</td>"
                       f"<td>{fmt_pct_or_na(ch.get('growth_2y_subs_pct'), na_label)}</td>"
                       f"<td>{fmt_pct_or_na(ch.get('growth_1y_views_pct'), na_label)}</td></tr>\n")

    # Trailer rows
    trailer_rows = ""
    for i, v in enumerate(trailers_data.get("top_trailers", [])[:12], 1):
        title = v['title'][:65] + "…" if len(v['title']) > 65 else v['title']
        pub   = str(v.get('published_at', ''))[:10]
        trailer_rows += (f"<tr><td>{i}</td><td>{v.get('channel_label','').replace('_',' ')}</td>"
                         f"<td>{title}</td><td>{fmt_num(v.get('views'))}</td>"
                         f"<td>{pub}</td>"
                         f"<td>{v.get('views_per_day', 0):.0f}/d</td></tr>\n")

    # Beginner funnel rows
    beg_rows = ""
    for i, v in enumerate(beg.get("top_videos", [])[:10], 1):
        title = v['title'][:65] + "…" if len(v['title']) > 65 else v['title']
        beg_rows += (f"<tr><td>{i}</td><td>{v.get('channel_label','').replace('_',' ')}</td>"
                     f"<td>{title}</td><td>{fmt_num(v.get('views'))}</td>"
                     f"<td>{v.get('views_per_day', 0):.0f}/d</td>"
                     f"<td>{str(v.get('published_at',''))[:10]}</td></tr>\n")

    # Top videos last 60d
    top_vid_rows = ""
    for i, v in enumerate(yt_vid.get("top_recent_60d", [])[:10], 1):
        title = v['title'][:65] + "…" if len(v['title']) > 65 else v['title']
        top_vid_rows += (f"<tr><td>{i}</td><td>{v['channel_label'].replace('_',' ')}</td>"
                         f"<td>{title}</td><td>{fmt_num(v['views'])}</td>"
                         f"<td>{v['views_per_day']:.0f}/d</td></tr>\n")

    # All-time top videos
    alltime_rows = ""
    for i, v in enumerate(yt_vid.get("top_all_time", [])[:10], 1):
        title = v['title'][:65] + "…" if len(v['title']) > 65 else v['title']
        alltime_rows += (f"<tr><td>{i}</td><td>{v['channel_label'].replace('_',' ')}</td>"
                         f"<td>{title}</td><td>{fmt_num(v['views'])}</td>"
                         f"<td>{str(v.get('published_at',''))[:10]}</td></tr>\n")

    # Fastest rising (gainers or velocity proxy)
    gainers       = yt_vid.get("top_view_gainers_7d", [])
    velocity      = yt_vid.get("top_velocity_proxy", [])
    gainer_label  = "Fastest Rising — Actual 7d View Gain" if gainers else \
                    "Fastest Rising — Daily Velocity Proxy (single snapshot)"
    gainer_note   = "" if gainers else \
        '<div class="callout callout-warn">⚠ Only 1 snapshot available. Showing views/day for videos published in the last 30 days as a velocity proxy. Actual 7d deltas will appear after the second weekly run.</div>'
    gainer_rows, gainer_hdr = "", ""
    if gainers:
        gainer_hdr = "<th>#</th><th>Channel</th><th>Title</th><th>Views</th><th>7d +Views</th>"
        for i, v in enumerate(gainers[:10], 1):
            title = v['title'][:60] + "…" if len(v['title']) > 60 else v['title']
            gainer_rows += (f"<tr><td>{i}</td><td>{v.get('channel_label','').replace('_',' ')}</td>"
                            f"<td>{title}</td><td>{fmt_num(v['views'])}</td>"
                            f"<td>{fmt_delta(v.get('views_delta_7d'))}</td></tr>\n")
    elif velocity:
        gainer_hdr = "<th>#</th><th>Channel</th><th>Title</th><th>Views</th><th>Velocity</th>"
        for i, v in enumerate(velocity[:10], 1):
            title = v['title'][:60] + "…" if len(v['title']) > 60 else v['title']
            gainer_rows += (f"<tr><td>{i}</td><td>{v.get('channel_label','').replace('_',' ')}</td>"
                            f"<td>{title}</td><td>{fmt_num(v.get('views'))}</td>"
                            f"<td>{v.get('views_per_day',0):.0f}/d <small>(~{fmt_num(v.get('est_7d_views'))}/wk)</small></td></tr>\n")

    # Steam rows (new: YoY player growth instead of 7d delta)
    steam_rows = ""
    steam_yoy_avail = steam.get("yoy_available", False)
    for g in steam.get("games", []):
        if not g.get("current_players") and not g.get("total_reviews"):
            continue
        pos     = f"{g['positive_pct']:.0f}%" if g.get("positive_pct") else "—"
        owners  = (f"{fmt_num(g.get('owners_low'))}–{fmt_num(g.get('owners_high'))}"
                   if g.get("owners_low") and g.get("owners_high") else "—")
        playtime = f"{g['avg_playtime_2w_min']}m" if g.get("avg_playtime_2w_min") else "—"
        yoy_p   = fmt_pct(g.get('growth_1y_players_pct')) if g.get('growth_1y_players_pct') is not None else \
                  '<span style="color:var(--muted);font-size:11px">building…</span>'
        steam_rows += (f"<tr><td>{g['label'].replace('_',' ')}</td>"
                       f"<td>{fmt_num(g.get('current_players'))}</td>"
                       f"<td>{yoy_p}</td>"
                       f"<td>{fmt_num(g.get('total_reviews'))}</td>"
                       f"<td>{pos}</td><td>{owners}</td><td>{playtime}</td></tr>\n")

    # Competitive events
    comp_note = ""
    comp_table = ""
    if comp:
        rows = "".join(
            f"<tr><td>{str(ev.get('event_date',''))[:10]}</td><td>{ev.get('system','')}</td>"
            f"<td>{str(ev.get('event_name',''))[:60]}</td>"
            f"<td>{fmt_num(ev.get('player_count')) if ev.get('player_count') else '—'}</td>"
            f"<td>{ev.get('location','')}</td><td>{ev.get('source','')}</td></tr>\n"
            for ev in comp[:10]
        )
        comp_table = f'<table><thead><tr><th>Date</th><th>System</th><th>Event</th><th>Players</th><th>Location</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table>'
    else:
        comp_note = '<div class="callout callout-warn">⚠ No tournament data yet. BCP/Longshanks not accessible on last fetch. Data populates once accessible or via manual CSV entry.</div>'

    # Retail signals
    retail_note = ""
    retail_table = ""
    if retail:
        rows = ""
        for r in retail[:10]:
            badges = "".join(
                f'<span class="badge badge-{s.split("_")[0]}">{s}</span>'
                for s in str(r.get("signal_types","")).split("|") if s
            )
            rows += (f"<tr><td>{r.get('channel_label','').replace('_',' ')}</td>"
                     f"<td>{str(r.get('published_at',''))[:10]}</td>"
                     f"<td>{str(r.get('title',''))[:65]}</td>"
                     f"<td>{fmt_num(r.get('views'))}</td>"
                     f"<td>{badges}</td></tr>\n")
        retail_table = f'<table><thead><tr><th>Channel</th><th>Published</th><th>Title</th><th>Views</th><th>Signals</th></tr></thead><tbody>{rows}</tbody></table>'
    else:
        retail_note = '<div class="callout">ℹ No Warhammer retail keyword signals found in current video data. Signals appear when tracked channels post videos mentioning pre-orders, restocks, sold-out products, etc.</div>'

    # Data health rows
    si = {"ok": "✅", "warn": "⚠️", "missing": "❌"}
    sc = {"ok": "health-ok", "warn": "health-warn", "missing": "health-miss"}
    health_rows = "".join(
        f'<tr class="{sc.get(h["status"],"")}"><td>{si.get(h["status"],"?")}</td>'
        f'<td>{h["metric"]}</td><td>{h["note"]}</td></tr>\n'
        for h in dh
    )

    # ── Chart.js static initialisation (no f-string — no brace escaping) ─────
    chart_init = """
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js"></script>
<script>
Chart.defaults.color = '#8b949e';
Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";

const CD = window.__chartData;
const gridColor = '#21262d';
function fmtK(v) {
    if (v >= 1e6) return (v/1e6).toFixed(1)+'M';
    if (v >= 1e3) return (v/1e3).toFixed(0)+'K';
    return String(v);
}

// ── r/Warhammer40k member growth line chart ──
(function(){
    const el = document.getElementById('chartW40k');
    if (!el || !CD.w40k_d.length) return;
    new Chart(el, {
        type: 'line',
        data: {
            labels: CD.w40k_d,
            datasets: [{
                label: 'r/Warhammer40k Members',
                data: CD.w40k_m,
                borderColor: '#d4a017',
                backgroundColor: 'rgba(212,160,23,0.08)',
                fill: true, tension: 0.3,
                pointRadius: 5, pointBackgroundColor: '#d4a017',
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: gridColor }, ticks: { color: '#8b949e' } },
                y: {
                    grid: { color: gridColor },
                    ticks: { color: '#8b949e', callback: fmtK }
                }
            }
        }
    });
})();

// ── Reddit community size horizontal bar chart ──
(function(){
    const el = document.getElementById('chartReddit');
    if (!el || !CD.rl.length) return;
    new Chart(el, {
        type: 'bar',
        data: {
            labels: CD.rl,
            datasets: [{
                label: 'Members — Feb 2026 (live API)',
                data: CD.rnow,
                backgroundColor: '#c0392b',
            },{
                label: 'Members — Sept 2025 (pre-hide estimate)',
                data: CD.rs25,
                backgroundColor: '#4a1515',
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#8b949e', boxWidth: 12 } } },
            scales: {
                x: { grid: { color: gridColor }, ticks: { color: '#8b949e', callback: fmtK } },
                y: { grid: { color: gridColor }, ticks: { color: '#8b949e' } }
            }
        }
    });
})();

// ── YouTube subscribers horizontal bar chart ──
(function(){
    const el = document.getElementById('chartYT');
    if (!el || !CD.ytl.length) return;
    new Chart(el, {
        type: 'bar',
        data: {
            labels: CD.ytl,
            datasets: [{
                label: 'Subscribers',
                data: CD.yts,
                backgroundColor: 'rgba(231,76,60,0.75)',
                borderColor: '#e74c3c',
                borderWidth: 1,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: gridColor }, ticks: { color: '#8b949e', callback: fmtK } },
                y: { grid: { color: gridColor }, ticks: { color: '#8b949e' } }
            }
        }
    });
})();

// ── Steam concurrent players bar chart ──
(function(){
    const el = document.getElementById('chartSteam');
    if (!el || !CD.stl.length) return;
    const PALETTE = ['#c0392b','#e74c3c','#e5852a','#d4a017','#3fb950','#58a6ff'];
    new Chart(el, {
        type: 'bar',
        data: {
            labels: CD.stl,
            datasets: [{
                label: 'Concurrent Players (now)',
                data: CD.stp,
                backgroundColor: CD.stl.map((_,i) => PALETTE[i % PALETTE.length]),
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: gridColor }, ticks: { color: '#8b949e' } },
                y: { grid: { color: gridColor }, ticks: { color: '#8b949e' } }
            }
        }
    });
})();
</script>
"""

    # ── Full HTML ─────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Warhammer Demand Intelligence — {date_str}</title>
<style>
  :root {{
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e;
    --accent: #c0392b; --accent2: #e74c3c;
    --green: #3fb950; --red: #f85149; --gold: #d4a017;
    --orange: #e5852a; --blue: #58a6ff; --purple: #bc8cff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; line-height: 1.6; }}
  .header {{ background: linear-gradient(135deg, #1a0000 0%, #2d0808 50%, #1a0000 100%); border-bottom: 2px solid var(--accent); padding: 28px 40px; }}
  .header h1 {{ font-size: 24px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #fff; }}
  .header .sub {{ color: var(--muted); margin-top: 4px; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; }}
  .container {{ max-width: 1150px; margin: 0 auto; padding: 24px 20px; }}
  .section {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 18px; }}
  .section-title {{ font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--accent2); margin-bottom: 14px; padding-bottom: 8px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; }}
  .ctx {{ font-size: 13px; color: #cdd9e5; background: var(--bg); border-left: 3px solid var(--accent); padding: 10px 14px; border-radius: 0 6px 6px 0; margin-bottom: 14px; line-height: 1.7; }}
  .callout {{ font-size: 12px; padding: 9px 13px; border-radius: 0 5px 5px 0; margin-bottom: 12px; line-height: 1.6; }}
  .callout {{ background: rgba(88,166,255,0.06); border-left: 3px solid var(--blue); color: #aac; }}
  .callout-warn {{ background: rgba(212,160,23,0.08); border-left: 3px solid var(--gold); color: var(--gold); }}
  .narrative .section-heading {{ font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--gold); margin: 18px 0 6px; }}
  .narrative p {{ color: #cdd9e5; line-height: 1.85; margin-bottom: 10px; }}
  .stats-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }}
  .stat-card {{ background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 10px 14px; min-width: 110px; flex: 1; }}
  .stat-label {{ font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 3px; }}
  .stat-value {{ font-size: 20px; font-weight: 700; color: var(--text); }}
  .stat-sub {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}
  .chart-wrap {{ position: relative; height: 240px; margin-bottom: 14px; }}
  .chart-wrap-sm {{ position: relative; height: 180px; margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; padding: 7px 10px; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); border-bottom: 1px solid var(--border); white-space: nowrap; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #21262d; vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: rgba(255,255,255,0.02); }}
  .takeaways {{ background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 14px 18px; margin-bottom: 16px; }}
  .takeaways .tk-label {{ font-size: 10px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--muted); margin-bottom: 9px; }}
  .takeaways ul {{ list-style: none; display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #cdd9e5; }}
  .badge {{ display: inline-block; font-size: 10px; padding: 1px 6px; border-radius: 3px; margin: 1px; white-space: nowrap; }}
  .badge-sales    {{ background: #1a3a1a; color: var(--green);  border: 1px solid var(--green); }}
  .badge-sold     {{ background: #3a1a1a; color: var(--red);    border: 1px solid var(--red); }}
  .badge-new      {{ background: #1a2a3a; color: var(--blue);   border: 1px solid var(--blue); }}
  .badge-industry {{ background: #2a1a3a; color: var(--purple); border: 1px solid var(--purple); }}
  .badge-discount {{ background: #3a2a1a; color: var(--orange); border: 1px solid var(--orange); }}
  .badge-demand   {{ background: #3a3a1a; color: var(--gold);   border: 1px solid var(--gold); }}
  .badge-tag      {{ background: #1a2a1a; color: var(--accent2); border: 1px solid var(--accent); font-size: 9px; padding: 1px 5px; }}
  .health-ok   td {{ color: #cdd9e5; }}
  .health-warn td {{ color: var(--gold); }}
  .health-miss td {{ color: var(--red); }}
  .footer {{ text-align: center; color: var(--muted); font-size: 11px; padding: 20px; border-top: 1px solid var(--border); margin-top: 4px; }}
  span[style*="color:green"] {{ color: var(--green) !important; }}
  span[style*="color:red"]   {{ color: var(--red)   !important; }}
</style>
</head>
<body>

<div class="header">
  <h1>⚔ Warhammer Demand Intelligence</h1>
  <div class="sub">Week of {date_str} &nbsp;|&nbsp; Generated {generated} &nbsp;|&nbsp; Reddit · YouTube · Steam · WarCom · Structural Growth Focus</div>
</div>

<div class="container">

<!-- ═══ ANALYST BRIEFING ═════════════════════════════════════════════════════ -->
<div class="section narrative">
  <div class="section-title">Analyst Briefing — Structural Growth Assessment</div>
  {narrative if narrative else '<p style="color:var(--muted)">Run generate_demand_report.py to generate the narrative.</p>'}
</div>

<!-- ═══ REDDIT COMMUNITY BASE ════════════════════════════════════════════════ -->
<div class="section">
  <div class="section-title">Community Base — Reddit Structural Engagement</div>
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-label">Ecosystem 30d Structural Trend</div>
      <div class="stat-value" style="font-size:18px">{fmt_pct(reddit.get('ecosystem_structural_30d_comments_pct'))}</div>
      <div class="stat-sub">combined comment volume (first 14d vs last 14d of 28d window)</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Total Community Members</div>
      <div class="stat-value">{fmt_num(total_members)}</div>
      <div class="stat-sub">across {len(mc_list)} tracked subreddits</div>
    </div>
  </div>
  <table>
    <thead><tr><th>Subreddit</th><th>30d Structural Trend</th></tr></thead>
    <tbody>{reddit_rows}</tbody>
  </table>
</div>

<!-- ═══ REDDIT COMMUNITY SIZE & HISTORICAL GROWTH ════════════════════════════ -->
<div class="section">
  <div class="section-title">Community Size &amp; Long-Term Member Growth</div>
  {f'<div class="ctx">{reddit_ctx}</div>' if reddit_ctx else ""}
  {platform_note_html}
  {"" if member_rows else '<div class="callout callout-warn">⚠ No member count data yet — run fetch_reddit_members.py</div>'}

  <div class="takeaways">
    <div class="tk-label">Key Structural Takeaways</div>
    <ul>{takeaways_html}</ul>
  </div>

  <!-- Community size comparison bar -->
  <div class="chart-wrap" style="height:260px">
    <canvas id="chartReddit"></canvas>
  </div>

  <!-- r/Warhammer40k growth trajectory -->
  <div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:6px;">r/Warhammer40k — Long-Term Member Growth Trajectory</div>
  <div class="chart-wrap-sm">
    <canvas id="chartW40k"></canvas>
  </div>

  <!-- Member growth table -->
  <table>
    <thead>
      <tr>
        <th>Subreddit</th>
        <th>Members (live API)</th>
        <th>Since Sept '25</th>
        <th>1-Year Growth</th>
        <th>2-Year Growth</th>
        <th>Oldest Data Point</th>
      </tr>
    </thead>
    <tbody>{member_rows}</tbody>
  </table>
  <p style="font-size:11px;color:var(--muted);margin-top:10px">
    Since Sept '25 = growth from Sept 2025 estimate → current live count (post-Reddit-hide period).
    1-Year &amp; 2-Year growth rates require reference snapshots — <em>building…</em> appears until sufficient history is available.
    Historical annual growth: <strong>13–25%</strong> across major Warhammer communities.
  </p>
</div>

<!-- ═══ YOUTUBE CREATOR ECOSYSTEM ════════════════════════════════════════════ -->
<div class="section">
  <div class="section-title">YouTube Creator Ecosystem — Channel Scale &amp; Expansion
    &nbsp;<small style="color:var(--muted);font-weight:400">({n_snaps} snapshot(s) · {yt_ch.get('as_of','')})</small>
  </div>
  {f'<div class="ctx">{yt_ctx}</div>' if yt_ctx else ""}
  {"" if yoy_avail else f'<div class="callout callout-warn">⚠ YoY subscriber growth rates require 52 weekly snapshots ({n_snaps} collected so far). Columns show <em>building…</em> until available. All current subscriber and view counts are live.</div>'}

  <!-- Subscribers bar chart -->
  <div class="chart-wrap" style="height:280px">
    <canvas id="chartYT"></canvas>
  </div>

  <!-- Channel YoY growth table -->
  <table>
    <thead>
      <tr>
        <th>Channel</th>
        <th>Subscribers</th>
        <th>Lifetime Views</th>
        <th>1yr Sub Growth</th>
        <th>2yr Sub Growth</th>
        <th>1yr View Growth</th>
      </tr>
    </thead>
    <tbody>{yt_ch_rows}</tbody>
  </table>
  {"" if yt_ch_rows else '<div class="callout callout-warn" style="margin-top:10px">⚠ No YouTube channel data — run fetch_youtube_channels.py</div>'}
</div>

<!-- ═══ TRAILER & TENTPOLE REVEALS ══════════════════════════════════════════ -->
<div class="section">
  <div class="section-title">Trailer &amp; Tentpole Reveals <span class="badge badge-tag">SIGNAL</span></div>
  <div class="ctx">{trailer_ctx}</div>
  {"" if trailer_rows else '<div class="callout">ℹ Trailer/reveal content will surface here as channels post launch trailers, gameplay reveals, and major announcements.</div>'}
  {"" if not trailer_rows else """<table>
    <thead><tr><th>#</th><th>Channel</th><th>Title</th><th>Views</th><th>Published</th><th>Velocity</th></tr></thead>
    <tbody>""" + trailer_rows + "</tbody></table>"}
</div>

<!-- ═══ NEW PLAYER FUNNEL SIGNALS ═══════════════════════════════════════════ -->
<div class="section">
  <div class="section-title">New Player Funnel — Beginner &amp; Starter Content <span class="badge badge-tag">SIGNAL</span></div>
  <div class="ctx">{beg_ctx}</div>
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-label">Total Beginner Videos</div>
      <div class="stat-value">{beg.get('total_videos', '—')}</div>
      <div class="stat-sub">all-time in library</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Last 90 Days</div>
      <div class="stat-value">{beg.get('last_90d_count', '—')}</div>
      <div class="stat-sub">{fmt_num(beg.get('last_90d_views'))} views</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Last 12 Months</div>
      <div class="stat-value">{beg.get('last_1y_count', '—')}</div>
      <div class="stat-sub">{fmt_num(beg.get('last_1y_views'))} views</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">All-Time Funnel Views</div>
      <div class="stat-value">{fmt_num(beg.get('all_time_views'))}</div>
      <div class="stat-sub">across all beginner content</div>
    </div>
  </div>
  {"" if beg_rows else '<div class="callout">ℹ Beginner and starter content will surface here as channels post videos with beginner/starter/getting-started keywords.</div>'}
  {"" if not beg_rows else """<table>
    <thead><tr><th>#</th><th>Channel</th><th>Title</th><th>Views</th><th>Velocity</th><th>Published</th></tr></thead>
    <tbody>""" + beg_rows + "</tbody></table>"}
</div>

<!-- ═══ TOP VIDEOS — LAST 60 DAYS ═══════════════════════════════════════════ -->
<div class="section">
  <div class="section-title">Top Videos — Last 60 Days (by total views)</div>
  <table>
    <thead><tr><th>#</th><th>Channel</th><th>Title</th><th>Views</th><th>Velocity</th></tr></thead>
    <tbody>{top_vid_rows}</tbody>
  </table>
</div>

<!-- ═══ FASTEST RISING VIDEOS ════════════════════════════════════════════════ -->
<div class="section">
  <div class="section-title">{gainer_label}</div>
  {gainer_note}
  <table>
    <thead><tr>{gainer_hdr}</tr></thead>
    <tbody>{gainer_rows}</tbody>
  </table>
</div>

<!-- ═══ ALL-TIME TOP VIDEOS ══════════════════════════════════════════════════ -->
<div class="section">
  <div class="section-title">All-Time Top Videos (last 50 per channel)</div>
  <table>
    <thead><tr><th>#</th><th>Channel</th><th>Title</th><th>Views</th><th>Published</th></tr></thead>
    <tbody>{alltime_rows}</tbody>
  </table>
</div>

<!-- ═══ DIGITAL GAMING BASE: STEAM ══════════════════════════════════════════ -->
<div class="section">
  <div class="section-title">Digital Gaming Base: Steam
    &nbsp;<small style="color:var(--muted);font-weight:400">Total active: {fmt_num(steam.get('total_players'))}</small>
  </div>
  {f'<div class="ctx">{steam_ctx}</div>' if steam_ctx else ""}
  {"" if steam_yoy_avail else '<div class="callout callout-warn">⚠ YoY player growth requires 12+ months of daily data. Column shows <em>building…</em> until available.</div>'}
  <div class="chart-wrap-sm">
    <canvas id="chartSteam"></canvas>
  </div>
  <table>
    <thead><tr><th>Game</th><th>Players Now</th><th>1yr Player Growth</th><th>Reviews</th><th>Score</th><th>Owners Est. (SteamSpy)</th><th>Avg Playtime 2w</th></tr></thead>
    <tbody>{steam_rows}</tbody>
  </table>
</div>

<!-- ═══ WARHAMMER COMMUNITY — GW NEWS CADENCE ════════════════════════════════ -->
<div class="section">
  <div class="section-title">Warhammer Community — GW News Cadence</div>
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-label">Articles last 7 days</div>
      <div class="stat-value">{warcom.get('articles_last_7d','—')}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Articles last 30 days</div>
      <div class="stat-value">{warcom.get('articles_last_30d') or '—'}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Week-on-week Δ</div>
      <div class="stat-value" style="font-size:18px">{fmt_delta(warcom.get('articles_7d_delta'))}</div>
    </div>
  </div>
  {"<div class='callout callout-warn'>⚠ Using homepage link proxy — not date-filtered. 7d ≈ 30d count is expected. Week-on-week Δ available after 2nd run.</div>" if warcom.get('method') == 'homepage_links' else ""}
</div>

<!-- ═══ COMPETITIVE EVENTS ════════════════════════════════════════════════════ -->
<div class="section">
  <div class="section-title">Tournament &amp; Competitive Attendance <span class="badge badge-tag">TRACKING</span></div>
  {comp_note}
  {comp_table}
</div>

<!-- ═══ RETAIL & SUPPLY SIGNALS ═════════════════════════════════════════════ -->
<div class="section">
  <div class="section-title">Retail &amp; Supply Signals <span class="badge badge-tag">TRACKING</span></div>
  {retail_note}
  {retail_table}
</div>

<!-- ═══ DATA HEALTH ════════════════════════════════════════════════════════════ -->
<div class="section">
  <div class="section-title">Data Health &amp; Collection Status</div>
  <table>
    <thead><tr><th></th><th>Metric</th><th>Status / Notes</th></tr></thead>
    <tbody>{health_rows}</tbody>
  </table>
</div>

</div><!-- /container -->

<div class="footer">
  Warhammer Demand Intelligence &nbsp;|&nbsp; Structural Growth Focus &nbsp;|&nbsp; Generated {generated}
</div>

<!-- Chart data injected by Python -->
<script>
window.__chartData = {{
  rl: {j_rl}, rnow: {j_rnow}, rs25: {j_rs25},
  w40k_d: {j_w40k_d}, w40k_m: {j_w40k_m},
  ytl: {j_ytl}, yts: {j_yts}, ytv: {j_ytv},
  stl: {j_stl}, stp: {j_stp}
}};
</script>
"""
    # Append static chart init (plain string — no brace-escaping issues)
    html += chart_init
    return html


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    with open(SUMMARY_FILE) as f:
        summary = json.load(f)

    report_text = ""
    if Path(REPORT_FILE).exists():
        with open(REPORT_FILE) as f:
            report_text = f.read()

    html = build_html(summary, report_text)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"HTML report saved → {OUTPUT_FILE}")
    abs_path = Path(OUTPUT_FILE).resolve()
    webbrowser.open(f"file://{abs_path}")
    print(f"Opened in browser: file://{abs_path}")
