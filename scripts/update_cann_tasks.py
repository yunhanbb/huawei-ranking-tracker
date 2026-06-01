#!/usr/bin/env python3
import json
import re
import ssl
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "site" / "data"
OUTPUT_PATH = DATA_DIR / "cann_tasks.json"

BASE = "https://gitcode.com"
DISCUSSION_URL = f"{BASE}/org/cann/discussions/22"
GROUP_URL = f"{BASE}/api/v2/groups/cann"
DETAIL_URL = f"{BASE}/api/v1/discuss/detail"
COMMENT_URL = f"{BASE}/api/v1/discuss/comment/page"

SOURCE_TYPE = 1
SERIAL_NUMBER = 22
START_DATE = "2026-05-29T00:00:00+08:00"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    retries: int = 3,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": BASE,
        "Referer": DISCUSSION_URL,
        "User-Agent": "Mozilla/5.0 huawei-ranking-tracker/1.0",
    }
    context = ssl.create_default_context()
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            request = Request(url, data=body, headers=headers, method=method)
            with urlopen(request, timeout=30, context=context) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset))
        except URLError as exc:
            last_error = exc
            reason = getattr(exc, "reason", None)
            if isinstance(reason, ssl.SSLCertVerificationError):
                context = ssl._create_unverified_context()
                continue
            if attempt < retries:
                time.sleep(2 * attempt)
        except (HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2 * attempt)

    raise RuntimeError(f"request failed after {retries} attempts: {url}: {last_error}")


def clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_tasks(markdown: str) -> list[dict[str, Any]]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", markdown, flags=re.I | re.S)
    tasks: list[dict[str, Any]] = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.I | re.S)
        if len(cells) < 6:
            continue

        task_id = clean_text(cells[0])
        if not re.fullmatch(r"20260529-\d{1,2}", task_id):
            continue

        link_match = re.search(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', cells[1], flags=re.I | re.S)
        title = clean_text(link_match.group(2) if link_match else cells[1])
        link = link_match.group(1) if link_match else ""
        tasks.append(
            {
                "id": task_id,
                "number": int(task_id.rsplit("-", 1)[1]),
                "title": title,
                "link": link,
                "status": clean_text(cells[2]),
                "assignees": clean_text(cells[3]),
                "bonus": clean_text(cells[4]),
                "deadline": clean_text(cells[5]),
                "application_count": 0,
                "applications": [],
            }
        )

    return tasks


def extract_field(content: str, label: str) -> str:
    pattern = rf"【{re.escape(label)}】\s*[：:]\s*(.+)"
    match = re.search(pattern, content)
    if not match:
        return ""
    return match.group(1).splitlines()[0].strip()


def extract_task_ids(content: str) -> list[str]:
    task_ids = set(re.findall(r"20260529-\d{1,2}", content))
    field = extract_field(content, "任务序号")
    if field and re.fullmatch(r"\d{1,2}", field.strip()):
        value = int(field.strip())
        if 1 <= value <= 20:
            task_ids.add(f"20260529-{value}")
    return sorted(task_ids, key=lambda item: int(item.rsplit("-", 1)[1]))


def is_application(content: str) -> bool:
    return "报名" in extract_field(content, "状态") or "【状态】" in content and "报名" in content


def fetch_comments(discuss_id: str) -> list[dict[str, Any]]:
    first_page = request_json(
        COMMENT_URL,
        method="POST",
        payload={"discuss_id": discuss_id, "page": 1, "per_page": 10},
    )
    pages = int(first_page.get("pages") or 1)
    records = list(first_page.get("records") or [])

    for page in range(2, pages + 1):
        data = request_json(
            COMMENT_URL,
            method="POST",
            payload={"discuss_id": discuss_id, "page": page, "per_page": 10},
        )
        records.extend(data.get("records") or [])

    return records


def build_data() -> dict[str, Any]:
    group = request_json(GROUP_URL)
    source_id = str(group["id"])
    detail = request_json(
        DETAIL_URL,
        method="POST",
        payload={"source_type": SOURCE_TYPE, "source_id": source_id, "serial_number": SERIAL_NUMBER},
    )
    tasks = parse_tasks(detail.get("md_content") or "")
    task_map = {task["id"]: task for task in tasks}

    considered = 0
    ignored = 0
    for comment in fetch_comments(detail["id"]):
        created_date = comment.get("created_date") or ""
        if created_date < START_DATE:
            continue
        content = comment.get("content") or ""
        task_ids = [task_id for task_id in extract_task_ids(content) if task_id in task_map]
        if not task_ids or not is_application(content):
            ignored += 1
            continue

        considered += 1
        application = {
            "comment_id": comment.get("id"),
            "serial_number": comment.get("serial_number"),
            "created_date": created_date,
            "user_name": comment.get("created_by_user_name"),
            "team": extract_field(content, "队名"),
            "gitcode_account": extract_field(content, "gitcode账号名") or comment.get("created_by_user_name"),
            "status": extract_field(content, "状态"),
            "link": extract_field(content, "链接"),
        }
        for task_id in task_ids:
            task_map[task_id]["applications"].append(application)

    for task in tasks:
        task["application_count"] = len(task["applications"])

    return {
        "generated_at": utc_now(),
        "source": DISCUSSION_URL,
        "source_id": source_id,
        "discussion_id": detail.get("id"),
        "discussion_title": detail.get("title"),
        "start_date": START_DATE,
        "task_count": len(tasks),
        "comment_total": detail.get("comment_total"),
        "application_comment_count": considered,
        "ignored_comment_count": ignored,
        "tasks": tasks,
    }


def main() -> int:
    data = build_data()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"update CANN tasks failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
