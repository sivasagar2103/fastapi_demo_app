"""API-owned durable-outbox publisher; jobs execute in the separate worker."""
import asyncio
import json
import logging
import aio_pika
from rest_api_server.repositories.exchange_rate_jobs import ExchangeRateJobRepository

QUEUE_NAME = 'exchange-rate-jobs'
logger = logging.getLogger('exchange.publisher')

async def dispatch(database, channel):
    while True:
        try:
            async with database.session_factory() as session:
                async with session.begin():
                    pending = await ExchangeRateJobRepository(session).pending_dispatch()
                for job_id, attempts in pending:
                    await channel.default_exchange.publish(aio_pika.Message(
                        body=json.dumps({'job_id':job_id}).encode(),message_id=job_id,
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT), routing_key=QUEUE_NAME, mandatory=True, timeout=10)
                    async with session.begin():
                        await ExchangeRateJobRepository(session).mark_published(job_id,attempts)
            await asyncio.sleep(2)
        except Exception:
            logger.warning('Outbox dispatch failed; retrying without logging credentials')
            await asyncio.sleep(3)


async def run_dispatcher(database, settings):
    while True:
        connection = None
        try:
            connection = await aio_pika.connect_robust(host=settings.rabbitmq_host,
                login=settings.rabbitmq_user,password=settings.rabbitmq_password,timeout=10)
            channel = await connection.channel(publisher_confirms=True)
            await channel.declare_queue(QUEUE_NAME,durable=True)
            await dispatch(database,channel)
        except Exception:
            logger.warning('RabbitMQ publisher unavailable; committed jobs remain pending')
            await asyncio.sleep(3)
        finally:
            if connection:
                await connection.close()
