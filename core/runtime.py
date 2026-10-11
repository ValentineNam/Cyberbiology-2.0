"""Синхронный единственный владелец мира, без транспорта и фонового цикла."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import StrEnum
from uuid import uuid4

from .biology import Kind, RulesConfig
from .scenarios import SCENARIOS
from .world import _require_int


class RuntimeState(StrEnum):
    PAUSED = 'paused'
    RUNNING = 'running'
    FAILED = 'failed'


class RuntimeStateError(RuntimeError):
    """Команда недопустима в текущем состоянии."""


class StaleRunError(ValueError):
    """Команда или чтение адресованы другому опыту."""


class NestedCommandError(RuntimeError):
    """Runtime уже выполняет команду."""


@dataclass(frozen=True)
class TickError:
    type: str
    message: str
    command: str
    attempted_tick: int


class SimulationRuntime:
    def __init__(self, *, scenario: str, seed: int, config: RulesConfig):
        self._world = self._build(scenario, seed, config)
        self._run_id = str(uuid4())
        self._state = RuntimeState.PAUSED
        self._error: TickError | None = None
        self._last_completed_tick = 0
        self._busy = False

    @staticmethod
    def _build(scenario, seed, config):
        _require_int(seed, 'seed')
        if type(config) is not RulesConfig:
            raise TypeError('config должен быть явно заданным RulesConfig')
        if type(scenario) is not str or scenario not in SCENARIOS:
            raise ValueError(f'Неизвестный сценарий: {scenario!r}')
        return SCENARIOS[scenario].build(seed=seed, config=config)

    @contextmanager
    def _command(self, expected_run_id):
        if self._busy:
            raise NestedCommandError('Вложенная команда или чтение запрещены')
        if expected_run_id is not None:
            if type(expected_run_id) is not str:
                raise TypeError('expected_run_id должен быть строкой или None')
            if expected_run_id != self._run_id:
                raise StaleRunError('run_id не соответствует текущему миру')
        self._busy = True
        try:
            yield
        finally:
            self._busy = False

    def _status(self) -> dict:
        metrics = self._world.metrics
        generations = [e.generation for e in self._world.entities if e.kind == Kind.ORGANISM]
        metrics.update(reserve=self._world.reserve, R=self._world.total_resources,
                       max_generation=max(generations, default=None))
        return {'status': self._state.value, 'run_id': self._run_id, 'tick': self._world.tick,
                'last_completed_tick': self._last_completed_tick,
                'completed': self._state != RuntimeState.FAILED,
                'error': None if self._error is None else asdict(self._error),
                'metrics': metrics, 'initial_budget': self._world.initial_budget}

    def status(self, *, expected_run_id: str | None = None) -> dict:
        with self._command(expected_run_id):
            return self._status()

    def start(self, *, expected_run_id: str | None = None) -> dict:
        with self._command(expected_run_id):
            if self._state == RuntimeState.FAILED:
                raise RuntimeStateError('Runtime failed; требуется reset')
            self._state = RuntimeState.RUNNING
            return self._status()

    def pause(self, *, expected_run_id: str | None = None) -> dict:
        with self._command(expected_run_id):
            if self._state != RuntimeState.FAILED:
                self._state = RuntimeState.PAUSED
            return self._status()

    def _tick(self, command: str, required: RuntimeState) -> dict:
        if self._state != required:
            raise RuntimeStateError(f'{command} доступен только в состоянии {required.value}')
        before = self._world.tick
        try:
            self._world.step()
            if self._world.tick != before + 1:
                raise RuntimeError('Биологический шаг не завершил ровно один тик')
        except Exception as error:
            self._state = RuntimeState.FAILED
            self._error = TickError(type(error).__name__, str(error), command, before + 1)
            raise
        self._last_completed_tick = self._world.tick
        return self._status()

    def step(self, *, expected_run_id: str | None = None) -> dict:
        with self._command(expected_run_id):
            return self._tick('step', RuntimeState.PAUSED)

    def advance(self, *, expected_run_id: str | None = None) -> dict:
        with self._command(expected_run_id):
            return self._tick('advance', RuntimeState.RUNNING)

    def reset(self, *, scenario: str, seed: int, config: RulesConfig,
              expected_run_id: str | None = None) -> dict:
        with self._command(expected_run_id):
            # В том числе размещение всех сущностей до замены рабочего мира.
            world = self._build(scenario, seed, config)
            run_id = str(uuid4())
            self._world = world
            self._run_id = run_id
            self._state = RuntimeState.PAUSED
            self._last_completed_tick = 0
            self._error = None
            return self._status()

    def field_snapshot(self, *, expected_run_id: str | None = None) -> dict:
        with self._command(expected_run_id):
            return {**self._status(), 'width': self._world.width, 'height': self._world.height,
                    'entities': [{'id': e.id, 'x': e.x, 'y': e.y, 'kind': e.kind.value,
                                  'profile': None if e.profile is None else e.profile.value,
                                  'direction': e.direction} for e in self._world.entities]}

    def entity_details(self, entity_id: int, *, expected_run_id: str | None = None) -> dict:
        with self._command(expected_run_id):
            entity = self._world.get(entity_id)
            return {**self._status(), 'entity': None if entity is None else asdict(entity)}
