"""In-process scheduler for PharmaCore's periodic jobs.

Run this as its ONE dedicated long-running process (not inside gunicorn, so it
fires exactly once, not once per web worker):

    python manage.py run_scheduler            # daily at 06:00 (server TZ)
    python manage.py run_scheduler --hour 2   # or a different time
    python manage.py run_scheduler --dry-run  # print the schedule and exit

Alternatively, skip this process entirely and drive the jobs from the host's
cron / systemd timer / Windows Task Scheduler by calling the commands directly,
e.g. a daily crontab line:  `python manage.py notify_alerts`.
"""

from __future__ import annotations

from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

# Jobs the scheduler owns: (job id, management command, cron kwargs override key).
_ALERT_JOB = "notify_alerts"


class Command(BaseCommand):
    help = "Run the periodic-job scheduler (fires notify_alerts daily)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--hour", type=int, default=6, help="Hour of day (0-23).")
        parser.add_argument("--minute", type=int, default=0, help="Minute (0-59).")
        parser.add_argument("--dry-run", action="store_true", help="Print the schedule and exit.")

    def handle(self, *args: Any, **options: Any) -> None:
        hour, minute = options["hour"], options["minute"]
        scheduler = BlockingScheduler(timezone=str(settings.TIME_ZONE))
        scheduler.add_job(
            lambda: call_command(_ALERT_JOB),
            CronTrigger(hour=hour, minute=minute),
            id=_ALERT_JOB,
            replace_existing=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Scheduler ready — '{_ALERT_JOB}' runs daily at {hour:02d}:{minute:02d} "
                f"({settings.TIME_ZONE})."
            )
        )
        if options["dry_run"]:
            return

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):  # pragma: no cover - process stop
            scheduler.shutdown()
