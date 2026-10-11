"""Команды, снимки и восстановление синхронного владельца мира."""

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from core.biology import RulesConfig
from core.runtime import SimulationRuntime, RuntimeStateError, StaleRunError, NestedCommandError
from core.scenarios import SCENARIOS


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = SimulationRuntime(scenario='mixed', seed=42, config=RulesConfig())

    def game(self, runtime=None):
        # RNG и внутренний мир доступны только тестам; публичный интерфейс их не выдаёт.
        world = (runtime or self.runtime)._world
        return (world.entities, world.reserve, world.metrics, world.tick,
                world.next_id, world.rng.getstate())

    def test_initial_pause_and_idempotent_start_pause(self):
        initial = self.runtime.status()
        self.assertEqual((initial['status'], initial['tick'], initial['completed']), ('paused', 0, True))
        self.assertEqual(initial['last_completed_tick'], 0)
        self.assertIsNone(initial['error'])
        before = self.game()
        for _ in range(2):
            self.assertEqual(self.runtime.start()['status'], 'running')
        for _ in range(2):
            self.assertEqual(self.runtime.pause()['status'], 'paused')
        self.assertEqual(self.game(), before)

    def test_state_restrictions_and_exactly_one_tick(self):
        before = self.game()
        with self.assertRaises(RuntimeStateError):
            self.runtime.advance()
        self.assertEqual(self.game(), before)
        self.assertEqual(self.runtime.step()['tick'], 1)
        self.assertEqual(self.runtime.step()['tick'], 2)
        self.runtime.start()
        before = self.game()
        with self.assertRaises(RuntimeStateError):
            self.runtime.step()
        self.assertEqual(self.game(), before)
        self.assertEqual(self.runtime.advance()['tick'], 3)
        self.assertEqual(self.runtime.advance()['tick'], 4)
        self.assertEqual(self.runtime.status()['last_completed_tick'], 4)
        self.runtime.pause()
        self.assertEqual(self.runtime.step()['tick'], 5)

    def test_reset_reproduces_start_clears_metrics_and_has_new_id(self):
        initial_game = self.game()
        initial = self.runtime.status()
        for _ in range(35):
            self.runtime.step()
        self.assertGreater(self.runtime.status()['metrics']['organism_births'], 0)
        self.runtime.start()
        result = self.runtime.reset(scenario='mixed', seed=42, config=RulesConfig(),
                                    expected_run_id=initial['run_id'])
        self.assertEqual(self.game(), initial_game)
        self.assertEqual((result['status'], result['tick']), ('paused', 0))
        self.assertNotEqual(result['run_id'], initial['run_id'])
        self.assertEqual(result['metrics']['organism_births'], 0)

    def test_reset_to_explicit_different_scenario_seed_and_config(self):
        config = RulesConfig(organism_max_age=2, mutation_percent=0)
        self.runtime.reset(scenario='nop', seed=7, config=config)
        expected = SCENARIOS['nop'].build(seed=7, config=config)
        self.assertEqual(self.runtime._world.entities, expected.entities)
        self.assertEqual(self.runtime._world.rng.getstate(), expected.rng.getstate())
        self.assertEqual(self.runtime.step()['metrics']['organisms'], 1)
        self.assertEqual(self.runtime.step()['metrics']['organisms'], 0)

    def test_invalid_reset_does_not_replace_running_world(self):
        self.runtime.start()
        before_status, before_game = self.runtime.status(), self.game()
        for kwargs, error in (({'scenario': 'missing', 'seed': 42, 'config': RulesConfig()}, ValueError),
                              ({'scenario': 'mixed', 'seed': True, 'config': RulesConfig()}, TypeError),
                              ({'scenario': 'mixed', 'seed': 42, 'config': None}, TypeError)):
            with self.assertRaises(error):
                self.runtime.reset(**kwargs)
            self.assertEqual(self.runtime.status(), before_status)
            self.assertEqual(self.game(), before_game)
        # Ошибка после частичной подготовки нового мира также не заменяет старый.
        broken = replace(SCENARIOS['mixed'], entities=SCENARIOS['mixed'].entities * 2)
        with patch.dict(SCENARIOS, {'broken': broken}):
            with self.assertRaises(ValueError):
                self.runtime.reset(scenario='broken', seed=42, config=RulesConfig())
        self.assertEqual(self.runtime.status(), before_status)
        self.assertEqual(self.game(), before_game)

    def test_old_run_id_rejected_by_all_methods_before_effects(self):
        old = self.runtime.status()['run_id']
        self.runtime.reset(scenario='mixed', seed=42, config=RulesConfig())
        before_game, before_status = self.game(), self.runtime.status()
        calls = [self.runtime.start, self.runtime.pause, self.runtime.step, self.runtime.advance,
                 self.runtime.status, self.runtime.field_snapshot,
                 lambda **kw: self.runtime.entity_details(1, **kw),
                 lambda **kw: self.runtime.reset(scenario='missing', seed=True, config=None, **kw)]
        for command in calls:
            with self.assertRaises(StaleRunError):
                command(expected_run_id=old)
            self.assertEqual(self.game(), before_game)
            self.assertEqual(self.runtime.status(), before_status)

    def test_snapshots_and_details_are_detached_without_genomes_in_field(self):
        field = self.runtime.field_snapshot()
        saved = deepcopy(field)
        details = self.runtime.entity_details(1)
        saved_details = deepcopy(details)
        self.assertEqual((field['width'], field['height']), (17, 11))
        self.assertTrue(all(set(e) == {'id', 'x', 'y', 'kind', 'profile', 'direction'} for e in field['entities']))
        self.assertEqual(details['entity']['genome'], (6,)+(0,)*31)
        self.assertEqual((details['entity']['parent_id'], details['entity']['founder_id'],
                          details['entity']['generation']), (None, 1, 0))
        self.assertIsNone(self.runtime.entity_details(999)['entity'])
        self.runtime.step()
        self.assertEqual(field, saved)
        self.assertEqual(details, saved_details)
        before = self.game()
        field['entities'][0]['x'] = -100
        field['metrics']['R'] = -1
        field['entities'].clear()
        details['entity']['energy'] = -1
        details['entity']['genome'] = (1,)*32
        self.assertEqual(self.game(), before)
        self.assertEqual(self.runtime.entity_details(1)['entity']['energy'], 913)

    def test_observation_does_not_change_rng_or_result(self):
        reference = SimulationRuntime(scenario='mixed', seed=42, config=RulesConfig())
        for _ in range(50):
            before = self.game()
            self.runtime.status()
            self.runtime.field_snapshot()
            self.runtime.entity_details(1)
            self.assertEqual(self.game(), before)
            self.runtime.step()
            reference.step()
        self.assertEqual(self.game(), self.game(reference))
        self.assertNotEqual(self.runtime.status()['run_id'], reference.status()['run_id'])

    def test_partial_tick_failure_is_visible_and_reset_recovers(self):
        self.runtime.step()
        original = self.runtime._world
        def fail():
            original.move(1, 9, 5)
            raise ArithmeticError('Искусственная ошибка после изменения')
        with patch.object(original, 'step', side_effect=fail):
            with self.assertRaisesRegex(ArithmeticError, 'после изменения'):
                self.runtime.step()
        status = self.runtime.status()
        self.assertEqual((status['status'], status['completed'], status['tick'], status['last_completed_tick']),
                         ('failed', False, 1, 1))
        self.assertEqual(status['error'], {'type': 'ArithmeticError', 'message': 'Искусственная ошибка после изменения',
                                          'command': 'step', 'attempted_tick': 2})
        self.assertEqual(self.runtime.entity_details(1)['entity']['x'], 9)
        self.assertFalse(self.runtime.field_snapshot()['completed'])
        for command in (self.runtime.start, self.runtime.step, self.runtime.advance):
            with self.assertRaises(RuntimeStateError):
                command()
        self.assertEqual(self.runtime.pause()['status'], 'failed')
        before = self.runtime.status()
        with self.assertRaises(ValueError):
            self.runtime.reset(scenario='missing', seed=42, config=RulesConfig())
        self.assertEqual(self.runtime.status(), before)
        reset = self.runtime.reset(scenario='mixed', seed=42, config=RulesConfig())
        self.assertEqual((reset['status'], reset['tick'], reset['error']), ('paused', 0, None))
        self.assertEqual(self.runtime.step()['tick'], 1)

    def test_failure_even_if_world_counter_was_advanced_is_not_success(self):
        self.runtime.start()
        original = self.runtime._world.step
        def fail_after_step():
            original()
            raise RuntimeError('Сбой после шага')
        with patch.object(self.runtime._world, 'step', side_effect=fail_after_step):
            with self.assertRaises(RuntimeError):
                self.runtime.advance()
        result = self.runtime.field_snapshot()
        self.assertEqual((result['status'], result['completed'], result['tick'], result['last_completed_tick']),
                         ('failed', False, 1, 0))
        self.assertEqual(result['error']['command'], 'advance')

    def test_nested_commands_and_reading_are_rejected(self):
        original = self.runtime._world.step
        commands = [self.runtime.start, self.runtime.pause, self.runtime.step, self.runtime.advance,
                    self.runtime.status, self.runtime.field_snapshot,
                    lambda: self.runtime.entity_details(1),
                    lambda: self.runtime.reset(scenario='mixed', seed=42, config=RulesConfig())]
        def update():
            for command in commands:
                with self.assertRaises(NestedCommandError):
                    command()
            original()
        with patch.object(self.runtime._world, 'step', side_effect=update):
            self.runtime.step()
        self.assertEqual(self.runtime.status()['tick'], 1)

    def test_invalid_entity_id_and_expected_id_have_no_effects(self):
        before = self.game()
        with self.assertRaises(TypeError):
            self.runtime.entity_details(True)
        with self.assertRaises(TypeError):
            self.runtime.start(expected_run_id=True)
        self.assertEqual(self.game(), before)
        self.assertEqual(self.runtime.status()['status'], 'paused')


if __name__ == '__main__':
    unittest.main()
