"""RabbitMQ 连接 + 发布/消费"""
import json
import aio_pika
from typing import Callable, Awaitable
from app.config import settings

_connection: aio_pika.RobustConnection | None = None
_channel: aio_pika.RobustChannel | None = None

EXCHANGE_SSE = "sse.events"
QUEUE_TASKS = "qpet.tasks"
QUEUE_LOGS = "qpet.logs"


async def init_rabbitmq():
    global _connection, _channel
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    _channel = await _connection.channel()
    await _channel.declare_exchange(EXCHANGE_SSE, aio_pika.ExchangeType.FANOUT, durable=False)
    await _channel.declare_queue(QUEUE_TASKS, durable=True)
    await _channel.declare_queue(QUEUE_LOGS, durable=True)


async def close_rabbitmq():
    if _connection:
        await _connection.close()


async def publish_sse_event(event_type: str, data: dict):
    msg = aio_pika.Message(body=json.dumps({"type": event_type, "data": data}).encode())
    await _channel.default_exchange.publish(msg, routing_key=EXCHANGE_SSE)


async def publish_task(task_type: str, account_id: str, params: dict | None = None):
    msg = aio_pika.Message(
        body=json.dumps({"type": task_type, "account_id": account_id, "params": params or {}}).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await _channel.default_exchange.publish(msg, routing_key=QUEUE_TASKS)


async def publish_log(entry: dict):
    msg = aio_pika.Message(
        body=json.dumps(entry).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await _channel.default_exchange.publish(msg, routing_key=QUEUE_LOGS)


async def consume_tasks(callback: Callable[[dict], Awaitable[None]]):
    queue = await _channel.declare_queue(QUEUE_TASKS, durable=True)
    async with queue.iterator() as it:
        async for msg in it:
            async with msg.process():
                await callback(json.loads(msg.body))


async def consume_logs(callback: Callable[[dict], Awaitable[None]]):
    queue = await _channel.declare_queue(QUEUE_LOGS, durable=True)
    async with queue.iterator() as it:
        async for msg in it:
            async with msg.process():
                await callback(json.loads(msg.body))
