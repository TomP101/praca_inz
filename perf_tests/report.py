from __future__ import annotations

from typing import Any, Dict, List, Optional


def _percentile(sorted_vals: List[float], p: float) -> Optional[float]:
    if not sorted_vals:
        return None
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1


def compute_http_report(latencies_ms: List[float], oks: List[bool], duration_sec: int) -> Dict[str, Any]:
    count = len(oks)
    ok_count = sum(1 for x in oks if x)
    error_count = count - ok_count
    error_rate = (error_count / count) if count else 0.0

    lat_sorted = sorted(latencies_ms)
    p50 = _percentile(lat_sorted, 50)
    p95 = _percentile(lat_sorted, 95)
    p99 = _percentile(lat_sorted, 99)

    achieved_rps = (count / duration_sec) if duration_sec > 0 else None

    return {
        "count": count,
        "ok_count": ok_count,
        "error_count": error_count,
        "error_rate": error_rate,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "p99_latency_ms": p99,
        "achieved_rps": achieved_rps,
    }


def diff_stats(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    b_counts = before.get("status_counts", {}) or {}
    a_counts = after.get("status_counts", {}) or {}

    out["total_tasks_before"] = before.get("total_tasks")
    out["total_tasks_after"] = after.get("total_tasks")

    out["status_counts_before"] = b_counts
    out["status_counts_after"] = a_counts

    out["delta_completed"] = (a_counts.get("COMPLETED", 0) - b_counts.get("COMPLETED", 0))

    out["avg_wait_time_sec_before"] = before.get("avg_wait_time_sec")
    out["avg_wait_time_sec_after"] = after.get("avg_wait_time_sec")

    out["avg_run_time_sec_by_type_before"] = before.get("avg_run_time_sec_by_type")
    out["avg_run_time_sec_by_type_after"] = after.get("avg_run_time_sec_by_type")

    out["throughput_tasks_per_min_before"] = before.get("throughput_tasks_per_min")
    out["throughput_tasks_per_min_after"] = after.get("throughput_tasks_per_min")

    return out
