
import asyncio
import json
import logging
from uuid import UUID
import aio_pika
from rest_api_server.globals import Database, Settings
from rest_api_server.repositories.exchange_rate_jobs import ExchangeRateJobRepository
from rest_api_server.services.exchange_rates import ExchangeRateClient, ExchangeRateError

QUEUE_NAME = 'exchange-rate-jobs'
logger = logging.getLogger('exchange.worker')

async def process_job(database, provider, job_id):
    async with database.session_factory() as session:
        async with session.begin():
            repo = ExchangeRateJobRepository(session)
            job = await repo.get(job_id)
            if not job or job['status'] in ('succeeded','failed'):
                return True
            if not await repo.claim(job_id):
                return False  # In-flight duplicate: defer until its lease expires.
        async with session.begin():
            job = await repo.get(job_id)
        try:
            if job['attempts'] > 3:
                raise ExchangeRateError('Maximum worker attempts exceeded')
            result = await provider.fetch(job['base_currency'])
        except ExchangeRateError as error:
            async with session.begin():
                await repo.finish(job_id,job['attempts'],error=str(error),retry=error.retry and job['attempts']<3)
        else:
            async with session.begin():
                await repo.finish(job_id,job['attempts'],result=result)
        return True

async def main():
    logging.basicConfig(level=logging.INFO)
    # The provider key is part of its URL: suppress HTTP request URL logging.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings()
    database = Database(settings)
    connection = None
    try:
        connection = await aio_pika.connect_robust(host=settings.rabbitmq_host,
            login=settings.rabbitmq_user,password=settings.rabbitmq_password,timeout=10)
        channel = await connection.channel(publisher_confirms=True)
        await channel.set_qos(prefetch_count=1)
        queue = await channel.declare_queue(QUEUE_NAME,durable=True)
        provider = ExchangeRateClient(settings.exchange_rates_api_key)
        logger.info('Worker ready; consuming %s',QUEUE_NAME)
        async with queue.iterator() as messages:
            async for message in messages:
                try:
                    payload = json.loads(message.body)
                    job_id = str(UUID(payload['job_id']))
                except (ValueError,KeyError,TypeError):
                    await message.reject(requeue=False)
                    continue
                try:
                    if await process_job(database,provider,job_id):
                        await message.ack()
                        logger.info('Acknowledged job %s',job_id)
                    else:
                        await asyncio.sleep(2)
                        await message.nack(requeue=True)
                except Exception:
                    logger.warning('Worker/database error; requeuing job %s',job_id)
                    await asyncio.sleep(3)
                    await message.nack(requeue=True)
    finally:
        if connection:
            await connection.close()
        await database.close()

if __name__ == '__main__':
    asyncio.run(main())
