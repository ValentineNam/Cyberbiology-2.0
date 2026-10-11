"""Реальный spawn и HTTP контракты с дедлайнами вместо точного TPS."""

import asyncio
from dataclasses import asdict, replace
import gc
import weakref
import multiprocessing
from queue import Full
from time import monotonic
import unittest
from unittest.mock import patch

from httpx import AsyncClient, ASGITransport

from backend.app import create_app
from backend.service import SimulationService, ChannelError
from core.biology import RulesConfig
from core.runtime import SimulationRuntime
from core.scenarios import SCENARIOS


def failing_runtime(**kwargs):
    runtime = SimulationRuntime(**kwargs)
    def fail():
        raise RuntimeError('SECRET tick implementation detail')
    runtime._world.step = fail
    return runtime


def value_error_runtime(**kwargs):
    runtime = SimulationRuntime(**kwargs)
    def fail():
        raise ValueError('SECRET biological error, not invalid input')
    runtime._world.step = fail
    return runtime


def delayed_worker(requests, responses):
    # Искусственно задерживается только первая команда: отдельный тест IPC timeout.
    import time
    first = True
    while True:
        cid, name, args = requests.get(timeout=10)
        if name == 'shutdown':
            responses.put((cid, {'ok': True, 'data': {}}), timeout=1)
            return
        if first:
            first = False
            time.sleep(0.2)
        responses.put((cid, {'ok': True, 'data': {'command': name}}), timeout=1)


def stuck_worker(requests, responses):
    import time
    time.sleep(30)  # Управляемое зависание для проверки bounded fallback.


async def wait_condition(read, condition, *, seconds=5):
    deadline = monotonic() + seconds
    while monotonic() < deadline:
        state = await read()
        if condition(state):
            return state
        await asyncio.sleep(0.02)
    raise AssertionError('Условие не выполнено до дедлайна')


class ProcessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = SimulationService()
        await self.service.start()

    async def asyncTearDown(self):
        await self.service.close()
        self.assertFalse(self.service.process.is_alive())

    async def test_real_spawn_pause_step_speed_reset_and_shutdown(self):
        s = self.service
        self.assertEqual(s.process._start_method, 'spawn')
        initial = await s.call('status')
        self.assertEqual((initial['status'], initial['tick'], initial['ticks_per_second']), ('paused', 0, 10))
        self.assertEqual(initial['configuration'], asdict(RulesConfig()))
        self.assertEqual((initial['scenario'], initial['seed']), ('mixed', 42))
        args = {'expected_run_id': initial['run_id']}
        step = await s.call('step', args)
        self.assertEqual(step['tick'], 1)
        speed = await s.call('speed', {**args, 'ticks_per_second': 100})
        self.assertEqual(speed['metrics'], step['metrics'])
        await s.call('start', args)
        await wait_condition(lambda: s.call('status'), lambda state: state['tick'] >= 3)
        pause = await s.call('pause', args)
        deadline = monotonic()+0.2
        while monotonic()<deadline:
            status = await s.call('status')
            self.assertEqual(status['tick'], pause['tick'])
            await asyncio.sleep(0.02)
        with self.assertRaises(ChannelError) as caught:
            await s.call('step', {'expected_run_id': 'old'})
        self.assertEqual(caught.exception.code, 'stale_run')
        reset = await s.call('reset', {**args, 'scenario': 'mixed', 'seed': 42, 'config': asdict(RulesConfig())})
        self.assertNotEqual(reset['run_id'], initial['run_id'])
        self.assertEqual((reset['status'], reset['tick']), ('paused', 0))
        await s.close()
        self.assertFalse(s.forced_shutdown)
        self.assertIsNone(s.requests)
        self.assertIsNone(s.responses)

    async def test_speed_changes_only_schedule_not_seeded_game(self):
        reference = SimulationRuntime(scenario='mixed', seed=42, config=RulesConfig())
        initial = await self.service.call('status')
        args = {'expected_run_id': initial['run_id']}
        for speed in (1, 100, 10):
            await self.service.call('speed', {**args, 'ticks_per_second': speed})
            actual = await self.service.call('step', args)
            expected = reference.step()
            self.assertEqual(actual['metrics'], expected['metrics'])
            field = await self.service.call('field_snapshot')
            self.assertEqual(field['entities'], reference.field_snapshot()['entities'])
            detail = await self.service.call('entity_details', {'entity_id': 1})
            self.assertEqual(detail['entity'], reference.entity_details(1)['entity'])

    async def test_close_releases_ipc_objects_before_server_exit(self):
        requests = weakref.ref(self.service.requests)
        responses = weakref.ref(self.service.responses)
        feeder = self.service.requests._thread
        await self.service.close()
        gc.collect()
        self.assertIsNone(requests())
        self.assertIsNone(responses())
        self.assertFalse(feeder.is_alive())
        self.assertFalse(self.service.process.is_alive())

    async def test_dead_process_is_unavailable_without_hanging(self):
        self.service.process.terminate()
        await asyncio.to_thread(self.service.process.join, 2)
        with self.assertRaises(ChannelError) as caught:
            await self.service.call('status')
        self.assertEqual((caught.exception.status_code, caught.exception.code), (503, 'process_unavailable'))

    async def test_channel_capacity_and_timeout_before_submission(self):
        with patch.object(self.service.requests, 'put_nowait', side_effect=Full):
            with self.assertRaises(ChannelError) as caught:
                await self.service.call('step')
        self.assertEqual((caught.exception.code, caught.exception.outcome), ('channel_full', 'not_submitted'))
        self.service._pending = self.service.capacity
        try:
            with self.assertRaises(ChannelError) as caught:
                await self.service.call('status')
            self.assertEqual(caught.exception.code, 'channel_full')
        finally:
            self.service._pending = 0
        await self.service._lock.acquire()
        try:
            with self.assertRaises(ChannelError) as caught:
                await self.service.call('step', timeout=0.02)
            self.assertEqual((caught.exception.code, caught.exception.outcome), ('timeout', 'not_submitted'))
        finally:
            self.service._lock.release()

    async def test_timeout_unknown_and_late_response_not_mismatched(self):
        other = SimulationService(target=delayed_worker)
        ctx = multiprocessing.get_context('spawn')
        other.requests, other.responses = ctx.Queue(16), ctx.Queue(16)
        other.process = ctx.Process(target=delayed_worker, args=(other.requests, other.responses))
        other.process.start()
        try:
            with self.assertRaises(ChannelError) as caught:
                await other.call('step', timeout=0.02)
            self.assertEqual((caught.exception.status_code, caught.exception.outcome), (504, 'unknown'))
            result = await other.call('status', timeout=5)
            self.assertEqual(result['command'], 'status')
            self.assertNotEqual(result['correlation_id'], caught.exception.correlation_id)
        finally:
            await other.close()

    async def test_background_failed_process_remains_resettable_and_sanitized(self):
        other = SimulationService(runtime_factory=failing_runtime)
        await other.start()
        try:
            initial = await other.call('status')
            args = {'expected_run_id': initial['run_id']}
            await other.call('start', args)
            status = await wait_condition(lambda: other.call('status'), lambda state: state['status']=='failed')
            self.assertFalse(status['completed'])
            self.assertNotIn('SECRET', str(status))
            self.assertNotIn('RuntimeError', str(status))
            reset = await other.call('reset', {**args, 'scenario':'nop', 'seed':42, 'config':asdict(RulesConfig())})
            self.assertEqual((reset['status'], reset['tick']), ('paused', 0))
            step = await other.call('step', {'expected_run_id':reset['run_id']})
            self.assertEqual(step['tick'], 1)
        finally:
            await other.close()

    async def test_shutdown_fallback_reaps_unresponsive_process(self):
        other = SimulationService(target=stuck_worker)
        ctx = multiprocessing.get_context('spawn')
        other.requests, other.responses = ctx.Queue(16), ctx.Queue(16)
        other.process = ctx.Process(target=stuck_worker, args=(other.requests, other.responses))
        other.process.start()
        before = monotonic()
        await other.close()
        self.assertLess(monotonic() - before, 10)
        self.assertTrue(other.forced_shutdown)
        self.assertFalse(other.process.is_alive())

    async def test_tick_value_error_is_failed_not_input_validation(self):
        other = SimulationService(runtime_factory=value_error_runtime)
        await other.start()
        try:
            initial = await other.call('status')
            with self.assertRaises(ChannelError) as caught:
                await other.call('step', {'expected_run_id': initial['run_id']})
            self.assertEqual((caught.exception.code, caught.exception.status_code), ('tick_failed', 500))
            self.assertNotIn('SECRET', str(caught.exception))
            self.assertEqual((await other.call('status'))['status'], 'failed')
            reset = await other.call('reset', {'expected_run_id': initial['run_id'], 'scenario': 'nop',
                                              'seed': 42, 'config': asdict(RulesConfig())})
            self.assertEqual(reset['status'], 'paused')
        finally:
            await other.close()


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = create_app()
        self.lifespan = self.app.router.lifespan_context(self.app)
        await self.lifespan.__aenter__()
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url='http://test')

    async def asyncTearDown(self):
        process = self.app.state.simulation.process
        await self.client.aclose()
        await self.lifespan.__aexit__(None, None, None)
        self.assertFalse(process.is_alive())

    async def test_routes_reset_speed_and_stale_run(self):
        initial = (await self.client.get('/api/status')).json()
        for key in ('run_id','status','tick','completed'):
            self.assertIn(key,initial)
        args = {'expected_run_id': initial['run_id']}
        step = await self.client.post('/api/step',json=args)
        self.assertEqual(step.status_code,200)
        self.assertEqual(step.json()['tick'],1)
        start = await self.client.post('/api/start',json=args)
        self.assertEqual(start.json()['status'],'running')
        self.assertEqual((await self.client.post('/api/step',json=args)).status_code,409)
        paused = (await self.client.post('/api/pause',json=args)).json()
        speed = (await self.client.post('/api/speed',json={**args,'ticks_per_second':20})).json()
        self.assertEqual(speed['metrics'],paused['metrics'])
        field = (await self.client.get('/api/field')).json()
        self.assertTrue(all('genome' not in e for e in field['entities']))
        detail = (await self.client.get('/api/entities/1')).json()
        self.assertEqual(len(detail['entity']['genome']),32)
        self.assertIsNone((await self.client.get('/api/entities/999')).json()['entity'])
        reset = (await self.client.post('/api/reset',json={**args,'scenario':'mixed','seed':42,'config':asdict(RulesConfig())})).json()
        self.assertNotEqual(reset['run_id'],initial['run_id'])
        self.assertEqual((reset['status'],reset['tick']),('paused',0))
        self.assertEqual((await self.client.post('/api/start',json=args)).status_code,409)
        self.assertEqual((await self.client.get('/api/status')).json()['tick'],0)

    async def test_input_rejected_before_ipc_and_body_limit(self):
        config=asdict(RulesConfig())
        cases=[('/api/start',{}),('/api/start',{'expected_run_id':True}),
               ('/api/speed',{'expected_run_id':'x','ticks_per_second':True}),
               ('/api/speed',{'expected_run_id':'x','ticks_per_second':0}),
               ('/api/speed',{'expected_run_id':'x','ticks_per_second':101}),
               ('/api/reset',{'expected_run_id':'x','scenario':'mixed','seed':True,'config':config}),
               ('/api/reset',{'expected_run_id':'x','scenario':'mixed','seed':42,'config':{}})]
        with patch.object(self.app.state.simulation,'call') as call:
            for route,body in cases:
                self.assertEqual((await self.client.post(route,json=body)).status_code,422)
            self.assertEqual((await self.client.get('/api/entities/-1')).status_code,422)
            self.assertEqual((await self.client.post('/api/start',content=' '*17000)).status_code,413)
            for definition in (replace(SCENARIOS['mixed'], width=65),
                               replace(SCENARIOS['mixed'], entities=SCENARIOS['mixed'].entities*17)):
                with patch.dict(SCENARIOS, {'mixed': definition}):
                    invalid = await self.client.post('/api/reset',json={'expected_run_id':'x','scenario':'mixed','seed':42,'config':config})
                    self.assertEqual(invalid.status_code,422)
            call.assert_not_called()
        response=await self.client.get('/api/status',headers={'Origin':'http://example.com'})
        self.assertNotIn('access-control-allow-origin',response.headers)

    async def test_http_unavailability_timeout_and_safe_errors(self):
        for error in (ChannelError('timeout','Исход неизвестен',504,outcome='unknown'),
                      ChannelError('process_unavailable','Процесс недоступен',503)):
            with patch.object(self.app.state.simulation,'call',side_effect=error):
                result=await self.client.get('/api/status')
            self.assertEqual(result.status_code,error.status_code)
            self.assertEqual(result.json()['error']['outcome'],error.outcome)

    async def test_import_does_not_start_process(self):
        import importlib
        import backend.app
        before={p.pid for p in multiprocessing.active_children()}
        importlib.reload(backend.app)
        self.assertEqual({p.pid for p in multiprocessing.active_children()},before)


class LifespanGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_multiple_uvicorn_worker_rejected_before_spawn(self):
        app = create_app()
        with patch('backend.app.multiprocessing.parent_process', return_value=object()):
            with patch.object(SimulationService, 'start') as start:
                with self.assertRaisesRegex(RuntimeError, 'один Uvicorn worker'):
                    async with app.router.lifespan_context(app):
                        self.fail('Не должен запускаться')
                start.assert_not_called()


if __name__=='__main__':
    unittest.main()
