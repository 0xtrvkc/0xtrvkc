#!/usr/bin/env python3
"""Refresh the repository section of the GitHub profile README."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime

OWNER = "0xtrvkc"
README = "README.md"
START = "<!-- RECENT-REPOS:START -->"
END = "<!-- RECENT-REPOS:END -->"
LIMIT = 12

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
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fallback_description(name: str) -> str:
    words = re.sub(r"[-_]+", " ", name).strip()
    return words[:1].upper() + words[1:] if words else "Project repository"


def main() -> None:
    repos = github_get(
        f"https://api.github.com/users/{OWNER}/repos"
        "?per_page=100&sort=updated&direction=desc&type=owner"
    )
    visible = [
        repo for repo in repos
        if not repo["fork"]
        and not repo["archived"]
        and repo["name"].lower() != OWNER.lower()
    ][:LIMIT]

    rows = [
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
        rows.append(f"| [{name}]({url}) | {description} | {language} | {updated} |")

    readme = open(README, encoding="utf-8").read()
    block = START + "\n" + "\n".join(rows) + "\n" + END
    updated_readme, count = re.subn(
        re.escape(START) + r".*?" + re.escape(END),
        block,
        readme,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError("README repository markers are missing or duplicated")

    if updated_readme != readme:
        with open(README, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(updated_readme)


if __name__ == "__main__":
    main()
