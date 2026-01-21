from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yaml

from loadgen import generate_load
from report import compute_http_report, diff_stats
from snapshots import health_checks, snapshot_summary
from utils import (
    EnvConfig,
    TestSpec,
    ensure_dir,
    folder_name_for_test,
    today_ymd_utc,
    utc_now_iso,
    write_csv,
    write_json,
    write_text,
)


def load_env(path: str) -> EnvConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return EnvConfig(
        project_name=str(data["project_name"]),
        task_api_base_url=str(data["task_api_base_url"]).rstrip("/"),
        result_service_base_url=str(data["result_service_base_url"]).rstrip("/"),
        default_headers=(data.get("default_headers") or {}),
        request_timeout_sec=float(data.get("request_timeout_sec", 10)),
        verify_tls=bool(data.get("verify_tls", True)),
    )


def load_matrix(path: str) -> List[TestSpec]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    raw_tests = data.get("tests") or []
    if not isinstance(raw_tests, list):
        raise SystemExit("test_matrix.yaml must contain a top-level key 'tests' with a list")

    out: List[TestSpec] = []
    for t in raw_tests:
        test_id = str(t.get("test_id", ""))

        schedule = t.get("schedule", None)

        if schedule is not None:
            if not isinstance(schedule, list):
                raise SystemExit(f"Invalid 'schedule' in test {test_id}: must be a list")
            duration_sec = int(sum(int(seg.get("duration_sec", 0)) for seg in schedule))
            rate = float(schedule[0].get("rate", 0)) if len(schedule) > 0 else 0.0
        else:
            try:
                rate = float(t["rate"])
                duration_sec = int(t["duration_sec"])
            except KeyError as e:
                raise SystemExit(f"Missing required key {e} in test {test_id}") from e

        out.append(
            TestSpec(
                test_id=str(t["test_id"]),
                task_type=str(t["task_type"]),
                complexity=int(t["complexity"]),
                rate=rate,
                duration_sec=duration_sec,
                concurrency=int(t["concurrency"]),
                mode=str(t["mode"]),
                schedule=schedule,
            )
        )

    return out


def select_tests(all_tests: List[TestSpec], test_id: Optional[str], group: Optional[str], run_all: bool) -> List[TestSpec]:
    if test_id:
        sel = [t for t in all_tests if t.test_id == test_id]
        if not sel:
            raise SystemExit(f"Unknown test_id: {test_id}")
        return sel
    if group:
        g = group.strip().upper()
        sel = [t for t in all_tests if t.test_id.upper().startswith(g + "_")]
        if not sel:
            raise SystemExit(f"No tests for group: {group}")
        return sel
    if run_all:
        return all_tests
    raise SystemExit("Provide --test-id or --group or --all")


async def drain_end_to_end(env: EnvConfig, client: httpx.AsyncClient, out_jsonl: Path, poll_sec: int, timeout_sec: int) -> None:
    start = asyncio.get_event_loop().time()
    while True:
        now = asyncio.get_event_loop().time()
        if now - start > timeout_sec:
            with out_jsonl.open("a", encoding="utf-8") as f:
                f.write(f'{{"timestamp_utc":"{utc_now_iso()}","event":"drain_timeout"}}\n')
            return

        stats = await snapshot_summary(env, client)
        counts = stats.get("status_counts", {}) or {}
        pending = int(counts.get("PENDING", 0))
        dispatched = int(counts.get("DISPATCHED", 0))
        running = int(counts.get("RUNNING", 0))

        with out_jsonl.open("a", encoding="utf-8") as f:
            f.write(
                (
                    f'{{"timestamp_utc":"{utc_now_iso()}","pending":{pending},'
                    f'"dispatched":{dispatched},"running":{running}}}\n'
                )
            )

        if pending == 0 and dispatched == 0 and running == 0:
            return

        await asyncio.sleep(poll_sec)


async def run_one(env: EnvConfig, spec: TestSpec, autoscaling: str, workers: str, base_results: Path) -> Path:
    day_dir = base_results / today_ymd_utc()
    ensure_dir(day_dir)

    run_dir = day_dir / folder_name_for_test(spec, workers)
    ensure_dir(run_dir)

    start_time = utc_now_iso()

    timeout = httpx.Timeout(env.request_timeout_sec)
    async with httpx.AsyncClient(headers=env.default_headers, timeout=timeout, verify=env.verify_tls) as client:
        meta: Dict[str, Any] = {
            "project_name": env.project_name,
            "test_id": spec.test_id,
            "task_type": spec.task_type,
            "complexity": spec.complexity,
            "rate": spec.rate,
            "duration_sec": spec.duration_sec,
            "concurrency": spec.concurrency,
            "mode": spec.mode,
            "schedule": getattr(spec, "schedule", None),
            "urls": {
                "task_api_base_url": env.task_api_base_url,
                "result_service_base_url": env.result_service_base_url,
            },
            "autoscaling": autoscaling,
            "workers": workers,
            "start_time_utc": start_time,
            "end_time_utc": None,
            "notes": "",
        }
        write_json(run_dir / "meta.json", meta)

        hc = await health_checks(env, client)
        write_json(run_dir / "health.json", hc)

        stats_before = await snapshot_summary(env, client)
        write_json(run_dir / "stats_before.json", stats_before)

        load_start = utc_now_iso()
        req_results = await generate_load(client, env.task_api_base_url, spec)
        load_end = utc_now_iso()

        rows = []
        for r in req_results:
            rows.append(
                {
                    "timestamp_utc": r.timestamp_utc,
                    "status_code": r.status_code,
                    "ok": str(bool(r.ok)),
                    "latency_ms": f"{r.latency_ms:.3f}",
                    "error_type": r.error_type,
                }
            )
        write_csv(run_dir / "request_results.csv", rows, fieldnames=["timestamp_utc", "status_code", "ok", "latency_ms", "error_type"])

        if spec.mode.lower() == "end_to_end":
            await drain_end_to_end(env, client, run_dir / "drain_log.jsonl", poll_sec=10, timeout_sec=1800)

        stats_after = await snapshot_summary(env, client)
        write_json(run_dir / "stats_after.json", stats_after)

        end_time = utc_now_iso()
        meta["end_time_utc"] = end_time
        meta["load_window_utc"] = {"load_start": load_start, "load_end": load_end}
        write_json(run_dir / "meta.json", meta)

        lat = [float(x.latency_ms) for x in req_results]
        oks = [bool(x.ok) for x in req_results]
        http_rep = compute_http_report(lat, oks, spec.duration_sec)
        stats_rep = diff_stats(stats_before, stats_after)

        report_out = {
            "http": http_rep,
            "stats_diff": stats_rep,
            "time_window_utc": {
                "start_time_utc": start_time,
                "end_time_utc": end_time,
                "load_start_utc": load_start,
                "load_end_utc": load_end,
            },
        }
        write_json(run_dir / "report.json", report_out)

        notes = (
            f"# Notes for {spec.test_id}\n\n"
            f"- CloudWatch screenshots taken: \n"
            f"- Observed bottleneck hypothesis: \n"
            f"- Anything unusual: \n"
            f"- Time window UTC: {start_time} → {end_time}\n"
        )
        write_text(run_dir / "notes.md", notes)

    print(f"\nRESULT_DIR: {run_dir}")
    print(f"TIME_UTC: {start_time} -> {end_time}")
    print(f"HTTP: error_rate={http_rep['error_rate']:.4f}, p95_ms={http_rep['p95_latency_ms']}, achieved_rps={http_rep['achieved_rps']}")
    print(f"PIPE: delta_completed={stats_rep['delta_completed']}, avg_wait_after={stats_rep['avg_wait_time_sec_after']}, throughput_after={stats_rep['throughput_tasks_per_min_after']}")
    return run_dir


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--matrix", required=True)
    ap.add_argument("--test-id", default=None)
    ap.add_argument("--group", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--autoscaling", required=True, choices=["on", "off"])
    ap.add_argument("--workers", default="MANUAL")
    args = ap.parse_args()

    env = load_env(args.env)
    matrix = load_matrix(args.matrix)
    selected = select_tests(matrix, args.test_id, args.group, args.all)

    base_results = Path(__file__).parent / "results"
    ensure_dir(base_results)

    for spec in selected:
        asyncio.run(run_one(env, spec, args.autoscaling, args.workers, base_results))


if __name__ == "__main__":
    main()
