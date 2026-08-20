from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pydantic import BaseModel, SecretStr

from paperflow.config import load_config_bundle
from paperflow.llm.openrouter import OpenRouterClient, UrllibJsonTransport


class StubOutput(BaseModel):
    ok: bool


def test_stub_server_receives_ordered_fallbacks_and_returns_metadata() -> None:
    captured: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"])
            captured.append(json.loads(self.rfile.read(length)))
            response = {
                "id": "stub-request",
                "model": "z-ai/glm-4.7-flash",
                "provider": "StubProvider",
                "choices": [
                    {"message": {"role": "assistant", "content": '{"ok":true}'}}
                ],
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 2,
                    "cost": 0.000001,
                },
            }
            body = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        root = Path(__file__).parents[2]
        config_data = load_config_bundle(root).models.model_dump(mode="python")
        config_data["base_url"] = f"http://127.0.0.1:{server.server_port}/api/v1"
        config_data["routing"]["require_structured_outputs"] = True
        # The production config requires HTTPS; the local stub uses an injected
        # validated copy with the URL constructed after validation.
        config = load_config_bundle(root).models.model_copy(
            update={"base_url": config_data["base_url"]}
        )
        client = OpenRouterClient(
            model_config=config,
            api_key=SecretStr("stub-placeholder"),
            transport=UrllibJsonTransport(),
            transient_retry_count=0,
        )

        result = client.structured_chat(
            task_name="stub",
            messages=[{"role": "user", "content": "Return true."}],
            schema=StubOutput,
            model_chain=["deepseek_v4_flash", "glm_4_7_flashx"],
            request_metadata={"run_id": "stub-run"},
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert captured[0]["models"] == [
        "deepseek/deepseek-v4-flash-0731",
        "z-ai/glm-4.7-flash",
    ]
    assert result.actual_model == "z-ai/glm-4.7-flash"
    assert result.provider == "StubProvider"
    assert result.parsed.ok is True
