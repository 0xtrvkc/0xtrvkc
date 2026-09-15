#!/usr/bin/env python3
"""Refresh project and delivery-operations sections of the profile README."""

from __future__ import annotations

import base64
from collections import Counter
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
    "ARE-YOU-READY-": "Adaptive trading-readiness assessment for beginner and quantitative routes",
    "btc-grid-sandbox": "Grid-strategy backtesting, cash-flow, APR, and risk analysis",
    "btc-options-sandbox": "BTC Friday 0DTE range-risk and options research workspace",
    "grid-bot-post-mortem": "Grid-bot performance, inventory, and cash-flow review",
    "tradingPortfolioDashboard": "Trading portfolio monitoring and analytics dashboard",
    "Fade-self-erasing-clipboard": "Cross-device clipboard with controlled, self-erasing content",
    "prop_challenge_simulator": "Prop-challenge probability and risk simulator",
    "btcEmaCrossBacktest": "BTC dual-EMA crossover research and backtesting",
    "btcLoanAnalyzer": "BTC-collateral loan, LTV, and repayment scenario modelling",
    "dynamic-btc-analytics-dashboard": "MVRV, market-cycle, momentum, and drawdown analytics",
    "pvd-vs-investment": "Provident-fund versus independent-investment comparison",
    "itd-oi-db": "Gold intraday open-interest and volatility research database",
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

    names = ", ".join(workflow["name"] for workflow in scheduled)
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
    visible = maintained[:LIMIT]

    repo_rows = [
        "| Project | Deliverable | Stack | Last updated |",
        "| --- | --- | --- | --- |",
    ]
    for repo in visible:
        name = repo["name"]
        description = CURATED.get(name) or repo.get("description") or fallback_description(name)
        description = description.replace("|", "\\|").replace("\n", " ")
        language = repo.get("language") or "—"
        updated = datetime.fromisoformat(repo["updated_at"].replace("Z", "+00:00")).date().isoformat()
        url = repo.get("homepage") or repo["html_url"]
        repo_rows.append(f"| [{name}]({url}) | {description} | {language} | {updated} |")

    ops_rows = [
        "| Project | Scheduled automation | Latest run | Health |",
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
    language_counts = Counter(repo.get("language") or "Other" for repo in maintained)
    language_lines = [
        f'    "{language.replace(chr(34), chr(39))}" : {count}'
        for language, count in language_counts.most_common(5)
    ] or ['    "No language data" : 1']
    refreshed = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    health_value = (
        f"{healthy_automations}/{automated_projects}"
        if automated_projects else "0/0"
    )
    snapshot_rows = [
        f"![Maintained projects](https://img.shields.io/badge/Maintained_projects-{len(maintained)}-334155?style=for-the-badge)",
        f"![Recently active](https://img.shields.io/badge/Active_30d-{recently_active}-2563eb?style=for-the-badge)",
        f"![Automated projects](https://img.shields.io/badge/Automated_projects-{automated_projects}-7c3aed?style=for-the-badge)",
        f"![Automation health](https://img.shields.io/badge/Automation_health-{health_value}-059669?style=for-the-badge)",
        "",
        "```mermaid",
        "pie showData",
        "    title Technology mix across maintained projects",
        *language_lines,
        "```",
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
