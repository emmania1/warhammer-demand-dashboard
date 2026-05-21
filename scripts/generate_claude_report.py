import os
import json
from anthropic import Anthropic

def generate_claude_report(summary):
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""
You are an institutional equity research analyst.

Analyze the following Warhammer demand data and produce a structured executive update.

Data:
{json.dumps(summary, indent=2)}
"""

    message = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


if __name__ == "__main__":
    with open("weekly_summary.json", "r") as f:
        summary = json.load(f)

    report = generate_claude_report(summary)

    with open("claude_weekly_report.txt", "w") as f:
        f.write(report)

    print("Claude report generated → claude_weekly_report.txt")
