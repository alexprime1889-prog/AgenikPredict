"""
Dedicated background worker entrypoint for persistent task execution.
"""

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app import create_app
from app.config import Config
from app.services.artifact_store import get_artifact_store
from app.services.task_worker import TaskWorker
from app.utils.logger import get_logger


logger = get_logger("agenikpredict.worker")


class _WorkerHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        is_active = Config.TASK_EXECUTION_MODE == "worker"
        payload = {
            "status": "ok" if is_active else "standby",
            "service": "AgenikPredict Worker",
            "role": "worker",
            "task_execution_mode": Config.TASK_EXECUTION_MODE,
            "task_store_mode": Config.TASK_STORE_MODE,
            "task_read_source": Config.TASK_READ_SOURCE,
            "artifact_storage_mode": Config.ARTIFACT_STORAGE_MODE,
            "artifact_root": Config.ARTIFACT_ROOT,
            "simulation_data_dir": Config.OASIS_SIMULATION_DATA_DIR,
            "worker_consumer_active": is_active,
            "worker_standby": not is_active,
        }
        body = json.dumps(payload).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def start_health_server() -> ThreadingHTTPServer:
    port = int(os.environ.get("PORT", os.environ.get("FLASK_PORT", "5001")))
    server = ThreadingHTTPServer(("0.0.0.0", port), _WorkerHealthHandler)
    thread = threading.Thread(
        target=server.serve_forever,
        name="worker-health-server",
        daemon=True,
    )
    thread.start()
    logger.info("Worker health server listening on 0.0.0.0:%s/health", port)
    return server


def build_worker_app():
    errors = Config.validate()
    if errors:
        details = "\n".join(f"  - {err}" for err in errors)
        raise RuntimeError(f"Configuration errors:\n{details}\n\nPlease check the environment configuration")
    return create_app()


def main():
    if Config.TASK_EXECUTION_MODE != "worker":
        errors = Config.validate_standby()
        if errors:
            details = "\n".join(f"  - {err}" for err in errors)
            raise RuntimeError(
                f"Configuration errors:\n{details}\n\nPlease check the environment configuration"
            )
        if Config.ARTIFACT_PROBE_ON_STARTUP:
            logger.info(
                "Starting standby worker artifact probe: mode=%s",
                Config.ARTIFACT_STORAGE_MODE,
            )
            try:
                probe = get_artifact_store().probe()
            except Exception:
                logger.exception(
                    "Standby worker artifact probe failed: mode=%s",
                    Config.ARTIFACT_STORAGE_MODE,
                )
                raise
            logger.info(
                "Standby worker artifact probe succeeded: mode=%s",
                probe.get("mode", Config.ARTIFACT_STORAGE_MODE),
            )
        start_health_server()
        logger.info(
            "Worker process is in standby because TASK_EXECUTION_MODE=%s",
            Config.TASK_EXECUTION_MODE,
        )
        while True:
            time.sleep(5)
    app = build_worker_app()
    start_health_server()
    worker = TaskWorker(app=app)
    worker.run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
