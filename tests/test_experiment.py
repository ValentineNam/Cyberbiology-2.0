"""Отчёты и диагностика не изменяют игру или RNG."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.biology import BiologicalWorld, DeathContext, RulesConfig
from core.experiment import main, observe, run_experiment, write_report
from core.lifecycle_example import build_world
from core.scenarios import SCENARIOS
from core.vm import Action


class ExperimentTests(unittest.TestCase):
    def snapshot(self, world):
        return (world.entities, world.reserve, world.metrics, world.tick,
                world.next_id, world.rng.getstate())

    def experiment(self, **kwargs):
        return run_experiment(scenario='mixed', seed=42, ticks=160, interval=10, **kwargs)

    def test_reproducible_report_and_game(self):
        config = RulesConfig(mutation_percent=0)
        first, second = self.experiment(config=config), self.experiment(config=config)
        self.assertEqual(first.report, second.report)
        self.assertEqual(self.snapshot(first.world), self.snapshot(second.world))

    def test_observation_interval_and_report_do_not_change_world_rng(self):
        baseline = self.experiment(collect_report=False)
        for interval in (1, 7, 1000):
            result = run_experiment(scenario='mixed', seed=42, ticks=160, interval=interval)
            self.assertEqual(self.snapshot(result.world), self.snapshot(baseline.world))
            self.assertEqual(result.report['final'], observe(baseline.world))
            before = self.snapshot(result.world)
            for _ in range(3):
                observe(result.world)
            with tempfile.TemporaryDirectory() as directory:
                write_report(result.report, Path(directory) / 'report.json')
            self.assertEqual(before, self.snapshot(result.world))
        self.assertIsNone(baseline.report)
        self.assertEqual(baseline.world.death_records, ())

    def test_history_zero_intervals_and_final_without_duplicates(self):
        for ticks, interval, expected in ((0, 5, [0]), (10, 5, [0, 5, 10]),
                                          (11, 5, [0, 5, 10, 11]), (3, 10, [0, 3])):
            result = run_experiment(scenario='nop', seed=1, ticks=ticks, interval=interval)
            self.assertEqual([h['tick'] for h in result.report['history']], expected)
            self.assertEqual(result.report['final'], result.report['history'][-1])

    def test_all_ticks_continue_after_extinction(self):
        result = run_experiment(scenario='nop', seed=42, ticks=35, interval=7)
        self.assertEqual(result.world.tick, 35)
        self.assertEqual(result.report['diagnostics']['organism_extinction_tick'], 20)
        self.assertEqual(result.report['final']['organisms'], 0)
        self.assertIsNone(result.report['final']['max_generation'])
        self.assertEqual(result.report['final']['remains'], 0)
        self.assertEqual(result.report['final']['reserve'], 1000)
        self.assertEqual(result.report['diagnostics']['deaths'][0]['reasons'], ('energy_depleted',))
        self.assertEqual(result.report['diagnostics']['deaths'][0]['context'], 'metabolism')

    def test_invariant_check_every_tick_even_without_history(self):
        from core.experiment import check_invariants
        for report in (False, True):
            with patch('core.experiment.check_invariants', wraps=check_invariants) as checked:
                run_experiment(scenario='mixed', seed=42, ticks=19, interval=1000, collect_report=report)
            self.assertEqual(checked.call_count, 20)  # tick 0 плюс каждый шаг.

    def test_invariant_failure_on_unrecorded_tick_is_not_hidden(self):
        from core.experiment import check_invariants
        def check(world):
            if world.tick == 2:
                raise AssertionError('Тестовый дефект в тик без записи')
            check_invariants(world)
        with patch('core.experiment.check_invariants', side_effect=check):
            with self.assertRaisesRegex(AssertionError, 'тик без записи'):
                run_experiment(scenario='nop', seed=42, ticks=10, interval=1000)

    def test_full_report_json_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            with redirect_stdout(io.StringIO()):
                main(['--seed', '42', '--scenario', 'branching', '--ticks', '7',
                      '--interval', '3', '--output', str(path)])
            report = json.loads(path.read_text())
            self.assertEqual(report['seed'], 42)
            self.assertEqual(report['requested_ticks'], 7)
            self.assertEqual(report['executed_ticks'], 7)
            self.assertEqual(report['report_version'], 1)
            self.assertEqual(report['rules_version'], '004-v1')
            self.assertIn('python_version', report)
            self.assertEqual(report['configuration']['rules']['organism_max_age'], 128)
            self.assertEqual(report['configuration']['rules']['tree']['max_age'], 512)
            self.assertEqual(report['configuration']['world'], {'width': 7, 'height': 3, 'initial_budget': 5000})
            self.assertEqual(report['configuration']['vm']['instruction_budget'], 16)
            self.assertEqual(report['scenario']['entities'][0]['genome'][:5], [10, 3, 4, 8, 6])
            self.assertEqual(report['final']['R'], 5000)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_invalid_cli_parameters_have_explanation_and_no_simulation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = ['--seed', '42', '--scenario', 'nop', '--ticks', '5',
                    '--interval', '1', '--output', str(Path(directory) / 'report.json')]
            cases = [[], ['--seed', 'not-int'], ['--scenario', 'missing'],
                     ['--ticks', '-1'], ['--ticks', '1.5'], ['--interval', '0'],
                     ['--interval', '-2'], ['--output', directory],
                     ['--output', str(Path(directory) / 'missing' / 'report.json')]]
            for invalid in cases:
                argv = [] if not invalid else base + invalid
                errors = io.StringIO()
                with patch('core.experiment.run_experiment') as run:
                    with redirect_stderr(errors), self.assertRaises(SystemExit) as stopped:
                        main(argv)
                    self.assertEqual(stopped.exception.code, 2)
                    self.assertIn('error:', errors.getvalue())
                    run.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_unwritable_output_is_explained(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = ['--seed', '42', '--scenario', 'nop', '--ticks', '0',
                    '--interval', '1', '--output', str(Path(directory) / 'report.json')]
            with patch('core.experiment.write_report', side_effect=PermissionError('нет доступа')):
                with redirect_stderr(io.StringIO()) as errors, self.assertRaises(SystemExit) as stopped:
                    main(argv)
                self.assertEqual(stopped.exception.code, 2)
                self.assertIn('не удалось записать отчёт', errors.getvalue())

    def test_invalid_runner_parameters(self):
        base = {'scenario': 'nop', 'seed': 42, 'ticks': 0, 'interval': 1}
        for override in ({'seed': True}, {'ticks': True}, {'ticks': -1},
                         {'interval': 0}, {'interval': False}, {'scenario': 'missing'}):
            with self.assertRaises((ValueError, TypeError)):
                run_experiment(**{**base, **override})

    def test_mixed_matches_previous_world_and_long_result(self):
        old, new = build_world(), SCENARIOS['mixed'].build(seed=42)
        self.assertEqual(self.snapshot(old), self.snapshot(new))
        result = run_experiment(scenario='mixed', seed=42, ticks=2000, interval=100)
        for _ in range(2000):
            old.step()
        self.assertEqual(self.snapshot(old), self.snapshot(result.world))
        diagnostics = result.report['diagnostics']
        self.assertEqual(diagnostics['organism_extinction_tick'], 158)
        self.assertEqual(diagnostics['max_generation_observed'], 1)
        deaths = [d for d in diagnostics['deaths'] if d['kind'] == 'organism']
        self.assertEqual([(d['tick'], d['reasons'], d['context']) for d in deaths],
                         [(128, ('age_limit',), 'turn_start'), (158, ('age_limit',), 'turn_start')])
        self.assertEqual(result.report['final']['organism_births'], 1)
        self.assertEqual(result.report['final']['mutations'], 0)
        self.assertEqual(result.report['final']['grass'], 43)
        self.assertEqual(result.report['final']['R'], 30000)

    def test_control_and_branching_expected_first_steps(self):
        expectations = [('nop', 19, 64), ('photosynthesis', 269, 64), ('branching', 223, 72)]
        for scenario, energy, minerals in expectations:
            result = run_experiment(scenario=scenario, seed=42, ticks=1, interval=1)
            self.assertEqual((result.world.get(1).energy, result.world.get(1).minerals), (energy, minerals))
        result = run_experiment(scenario='branching', seed=42, ticks=4, interval=4)
        self.assertEqual((result.world.get(1).energy, result.world.get(1).minerals), (216, 80))


class DeathDiagnosticTests(unittest.TestCase):
    def world(self, config=None, record_deaths=True):
        return BiologicalWorld(7, 3, seed=42, reserve=5000, config=config, record_deaths=record_deaths)

    def test_all_simultaneous_flags_at_turn_start(self):
        w = self.world(RulesConfig(organism_max_age=1))
        a = w.create_organism(1, 1, [0]*32, energy=0, minerals=0)
        w.step()
        death = w.death_records[0]
        self.assertEqual(death.entity_id, a.id)
        self.assertEqual(death.reasons, ('age_limit', 'energy_depleted', 'minerals_depleted'))
        self.assertEqual((death.tick, death.age, death.context), (1, 1, DeathContext.TURN_START))
        self.assertIsNone(w.get_at(1, 1))
        with self.assertRaises(FrozenInstanceError):
            death.age = 10
        w.step()
        self.assertEqual(w.death_records, (death,))

    def test_metabolism_and_own_action_contexts(self):
        for program, energy, context in (([0]*32, 1, DeathContext.METABOLISM),
                                         ([2]+[0]*31, 2, DeathContext.OWN_ACTION)):
            w = self.world()
            a = w.create_organism(1, 1, program, energy=energy, minerals=1)
            w.step()
            death = w.death_records[0]
            self.assertEqual(death.entity_id, a.id)
            self.assertEqual((death.tick, death.context, death.energy, death.reasons),
                             (1, context, 0, ('energy_depleted',)))

    def test_direct_action_minerals_context_and_no_duplicate_records(self):
        w = self.world()
        a = w.create_organism(1, 1, [7]+[0]*31, energy=10, minerals=8)
        w.perform(a.id, Action.MINERALS_TO_ENERGY)
        death = w.death_records[0]
        self.assertEqual((death.tick, death.context, death.reasons),
                         (0, DeathContext.OWN_ACTION, ('minerals_depleted',)))
        self.assertEqual((death.energy, death.minerals), (42, 0))
        for _ in range(10):
            w.step()
        self.assertEqual(w.death_records, (death,))
        self.assertEqual(w.metrics['organism_deaths'], 1)

    def test_other_feeding_context_keeps_all_flags(self):
        w = self.world()
        victim = w.create_organism(1, 0, [0]*32, energy=5, minerals=1)
        eater = w.create_organism(1, 1, [5]+[0]*31, energy=20, minerals=10)
        w.step()  # seed 42: eater первым.
        death = w.death_records[0]
        self.assertEqual((death.entity_id, death.tick, death.context),
                         (victim.id, 1, DeathContext.OTHER_FEEDING))
        self.assertEqual(death.reasons, ('energy_depleted', 'minerals_depleted'))
        self.assertIsNotNone(w.get(eater.id))

    def test_plant_diagnostics_and_technical_remove_not_a_death(self):
        w = self.world()
        p = w.create_plant(1, 1, 'grass', energy=0, minerals=1)
        a = w.create_organism(2, 1, [0]*32)
        w.remove(a.id)
        w.step()
        death = w.death_records[0]
        self.assertEqual((death.entity_id, death.profile, death.context), (p.id, 'grass', DeathContext.TURN_START))
        self.assertEqual(death.reasons, ('energy_depleted',))
        self.assertEqual(len(w.death_records), 1)

    def test_recording_flag_does_not_change_rng_or_game(self):
        worlds = [self.world(record_deaths=value) for value in (False, True)]
        for world in worlds:
            world.create_organism(1, 1, [4, 1]+[0]*30, energy=10, minerals=10)
            for _ in range(20):
                world.step()
        a, b = worlds
        self.assertEqual((a.entities, a.reserve, a.metrics, a.rng.getstate()),
                         (b.entities, b.reserve, b.metrics, b.rng.getstate()))
        self.assertFalse(a.death_records)
        self.assertTrue(b.death_records)


if __name__ == '__main__':
    unittest.main()
