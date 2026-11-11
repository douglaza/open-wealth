from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.sync import sync_weekly

scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")


def start_scheduler():
    # Toda segunda-feira às 06:00
    scheduler.add_job(
        sync_weekly,
        CronTrigger(day_of_week="mon", hour=6, minute=0),
        id="sync_weekly",
        replace_existing=True,
    )
    scheduler.start()
    print("⏰ Scheduler iniciado: sync semanal seg 06:00")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
