from __future__ import annotations

from typing import Any, Dict

import httpx

from utils import EnvConfig


async def get_json(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    r = await client.get(url)
    r.raise_for_status()
    return r.json()


async def snapshot_summary(env: EnvConfig, client: httpx.AsyncClient) -> Dict[str, Any]:
    return await get_json(client, f"{env.result_service_base_url}/stats/summary")


async def health_checks(env: EnvConfig, client: httpx.AsyncClient) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        out["task_api_health"] = await get_json(client, f"{env.task_api_base_url}/health")
    except Exception as e:
        out["task_api_health_error"] = str(e)
    try:
        out["result_health"] = await get_json(client, f"{env.result_service_base_url}/health")
    except Exception as e:
        out["result_health_error"] = str(e)
    return out
