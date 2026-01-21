from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional



def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_ymd_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: Iterable[Dict[str, Any]], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


@dataclass(frozen=True)
class EnvConfig:
    project_name: str
    task_api_base_url: str
    result_service_base_url: str
    default_headers: Dict[str, str]
    request_timeout_sec: float
    verify_tls: bool


@dataclass(frozen=True)
class TestSpec:
    test_id: str
    task_type: str
    complexity: int
    rate: float
    duration_sec: int
    concurrency: int
    mode: str
    schedule: Optional[List[Dict[str, Any]]] = None


def folder_name_for_test(spec: TestSpec, workers: str) -> str:
    rate_str = str(int(spec.rate)) if float(spec.rate).is_integer() else str(spec.rate).replace(".", "p")
    return f"{spec.test_id}__rate{rate_str}__dur{spec.duration_sec}__conc{spec.concurrency}__workers{workers}"
