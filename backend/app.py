"""FastAPI HTTP адаптер; импорт не запускает процесс."""

from contextlib import asynccontextmanager
import logging
import multiprocessing
import asyncio
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import FastAPI, Request, Path
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.biology import RulesConfig
from core.scenarios import SCENARIOS
from .service import SimulationService, ChannelError
from .worker import rules_from_dict

MAX_BODY = 16 * 1024


class Change(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_run_id: Annotated[str, Field(min_length=1, max_length=64)]


class Reset(Change):
    scenario: Literal['nop', 'photosynthesis', 'branching', 'mixed']
    seed: Annotated[int, Field(ge=-(2**63), le=2**63-1)]
    config: dict

    @field_validator('config')
    @classmethod
    def validate_config(cls, value):
        # Полный config нужен для воспроизводимого reset, без неявных defaults.
        defaults = asdict(RulesConfig())
        if set(value) != set(defaults):
            raise ValueError('Требуется полный config RulesConfig')
        try:
            return asdict(rules_from_dict(value))
        except (TypeError, ValueError) as error:
            raise ValueError('Некорректная конфигурация правил') from error

    @field_validator('scenario')
    @classmethod
    def validate_scenario_limits(cls, name):
        scenario = SCENARIOS[name]
        if (scenario.width > 64 or scenario.height > 64 or scenario.width * scenario.height > 4096
                or len(scenario.entities) > 64):
            raise ValueError('Сценарий превышает ограничения API')
        return name


class Speed(Change):
    ticks_per_second: Annotated[int, Field(ge=1, le=100)]


def create_app(service_factory=SimulationService):
    @asynccontextmanager
    async def lifespan(app):
        if multiprocessing.parent_process() is not None:
            raise RuntimeError('Нужен один Uvicorn worker без reload')
        service = service_factory()
        app.state.simulation = service
        await service.start()
        logging.getLogger('uvicorn.error').info('Simulation process started pid=%s', service.process.pid)
        try:
            yield
        finally:
            await service.close()

    app = FastAPI(title='Cyberbiology local API', lifespan=lifespan)

    @app.middleware('http')
    async def body_limit(request, call_next):
        if request.method == 'POST':
            # Потоковое ограничение работает и без Content-Length.
            body = bytearray()
            try:
                async with asyncio.timeout(3):
                    async for chunk in request.stream():
                        if len(body) + len(chunk) > MAX_BODY:
                            return JSONResponse(status_code=413, content={'error': {'code': 'body_too_large', 'message': 'Тело превышает 16 KiB'}})
                        body.extend(chunk)
            except TimeoutError:
                return JSONResponse(status_code=408, content={'error': {'code': 'body_timeout', 'message': 'Истекло ожидание тела запроса', 'outcome': 'not_submitted'}})
            request._body = bytes(body)
        return await call_next(request)

    @app.exception_handler(ChannelError)
    async def channel_error(request, error):
        return JSONResponse(status_code=error.status_code, content={'error': error.payload()})

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        # Без исходных входных данных, сообщений внутренних validators или traceback.
        return JSONResponse(status_code=422, content={'error': {'code': 'invalid_input',
                             'message': 'Некорректные параметры запроса',
                             'fields': [list(item['loc']) for item in error.errors()]}})

    async def call(request, name, args=None):
        return await request.app.state.simulation.call(name, args)

    @app.get('/api/status')
    async def status(request: Request):
        return await call(request, 'status')

    @app.get('/api/field')
    async def field(request: Request):
        return await call(request, 'field_snapshot')

    @app.get('/api/entities/{entity_id}')
    async def entity(request: Request, entity_id: Annotated[int, Path(ge=1, le=2**63-1)]):
        return await call(request, 'entity_details', {'entity_id': entity_id})

    @app.post('/api/start')
    async def start(request: Request, body: Change):
        return await call(request, 'start', body.model_dump())

    @app.post('/api/pause')
    async def pause(request: Request, body: Change):
        return await call(request, 'pause', body.model_dump())

    @app.post('/api/step')
    async def step(request: Request, body: Change):
        return await call(request, 'step', body.model_dump())

    @app.post('/api/reset')
    async def reset(request: Request, body: Reset):
        return await call(request, 'reset', body.model_dump())

    @app.post('/api/speed')
    async def speed(request: Request, body: Speed):
        return await call(request, 'speed', body.model_dump())

    return app


app = create_app()
