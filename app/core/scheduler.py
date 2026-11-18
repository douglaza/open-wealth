from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.sync import sync_weekly

scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")


def start_scheduler():
    # Todos os dias às 09:00
    scheduler.add_job(
        sync_weekly,
        CronTrigger(hour=9, minute=0),
        id="sync_daily",
        replace_existing=True,
    )
    scheduler.start()
    print("⏰ Scheduler iniciado: sync diário às 09:00")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
