"""
Warhammer Demand Intelligence Report Generator.

Reads weekly_summary.json, formats a structured data brief, and calls Claude
to write a structural growth analyst briefing.

Strategic focus: YoY expansion, compounding audience growth, supply signals.
Google Trends and short-term weekly noise removed.

Output: demand_report.txt
"""

import json
import os
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

INPUT_FILE  = "weekly_summary.json"
OUTPUT_FILE = "demand_report.txt"

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")


# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_pct(val, decimals=1):
    if val is None:
        return "N/A"
    arrow = "▲" if val > 0 else ("▼" if val < 0 else "—")
    return f"{arrow} {val:+.{decimals}f}%"

def fmt_num(val):
    if val is None:
        return "N/A"
    if val >= 1_000_000:
        return f"{val/1_000_000:.2f}M"
    if val >= 1_000:
        return f"{val/1_000:.1f}K"
    return str(int(val))

def divider(char="═", width=60):
    return char * width

def section(title, char="─", width=60):
    return f"\n{title}\n{char * width}"


# ── Data brief for Claude ─────────────────────────────────────────────────────

def build_data_brief(summary):
    """Build a structured plain-text brief of all available data for Claude."""
    reddit  = summary.get("reddit_ecosystem", {})
    yt_ch   = summary.get("youtube_channels", {})
    yt_vid  = summary.get("youtube_videos", {})
    steam   = summary.get("steam", {})
    warcom  = summary.get("warcom", {})

    lines = [f"Report date: {summary.get('date')}", ""]

    # ── Reddit member counts + structural growth ──────────────────────────────
    mc_list = sorted(reddit.get("member_counts", []), key=lambda x: -(x.get("members") or 0))
    hist_ctx = reddit.get("history_context", {})
    if mc_list:
        lines += ["REDDIT COMMUNITY SIZE & STRUCTURAL GROWTH:"]
        lines.append(f"  Note: {hist_ctx.get('platform_note','')}")
        for ms in hist_ctx.get("milestones", []):
            lines.append(f"  Milestone: r/{ms['subreddit']} — {ms['event']} ({ms['date']})")
        lines.append(f"  Historical annual growth range: {hist_ctx.get('annual_growth_rate_range_pct',[13,25])[0]}–{hist_ctx.get('annual_growth_rate_range_pct',[13,25])[1]}%")
        lines.append("")
        for m in mc_list:
            g1y = fmt_pct(m.get("growth_1y_pct"))
            g2y = fmt_pct(m.get("growth_2y_pct"))
            g5m = fmt_pct(m.get("growth_5m_pct"))
            old = m.get("oldest_data_point") or {}
            old_str = f"(oldest: {old.get('date','')[:7]} = {fmt_num(old.get('members'))})" if old.get("members") else ""
            lines.append(
                f"  r/{m['subreddit']}: {fmt_num(m.get('members'))} members  "
                f"1yr growth: {g1y}  2yr: {g2y}  since-Sept25: {g5m}  {old_str}"
            )

    # ── Reddit engagement (30d structural) ───────────────────────────────────
    lines += ["", "REDDIT COMMUNITY ENGAGEMENT (30d structural):"]
    lines.append(f"  Ecosystem structural trend: {fmt_pct(reddit.get('ecosystem_structural_30d_comments_pct'))}")
    for sub in reddit.get("subreddits", []):
        lines.append(
            f"  r/{sub['subreddit']}: 30d structural = {fmt_pct(sub.get('structural_30d_comments_pct'))}"
        )

    # ── YouTube channels — ecosystem expansion ────────────────────────────────
    if yt_ch:
        total_subs  = yt_ch.get("total_ecosystem_subscribers", 0)
        total_views = yt_ch.get("total_ecosystem_views", 0)
        n_snaps     = yt_ch.get("snapshots_available", 1)
        lines += ["", "YOUTUBE CREATOR ECOSYSTEM:"]
        lines.append(f"  Ecosystem total subscribers: {fmt_num(total_subs)}")
        lines.append(f"  Ecosystem total lifetime views: {fmt_num(total_views)}")
        lines.append(f"  Snapshots collected: {n_snaps} (need 52+ for YoY data)")
        lines.append(f"  YoY data available: {yt_ch.get('yoy_data_available', False)}")
        lines.append("")
        for ch in sorted(yt_ch.get("channels", []), key=lambda x: -x.get("subscribers", 0)):
            g1y = fmt_pct(ch.get("growth_1y_subs_pct"))
            g2y = fmt_pct(ch.get("growth_2y_subs_pct"))
            lines.append(
                f"  {ch['label']}: {fmt_num(ch['subscribers'])} subs, "
                f"{fmt_num(ch['total_views'])} lifetime views  "
                f"1yr sub growth: {g1y}  2yr: {g2y}"
            )

    # ── YouTube trailers & tentpole performance ────────────────────────────────
    trailers = yt_vid.get("trailers", {})
    if trailers.get("top_trailers"):
        lines += ["", f"TRAILER & TENTPOLE CONTENT ({trailers.get('total_found',0)} found):"]
        for t in trailers["top_trailers"][:8]:
            lines.append(
                f"  [{t['channel_label']}] {t['title'][:65]} — "
                f"{fmt_num(t['views'])} views, {t['views_per_day']:.0f}/day"
            )

    # ── Beginner / new player funnel ──────────────────────────────────────────
    funnel = yt_vid.get("beginner_funnel", {})
    if funnel:
        lines += ["", "NEW PLAYER FUNNEL SIGNALS (beginner/starter content):"]
        lines.append(f"  Total beginner/starter videos found: {funnel.get('total_videos', 0)}")
        lines.append(f"  Last 90 days: {funnel.get('last_90d_count', 0)} videos, {fmt_num(funnel.get('last_90d_views', 0))} views")
        lines.append(f"  Last 12 months: {funnel.get('last_1y_count', 0)} videos, {fmt_num(funnel.get('last_1y_views', 0))} views")
        lines.append(f"  All-time beginner content views: {fmt_num(funnel.get('all_time_views', 0))}")
        lines.append("  Top beginner videos:")
        for v in funnel.get("top_videos", [])[:5]:
            lines.append(f"    [{v['channel_label']}] {v['title'][:60]} — {fmt_num(v['views'])} views")

    # ── YouTube top recent videos ─────────────────────────────────────────────
    top_recent = yt_vid.get("top_recent_60d", [])[:8]
    if top_recent:
        lines += ["", "YOUTUBE TOP CONTENT — LAST 60 DAYS:"]
        for v in top_recent:
            lines.append(
                f"  [{v['channel_label']}] {v['title'][:65]} — "
                f"{fmt_num(v['views'])} views, {v['views_per_day']:.0f}/day"
            )

    # ── Steam — structural digital gaming base ────────────────────────────────
    if steam:
        lines += ["", "STEAM — WARHAMMER DIGITAL GAMING BASE:"]
        lines.append(f"  Total concurrent players across all titles: {fmt_num(steam.get('total_players'))}")
        lines.append(f"  YoY player data available: {steam.get('yoy_available', False)}")
        for g in steam.get("games", []):
            owners = (f"  Owners: {fmt_num(g.get('owners_low'))}–{fmt_num(g.get('owners_high'))} (SteamSpy)"
                      if g.get("owners_low") else "")
            playtime = f"  Avg playtime 2w: {g.get('avg_playtime_2w_min')}min" if g.get("avg_playtime_2w_min") else ""
            yoy_p = f"  YoY players: {fmt_pct(g.get('growth_1y_players_pct'))}" if g.get("growth_1y_players_pct") is not None else ""
            pos = f"{g['positive_pct']:.0f}% positive" if g.get("positive_pct") else ""
            lines.append(
                f"  {g['label']}: {fmt_num(g.get('current_players'))} players, "
                f"{fmt_num(g.get('total_reviews'))} reviews, {pos}{owners}{playtime}{yoy_p}"
            )

    # ── WarCom ────────────────────────────────────────────────────────────────
    if warcom:
        lines += ["", "GW NEWS CADENCE (Warhammer Community):"]
        lines.append(f"  Articles on homepage (7d proxy): {warcom.get('articles_last_7d', 'N/A')}")

    return "\n".join(lines)


# ── Claude structural growth narrative ───────────────────────────────────────

def get_claude_narrative(summary):
    if not ANTHROPIC_KEY:
        return (
            "[ ANALYSIS UNAVAILABLE ]\n\n"
            "Add your Anthropic API key to .env to enable the full written analysis:\n"
            "  ANTHROPIC_API_KEY=\"sk-ant-...\"\n\n"
            "Get a key at: console.anthropic.com → API Keys"
        )

    client     = Anthropic(api_key=ANTHROPIC_KEY)
    data_brief = build_data_brief(summary)

    prompt = f"""You are a senior games industry analyst specialising in audience growth and structural market expansion. Your client tracks the long-term growth of the Warhammer (Games Workshop) franchise across community, content, digital gaming, and retail channels.

Your mandate is to identify structural audience growth, not report on weekly fluctuations. Write for institutional readers who care about compounding growth, YoY expansion, and evidence of sustained demand acceleration — not short-term noise.

Below is this week's data snapshot. Write a full structural analyst briefing covering ALL sections below. Use plain prose — no markdown, no bullet points, just clean paragraphs with clear section labels. Be specific, use actual numbers, and compare against prior periods wherever data allows. If a YoY comparison is not yet available because tracking history is insufficient, say so directly and note when it will become available.

SECTION 1 — STRUCTURAL VERDICT (1 paragraph)
Assess the franchise's structural health and audience trajectory. Is the overall audience base expanding or contracting on a multi-year basis? Reference the community size data (Reddit member trajectory, creator subscriber growth, digital game sales) to support a clear verdict on whether Warhammer's audience is compounding, plateauing, or declining. Give the single most important structural insight from this data.

SECTION 2 — COMMUNITY BASE EXPANSION: REDDIT (1-2 paragraphs)
Analyse the long-term member growth trajectory across the 9 tracked Reddit communities. Reference the r/Warhammer40k milestone (surpassed 1M in October 2024, now at X), the historical growth rate range (13–25% annually), and any available YoY or multi-year growth figures. Note that Reddit removed public subscriber counts from the web in September 2025 but the API still returns accurate values — this is not a data gap, it is a platform change. Discuss where member growth is strongest and what this tells us about which parts of the Warhammer franchise (40K, AoS, Fantasy, hobby) are attracting new audiences fastest. If 1-year growth is N/A for most subs, explain this is because systematic tracking only began in February 2026 and compare the oldest available data points.

SECTION 3 — CREATOR ECOSYSTEM EXPANSION: YOUTUBE (1-2 paragraphs)
Assess the structural health and scale of the Warhammer creator ecosystem. Report the total ecosystem subscriber count and lifetime view count across all tracked channels. Which creators are largest and which appear to be growing fastest (use subscriber and view data to infer relative momentum)? What content categories are driving the most audience engagement right now — lore, hobby, tactics, news? Reference the top recent and all-time videos. Note that YoY subscriber growth data requires 52 weeks of snapshots and note when this will be fully available. Cover the trailer and tentpole content performance — major reveal and launch trailers are the most important barometers of franchise excitement.

SECTION 4 — NEW PLAYER INFLOW: BEGINNER FUNNEL (1 paragraph)
Analyse the volume and reach of beginner/starter/new-player-focused content across the creator ecosystem. How many beginner-oriented videos exist? How many have been published in the last 90 days and what is their aggregate view count? A healthy beginner funnel is a leading indicator of new player acquisition. What does the current data tell us about the rate of new players entering the hobby?

SECTION 5 — DIGITAL GAMING AUDIENCE: STEAM (1 paragraph)
Assess the structural scale of Warhammer's digital gaming audience. Lead with the total units sold estimate for Space Marine 2 (the flagship release). Which games are maintaining the largest sustained player bases? What do the review scores tell us about player satisfaction and retention? Note the SteamSpy owner estimates as evidence of commercial scale. If YoY player comparison is not yet available, note when it will be.

SECTION 6 — RETAIL & SUPPLY SIGNALS (1 short paragraph)
Comment on any available retail and supply signals from tracked YouTube creators. Are there indicators of strong or constrained supply? Any mentions of sold-out products, pre-order launches, or new release activity? If retail signals are limited, note what we are watching for.

SECTION 7 — STRUCTURAL OUTLOOK (1 paragraph)
What are the 3–4 most important structural signals to monitor as data matures? Focus on: when YoY comparisons will first be available, which metrics show the clearest evidence of structural expansion, and any leading indicators of acceleration or deceleration in the franchise's audience growth trajectory.

Be honest about data maturity. Do not invent confidence you don't have. If a metric is N/A because systematic tracking has only just begun, say plainly when the data will mature.

DATA:
{data_brief}"""

    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3500,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()


# ── Report builder ────────────────────────────────────────────────────────────

def build_report(summary):
    date_str = summary.get("date", str(datetime.now().date()))
    lines    = []

    lines += [
        divider("═"),
        "  WARHAMMER DEMAND INTELLIGENCE",
        f"  Report Date: {date_str}",
        divider("═"),
        "",
    ]

    lines += [
        section("ANALYST BRIEFING — STRUCTURAL GROWTH", "─"),
        "",
        get_claude_narrative(summary),
        "",
        divider("─"),
        "  RAW DATA TABLES",
        divider("─"),
        "",
    ]

    # ── Reddit member counts ───────────────────────────────────────────────────
    reddit   = summary.get("reddit_ecosystem", {})
    mc_list  = sorted(reddit.get("member_counts", []), key=lambda x: -(x.get("members") or 0))
    hist_ctx = reddit.get("history_context", {})

    if mc_list:
        lines += [
            section("REDDIT COMMUNITY SIZE & STRUCTURAL GROWTH", "─"),
            f"  Note: {hist_ctx.get('platform_note', '')}",
            "",
            f"  {'Subreddit':<22} {'Members':>10}  {'1yr Growth':>12}  {'2yr Growth':>12}  {'Since Sept 25':>14}  Oldest Data",
            f"  {'─'*22} {'─'*10}  {'─'*12}  {'─'*12}  {'─'*14}  {'─'*16}",
        ]
        for m in mc_list:
            old    = m.get("oldest_data_point") or {}
            old_str = f"{old.get('date','')[:7]}: {fmt_num(old.get('members'))}" if old.get("members") else "—"
            lines.append(
                f"  r/{m['subreddit']:<20} {fmt_num(m.get('members')):>10}  "
                f"{fmt_pct(m.get('growth_1y_pct')):>12}  "
                f"{fmt_pct(m.get('growth_2y_pct')):>12}  "
                f"{fmt_pct(m.get('growth_5m_pct')):>14}  {old_str}"
            )
        lines.append("")

    # ── Reddit engagement ─────────────────────────────────────────────────────
    lines += [
        section("REDDIT COMMUNITY ENGAGEMENT (30d structural)", "─"),
        f"  Ecosystem structural trend: {fmt_pct(reddit.get('ecosystem_structural_30d_comments_pct'))}",
        "",
        f"  {'Subreddit':<24} {'30d Structural':>16}",
        f"  {'─'*24} {'─'*16}",
    ]
    for sub in reddit.get("subreddits", []):
        lines.append(
            f"  r/{sub['subreddit']:<22} {fmt_pct(sub.get('structural_30d_comments_pct')):>16}"
        )
    lines.append("")

    # ── YouTube channels ───────────────────────────────────────────────────────
    yt_ch = summary.get("youtube_channels", {})
    if yt_ch:
        n_snaps = yt_ch.get("snapshots_available", 1)
        lines += [
            section("YOUTUBE CREATOR ECOSYSTEM", "─"),
            f"  Ecosystem subscribers: {fmt_num(yt_ch.get('total_ecosystem_subscribers'))}",
            f"  Ecosystem lifetime views: {fmt_num(yt_ch.get('total_ecosystem_views'))}",
            f"  Snapshots: {n_snaps} (need 52 for YoY; {'ready' if yt_ch.get('yoy_data_available') else 'building'})",
            "",
            f"  {'Channel':<24} {'Subscribers':>12}  {'Lifetime Views':>14}  {'1yr Subs':>10}  {'2yr Subs':>10}",
            f"  {'─'*24} {'─'*12}  {'─'*14}  {'─'*10}  {'─'*10}",
        ]
        for ch in sorted(yt_ch.get("channels", []), key=lambda x: -x.get("subscribers", 0)):
            lines.append(
                f"  {ch['label']:<24} {fmt_num(ch['subscribers']):>12}  "
                f"{fmt_num(ch['total_views']):>14}  "
                f"{fmt_pct(ch.get('growth_1y_subs_pct')):>10}  "
                f"{fmt_pct(ch.get('growth_2y_subs_pct')):>10}"
            )
        lines.append("")

    # ── Trailer & tentpole ────────────────────────────────────────────────────
    yt_vid   = summary.get("youtube_videos", {})
    trailers = yt_vid.get("trailers", {})
    if trailers.get("top_trailers"):
        lines += [
            section(f"TRAILER & TENTPOLE CONTENT ({trailers.get('total_found',0)} found)", "─"),
            f"  {'#':<3} {'Channel':<24} {'Views':>9}  {'Views/day':>10}  Title",
            f"  {'─'*3} {'─'*24} {'─'*9}  {'─'*10}  {'─'*35}",
        ]
        for i, t in enumerate(trailers["top_trailers"][:10], 1):
            title = t['title'][:50] + "…" if len(t['title']) > 50 else t['title']
            lines.append(
                f"  {i:<3} {t['channel_label']:<24} {fmt_num(t['views']):>9}  "
                f"{t['views_per_day']:>9.0f}  {title}"
            )
        lines.append("")

    # ── Beginner funnel ───────────────────────────────────────────────────────
    funnel = yt_vid.get("beginner_funnel", {})
    if funnel:
        lines += [
            section("NEW PLAYER FUNNEL SIGNALS", "─"),
            f"  Total beginner/starter videos found   : {funnel.get('total_videos', 0)}",
            f"  Last 90 days — videos                 : {funnel.get('last_90d_count', 0)}",
            f"  Last 90 days — views                  : {fmt_num(funnel.get('last_90d_views', 0))}",
            f"  Last 12 months — views                : {fmt_num(funnel.get('last_1y_views', 0))}",
            f"  All-time views (beginner content)     : {fmt_num(funnel.get('all_time_views', 0))}",
            "",
        ]

    # ── YouTube top recent ────────────────────────────────────────────────────
    recent = yt_vid.get("top_recent_60d", [])
    if recent:
        lines += [
            section("TOP VIDEOS — LAST 60 DAYS (by views)", "─"),
            f"  {'#':<3} {'Channel':<24} {'Views':>9}  {'Views/day':>10}  Title",
            f"  {'─'*3} {'─'*24} {'─'*9}  {'─'*10}  {'─'*35}",
        ]
        for i, v in enumerate(recent, 1):
            title = v['title'][:50] + "…" if len(v['title']) > 50 else v['title']
            lines.append(
                f"  {i:<3} {v['channel_label']:<24} {fmt_num(v['views']):>9}  "
                f"{v['views_per_day']:>9.0f}  {title}"
            )
        lines.append("")

    # ── Steam ─────────────────────────────────────────────────────────────────
    steam = summary.get("steam", {})
    if steam:
        lines += [
            section("STEAM — WARHAMMER DIGITAL GAMING BASE", "─"),
            f"  Total concurrent players: {fmt_num(steam.get('total_players'))}",
            "",
            f"  {'Game':<28} {'Players':>10}  {'Reviews':>9}  {'Score':>6}  {'Owners Est.':>16}  {'Playtime 2w':>12}  {'YoY':>8}",
            f"  {'─'*28} {'─'*10}  {'─'*9}  {'─'*6}  {'─'*16}  {'─'*12}  {'─'*8}",
        ]
        for g in steam.get("games", []):
            pos     = f"{g['positive_pct']:.0f}%" if g.get("positive_pct") else "N/A"
            owners  = f"{fmt_num(g.get('owners_low'))}–{fmt_num(g.get('owners_high'))}" if g.get("owners_low") else "—"
            playtime = f"{g.get('avg_playtime_2w_min')}m" if g.get("avg_playtime_2w_min") else "—"
            yoy_p   = fmt_pct(g.get("growth_1y_players_pct")) if g.get("growth_1y_players_pct") is not None else "N/A"
            lines.append(
                f"  {g['label']:<28} {fmt_num(g.get('current_players')):>10}  "
                f"{fmt_num(g.get('total_reviews')):>9}  {pos:>6}  {owners:>16}  {playtime:>12}  {yoy_p:>8}"
            )
        lines.append("")

    # ── Data coverage ─────────────────────────────────────────────────────────
    lines += [section("DATA COVERAGE", "─")]
    lines.append(f"  Reddit communities tracked   : {len(reddit.get('subreddits', []))}")
    lines.append(f"  Reddit member history        : {len(reddit.get('member_history', {}))}")
    lines.append(f"  YouTube channels             : {len(yt_ch.get('channels', []) if yt_ch else [])}")
    yt_snaps = yt_vid.get("snapshots_available", 0) if yt_vid else 0
    lines.append(f"  YouTube video snapshots      : {yt_snaps} (need 52 for YoY)")
    ch_snaps = yt_ch.get("snapshots_available", 0) if yt_ch else 0
    lines.append(f"  YouTube channel snapshots    : {ch_snaps} (need 52 for YoY)")
    lines.append(f"  Steam games tracked          : {len(steam.get('games', []) if steam else [])}")
    lines.append(f"  Report generated             : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append(divider("═"))

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with open(INPUT_FILE, "r") as f:
        summary = json.load(f)

    print("Building structural growth report (calling Claude for narrative)...")
    report = build_report(summary)

    with open(OUTPUT_FILE, "w") as f:
        f.write(report)

    print(f"Demand report saved → {OUTPUT_FILE}")
    print()
    print(report)
