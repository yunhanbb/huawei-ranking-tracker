#!/usr/bin/env python3
import json
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"
DATA_DIR = ROOT / "site" / "data"
CURRENT_PATH = DATA_DIR / "rankings.json"
HISTORY_PATH = DATA_DIR / "history.json"

BASE = "https://devdata2.huaweicloud.cn"
DETAIL_URL = (
    BASE
    + "/rest/developer/fwdo/rest/developer/servlet"
    + "/hdcompetitionservice/v1/competition/get-competition-detail"
)
RANKING_URL = (
    BASE
    + "/rest/developer/fwdo/rest/developer/servlet"
    + "/hdcompetitionservice/v1/teams/ranking"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def post_json(url: str, payload: dict[str, Any], referer: str, retries: int = 3) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://developer.huaweicloud.cn",
        "Referer": referer,
        "User-Agent": "Mozilla/5.0 huawei-ranking-tracker/1.0",
    }

    last_error: Exception | None = None
    context = ssl.create_default_context()
    for attempt in range(1, retries + 1):
        try:
            request = Request(url, data=body, headers=headers, method="POST")
            with urlopen(request, timeout=30, context=context) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                raw = response.read().decode(charset)
                return json.loads(raw)
        except URLError as exc:
            last_error = exc
            reason = getattr(exc, "reason", None)
            if isinstance(reason, ssl.SSLCertVerificationError):
                context = ssl._create_unverified_context()
                continue
            if attempt < retries:
                time.sleep(2 * attempt)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2 * attempt)

    raise RuntimeError(f"request failed after {retries} attempts: {url}: {last_error}")


def extract_url_id(target: dict[str, Any]) -> str:
    if target.get("competition_url_id"):
        return str(target["competition_url_id"])

    url = str(target.get("competition_url", ""))
    parts = [part for part in urlparse(url).path.split("/") if part]
    for index, part in enumerate(parts):
        if part == "information" and index + 1 < len(parts):
            return parts[index + 1]

    raise ValueError("target needs competition_url_id or a Huawei competition information URL")


def first_result(response: dict[str, Any]) -> dict[str, Any]:
    if isinstance(response.get("data"), dict):
        return response["data"]
    results = response.get("results")
    if isinstance(results, list) and results:
        return results[0]
    raise RuntimeError(f"unexpected competition detail response: {response}")


def ranking_payload(response: dict[str, Any]) -> dict[str, Any]:
    if isinstance(response.get("data"), dict):
        return response["data"]
    return response


def find_team(rows: list[dict[str, Any]], team: str) -> dict[str, Any] | None:
    needle = team.strip().lower()
    for row in rows:
        values = [
            row.get("team_name"),
            row.get("team_id"),
            row.get("user_id"),
            row.get("domain_name"),
        ]
        if any(str(value).strip().lower() == needle for value in values if value is not None):
            return row
    return None


def fetch_target(target: dict[str, Any], page_size: int) -> dict[str, Any]:
    competition_url_id = extract_url_id(target)
    referer = target.get("competition_url") or (
        f"https://developer.huaweicloud.cn/competition/information/{competition_url_id}/ranking"
    )

    detail = first_result(
        post_json(DETAIL_URL, {"competition_id": competition_url_id}, referer=referer)
    )
    stage_id = target.get("stage_id") or detail.get("current_stage_id")
    if not stage_id:
        raise RuntimeError(f"no stage_id found for competition {competition_url_id}")

    competition_type = target.get("competition_type")
    if competition_type is None:
        competition_type = detail.get("type", 0)

    offset = 1
    all_rows: list[dict[str, Any]] = []
    target_row: dict[str, Any] | None = None
    total = None
    refresh_time = None
    stage_name = None

    while True:
        payload = {
            "competition_id": competition_url_id,
            "stage_id": stage_id,
            "area_id": target.get("area_id", ""),
            "offset": offset,
            "limit": page_size,
            "competition_type": competition_type,
        }
        ranking = ranking_payload(post_json(RANKING_URL, payload, referer=referer))
        if ranking.get("error_code"):
            raise RuntimeError(f"ranking API error: {ranking}")

        rows = ranking.get("team_ranking_list") or []
        if not isinstance(rows, list):
            raise RuntimeError(f"unexpected ranking rows: {ranking}")

        all_rows.extend(rows)
        target_row = target_row or find_team(rows, str(target["team"]))
        total = ranking.get("total", total)
        refresh_time = ranking.get("refresh_time", refresh_time)
        stage_name = ranking.get("stage_name", stage_name)

        if target_row or not rows:
            break
        if isinstance(total, int) and offset + page_size > total:
            break
        offset += page_size

    return {
        "name": target.get("name") or detail.get("title") or competition_url_id,
        "competition_url": referer,
        "competition_url_id": competition_url_id,
        "competition_id": detail.get("competition_id"),
        "competition_title": detail.get("title"),
        "team": target["team"],
        "stage_id": stage_id,
        "stage_name": stage_name,
        "total": total,
        "refresh_time": refresh_time,
        "found": target_row is not None,
        "target": target_row,
        "top": all_rows[:20],
    }


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    config = load_json(CONFIG_PATH, {})
    targets = config.get("targets") or []
    if not targets:
        raise RuntimeError("config.json has no targets")

    page_size = int(config.get("page_size", 100))
    checked_at = utc_now()
    results = []
    errors = []

    for target in targets:
        try:
            results.append(fetch_target(target, page_size))
        except Exception as exc:
            errors.append({"target": target, "error": str(exc)})

    current = {
        "generated_at": checked_at,
        "source": "Huawei Cloud Developer competition ranking API",
        "targets": results,
        "errors": errors,
    }
    save_json(CURRENT_PATH, current)

    history_limit = int(config.get("history_limit", 300))
    history = load_json(HISTORY_PATH, {"items": []})
    items = history.get("items", [])
    for result in results:
        row = result.get("target") or {}
        items.append(
            {
                "checked_at": checked_at,
                "name": result.get("name"),
                "competition_url_id": result.get("competition_url_id"),
                "team": result.get("team"),
                "found": result.get("found"),
                "ranking": row.get("ranking"),
                "score": row.get("score"),
                "ranking_change": row.get("ranking_change"),
                "ranking_change_num": row.get("ranking_change_num"),
                "refresh_time": result.get("refresh_time"),
            }
        )
    save_json(HISTORY_PATH, {"items": items[-history_limit:]})

    if errors:
        print(json.dumps(current, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(current, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
