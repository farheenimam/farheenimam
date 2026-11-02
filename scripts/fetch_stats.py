"""Fetch live GitHub stats for farheenimam and write them to a JSON file.

Needs STATS_TOKEN (a personal access token with read:user and repo read access).
Usage: python scripts/fetch_stats.py assets/stats.json
"""
import datetime as dt
import json
import os
import sys

import requests

LOGIN = "farheenimam"
API = "https://api.github.com/graphql"
TOKEN = os.environ["STATS_TOKEN"]
HEADERS = {"Authorization": f"bearer {TOKEN}"}

USER_Q = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      nodes {
        stargazerCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
      }
    }
  }
}
"""

YEAR_Q = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def gql(query, variables):
    r = requests.post(API, json={"query": query, "variables": variables}, headers=HEADERS, timeout=60)
    r.raise_for_status()
    body = r.json()
    if "errors" in body:
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]


def parse_day(s):
    return dt.date.fromisoformat(s)


def fmt_range(a, b):
    return f"{a:%b %d} - {b:%b %d}"


def main(out_path):
    today = dt.datetime.now(dt.timezone.utc).date()
    user = gql(USER_Q, {"login": LOGIN})["user"]
    created = dt.datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00")).date()

    # Sum yearly contribution data from account creation to today.
    days = {}
    commits = prs = issues = 0
    year = created.year
    while year <= today.year:
        start = max(dt.date(year, 1, 1), created)
        end = min(dt.date(year, 12, 31), today)
        if start <= end:
            c = gql(YEAR_Q, {
                "login": LOGIN,
                "from": f"{start.isoformat()}T00:00:00Z",
                "to": f"{end.isoformat()}T23:59:59Z",
            })["user"]["contributionsCollection"]
            commits += c["totalCommitContributions"]
            prs += c["totalPullRequestContributions"]
            issues += c["totalIssueContributions"]
            for week in c["contributionCalendar"]["weeks"]:
                for d in week["contributionDays"]:
                    days[parse_day(d["date"])] = d["contributionCount"]
        year += 1

    ordered = sorted(d for d in days if d <= today)
    counts = [days[d] for d in ordered]
    total = sum(counts)

    # Current streak: count back from today; if today has no contributions yet, start from yesterday.
    cur_end = today if days.get(today, 0) > 0 else today - dt.timedelta(days=1)
    cur_len, d = 0, cur_end
    while days.get(d, 0) > 0:
        cur_len += 1
        d -= dt.timedelta(days=1)
    cur_start = d + dt.timedelta(days=1)

    # Longest streak across all days.
    best_len, best_start, best_end = 0, None, None
    run_len, run_start = 0, None
    for day in ordered:
        if days[day] > 0:
            if run_len == 0:
                run_start = day
            run_len += 1
            if run_len > best_len:
                best_len, best_start, best_end = run_len, run_start, day
        else:
            run_len = 0

    # Heatmap: last 371 days (53 weeks x 7), stored row-major for the 7-row x 53-column grid.
    window = [today - dt.timedelta(days=370 - i) for i in range(371)]
    window_counts = [days.get(d, 0) for d in window]
    nonzero = sorted(c for c in window_counts if c > 0)
    def q(p):
        return nonzero[min(len(nonzero) - 1, int(p * len(nonzero)))] if nonzero else 1
    q1, q2, q3 = q(0.25), q(0.5), q(0.75)
    def level(c):
        if c == 0:
            return 0
        if c <= q1:
            return 1
        if c <= q2:
            return 2
        if c <= q3:
            return 3
        return 4
    levels = [0] * 371
    for i, c in enumerate(window_counts):
        week, dow = i // 7, i % 7
        levels[dow * 53 + week] = level(c)

    # Language share by bytes across owned, non-fork repos.
    sizes = {}
    stars = 0
    for repo in user["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
    total_bytes = sum(sizes.values()) or 1
    languages = [
        {"name": n, "pct": round(100 * s / total_bytes)}
        for n, s in sorted(sizes.items(), key=lambda kv: -kv[1])[:5]
    ]

    last_year = sum(c for d, c in days.items() if d > today - dt.timedelta(days=365))
    stats = {
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "totalContributions": total,
        "totalRange": f"{created:%b %d, %Y} - Present",
        "currentStreak": cur_len,
        "currentRange": fmt_range(cur_start, cur_end) if cur_len else "-",
        "longestStreak": best_len,
        "longestRange": fmt_range(best_start, best_end) if best_len else "-",
        "lastYear": last_year,
        "stars": stars,
        "commits": commits,
        "prs": prs,
        "issues": issues,
        "reposContributed": user["repositoriesContributedTo"]["totalCount"],
        "languages": languages,
        "levels": levels,
    }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(f"wrote {out_path}: total={total} streak={cur_len} longest={best_len}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "assets/stats.json")
