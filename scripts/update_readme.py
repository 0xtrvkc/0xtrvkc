#!/usr/bin/env python3
"""Refresh project and delivery-operations sections of the profile README."""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

OWNER = "0xtrvkc"
README = "README.md"
REPOS_START = "<!-- RECENT-REPOS:START -->"
REPOS_END = "<!-- RECENT-REPOS:END -->"
OPS_START = "<!-- WORKFLOW-TRACKER:START -->"
OPS_END = "<!-- WORKFLOW-TRACKER:END -->"
SNAPSHOT_START = "<!-- DELIVERY-SNAPSHOT:START -->"
SNAPSHOT_END = "<!-- DELIVERY-SNAPSHOT:END -->"
LIMIT = 12

TRACKED = {
    "0xtrvkc": "Profile",
    "btc-grid-sandbox": "BTC Grid Sandbox",
    "btc-options-sandbox": "BTC Options Sandbox",
    "btcLoanAnalyzer": "BTC Loan Analyzer",
    "dynamic-btc-analytics-dashboard": "Dynamic BTC Analytics",
    "ARE-YOU-READY-": "ARE YOU READY?",
    "Fade-self-erasing-clipboard": "Fade",
}

CURATED = {
    "ARE-YOU-READY-": "Adaptive trading assessment with beginner and quant paths",
    "btc-grid-sandbox": "Compare grid returns, inventory, and range risk",
    "btc-options-sandbox": "Study Friday 0DTE range and breach risk",
    "grid-bot-post-mortem": "Review bot cash flow and open inventory",
    "tradingPortfolioDashboard": "Monitor trading portfolio performance",
    "Fade-self-erasing-clipboard": "Organize temporary notes and media",
    "prop_challenge_simulator": "Simulate prop-challenge risk and outcomes",
    "btcEmaCrossBacktest": "Test dual-EMA crossover strategies",
    "btcLoanAnalyzer": "Compare BTC-loan LTV and repayment paths",
    "dynamic-btc-analytics-dashboard": "Interpret MVRV, cycles, and drawdowns",
    "pvd-vs-investment": "Compare provident-fund and investment paths",
    "itd-oi-db": "Explore gold open interest and volatility",
    "dynamic-btc-dxy-analytics-dashboard": "Explore BTC and DXY analytics",
    "BTC-Daily-Short-Call-Premium-Income-Checklist": "Review a daily BTC short-call checklist",
    "Portfolio": "Browse selected projects",
    "dynamic-btc-analytics-dashboard_mobile": "Explore BTC analytics on mobile",
}


def github_get(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{OWNER}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):
            return None
        raise


def replace_block(text: str, start: str, end: str, rows: list[str]) -> str:
    block = start + "\n" + "\n".join(rows) + "\n" + end
    updated, count = re.subn(
        re.escape(start) + r".*?" + re.escape(end),
        block,
        text,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError(f"README marker pair missing or duplicated: {start}")
    return updated


def fallback_description(name: str) -> str:
    words = re.sub(r"[-_]+", " ", name).strip()
    return words[:1].upper() + words[1:] if words else "Project repository"


def has_schedule(repo: str, path: str) -> bool:
    encoded_path = urllib.parse.quote(path, safe="/")
    data = github_get(f"https://api.github.com/repos/{OWNER}/{repo}/contents/{encoded_path}")
    if not data or "content" not in data:
        return False
    source = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return bool(re.search(r"(?m)^\s*schedule\s*:", source))


def workflow_status(repo: str) -> tuple[str, str, str]:
    data = github_get(f"https://api.github.com/repos/{OWNER}/{repo}/actions/workflows?per_page=100")
    workflows = data.get("workflows", []) if data else []
    scheduled = [workflow for workflow in workflows if has_schedule(repo, workflow["path"])]

    if not scheduled:
        return "None detected", "—", "No schedule"

    count = len(scheduled)
    names = f"{count} scheduled workflow" + ("s" if count != 1 else "")
    disabled = [workflow for workflow in scheduled if workflow.get("state") != "active"]
    if disabled:
        return names, "—", "Attention: disabled"

    latest = None
    for workflow in scheduled:
        runs = github_get(
            f"https://api.github.com/repos/{OWNER}/{repo}/actions/workflows/"
            f"{workflow['id']}/runs?event=schedule&per_page=1"
        )
        items = runs.get("workflow_runs", []) if runs else []
        if items and (latest is None or items[0]["created_at"] > latest["created_at"]):
            latest = items[0]

    if not latest:
        return names, "Not run yet", "Ready"

    date = datetime.fromisoformat(latest["created_at"].replace("Z", "+00:00")).date().isoformat()
    status = latest.get("status")
    conclusion = latest.get("conclusion")
    if status != "completed":
        health = "Running"
    elif conclusion == "success":
        health = "Healthy"
    else:
        health = f"Attention: {conclusion or 'unknown'}"
    return names, date, health


def main() -> None:
    repos = github_get(
        f"https://api.github.com/users/{OWNER}/repos"
        "?per_page=100&sort=updated&direction=desc&type=owner"
    ) or []
    maintained = [
        repo for repo in repos
        if not repo["fork"]
        and not repo["archived"]
        and repo["name"].lower() != OWNER.lower()
    ]
    visible = sorted(maintained, key=lambda repo: repo.get("pushed_at") or "", reverse=True)[:LIMIT]

    repo_rows = [
        "| Project | What it helps with | Last code push |",
        "| --- | --- | ---",
    ]
    for repo in visible:
        name = repo["name"]
        description = CURATED.get(name) or repo.get("description") or fallback_description(name)
        description = " ".join(description.replace("|", "\\|").split())
        if len(description) > 88:
            description = description[:85].rsplit(" ", 1)[0] + "…"
        pushed = repo.get("pushed_at")
        updated = datetime.fromisoformat(pushed.replace("Z", "+00:00")).date().isoformat() if pushed else "—"
        url = repo.get("homepage") or repo["html_url"]
        repo_rows.append(f"| [{name}]({url}) | {description} | {updated} |")

    ops_rows = [
        "| Project | Scheduled workflows | Latest run | Status |",
        "| --- | --- | --- | --- |",
    ]
    automated_projects = 0
    healthy_automations = 0
    for repo, label in TRACKED.items():
        workflow, last_run, health = workflow_status(repo)
        if workflow == "None detected":
            continue
        automated_projects += 1
        if health in ("Healthy", "Ready"):
            healthy_automations += 1
        actions_url = f"https://github.com/{OWNER}/{repo}/actions"
        ops_rows.append(f"| [{label}]({actions_url}) | {workflow} | {last_run} | {health} |")

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    recently_active = sum(
        datetime.fromisoformat(repo["updated_at"].replace("Z", "+00:00")) >= cutoff
        for repo in maintained
    )
    maintained_names = {repo["name"] for repo in maintained}
    featured = [
        ("Analytics & reporting", "dynamic-btc-analytics-dashboard",
         "Combine cycle, momentum and drawdown views for interpretation"),
        ("Scenario & risk tools", "btc-grid-sandbox",
         "Compare grid cash flow, open inventory and range risk"),
        ("Learning & assessment", "ARE-YOU-READY-",
         "Route beginner and advanced learners through an adaptive assessment"),
        ("Productivity & workflows", "Fade-self-erasing-clipboard",
         "Organize temporary content and control when it expires"),
    ]
    work_rows = [
        "| Work area | Example | What the product helps someone do |",
        "| --- | --- | --- |",
        *(
            f"| {area} | [{repo}](https://github.com/{OWNER}/{repo}) | {purpose} |"
            for area, repo, purpose in featured if repo in maintained_names
        ),
    ]
    refreshed = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    health_value = (
        f"{healthy_automations}/{automated_projects}"
        if automated_projects else "0/0"
    )
    snapshot_rows = [
        f"![Maintained projects](https://img.shields.io/badge/Maintained_projects-{len(maintained)}-2563eb?style=for-the-badge)",
        f"![Recently active](https://img.shields.io/badge/Active_30d-{recently_active}-dc2626?style=for-the-badge)",
        f"![Automated projects](https://img.shields.io/badge/Automated_projects-{automated_projects}-eab308?style=for-the-badge)",
        f"![Automation health](https://img.shields.io/badge/Automation_health-{health_value}-2563eb?style=for-the-badge)",
        "",
        "### Work in practice",
        "",
        *work_rows,
        "",
        f"<sub>Updated {refreshed} · Automation health means healthy or ready scheduled workflows among tracked production projects.</sub>",
    ]

    readme = open(README, encoding="utf-8").read()
    updated_readme = replace_block(readme, REPOS_START, REPOS_END, repo_rows)
    updated_readme = replace_block(updated_readme, OPS_START, OPS_END, ops_rows)
    updated_readme = replace_block(
        updated_readme, SNAPSHOT_START, SNAPSHOT_END, snapshot_rows
    )

    if updated_readme != readme:
        with open(README, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(updated_readme)


if __name__ == "__main__":
    main()
