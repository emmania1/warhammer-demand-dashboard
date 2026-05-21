import json
from datetime import datetime

INPUT_FILE = "weekly_summary.json"
OUTPUT_FILE = "weekly_demand_report.txt"

def load_summary():
    with open(INPUT_FILE, "r") as f:
        return json.load(f)

def format_pct(value):
    if value is None:
        return "N/A"
    return f"{value:.1f}%"

def generate_report(summary):
    today = summary.get("date", str(datetime.now().date()))

    report_lines = []
    report_lines.append("WARHAMMER DEMAND MOMENTUM UPDATE")
    report_lines.append(f"Week Ending {today}")
    report_lines.append("=" * 50)
    report_lines.append("")

    # Reddit Section
    reddit = summary.get("reddit_ecosystem", {})
    subreddits = reddit.get("subreddits", [])
    ecosystem_structural = reddit.get("ecosystem_structural_30d_comments_pct")

    report_lines.append("REDDIT ECOSYSTEM")
    report_lines.append("-" * 30)

    report_lines.append(
        f"Ecosystem Structural (30d): {format_pct(ecosystem_structural)}"
    )
    report_lines.append("")

    for sub in subreddits:
        name = sub.get("subreddit")
        structural = format_pct(sub.get("structural_30d_comments_pct"))
        momentum = format_pct(sub.get("momentum_7d_comments_pct"))

        report_lines.append(f"{name}")
        report_lines.append(f"  30d Structural: {structural}")
        report_lines.append(f"  7d Momentum:    {momentum}")
        report_lines.append("")

    # Google Trends
    trends = summary.get("google_trends", {})
    trends_structural = format_pct(trends.get("structural_30d_interest_pct"))
    trends_momentum = format_pct(trends.get("momentum_7d_interest_pct"))
    latest_score = trends.get("latest_avg_score")

    report_lines.append("GOOGLE SEARCH INTEREST")
    report_lines.append("-" * 30)
    report_lines.append(f"Latest Avg Score: {latest_score}")
    report_lines.append(f"30d Structural:   {trends_structural}")
    report_lines.append(f"7d Momentum:      {trends_momentum}")
    report_lines.append("")

    return "\n".join(report_lines)

if __name__ == "__main__":
    summary = load_summary()
    report = generate_report(summary)

    with open(OUTPUT_FILE, "w") as f:
        f.write(report)

    print(f"Executive report generated → {OUTPUT_FILE}")