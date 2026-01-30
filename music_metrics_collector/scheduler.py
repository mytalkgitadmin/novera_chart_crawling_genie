"""APScheduler를 이용해 수집 작업을 주기적으로 실행하는 스케줄러 모듈."""

import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)


class Scheduler:
    """메트릭 정기 수집용 스케줄러."""
    
    def __init__(self, config: dict):
        """
        스케줄러를 초기화한다.

        Args:
            config: 설정 딕셔너리
        """
        self.config = config
        self.scheduler = BlockingScheduler(timezone=pytz.timezone('Asia/Seoul'))
        self._setup_job()
    
    def _setup_job(self):
        """설정에 따라 스케줄 작업을 등록한다."""
        schedule_config = self.config.get('schedule', {})
        
        if not schedule_config.get('enabled', False):
            logger.warning("Scheduler is disabled in config")
            return
        
        cron_expr = schedule_config.get('cron', '0 3 * * *')  # 기본값: 매일 03:00
        
        # cron 표현식 파싱 ("minute hour day month day_of_week" 형식)
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expr}. Expected format: 'minute hour day month day_of_week'")
        
        minute, hour, day, month, day_of_week = parts
        
        # 수집 작업 등록
        self.scheduler.add_job(
            self._collect_job,
            trigger=CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=pytz.timezone('Asia/Seoul')
            ),
            id='collect_metrics',
            name='Collect Music Metrics',
            replace_existing=True
        )
        
        logger.info(f"스케줄이 cron='{cron_expr}'로 설정되었습니다.")
    
    def _collect_job(self):
        """정기 수집 시 실행되는 작업 함수."""
        # 순환 의존성을 피하기 위해 지연 import 사용
        from .main import collect_metrics
        
        logger.info("스케줄러에 의해 수집을 시작합니다...")
        try:
            stats = collect_metrics(self.config)
            logger.info(
                f"스케줄 수집 완료: success={stats['success']}, failed={stats['failed']}"
            )
        except Exception as e:
            logger.error(f"스케줄 수집 중 오류 발생: {e}", exc_info=True)
    
    def start(self):
        """스케줄러를 시작한다."""
        logger.info("스케줄러를 시작합니다...")
        self.scheduler.start()
    
    def stop(self):
        """스케줄러를 중지한다."""
        logger.info("스케줄러를 중지합니다...")
        self.scheduler.shutdown()

