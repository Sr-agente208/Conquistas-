#!/usr/bin/env python3
"""Atualiza os dados do site a partir do tópico `microsoft-rewards` no GitHub.

Uso:
    python scripts/fetch_repos.py            # requer `gh` autenticado
    python scripts/fetch_repos.py --out docs/data

Gera:
    docs/data/repos.json   (para uso programático)
    docs/data/repos.js     (window.REPOS_DATA, funciona até em file://)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

TOPIC = "microsoft-rewards"
SOURCE_URL = f"https://github.com/topics/{TOPIC}"

FIELDS = (
    "full_name,html_url,description,homepage,stargazers_count,forks_count,language,"
    "topics,pushed_at,created_at,archived,fork,open_issues_count,license,owner"
)


def gh_search(page: int) -> dict:
    cmd = [
        "gh",
        "api",
        "-X",
        "GET",
        "search/repositories",
        "-f",
        f"q=topic:{TOPIC}",
        "-f",
        "sort=stars",
        "-f",
        "order=desc",
        "-f",
        "per_page=100",
        "-f",
        f"page={page}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(
            "Falha ao consultar o GitHub (gh). Verifique `gh auth status`.\n"
            f"{result.stderr.strip()}"
        )
    return json.loads(result.stdout)


def collect() -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        payload = gh_search(page)
        batch = payload.get("items", [])
        items.extend(batch)
        if len(batch) < 100 or len(items) >= payload.get("total_count", 0):
            break
        page += 1
    return items


def normalize(item: dict) -> dict:
    license_info = item.get("license") or {}
    return {
        "full_name": item["full_name"],
        "owner": item["owner"]["login"],
        "avatar": item["owner"].get("avatar_url", ""),
        "description": (item.get("description") or "").strip(),
        "url": item["html_url"],
        "homepage": (item.get("homepage") or "").strip(),
        "stars": item.get("stargazers_count", 0),
        "forks": item.get("forks_count", 0),
        "open_issues": item.get("open_issues_count", 0),
        "language": item.get("language"),
        "topics": [t for t in item.get("topics", []) if t != TOPIC],
        "pushed_at": item.get("pushed_at"),
        "created_at": item.get("created_at"),
        "archived": bool(item.get("archived")),
        "fork": bool(item.get("fork")),
        "license": license_info.get("spdx_id"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/data", help="pasta de saída")
    args = parser.parse_args()

    raw = collect()
    repos = sorted((normalize(item) for item in raw), key=lambda r: (-r["stars"], r["full_name"]))
    languages: dict[str, int] = {}
    for repo in repos:
        key = repo["language"] or "Sem linguagem"
        languages[key] = languages.get(key, 0) + 1

    payload = {
        "topic": TOPIC,
        "source_url": SOURCE_URL,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "total": len(repos),
        "total_stars": sum(r["stars"] for r in repos),
        "languages": dict(sorted(languages.items(), key=lambda kv: (-kv[1], kv[0]))),
        "repos": repos,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (out_dir / "repos.json").write_text(text + "\n", encoding="utf-8")
    (out_dir / "repos.js").write_text(
        f"// Gerado por scripts/fetch_repos.py — não edite à mão.\nwindow.REPOS_DATA = {text};\n",
        encoding="utf-8",
    )
    print(
        f"{len(repos)} repositórios, {payload['total_stars']:,} estrelas, "
        f"{len(languages)} linguagens → {out_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
