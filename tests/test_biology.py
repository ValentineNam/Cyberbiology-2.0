"""Наблюдаемая приёмка ресурсов, адаптера и биологического шага."""

from dataclasses import FrozenInstanceError
from random import Random
import unittest
from unittest.mock import patch

from core.biology import BiologicalWorld, OrganismAdapter, InsufficientReserveError, RulesConfig
from core.vm import Action, execute
from core.world import World, OccupiedCellError, OutOfBoundsError, UnknownEntityError


def tape(*values):
    return list(values) + [0] * (32 - len(values))


class BiologyTests(unittest.TestCase):
    def world(self, reserve=10000, seed=42):
        return BiologicalWorld(17, 11, seed=seed, reserve=reserve)

    def check_balance(self, world):
        self.assertEqual(world.total_resources, world.initial_budget)
        self.assertGreaterEqual(world.reserve, 0)
        found = []
        for y in range(world.height):
            for x in range(world.width):
                entity = world.get_at(x, y)
                if entity:
                    self.assertEqual((entity.x, entity.y), (x, y))
                    self.assertEqual(world.get(entity.id), entity)
                    self.assertGreaterEqual(entity.energy, 0)
                    self.assertGreaterEqual(entity.minerals, 0)
                    found.append(entity.id)
        self.assertEqual(sorted(found), [e.id for e in world.entities])

    def snapshot(self, world):
        return world.entities, world.reserve, world.next_id, world.tick, world.rng.getstate()

    def action(self, world, entity, action, expected=True):
        self.assertEqual(world.perform(entity.id, action), expected)
        self.check_balance(world)
        return world.get(entity.id)

    def test_creation_removal_movement_and_independent_genomes(self):
        w = self.world()
        genome = tape(1)
        a = w.create_organism(1, 1, genome)
        b = w.create_organism(2, 1, genome)
        self.assertEqual((a.energy, a.minerals, a.direction), (256, 64, 0))
        self.assertEqual(w.reserve, 8976)
        genome[0] = 6
        self.assertEqual(a.genome[0], 1)
        self.assertEqual(b.genome[0], 1)
        with self.assertRaises(FrozenInstanceError):
            a.energy = 0
        moved = w.move(a.id, 16, 10)
        self.assertEqual((moved.id, moved.energy, moved.minerals), (a.id, 256, 64))
        self.assertIsNone(w.get_at(1, 1))
        self.check_balance(w)
        w.remove(a.id)
        self.assertEqual(w.reserve, 9488)
        self.check_balance(w)
        for create in (lambda: w.create_plant(3, 3, 'tree', energy=3, minerals=7),
                       lambda: w.create_remains(4, 4, energy=0, minerals=20)):
            entity = create()
            self.check_balance(w)
            w.remove(entity.id)
            self.check_balance(w)
        w.remove(b.id)
        self.assertEqual(w.reserve, 10000)

    def test_invalid_and_impossible_operations_are_atomic(self):
        w = self.world()
        a = w.create_organism(1, 1, tape(1))
        operations = [
            (OccupiedCellError, lambda: w.create_organism(1, 1, tape(1))),
            (OutOfBoundsError, lambda: w.create_remains(17, 0, energy=1, minerals=0)),
            (ValueError, lambda: w.create_organism(2, 1, tape(1), energy=1025)),
            (ValueError, lambda: w.create_organism(2, 1, tape(1), minerals=257)),
            (TypeError, lambda: w.create_organism(2, 1, tape(1), energy=True)),
            (ValueError, lambda: w.create_remains(2, 1, energy=-1, minerals=0)),
            (TypeError, lambda: w.create_plant(2, 1, 'tree', energy=1, minerals=1.5)),
            (ValueError, lambda: w.create_plant(2, 1, 'flower', energy=1, minerals=0)),
            (ValueError, lambda: w.create_organism(2, 1, [0] * 31)),
            (ValueError, lambda: w.create_organism(2, 1, tape(1), direction=8)),
            (TypeError, lambda: w.create_organism(2, 1, tape(1), direction=True)),
            (InsufficientReserveError, lambda: w.create_remains(2, 1, energy=10001, minerals=0)),
            (UnknownEntityError, lambda: w.remove(999)),
            (OutOfBoundsError, lambda: w.move(a.id, -1, 0)),
            (TypeError, lambda: w.perform(a.id, 1)),
        ]
        occupied = w.create_remains(2, 1, energy=0, minerals=0)
        operations.append((OccupiedCellError, lambda: w.move(a.id, occupied.x, occupied.y)))
        for error, operation in operations:
            before = self.snapshot(w)
            with self.assertRaises(error):
                operation()
            self.assertEqual(self.snapshot(w), before)
            self.check_balance(w)
        for reserve, error in ((-1, ValueError), (True, TypeError)):
            with self.assertRaises(error):
                self.world(reserve)
        with self.assertRaises(ValueError):
            RulesConfig(turn_cost=2)

    def test_all_directions_and_move_prices(self):
        expected = [(8, 4), (9, 4), (9, 5), (9, 6),
                    (8, 6), (7, 6), (7, 5), (7, 4)]
        costs = [4, 6, 4, 6, 4, 6, 4, 6]
        for direction, (position, cost) in enumerate(zip(expected, costs)):
            w = self.world()
            a = w.create_organism(8, 5, tape(1), direction=direction, energy=10, minerals=1)
            moved = self.action(w, a, Action.MOVE)
            self.assertEqual((moved.x, moved.y, moved.energy), (*position, 10-cost))
            self.assertIsNone(w.get_at(8, 5))

    def test_boundaries_and_occupied_move_cost_one(self):
        edges = [(8, 0), (16, 0), (16, 5), (16, 10),
                 (8, 10), (0, 10), (0, 5), (0, 0)]
        for direction, (x, y) in enumerate(edges):
            w = self.world()
            a = w.create_organism(x, y, tape(1), direction=direction, energy=2, minerals=1)
            self.assertEqual(OrganismAdapter(w, a.id).front(), 5)
            a = self.action(w, a, Action.MOVE, False)
            self.assertEqual((a.x, a.y, a.energy), (x, y, 1))
        w = self.world()
        a = w.create_organism(1, 1, tape(1), energy=2, minerals=1)
        w.create_remains(1, 0, energy=0, minerals=0)
        a = self.action(w, a, Action.MOVE, False)
        self.assertEqual(a.energy, 1)

    def test_insufficient_move_energy_never_charges_attempt_for_free_cell(self):
        for direction, energy in ((0, 3), (1, 5)):
            w = self.world()
            a = w.create_organism(8, 5, tape(1), direction=direction, energy=energy, minerals=1)
            before = self.snapshot(w)
            self.action(w, a, Action.MOVE, False)
            self.assertEqual(self.snapshot(w), before)
        # Нулевой запас теперь вызывает смерть; бюджет/RNG всё равно сохраняются.
        w = self.world()
        a = w.create_organism(0, 0, tape(1), energy=0, minerals=1)
        rng = w.rng.getstate()
        self.action(w, a, Action.MOVE, False)
        self.assertIsNone(w.get(a.id))
        self.assertEqual(w.rng.getstate(), rng)

    def test_turns_all_directions_and_rng(self):
        for direction in range(8):
            w = self.world()
            a = w.create_organism(8, 5, tape(1), direction=direction, energy=3, minerals=1)
            a = self.action(w, a, Action.TURN_LEFT)
            self.assertEqual((a.direction, a.energy), ((direction-1) % 8, 2))
            a = self.action(w, a, Action.TURN_RIGHT)
            self.assertEqual((a.direction, a.energy), (direction, 1))
            state = w.rng.getstate()
            self.action(w, a, Action.TURN_RANDOM, False)  # Смерть на оплате.
            self.assertIsNone(w.get(a.id))
            self.assertEqual(w.rng.getstate(), state)
        w = self.world()
        a = w.create_organism(8, 5, tape(1), energy=20, minerals=1)
        reference = Random(42)
        for _ in range(8):
            a = self.action(w, a, Action.TURN_RANDOM)
            self.assertEqual(a.direction, reference.randrange(8))
            self.assertEqual(w.rng.getstate(), reference.getstate())

    def test_all_front_categories_genome_distance_and_hunger_threshold(self):
        for distance, expected in ((0, 1), (2, 1), (3, 2)):
            w = self.world()
            a = w.create_organism(1, 1, tape(1))
            other = tape(1)
            for i in range(distance):
                other[i+1] = 12
            w.create_organism(1, 0, other)
            self.assertEqual(OrganismAdapter(w, a.id).front(), expected)
        for profile in ('tree', 'bush', 'grass'):
            w = self.world()
            a = w.create_organism(1, 1, tape(1))
            p = w.create_plant(1, 0, profile, energy=0, minerals=0)
            self.assertEqual(OrganismAdapter(w, a.id).front(), 3)
            w.remove(p.id)
            self.assertEqual(OrganismAdapter(w, a.id).front(), 0)
            w.create_remains(1, 0, energy=0, minerals=0)
            self.assertEqual(OrganismAdapter(w, a.id).front(), 4)
        for energy, hungry in ((204, True), (205, False), (0, True), (1024, False)):
            w = self.world()
            a = w.create_organism(1, 1, tape(1), energy=energy, minerals=1)
            self.assertEqual(OrganismAdapter(w, a.id).hungry(), hungry)

    def test_eat_organism_and_all_plant_profiles(self):
        for kind, bite, minerals in (('organism', 80, 16), ('tree', 120, 30),
                                     ('bush', 120, 30), ('grass', 120, 30)):
            w = self.world()
            a = w.create_organism(1, 1, tape(5), energy=10, minerals=1)
            if kind == 'organism':
                target = w.create_organism(1, 0, tape(5), energy=150, minerals=40)
            else:
                target = w.create_plant(1, 0, kind, energy=150, minerals=40)
            a = self.action(w, a, Action.EAT)
            self.assertEqual((a.energy, a.minerals), (9+bite, minerals+1))
            target = w.get(target.id)
            self.assertEqual((target.energy, target.minerals), (150-bite, 40-minerals))

    def test_eat_price_before_transfer_and_rounding(self):
        for kind, energy in (('organism', 6), ('tree', 5)):
            w = self.world()
            a = w.create_organism(1, 1, tape(5), energy=1024, minerals=1)
            if kind == 'organism':
                target = w.create_organism(1, 0, tape(5), energy=energy, minerals=10)
            else:
                target = w.create_plant(1, 0, kind, energy=energy, minerals=10)
            a = self.action(w, a, Action.EAT)
            self.assertEqual((a.energy, a.minerals), (1024, 2))
            self.assertEqual(w.get(target.id).energy, energy-1)
            w.remove(a.id)
            a = w.create_organism(1, 1, tape(5), energy=2, minerals=255)
            a = self.action(w, a, Action.EAT)
            self.assertEqual((a.energy, a.minerals), (energy, 256))
            self.assertIsNone(w.get(target.id))  # Цель погибла сразу.
            self.assertEqual(w.get_at(1, 0).minerals, 8)
        w = self.world()
        a = w.create_organism(1, 1, tape(5), energy=2, minerals=1)
        t = w.create_organism(1, 0, tape(5), energy=6, minerals=10)
        a = self.action(w, a, Action.EAT)
        self.assertEqual((a.energy, a.minerals), (7, 3))
        self.assertIsNone(w.get(t.id))
        self.assertEqual((w.get_at(1, 0).energy, w.get_at(1, 0).minerals), (0, 8))

    def test_plant_minerals_round_up_from_actual_energy(self):
        w = self.world()
        a = w.create_organism(1, 1, tape(5), energy=2, minerals=1)
        target = w.create_plant(1, 0, 'tree', energy=5, minerals=10)
        a = self.action(w, a, Action.EAT)
        self.assertEqual((a.energy, a.minerals), (6, 3))
        self.assertIsNone(w.get(target.id))
        self.assertEqual((w.get_at(1, 0).energy, w.get_at(1, 0).minerals), (0, 8))
        before = self.snapshot(w)
        adapter = OrganismAdapter(w, a.id)
        adapter.front()
        adapter.hungry()
        self.assertEqual(self.snapshot(w), before)

    def test_eat_remains_independent_minerals_and_limits(self):
        for energy, eater_m, expected_e, expected_m in ((100, 1, 89, 21),
                                                       (0, 1, 9, 21), (0, 255, 9, 256)):
            w = self.world()
            a = w.create_organism(1, 1, tape(5), energy=10, minerals=eater_m)
            target = w.create_remains(1, 0, energy=energy, minerals=25)
            a = self.action(w, a, Action.EAT)
            self.assertEqual((a.energy, a.minerals), (expected_e, expected_m))
            self.assertIsNotNone(w.get(target.id))

    def test_eat_empty_wall_no_energy_and_zero_target(self):
        for position in ((1, 1), (1, 0)):
            w = self.world()
            a = w.create_organism(*position, tape(5), energy=2, minerals=1)
            a = self.action(w, a, Action.EAT, False)
            self.assertEqual(a.energy, 1)
        for kind in ('organism', 'tree', 'remains'):
            w = self.world()
            a = w.create_organism(1, 1, tape(5), energy=0, minerals=1)
            if kind == 'organism':
                t = w.create_organism(1, 0, tape(5), energy=0, minerals=10)
            elif kind == 'tree':
                t = w.create_plant(1, 0, kind, energy=0, minerals=10)
            else:
                t = w.create_remains(1, 0, energy=0, minerals=0)
            self.action(w, a, Action.EAT, False)
            self.assertIsNone(w.get(a.id))
            self.assertEqual(w.get(t.id), t)
            w.remove(w.get_at(1, 1).id)
            a = w.create_organism(1, 1, tape(5), energy=2, minerals=1)
            a = self.action(w, a, Action.EAT, False)
            self.assertEqual((a.energy, a.minerals), (1, 1))
            # Проверка после действия превращает нулевую живую цель в останки.
            if kind != 'remains':
                self.assertEqual(w.get_at(1, 0).minerals, 10)
                self.assertIsNone(w.get(t.id))
            else:
                self.assertIsNone(w.get(t.id))

    def test_conversions_success_and_exact_boundaries(self):
        w = self.world()
        a = w.create_organism(1, 1, tape(7), energy=992, minerals=9)
        a = self.action(w, a, Action.MINERALS_TO_ENERGY)
        self.assertEqual((a.energy, a.minerals), (1024, 1))
        a = self.action(w, a, Action.ENERGY_TO_MINERALS)
        self.assertEqual((a.energy, a.minerals), (992, 9))
        w.remove(a.id)
        a = w.create_organism(1, 1, tape(8), energy=33, minerals=248)
        a = self.action(w, a, Action.ENERGY_TO_MINERALS)
        self.assertEqual((a.energy, a.minerals), (1, 256))
        # Точное обнуление минералов теперь смертельно, но сохраняет конверсию/R.
        w.remove(a.id)
        a = w.create_organism(1, 1, tape(7), energy=992, minerals=8)
        self.action(w, a, Action.MINERALS_TO_ENERGY)
        self.assertIsNone(w.get(a.id))
        self.assertEqual((w.get_at(1, 1).energy, w.get_at(1, 1).minerals), (1024, 0))

    def test_conversions_refuse_without_partial_changes(self):
        cases = [(7, 1, 7), (7, 993, 8), (8, 31, 1), (8, 32, 249)]
        for opcode, energy, minerals in cases:
            w = self.world()
            a = w.create_organism(1, 1, tape(opcode), energy=energy, minerals=minerals)
            before = self.snapshot(w)
            self.action(w, a, Action(opcode), False)
            self.assertEqual(self.snapshot(w), before)

    def test_photosynthesis_empty_partial_and_capacity(self):
        for reserve, energy, expected_energy, expected_reserve in (
                (5, 1, 1, 0), (10, 1, 6, 0), (25, 1, 15, 6),
                (1023+4+20, 1023, 1024, 19), (1024+4+20, 1024, 1024, 20)):
            w = self.world(reserve)
            a = w.create_organism(1, 1, tape(6), energy=energy, minerals=1)
            a = self.action(w, a, Action.PHOTOSYNTHESIS, expected_energy > energy)
            self.assertEqual((a.energy, w.reserve), (expected_energy, expected_reserve))

    def test_reproducible_shuffle_actions_and_one_turn_after_move(self):
        def run():
            w = self.world(seed=42)
            for x in (3, 6, 9, 12):
                w.create_organism(x, 5, tape(4, 1))
            w.create_plant(0, 0, 'grass', energy=0, minerals=0)
            order_log = []
            for _ in range(3):
                results = w.step()
                order = [i for i, _ in results]
                self.assertEqual(sorted(order), [1, 2, 3, 4])
                self.assertEqual(len(order), len(set(order)))
                self.assertTrue(all(r.instructions_executed == 2 for _, r in results))
                order_log.append(order)
                self.check_balance(w)
            self.assertEqual(w.tick, 3)
            return order_log, self.snapshot(w)
        first = run()
        self.assertEqual(first, run())
        self.assertEqual(first[0][0], [3, 2, 4, 1])

    def test_biological_snapshot_skips_removed_and_defers_new(self):
        w = self.world(seed=42)
        first = w.create_organism(1, 1, tape(0))
        second = w.create_organism(2, 1, tape(0))
        calls = []
        # seed 42 даёт порядок [2, 1]; модель рождения ещё не вводится.
        def fake_execute(genome, **kwargs):
            calls.append(genome[0])
            if len(calls) == 1:
                w.remove(first.id)
                w.create_organism(3, 1, tape(6))
            return 'test-result'
        with patch('core.biology.execute', side_effect=fake_execute):
            results = w.step()
        self.assertEqual([i for i, _ in results], [second.id])
        self.assertEqual(calls, [0])
        self.assertEqual([i for i, _ in w.step()], [3, 2])
        self.check_balance(w)

    def test_real_front_turn_move_integration(self):
        w = self.world()
        # empty выбирает offset=7, TURN_RIGHT, затем MOVE.
        a = w.create_organism(8, 5, tape(9, 7, 0, 0, 0, 0, 0, 3, 1))
        adapter = OrganismAdapter(w, a.id)
        result = execute(a.genome, sensors=adapter, perform=adapter.perform, rng=w.rng)
        self.assertEqual((result.instructions_executed, result.last_pc), (3, 8))
        a = w.get(a.id)
        self.assertEqual((a.x, a.y, a.direction, a.energy), (9, 4, 1, 249))
        self.check_balance(w)


class ExplicitOrderTests(unittest.TestCase):
    def test_explicit_order_snapshot_and_default_compatibility(self):
        w = World(17, 11, seed=42)
        a, b = w.place(0, 0), w.place(1, 0)
        seen = []
        order = [b.id, a.id]
        def update(world, entity):
            seen.append(entity.id)
            order.clear()
            if entity.id == b.id:
                world.remove(a.id)
                world.place(2, 0)
        w.step(update, order=order)
        self.assertEqual(seen, [b.id])
        seen.clear()
        w.step(lambda _, e: seen.append(e.id))
        self.assertEqual(seen, [2, 3])

    def test_invalid_order_is_rejected_before_updates(self):
        w = World(17, 11, seed=42)
        w.place(0, 0)
        for order, error in (([1, 1], ValueError), ([True], TypeError), ([999], UnknownEntityError)):
            with self.assertRaises(error):
                w.step(lambda *_: self.fail('Не должен вызываться'), order=order)
            self.assertEqual(w.tick, 0)


if __name__ == '__main__':
    unittest.main()
