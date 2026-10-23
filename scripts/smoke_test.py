"""Smoke test HTTP minimal pour l'image Docker."""

from __future__ import annotations

import argparse
import json
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


PAYLOAD = {
    "machine_type": "A",
    "air_temperature_k": 298.1,
    "process_temperature_k": 308.6,
    "rotational_speed_rpm": 1551,
    "torque_nm": 42.8,
    "tool_wear_min": 0,
}


def request(base_url: str, path: str, payload: dict | None = None) -> tuple[int, dict | str]:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request_obj = Request(base_url + path, data=body, headers=headers, method="POST" if body else "GET")
    with urlopen(request_obj, timeout=5) as response:
        content = response.read().decode()
        try:
            return response.status, json.loads(content)
        except json.JSONDecodeError:
            return response.status, content


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    last_error = None
    ready = False
    for _ in range(20):
        try:
            status, _ = request(args.base_url, "/health")
            if status == 200:
                ready = True
                break
            last_error = f"/health returned HTTP {status}"
            time.sleep(0.5)
        except (ConnectionError, OSError, TimeoutError, URLError) as exc:
            last_error = exc
            time.sleep(0.5)
    if not ready:
        raise RuntimeError(f"service unavailable: {last_error}")

    for path in ("/health", "/model-info", "/metrics", "/v1/health", "/v1/model-info", "/v1/metrics"):
        status, _ = request(args.base_url, path)
        if status != 200:
            raise RuntimeError(f"{path} returned HTTP {status}")
    status, prediction = request(args.base_url, "/v1/predict", PAYLOAD)
    if status != 200 or not isinstance(prediction, dict):
        raise RuntimeError(f"/predict returned HTTP {status}: {prediction}")
    for field in ("prediction", "probability", "model_name", "alias", "version"):
        if field not in prediction:
            raise RuntimeError(f"/predict response misses {field}")
    print("Docker smoke test: ACCEPT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
