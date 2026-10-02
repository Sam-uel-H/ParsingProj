from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.db.session import SessionFactory
from app.jobs.dispatch import publish_task
from app.parsing.models import LLMInvocation, ParsingResult
from tests.integration.test_phase11_jobs import create_case

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or os.getenv("RUN_WORKER_TESTS") != "1",
    reason="Requires Linux, Redis, PostgreSQL, and RUN_WORKER_TESTS=1.",
)


def wait_until(check, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except httpx.TransportError:
            pass
        time.sleep(0.2)
    raise AssertionError("Timed out waiting for worker/API state")


def test_real_worker_and_api_restart_preserve_results(phase1_client, tmp_path):
    data, _ = create_case(phase1_client, 50)
    job = phase1_client.post("/parsing-jobs", json=data).json()
    api_root = Path(__file__).resolve().parents[2]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    processes = []
    logs = []

    def start(name, args):
        log = (tmp_path / f"{name}.log").open("w+")
        logs.append(log)
        process = subprocess.Popen(
            [sys.executable, *args],
            cwd=api_root,
            start_new_session=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        processes.append(process)
        return process

    def stop(process):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)

    worker_args = [
        "-m",
        "celery",
        "-A",
        "tests.worker_fixture",
        "worker",
        "--concurrency=2",
        "--loglevel=warning",
    ]
    api_args = ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)]
    try:
        worker = start("worker-before", worker_args)
        start(
            "beat",
            [
                "-m",
                "celery",
                "-A",
                "app.jobs.celery_app",
                "beat",
                "--schedule",
                str(tmp_path / "beat.db"),
                "--loglevel=warning",
            ],
        )
        api = start("api-before", api_args)
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
            wait_until(lambda: client.get("/health").status_code == 200)
            publish_task(uuid.UUID(job["progress"]["id"]))

            def partial():
                state = client.get(f"/parsing-jobs/{job['id']}").json()
                return state if 0 < len(state["results"]) < 50 else None

            state = wait_until(partial)
            completed_ids = {r["id"] for r in state["results"]}
            stop(worker)
            stop(api)
            start("api-after", api_args)
            wait_until(lambda: client.get("/health").status_code == 200)
            assert completed_ids <= {
                r["id"] for r in client.get(f"/parsing-jobs/{job['id']}").json()["results"]
            }
            start("worker-after", worker_args)
            # Beat redelivers the durable row after the worker dies, without another API submission.
            final = wait_until(
                lambda: (
                    state
                    if (state := client.get(f"/parsing-jobs/{job['id']}").json())["status"]
                    == "completed"
                    else None
                )
            )
            assert len(final["results"]) == 50
            assert completed_ids <= {r["id"] for r in final["results"]}
            assert final["progress"]["attempts"] >= 2
            with SessionFactory() as db:
                assert db.scalar(select(func.count()).select_from(ParsingResult)) == 50
                assert db.scalar(select(func.count()).select_from(LLMInvocation)) == 50
    except BaseException:
        for log in logs:
            log.flush()
            log.seek(0)
            print(log.read()[-8000:])
        raise
    finally:
        for process in reversed(processes):
            stop(process)
        for log in logs:
            log.close()
