"""
Scheduler - APScheduler configuration for automated data updates
Runs background jobs to keep market data fresh
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import logging
import os

# Importamos a classe para evitar conflitos de nomes
from database.db_manager import DatabaseManager

from scheduler.data_updater import (
    update_stocks_br,
    update_stocks_us,
    update_etfs,
    update_fiis,
    update_all_data,
    cleanup_old_logs
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
UPDATE_INTERVAL_HOURS = int(os.getenv('UPDATE_INTERVAL_HOURS', '1'))
AUTO_UPDATE_ENABLED = os.getenv('AUTO_UPDATE_ENABLED', 'true').lower() == 'true'

# Create scheduler instance
scheduler = BackgroundScheduler()

def start_scheduler():
    """Start the background scheduler"""
    if not AUTO_UPDATE_ENABLED:
        logger.info("⏸️  Auto-update is disabled")
        return
    
    logger.info("🚀 Starting background scheduler...")
    
    # Schedule hourly updates
    scheduler.add_job(
        update_all_data,
        trigger=IntervalTrigger(hours=UPDATE_INTERVAL_HOURS),
        id='update_all_data',
        name='Update All Market Data',
        replace_existing=True
    )
    
    # Schedule daily cleanup at 3 AM
    scheduler.add_job(
        cleanup_old_logs,
        trigger=CronTrigger(hour=3, minute=0),
        id='cleanup_logs',
        name='Cleanup Old Logs',
        replace_existing=True
    )
    
    # Start scheduler
    scheduler.start()
    
    logger.info(f"✅ Scheduler started - Updates every {UPDATE_INTERVAL_HOURS} hour(s)")
    
    # Run first update immediately in background
    logger.info("📊 Triggering immediate initial update...")
    scheduler.add_job(
        update_all_data,
        id='initial_update',
        name='Initial Data Update',
        replace_existing=True
    )
    
    try:
        next_run = scheduler.get_job('update_all_data').next_run_time
        logger.info(f"📊 Next scheduled update: {next_run}")
    except:
        logger.warning("⚠️ Could not determine next run time")


def stop_scheduler():
    """Stop the background scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("⏹️  Scheduler stopped")


def get_scheduler_status():
    """Get scheduler status and job information"""
    if not scheduler.running:
        return {
            'running': False,
            'jobs': []
        }
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None
        })
    
    return {
        'running': True,
        'jobs': jobs,
        'update_interval_hours': UPDATE_INTERVAL_HOURS
    }


# For standalone execution (útil para testes manuais via terminal na Render)
if __name__ == "__main__":
    logger.info("Manual update trigger...")
    update_all_data()