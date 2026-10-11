"""Приёмка каркаса мира через его публичное поведение."""

from dataclasses import FrozenInstanceError
import unittest

from core import OccupiedCellError, OutOfBoundsError, UnknownEntityError, World


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.world = World(17, 11, seed=42)

    def snapshot(self, world):
        return (
            world.entities,
            tuple(tuple(world.get_at(x, y) for x in range(world.width))
                  for y in range(world.height)),
            world.next_id, world.tick, world.rng.getstate(),
        )

    def assert_consistent(self, world):
        cells = []
        for y in range(world.height):
            for x in range(world.width):
                entity = world.get_at(x, y)
                if entity is not None:
                    self.assertEqual((entity.x, entity.y), (x, y))
                    self.assertEqual(world.get(entity.id), entity)
                    cells.append(entity)
        self.assertEqual(tuple(sorted(cells, key=lambda e: e.id)), world.entities)
        self.assertEqual(len({e.id for e in cells}), len(cells))

    def assert_rejected(self, error, operation):
        before = self.snapshot(self.world)
        with self.assertRaises(error):
            operation()
        self.assertEqual(before, self.snapshot(self.world))
        self.assert_consistent(self.world)

    def test_rectangular_boundaries(self):
        self.assertEqual((self.world.width, self.world.height), (17, 11))
        for x, y in ((0, 0), (16, 0), (0, 10), (16, 10), (8, 5)):
            self.assertIsNone(self.world.get_at(x, y))
            entity = self.world.place(x, y)
            self.assertEqual(self.world.get_at(x, y), entity)
        for x, y in ((-1, 0), (0, -1), (17, 0), (0, 11), (17, 11)):
            self.assert_rejected(OutOfBoundsError, lambda: self.world.get_at(x, y))
            self.assert_rejected(OutOfBoundsError, lambda: self.world.place(x, y))
        tiny = World(1, 1, seed=0)
        tiny.place(0, 0)
        with self.assertRaises(OutOfBoundsError):
            tiny.get_at(1, 0)
        self.assert_consistent(self.world)
        self.assert_consistent(tiny)

    def test_invalid_dimensions_and_seed(self):
        for value in (0, -1):
            for width, height in ((value, 11), (17, value)):
                with self.assertRaises(ValueError):
                    World(width, height, seed=0)
        for value in (True, 1.5, '17', None):
            for width, height in ((value, 11), (17, value)):
                with self.assertRaises(TypeError):
                    World(width, height, seed=0)
        with self.assertRaises(TypeError):
            World(17, 11, seed=None)

    def test_occupied_cell_does_not_replace_entity_or_consume_id(self):
        entity = self.world.place(2, 3)
        self.assert_rejected(OccupiedCellError, lambda: self.world.place(2, 3))
        self.assertEqual(self.world.get_at(2, 3), entity)
        self.assertEqual(self.world.place(3, 3).id, entity.id + 1)

    def test_move_preserves_id_and_frees_old_cell(self):
        entity = self.world.place(0, 0)
        moved = self.world.move(entity.id, 16, 10)
        self.assertEqual(moved.id, entity.id)
        self.assertIsNone(self.world.get_at(0, 0))
        self.assertEqual(self.world.get_at(16, 10), moved)
        self.assertEqual(self.world.get(entity.id), moved)
        self.world.move(entity.id, 16, 10)
        self.assert_consistent(self.world)
        with self.assertRaises(FrozenInstanceError):
            moved.x = 0

    def test_failed_moves_and_removals_are_atomic(self):
        entity = self.world.place(0, 0)
        self.world.place(1, 0)
        self.assert_rejected(OccupiedCellError, lambda: self.world.move(entity.id, 1, 0))
        self.assert_rejected(OutOfBoundsError, lambda: self.world.move(entity.id, 17, 0))
        self.assert_rejected(TypeError, lambda: self.world.move(entity.id, True, 0))
        self.assert_rejected(TypeError, lambda: self.world.place(0, 1.5))
        self.assert_rejected(TypeError, lambda: self.world.remove(True))
        self.assert_rejected(UnknownEntityError, lambda: self.world.move(999, 2, 0))
        self.assert_rejected(UnknownEntityError, lambda: self.world.remove(999))

    def test_removal_frees_cell_and_id_is_not_reused(self):
        entity = self.world.place(3, 4)
        self.assertEqual(self.world.remove(entity.id), entity)
        self.assertIsNone(self.world.get(entity.id))
        self.assertIsNone(self.world.get_at(3, 4))
        self.assert_rejected(UnknownEntityError, lambda: self.world.remove(entity.id))
        self.assertGreater(self.world.place(3, 4).id, entity.id)
        self.assert_consistent(self.world)

    def test_empty_and_ordinary_steps(self):
        self.world.step()
        self.assertEqual(self.world.tick, 1)
        entities = [self.world.place(16, 10), self.world.place(0, 0)]
        for expected_tick in (2, 3, 4):
            updated = []
            self.world.step(lambda _, e: updated.append(e.id))
            self.assertEqual(updated, [e.id for e in entities])
            self.assertEqual(self.world.tick, expected_tick)
        self.world.step()
        self.assertEqual(self.world.tick, 5)

    def test_deleted_created_and_moved_entities_during_step(self):
        first = self.world.place(0, 0)
        removed = self.world.place(1, 0)
        last = self.world.place(2, 0)
        updated = []
        created = []

        def update(world, entity):
            updated.append(entity.id)
            if entity.id == first.id:
                world.move(first.id, 16, 10)
                self.assert_consistent(world)
                world.remove(removed.id)
                self.assert_consistent(world)
                created.append(world.place(1, 0))
                self.assert_consistent(world)

        self.world.step(update)
        self.assertEqual(updated, [first.id, last.id])
        self.assertEqual(self.world.tick, 1)
        updated.clear()
        self.world.step(lambda _, e: updated.append(e.id))
        self.assertEqual(updated, [first.id, last.id, created[0].id])
        self.assertEqual(self.world.tick, 2)
        self.assert_consistent(self.world)

    def test_same_seed_and_operations_reproduce_rng_and_world(self):
        def scenario():
            world = World(17, 11, seed=123)
            choices = []
            for y in range(5):
                x = world.rng.randrange(world.width)
                choices.append(x)
                world.place(x, y)
                world.step()
                self.assert_consistent(world)
            return choices, self.snapshot(world)
        self.assertEqual(scenario(), scenario())

    def test_rng_instances_are_independent(self):
        reference = World(17, 11, seed=42)
        other = World(17, 11, seed=42)
        for _ in range(20):
            other.rng.random()
        self.assertEqual([self.world.rng.random() for _ in range(20)],
                         [reference.rng.random() for _ in range(20)])

    def test_nested_step_is_rejected(self):
        self.world.place(0, 0)
        def update(world, entity):
            with self.assertRaises(RuntimeError):
                world.step()
        self.world.step(update)
        self.assertEqual(self.world.tick, 1)

    def test_handler_failure_does_not_increment_tick_or_lock_world(self):
        entity = self.world.place(0, 0)
        def update(world, current):
            world.move(current.id, 1, 0)
            raise RuntimeError('Ошибка тестового обработчика')
        with self.assertRaises(RuntimeError):
            self.world.step(update)
        self.assertEqual(self.world.tick, 0)
        self.assertEqual(self.world.get(entity.id).x, 1)
        self.assert_consistent(self.world)
        self.world.step()
        self.assertEqual(self.world.tick, 1)


if __name__ == '__main__':
    unittest.main()
