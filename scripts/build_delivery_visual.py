"""Generate a truthful, public-repository portfolio brief as an SVG."""
import datetime as dt
import html
import json
import os
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

OWNER = "0xtrvkc"
ROOT = Path(__file__).resolve().parents[1]
NOW = dt.datetime.now(dt.timezone.utc)
TOKEN = os.environ.get("GH_TOKEN", "")


def api(path):
    request = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "portfolio-brief-generator",
            **({"Authorization": "Bearer " + TOKEN} if TOKEN else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def text(value):
    return html.escape(str(value), quote=True)


def category(repo):
    name = repo["name"].lower()
    description = (repo.get("description") or "").lower()
    words = name + " " + description
    if any(term in words for term in ("dashboard", "analytics", "visualizer", "database")):
        return "Analytics"
    if any(term in words for term in ("sandbox", "backtest", "simulator", "analyzer")):
        return "Decision tools"
    if any(term in words for term in ("quiz", "ready", "education", "learning")):
        return "Learning"
    return "Other builds"


def main():
    repos = []
    for page in range(1, 11):
        batch = api(f"/users/{OWNER}/repos?per_page=100&page={page}&type=owner")
        repos.extend(batch)
        if len(batch) < 100:
            break
    repos = [r for r in repos if not r.get("fork") and not r.get("archived") and r["name"] != OWNER]
    counts = Counter(category(r) for r in repos)
    recent = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[:5]
    active_30d = sum(dt.datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) >= NOW - dt.timedelta(days=30) for r in repos)
    weeks = []
    for i in range(7, -1, -1):
        end = NOW - dt.timedelta(days=7 * i)
        start = end - dt.timedelta(days=7)
        count = sum(start <= dt.datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) < end for r in repos)
        weeks.append((start.strftime("%d %b"), count))
    maximum = max(1, *(v for _, v in weeks))

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="510" viewBox="0 0 960 510" role="img" aria-labelledby="title desc">',
        '<title id="title">Public project delivery brief</title>',
        '<desc id="desc">Repository counts by category, weekly last-push activity, and five recently pushed projects. Counts reflect public non-fork, non-archived repositories, not project completion or team delivery.</desc>',
        '<rect width="960" height="510" fill="#f8fafc"/><rect x="16" y="16" width="928" height="478" rx="16" fill="white" stroke="#cbd5e1"/>',
        '<text x="40" y="58" font-family="Arial,sans-serif" font-size="25" font-weight="700" fill="#0f172a">Public project delivery brief</text>',
        f'<text x="40" y="84" font-family="Arial,sans-serif" font-size="13" fill="#475569">Source: GitHub public repository metadata · Refreshed {NOW:%Y-%m-%d %H:%M} UTC</text>',
        f'<text x="40" y="135" font-family="Arial,sans-serif" font-size="35" font-weight="700" fill="#0f172a">{len(repos)}</text>',
        '<text x="40" y="157" font-family="Arial,sans-serif" font-size="12" fill="#475569">maintained public repos</text>',
        f'<text x="266" y="135" font-family="Arial,sans-serif" font-size="35" font-weight="700" fill="#2563eb">{active_30d}</text>',
        '<text x="266" y="157" font-family="Arial,sans-serif" font-size="12" fill="#475569">pushed in past 30 days</text>',
        '<path d="M40 177H920" stroke="#e2e8f0"/>',
        '<text x="40" y="211" font-family="Arial,sans-serif" font-size="16" font-weight="700" fill="#0f172a">Project mix</text>',
        '<text x="492" y="211" font-family="Arial,sans-serif" font-size="16" font-weight="700" fill="#0f172a">Last push by week</text>',
    ]
    palette = {"Analytics": "#2563eb", "Decision tools": "#0d9488", "Learning": "#7c3aed", "Other builds": "#64748b"}
    for index, label in enumerate(palette):
        y = 237 + index * 43
        width = round(280 * counts[label] / max(1, len(repos)))
        parts += [
            f'<text x="40" y="{y}" font-family="Arial,sans-serif" font-size="13" fill="#334155">{label}</text>',
            f'<rect x="170" y="{y-13}" width="280" height="16" rx="4" fill="#e2e8f0"/>',
            f'<rect x="170" y="{y-13}" width="{width}" height="16" rx="4" fill="{palette[label]}"/>',
            f'<text x="460" y="{y}" text-anchor="end" font-family="Arial,sans-serif" font-size="13" fill="#334155">{counts[label]}</text>',
        ]
    for index, (label, count) in enumerate(weeks):
        x = 500 + index * 52
        height = round(108 * count / maximum)
        parts += [
            f'<rect x="{x}" y="{346-height}" width="32" height="{height}" rx="3" fill="#2563eb"/>',
            f'<text x="{x+16}" y="{337-height}" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="#334155">{count}</text>',
            f'<text x="{x+16}" y="366" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" fill="#64748b">{text(label)}</text>',
        ]
    names = ", ".join(r["name"] for r in recent)
    if len(names) > 104:
        names = names[:101] + "..."
    parts += [
        '<path d="M40 394H920" stroke="#e2e8f0"/>',
        '<text x="40" y="422" font-family="Arial,sans-serif" font-size="15" font-weight="700" fill="#0f172a">Recently pushed</text>',
        f'<text x="40" y="445" font-family="Arial,sans-serif" font-size="12" fill="#334155">{text(names)}</text>',
        '<text x="40" y="475" font-family="Arial,sans-serif" font-size="11" fill="#64748b">A push is a code update, not a completed milestone. Categories are inferred from repository names and descriptions.</text>',
        '</svg>',
    ]
    output = ROOT / "assets" / "delivery-brief.svg"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote {output}; {len(repos)} repositories")


if __name__ == "__main__":
    main()
