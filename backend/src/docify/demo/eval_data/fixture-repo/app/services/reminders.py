"""Daily overdue-task reminder emails (APScheduler cron job)."""

import smtplib
from datetime import date
from email.message import EmailMessage

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.db import SessionLocal
from app.models import Task, User


def overdue_tasks_by_user(today: date) -> dict[str, list[str]]:
    with SessionLocal() as db:
        rows = (db.query(User.email, Task.title).join(Task, Task.owner_id == User.id)
                .filter(Task.done.is_(False), Task.due_date < today).all())
    grouped: dict[str, list[str]] = {}
    for email, title in rows:
        grouped.setdefault(email, []).append(title)
    return grouped


def send_reminders() -> int:
    sent = 0
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        for email, titles in overdue_tasks_by_user(date.today()).items():
            msg = EmailMessage()
            msg["To"], msg["From"], msg["Subject"] = email, "taskly@example.com", "You have overdue tasks"
            msg.set_content("Overdue:\n" + "\n".join(f"- {t}" for t in titles))
            smtp.send_message(msg)
            sent += 1
    return sent


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_reminders, "cron", hour=settings.reminder_hour)
    scheduler.start()
    return scheduler
