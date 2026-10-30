"""The server's periodic jobs: one timer in the process wakes every `EVERY` seconds and runs each job;
a job decides for itself whether it is due (the web sweep keeps its last time beside the graph).
Keeping topics current from the web (memory/refresh.py) is the first."""
import logging
import threading
import time

log = logging.getLogger("memory.jobs")

EVERY = 60
JOBS: list = []


def add(job) -> None:
    JOBS.append(job)


def start(every: float = EVERY) -> None:
    def run():
        while True:
            for job in list(JOBS):
                try:
                    job()
                except Exception:  # noqa: BLE001 - one job failing leaves the others and the next wake
                    log.exception("a periodic job failed")
            time.sleep(every)
    threading.Thread(target=run, daemon=True, name="jobs").start()
