"""Load profile for the Task Tracker API.

Each simulated user registers its own account and seeds its own projects, so load runs are isolated from
each other and from the functional suites in the same way the pytest fixtures are.

    locust -f load/locustfile.py --host http://localhost:8080 --headless -u 50 -r 10 -t 2m

SLO thresholds (env vars) turn the run into a pass/fail gate for CI:
    LOAD_MAX_P95_MS       p95 latency budget for each key endpoint (default 500)
    LOAD_MAX_FAIL_RATIO   share of failed requests allowed overall (default 0.01)
"""

from __future__ import annotations

import logging
import os
import random
import sys
from pathlib import Path

from locust import HttpUser, between, events, task
from locust.exception import StopUser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make the shared framework importable

from framework import factories  # noqa: E402

SEED_PROJECTS = int(os.getenv("LOAD_SEED_PROJECTS", "20"))
SEED_TASKS_PER_PROJECT = int(os.getenv("LOAD_SEED_TASKS_PER_PROJECT", "3"))
MAX_P95_MS = float(os.getenv("LOAD_MAX_P95_MS", "500"))
MAX_FAIL_RATIO = float(os.getenv("LOAD_MAX_FAIL_RATIO", "0.01"))

# (method, name) pairs that the latency budget applies to.
KEY_ENDPOINTS = [
    ("GET", "GET /api/projects"),
    ("GET", "GET /api/projects/{id}/tasks"),
    ("POST", "POST /api/projects/{id}/tasks"),
    ("POST", "POST /api/tasks/{id}/status"),
]


class TaskTrackerUser(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self) -> None:
        payload = factories.user_payload()
        self._expect(self.client.post("/api/auth/register", json=payload, name="[setup] register"), 201)
        login = self._expect(
            self.client.post(
                "/api/auth/login",
                json={"email": payload["email"], "password": payload["password"]},
                name="[setup] login",
            ),
            200,
        )
        self.client.headers["Authorization"] = f"Bearer {login.json()['accessToken']}"

        self.project_ids: list[str] = []
        self.todo_task_ids: list[str] = []
        for _ in range(SEED_PROJECTS):
            project = self._expect(
                self.client.post("/api/projects", json=factories.project_payload(), name="[setup] create project"), 201
            ).json()
            self.project_ids.append(project["id"])
            for _ in range(SEED_TASKS_PER_PROJECT):
                created = self._expect(
                    self.client.post(
                        f"/api/projects/{project['id']}/tasks", json=factories.task_payload(), name="[setup] create task"
                    ),
                    201,
                ).json()
                self.todo_task_ids.append(created["id"])

    def on_stop(self) -> None:
        if "Authorization" in self.client.headers:
            self.client.delete("/api/auth/me", name="[teardown] delete account")

    @task(6)
    def view_dashboard(self) -> None:
        self.client.get("/api/projects", params={"page": 1, "pageSize": 20}, name="GET /api/projects")

    @task(3)
    def open_project(self) -> None:
        project_id = random.choice(self.project_ids)
        self.client.get(f"/api/projects/{project_id}/tasks", params={"pageSize": 50}, name="GET /api/projects/{id}/tasks")

    @task(2)
    def add_task(self) -> None:
        project_id = random.choice(self.project_ids)
        response = self.client.post(
            f"/api/projects/{project_id}/tasks", json=factories.task_payload(), name="POST /api/projects/{id}/tasks"
        )
        if response.status_code == 201:
            self.todo_task_ids.append(response.json()["id"])

    @task(1)
    def start_task(self) -> None:
        if not self.todo_task_ids:
            return
        task_id = self.todo_task_ids.pop(random.randrange(len(self.todo_task_ids)))
        self.client.post(f"/api/tasks/{task_id}/status", json={"status": "in_progress"}, name="POST /api/tasks/{id}/status")

    @staticmethod
    def _expect(response, status: int):
        if response.status_code != status:
            logging.error("Setup request %s failed with %s: %s", response.url, response.status_code, response.text[:300])
            raise StopUser()
        return response


@events.quitting.add_listener
def enforce_slos(environment, **_kwargs) -> None:
    stats = environment.stats
    breaches = []
    if stats.total.fail_ratio > MAX_FAIL_RATIO:
        breaches.append(f"failure ratio {stats.total.fail_ratio:.2%} > {MAX_FAIL_RATIO:.2%}")
    for method, name in KEY_ENDPOINTS:
        entry = stats.entries.get((name, method))
        if entry is None or entry.num_requests == 0:
            continue
        p95 = entry.get_response_time_percentile(0.95)
        if p95 > MAX_P95_MS:
            breaches.append(f"{name} p95 {p95:.0f} ms > {MAX_P95_MS:.0f} ms")

    if breaches:
        logging.error("Load test SLO breached: %s", "; ".join(breaches))
        environment.process_exit_code = 1
    else:
        logging.info("Load test SLOs met (p95 <= %.0f ms, failures <= %.2f%%)", MAX_P95_MS, MAX_FAIL_RATIO * 100)
