"""Владелец симуляции: spawn target, никаких процессов при импорте."""

import logging
from dataclasses import asdict
from queue import Empty, Full
from time import monotonic

from core.biology import RulesConfig, PlantRules
from core.runtime import SimulationRuntime, RuntimeStateError, StaleRunError

logger = logging.getLogger(__name__)


def rules_from_dict(data):
    data = dict(data)
    for name in ('tree', 'bush', 'grass'):
        if name in data:
            data[name] = PlantRules(**data[name])
    return RulesConfig(**data)


def safe_state(state):
    state = dict(state)
    if state.get('error'):
        raw = state['error']
        state['error'] = {'code': 'tick_failed', 'message': 'Ошибка вычисления тика; требуется reset',
                          'command': raw['command'], 'attempted_tick': raw['attempted_tick']}
    return state


def worker_main(requests, responses, runtime_factory=SimulationRuntime):
    active_scenario, active_seed, active_config = 'mixed', 42, RulesConfig()
    runtime = runtime_factory(scenario=active_scenario, seed=active_seed, config=active_config)
    speed = 10
    next_tick = monotonic() + 1 / speed
    while True:
        running = runtime.status()['status'] == 'running'
        wait = min(0.1, max(0, next_tick - monotonic())) if running else 0.1
        try:
            command = requests.get(timeout=wait)
        except Empty:
            command = None
        if command is not None:
            correlation_id, name, arguments = command
            if name == 'shutdown':
                try:
                    responses.put((correlation_id, {'ok': True, 'data': {'stopped': True}}), timeout=0.1)
                except Full:
                    logger.warning('Shutdown response channel full')
                return
            try:
                if name == 'speed':
                    data = runtime.status(expected_run_id=arguments['expected_run_id'])
                    speed = arguments['ticks_per_second']
                elif name == 'reset':
                    arguments = dict(arguments)
                    arguments['config'] = rules_from_dict(arguments['config'])
                    data = runtime.reset(**arguments)
                    active_scenario, active_seed, active_config = arguments['scenario'], arguments['seed'], arguments['config']
                else:
                    data = getattr(runtime, name)(**arguments)
                data = {**safe_state(data), 'ticks_per_second': speed}
                if name == 'status':
                    data.update(scenario=active_scenario, seed=active_seed, configuration=asdict(active_config))
                answer = {'ok': True, 'data': data}
                if name in ('reset', 'speed') or (name == 'start' and not running):
                    next_tick = monotonic() + 1 / speed
            except StaleRunError:
                answer = {'ok': False, 'code': 'stale_run', 'message': 'Опыт сменился; прочитайте status', 'status_code': 409}
            except RuntimeStateError:
                answer = {'ok': False, 'code': 'invalid_state', 'message': 'Команда недоступна в текущем состоянии', 'status_code': 409}
            except (ValueError, TypeError):
                logger.exception('Invalid command %s correlation=%s', name, correlation_id)
                answer = ({'ok': False, 'code': 'tick_failed', 'message': 'Ошибка вычисления; требуется reset', 'status_code': 500}
                          if runtime.status()['status'] == 'failed' else
                          {'ok': False, 'code': 'invalid_command', 'message': 'Некорректная команда', 'status_code': 422})
            except Exception:
                logger.exception('Command failed %s correlation=%s', name, correlation_id)
                answer = {'ok': False, 'code': 'tick_failed' if runtime.status()['status'] == 'failed' else 'internal_error',
                          'message': 'Ошибка вычисления; проверьте status', 'status_code': 500}
            try:
                responses.put((correlation_id, answer), timeout=0.1)
            except Full:
                logger.warning('Response channel full correlation=%s', correlation_id)
        if runtime.status()['status'] == 'running' and monotonic() >= next_tick:
            try:
                runtime.advance()
            except Exception:
                logger.exception('Background tick failed')
            # Никаких долгов тиков: период начинается после завершения расчёта.
            next_tick = monotonic() + 1 / speed
