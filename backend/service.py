"""Ограниченный asyncio мост к одному spawn-процессу."""

import asyncio
import logging
import multiprocessing
from queue import Empty, Full
from time import monotonic
from uuid import uuid4

from .worker import worker_main

logger = logging.getLogger(__name__)


class ChannelError(Exception):
    def __init__(self, code, message, status_code, *, correlation_id=None, outcome='not_submitted'):
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code
        self.correlation_id, self.outcome = correlation_id, outcome

    def payload(self):
        return {'code': self.code, 'message': self.message, 'correlation_id': self.correlation_id,
                'outcome': self.outcome}


class SimulationService:
    def __init__(self, *, timeout=3.0, capacity=16, target=worker_main, runtime_factory=None):
        self.timeout, self.capacity = timeout, capacity
        self.target, self.runtime_factory = target, runtime_factory
        self.process = None
        self.requests = self.responses = None
        self._lock = asyncio.Lock()
        self._pending = 0
        self._closed = False
        self.forced_shutdown = False

    async def start(self):
        context = multiprocessing.get_context('spawn')
        self.requests = context.Queue(maxsize=self.capacity)
        self.responses = context.Queue(maxsize=self.capacity)
        arguments = (self.requests, self.responses)
        if self.runtime_factory is not None:
            arguments += (self.runtime_factory,)
        self.process = context.Process(target=self.target, args=arguments, name='cyberbiology-simulation')
        try:
            self.process.start()
            await self.call('status', timeout=10)
        except BaseException:
            await self.close()
            raise

    async def call(self, name, arguments=None, *, timeout=None):
        correlation_id = str(uuid4())
        if self._closed or self.process is None or not self.process.is_alive():
            raise ChannelError('process_unavailable', 'Процесс симуляции недоступен', 503, correlation_id=correlation_id)
        if self._pending >= self.capacity:
            raise ChannelError('channel_full', 'Канал команд заполнен', 503, correlation_id=correlation_id)
        self._pending += 1
        acquired = False
        deadline = monotonic() + (self.timeout if timeout is None else timeout)
        try:
            try:
                await asyncio.wait_for(self._lock.acquire(), max(0, deadline - monotonic()))
                acquired = True
            except TimeoutError:
                raise ChannelError('timeout', 'Истекло ожидание канала; команда не отправлена', 504,
                                   correlation_id=correlation_id) from None
            if not self.process.is_alive():
                raise ChannelError('process_unavailable', 'Процесс симуляции недоступен', 503, correlation_id=correlation_id)
            if monotonic() >= deadline:
                raise ChannelError('timeout', 'Команда не отправлена до дедлайна', 504, correlation_id=correlation_id)
            try:
                self.requests.put_nowait((correlation_id, name, arguments or {}))
            except Full:
                raise ChannelError('channel_full', 'Канал команд заполнен', 503, correlation_id=correlation_id) from None
            while monotonic() < deadline:
                try:
                    received_id, answer = self.responses.get_nowait()
                except Empty:
                    if not self.process.is_alive():
                        raise ChannelError('process_unavailable', 'Процесс завершился; исход запроса неизвестен', 503,
                                           correlation_id=correlation_id, outcome='unknown')
                    await asyncio.sleep(min(0.01, max(0, deadline-monotonic())))
                    continue
                if received_id != correlation_id:
                    logger.info('Discarding late response correlation=%s', received_id)
                    continue
                if not answer['ok']:
                    raise ChannelError(answer['code'], answer['message'], answer['status_code'],
                                       correlation_id=correlation_id, outcome='rejected' if answer['status_code'] < 500 else 'unknown')
                return {**answer['data'], 'correlation_id': correlation_id}
            raise ChannelError('timeout', 'Ответ не получен; команда могла быть применена. Прочитайте status', 504,
                               correlation_id=correlation_id, outcome='unknown')
        finally:
            if acquired:
                self._lock.release()
            self._pending -= 1

    async def close(self):
        if self._closed:
            return
        try:
            if self.process is not None and self.process.is_alive():
                try:
                    await self.call('shutdown', timeout=3)
                except ChannelError:
                    logger.warning('Graceful shutdown request failed')
                await asyncio.to_thread(self.process.join, 2)
                if self.process.is_alive():
                    self.forced_shutdown = True
                    logger.warning('Terminating simulation process')
                    self.process.terminate()
                    await asyncio.to_thread(self.process.join, 2)
                if self.process.is_alive():
                    self.process.kill()
                    await asyncio.to_thread(self.process.join, 2)
            elif self.process is not None and self.process.pid is not None:
                await asyncio.to_thread(self.process.join, 2)
        finally:
            self._closed = True
            feeders = []
            for channel in (self.requests, self.responses):
                if channel is not None:
                    # Не оставлять Queue/SemLock до завершения Uvicorn сигналом.
                    feeder = getattr(channel, '_thread', None)
                    if feeder is not None:
                        feeders.append(feeder)
                    channel.cancel_join_thread()
                    channel.close()
            self.requests = self.responses = None
            channel = None
            # join_thread не имеет timeout; feeder CPython ожидаем только до дедлайна.
            deadline = monotonic() + 2
            while any(feeder.is_alive() for feeder in feeders) and monotonic() < deadline:
                await asyncio.sleep(0.01)
