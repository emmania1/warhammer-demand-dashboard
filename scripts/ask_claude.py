"""
Warhammer Demand Intelligence — Interactive Claude Chat Agent

Loads your latest data and opens a live conversation with Claude.
Ask anything about demand signals, trends, channels, games, or outlook.

Usage:
  python scripts/ask_claude.py
  ./run_pipeline.sh --ask
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

from anthropic import Anthropic

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set in .env file.")
    print("Add it to .env:  ANTHROPIC_API_KEY=\"sk-ant-...\"")
    sys.exit(1)

BASE = Path(__file__).parent.parent

# ── Load data context ──────────────────────────────────────────────────────────

def load_file(path, mode="r"):
    p = BASE / path
    if p.exists():
        with open(p, mode) as f:
            return f.read()
    return None

summary_raw  = load_file("weekly_summary.json")
report_raw   = load_file("demand_report.txt")

if not summary_raw:
    print("No weekly_summary.json found. Run the pipeline first:")
    print("  python run_weekly_pipeline.py")
    sys.exit(1)

summary = json.loads(summary_raw)
report_date = summary.get("date", "unknown")

# Build a compact data context for Claude (not the full JSON — too verbose)
def build_context(summary, report):
    lines = [
        f"Today's date: {datetime.now().strftime('%Y-%m-%d')}",
        f"Report date: {report_date}",
        "",
        "=== LATEST DEMAND REPORT ===",
        report or "(no report available)",
        "",
        "=== RAW SUMMARY JSON (for precise numbers) ===",
        json.dumps(summary, indent=2),
    ]
    return "\n".join(lines)

DATA_CONTEXT = build_context(summary, report_raw)

SYSTEM_PROMPT = f"""You are a Warhammer demand intelligence analyst with access to the user's live tracking data.

Your data covers:
- Reddit community engagement across 8+ Warhammer subreddits (daily post counts, comment velocity, momentum)
- YouTube performance for 10+ tracked channels (subscribers, views, top/recent videos, view velocity)
- Steam live player counts and review scores for 7 Warhammer games
- Warhammer Community (GW official site) news article cadence
- Google Trends search interest data

When answering:
- Be direct and analytical. Lead with the insight, not the data.
- Use specific numbers when they support the point.
- Flag when data is missing or too early to draw conclusions (e.g. "only 1 YouTube snapshot so no velocity yet").
- When asked about outlook, be honest about uncertainty but give your best read.
- Keep answers concise unless the user asks for more depth.

Special commands the user can type:
  /refresh  — remind them to run the pipeline to get fresh data
  /report   — show the full text report
  /data     — show what data sources are active
  /quit     — exit

Here is the current data you have access to:

{DATA_CONTEXT}
"""

# ── Chat loop ──────────────────────────────────────────────────────────────────

client       = Anthropic(api_key=ANTHROPIC_KEY)
conversation = []

def print_divider():
    print("─" * 60)

def handle_command(cmd):
    cmd = cmd.strip().lower()
    if cmd == "/report":
        print_divider()
        print(report_raw or "(no report available)")
        print_divider()
        return True
    if cmd == "/data":
        print_divider()
        reddit  = summary.get("reddit_ecosystem", {})
        steam   = summary.get("steam", {})
        yt_ch   = summary.get("youtube_channels", {})
        yt_vid  = summary.get("youtube_videos", {})
        warcom  = summary.get("warcom", {})
        print(f"  Report date         : {report_date}")
        print(f"  Reddit subreddits   : {len(reddit.get('subreddits', []))}")
        print(f"  YouTube channels    : {len(yt_ch.get('channels', []))}")
        print(f"  YouTube snapshots   : {yt_vid.get('snapshots_available', 0)}")
        print(f"  Steam games         : {len(steam.get('games', []))}")
        print(f"  WarCom articles 7d  : {warcom.get('articles_last_7d', 'N/A')}")
        print_divider()
        return True
    if cmd == "/refresh":
        print("  Run:  python run_weekly_pipeline.py")
        print("  Or:   ./run_pipeline.sh")
        print("  Then restart this chat to load fresh data.")
        return True
    if cmd in ("/quit", "/exit", "/q"):
        print("Bye.")
        sys.exit(0)
    return False


print()
print("╔══════════════════════════════════════════════════════════╗")
print("║   WARHAMMER DEMAND INTELLIGENCE — Claude Chat Agent      ║")
print(f"║   Data as of: {report_date:<44} ║")
print("╚══════════════════════════════════════════════════════════╝")
print()
print("Ask anything about Warhammer demand, YouTube, Steam, Reddit...")
print("Commands: /report  /data  /refresh  /quit")
print()

while True:
    try:
        user_input = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nBye.")
        break

    if not user_input:
        continue

    if user_input.startswith("/"):
        handle_command(user_input)
        continue

    conversation.append({"role": "user", "content": user_input})

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=conversation,
    )

    reply = response.content[0].text
    conversation.append({"role": "assistant", "content": reply})

    print()
    print(f"Claude: {reply}")
    print()
