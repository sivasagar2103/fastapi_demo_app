import time
from datetime import datetime, timezone
from sqlalchemy import select, update, or_, and_
from rest_api_server.models import ExchangeRateJob
from rest_api_server.repositories.base import BaseRepository

def utcnow():
    return datetime.now(timezone.utc).isoformat()

class ExchangeRateJobRepository(BaseRepository):
    model = ExchangeRateJob

    async def pending_dispatch(self):
        return list((await self.session.execute(select(self.model.id,self.model.attempts).where(self.model.status == 'queued', self.model.published_at.is_(None)).order_by(self.model.created_at).limit(20))).all())

    async def mark_published(self, job_id, expected_attempts):
        await self.session.execute(update(self.model).where(self.model.id == job_id,self.model.status == 'queued',self.model.attempts == expected_attempts).values(published_at=time.time()))

    async def claim(self, job_id):
        now = time.time()
        result = await self.session.execute(update(self.model).where(self.model.id == job_id,
            or_(self.model.status == 'queued', and_(self.model.status == 'running', self.model.lease_until < now))).values(
                status='running', attempts=self.model.attempts+1, lease_until=now+60, started_at=utcnow(), error=None))
        return bool(result.rowcount)

    async def finish(self, job_id, attempts, result=None, error=None, retry=False):
        values = {'status':'queued' if retry else 'failed' if error else 'succeeded',
                  'result':result, 'error':error, 'lease_until':None,
                  'finished_at':None if retry else utcnow()}
        if retry:
            values['published_at'] = None
        await self.session.execute(update(self.model).where(self.model.id == job_id,self.model.status == 'running',self.model.attempts == attempts).values(**values))
