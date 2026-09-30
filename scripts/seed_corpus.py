from __future__ import annotations

import argparse
import getpass
import mimetypes
import os
import time

import httpx

from scripts.generate_corpus import DEFAULT_OUTPUT, generate_corpus, load_manifest


def seed(base_url: str, username: str, password: str) -> tuple[int, int]:
    paths = {path.stem: path for path in generate_corpus(DEFAULT_OUTPUT)}
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=180, trust_env=False) as client:
        login = client.post("/api/v1/auth/login", data={"username": username, "password": password})
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        listed = client.get("/api/v1/documents")
        listed.raise_for_status()
        active_titles = {
            document["title"] for document in listed.json() if document["active_version_id"] is not None
        }
        created = skipped = 0
        for record in load_manifest():
            if record["title"] in active_titles:
                skipped += 1
                continue
            path = paths[record["id"]]
            with path.open("rb") as content:
                uploaded = client.post(
                    "/api/v1/documents",
                    data={
                        "title": record["title"],
                        "department": record["department"] or "",
                        "allowed_roles": "employee",
                    },
                    files={"file": (path.name, content, mimetypes.guess_type(path.name)[0] or "application/octet-stream")},
                )
            uploaded.raise_for_status()
            receipt = uploaded.json()
            deadline = time.monotonic() + 180
            while True:
                job = client.get(f"/api/v1/jobs/{receipt['job_id']}")
                job.raise_for_status()
                status = job.json()["status"]
                if status == "DONE":
                    break
                if status in {"FAILED", "CANCELLED"}:
                    raise RuntimeError(f"Indexing failed for {record['id']}: {job.json().get('error')}")
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Indexing timed out for {record['id']}")
                time.sleep(2)
            activated = client.post(
                f"/api/v1/documents/{receipt['document_id']}/versions/{receipt['version_id']}/activate"
            )
            activated.raise_for_status()
            created += 1
            print(f"Published {created:02d}: {record['id']}", flush=True)
    return created, skipped


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload and publish fictional policies through the admin API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8766")
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()
    password = os.getenv("DEMO_PASSWORD") or getpass.getpass("Demo password: ")
    created, skipped = seed(args.base_url, args.username, password)
    print(f"Published {created} policies; skipped {skipped} already active policies")
