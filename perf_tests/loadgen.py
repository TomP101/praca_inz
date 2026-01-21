from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from utils import TestSpec, utc_now_iso


@dataclass
class RequestResult:
    timestamp_utc: str
    status_code: int
    ok: bool
    latency_ms: float
    error_type: str


async def _post_task(client: httpx.AsyncClient, url: str, payload: Dict[str, Any]) -> RequestResult:
    ts = utc_now_iso()
    t0 = asyncio.get_event_loop().time()
    try:
        r = await client.post(url, json=payload)
        t1 = asyncio.get_event_loop().time()
        latency_ms = (t1 - t0) * 1000.0
        ok = r.status_code == 201
        return RequestResult(ts, r.status_code, ok, latency_ms, "none" if ok else "http_error")
    except httpx.TimeoutException:
        t1 = asyncio.get_event_loop().time()
        latency_ms = (t1 - t0) * 1000.0
        return RequestResult(ts, 0, False, latency_ms, "timeout")
    except Exception:
        t1 = asyncio.get_event_loop().time()
        latency_ms = (t1 - t0) * 1000.0
        return RequestResult(ts, 0, False, latency_ms, "exception")


def _normalize_schedule(spec: TestSpec) -> List[Dict[str, float]]:
    schedule = getattr(spec, "schedule", None)
    if schedule:
        out: List[Dict[str, float]] = []
        for seg in schedule:
            rate = float(seg.get("rate", 0))
            dur = float(seg.get("duration_sec", 0))
            if rate < 0:
                rate = 0.0
            if dur < 0:
                dur = 0.0
            out.append({"rate": rate, "duration_sec": dur})
        return out
    return [{"rate": float(spec.rate), "duration_sec": float(spec.duration_sec)}]


async def _run_segment(
    client: httpx.AsyncClient,
    url: str,
    payload: Dict[str, Any],
    rate: float,
    duration_sec: float,
    sem: asyncio.Semaphore,
    results: List[RequestResult],
) -> None:
    if duration_sec <= 0:
        return
    if rate <= 0:
        await asyncio.sleep(duration_sec)
        return

    total = int(round(rate * duration_sec))
    if total <= 0:
        await asyncio.sleep(duration_sec)
        return

    interval = 1.0 / rate

    async def one_request() -> None:
        async with sem:
            res = await _post_task(client, url, payload)
            results.append(res)

    start = asyncio.get_event_loop().time()
    tasks: List[asyncio.Task] = []
    for i in range(total):
        scheduled_at = start + i * interval
        now = asyncio.get_event_loop().time()
        delay = scheduled_at - now
        if delay > 0:
            await asyncio.sleep(delay)
        tasks.append(asyncio.create_task(one_request()))

    await asyncio.gather(*tasks, return_exceptions=True)


async def generate_load(client: httpx.AsyncClient, task_api_base_url: str, spec: TestSpec) -> List[RequestResult]:
    url = f"{task_api_base_url}/tasks/"
    payload = {
        "task_type": spec.task_type,
        "complexity": int(spec.complexity),
        "expected_duration_sec": None,
        "payload_size_kb": 0,
    }

    sem = asyncio.Semaphore(int(spec.concurrency))
    results: List[RequestResult] = []

    schedule = _normalize_schedule(spec)
    for seg in schedule:
        await _run_segment(
            client=client,
            url=url,
            payload=payload,
            rate=float(seg["rate"]),
            duration_sec=float(seg["duration_sec"]),
            sem=sem,
            results=results,
        )

    return results
