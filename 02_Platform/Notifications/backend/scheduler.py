"""
APScheduler BackgroundScheduler lifecycle management.

Isolates scheduler wiring from main.py for testability.
Uses a memory job store (no durable job state required — the notification
records in Postgres are the durable state; the scheduler only tracks which
job to run and when to run it).
"""

import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.dispatch_job import dispatch_due_notifications

_DISPATCH_INTERVAL = int(os.environ.get("NOTIFICATIONS_DISPATCH_INTERVAL_SECONDS", "30"))


def start_scheduler() -> BackgroundScheduler:
    """Create a BackgroundScheduler with memory job store, register
    dispatch_due_notifications with IntervalTrigger(seconds=NOTIFICATIONS_DISPATCH_INTERVAL_SECONDS),
    start the scheduler, and return it.
    """
    scheduler = BackgroundScheduler(
        job_defaults={"coalesce": True, "max_instances": 1},
    )
    scheduler.add_job(
        dispatch_due_notifications,
        trigger=IntervalTrigger(seconds=_DISPATCH_INTERVAL),
        id="dispatch_due_notifications",
        name="Dispatch due notifications via FCM",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


def stop_scheduler(scheduler: BackgroundScheduler) -> None:
    """Stop the scheduler cleanly. Called on FastAPI shutdown.

    APScheduler default behavior allows in-flight jobs to complete before
    the scheduler thread exits. No durable state is lost — the in-memory
    job schedule is recreated on next startup from the registered job.
    """
    scheduler.shutdown(wait=True)
