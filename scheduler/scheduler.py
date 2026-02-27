"""
Scheduler Manager - Background job scheduling
Uses APScheduler with database-backed configuration
"""
import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

import asyncio
from scheduler.data_updater import update_all_data, update_flipping, cleanup_old_logs

logger = logging.getLogger(__name__)

# Default values (overridden by database settings)
UPDATE_INTERVAL_HOURS = float(os.getenv('UPDATE_INTERVAL_HOURS', '1'))
AUTO_UPDATE_ENABLED = os.getenv('AUTO_UPDATE_ENABLED', 'true').lower() == 'true'

# Global scheduler instance
scheduler = BackgroundScheduler()


def _run_async(coro):
    """Run an async coroutine from sync APScheduler context"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _run_flipping_update():
    """Sync wrapper for the async flipping update"""
    _run_async(update_flipping())


def _get_flipping_interval_days():
    """Get flipping update interval from DB settings"""
    try:
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        interval = db.get_setting('flipping_update_interval_days')
        if interval:
            return int(interval)
    except Exception as e:
        logger.warning(f"Could not read flipping interval from DB: {e}")
    return 1  # Default: 1 day


def _get_update_interval_minutes():
    """Get update interval from database settings, with env var fallback"""
    try:
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        interval = db.get_setting('market_update_interval_minutes')
        if interval:
            return int(interval)
    except Exception as e:
        logger.warning(f"Could not read interval from DB: {e}")
    
    # Fallback to env var (in hours, convert to minutes)
    return int(UPDATE_INTERVAL_HOURS * 60)


def _is_auto_update_enabled():
    """Check if auto update is enabled from database settings"""
    try:
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        enabled = db.get_setting('auto_update_enabled')
        if enabled is not None:
            return enabled.lower() == 'true'
    except Exception as e:
        logger.warning(f"Could not read auto_update from DB: {e}")
    
    return AUTO_UPDATE_ENABLED


def start_scheduler():
    """Start the background scheduler"""
    if not _is_auto_update_enabled():
        logger.info("⏸️  Auto-update is disabled")
        return
    
    logger.info("🚀 Starting background scheduler...")
    
    interval_minutes = _get_update_interval_minutes()
    
    # Schedule periodic updates
    scheduler.add_job(
        update_all_data,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id='update_all_data',
        name='Update All Market Data',
        replace_existing=True
    )
    
    # Schedule flipping updates
    flipping_interval_days = _get_flipping_interval_days()
    scheduler.add_job(
        _run_flipping_update,
        trigger=IntervalTrigger(days=flipping_interval_days),
        id='update_flipping_data',
        name='Update House Flipping Data',
        replace_existing=True
    )
    logger.info(f"🏠 Flipping updates scheduled every {flipping_interval_days} day(s)")

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
    
    logger.info(f"✅ Scheduler started - Updates every {interval_minutes} minute(s)")
    
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
        scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler stopped")


def get_scheduler_status():
    """Get scheduler status and job info"""
    status = {
        'running': scheduler.running,
        'auto_update_enabled': _is_auto_update_enabled(),
        'update_interval_minutes': _get_update_interval_minutes(),
        'jobs': []
    }
    
    if scheduler.running:
        for job in scheduler.get_jobs():
            status['jobs'].append({
                'id': job.id,
                'name': job.name,
                'next_run': str(job.next_run_time) if job.next_run_time else None
            })
    
    return status


def reschedule_jobs():
    """Reschedule jobs after settings change (called from admin panel)"""
    if not scheduler.running:
        logger.warning("⚠️  Scheduler not running, cannot reschedule")
        return False
    
    interval_minutes = _get_update_interval_minutes()
    
    try:
        # Reschedule the main update job
        scheduler.reschedule_job(
            'update_all_data',
            trigger=IntervalTrigger(minutes=interval_minutes)
        )
        logger.info(f"✅ Rescheduled updates to every {interval_minutes} minutes")
        return True
    except Exception as e:
        logger.error(f"❌ Error rescheduling: {e}")
        return False