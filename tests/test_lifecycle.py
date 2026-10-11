"""Явные граничные сценарии жизни, наследования и закрытого бюджета."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from core.biology import BiologicalWorld, Kind, OrganismAdapter, RulesConfig
from core.vm import Action, StopReason, execute


def tape(*values):
    return list(values) + [0] * (32 - len(values))


class LifecycleTests(unittest.TestCase):
    def world(self, *, reserve=10000, seed=42, config=None, width=17, height=11):
        return BiologicalWorld(width, height, seed=seed, reserve=reserve, config=config)

    def balance(self, w):
        self.assertEqual(w.total_resources, w.initial_budget)
        self.assertGreaterEqual(w.reserve, 0)
        found = []
        for y in range(w.height):
            for x in range(w.width):
                entity = w.get_at(x, y)
                if entity:
                    self.assertEqual((entity.x, entity.y), (x, y))
                    self.assertEqual(w.get(entity.id), entity)
                    self.assertGreaterEqual(entity.energy, 0)
                    self.assertGreaterEqual(entity.minerals, 0)
                    found.append(entity.id)
        self.assertEqual(sorted(found), [e.id for e in w.entities])

    def advance(self, w, n):
        for _ in range(n):
            w.step()
            self.balance(w)

    def test_phase_order_reserve_and_single_tick(self):
        c = RulesConfig(remains_max_age=1)
        w = self.world(reserve=43, config=c)
        r = w.create_remains(0, 0, energy=10, minerals=1)
        p = w.create_plant(2, 2, 'grass', energy=1, minerals=1)
        a = w.create_organism(3, 3, tape(6), energy=20, minerals=1)
        events = []
        original_grow = w._grow
        original_perform = w.perform
        def grow(entity):
            self.assertIsNone(w.get(r.id))
            self.assertEqual(w.reserve, 14)
            events.append('plant')
            original_grow(entity)
        def perform(entity_id, action):
            self.assertEqual((w.get(p.id).energy, w.get(p.id).minerals), (11, 2))
            self.assertEqual(w.get(a.id).age, 1)
            self.assertEqual(w.tick, 0)
            events.append('organism')
            return original_perform(entity_id, action)
        with patch.object(w, '_grow', side_effect=grow), patch.object(w, 'perform', side_effect=perform):
            results = w.step()
        self.assertEqual(events, ['plant', 'organism'])
        self.assertEqual(w.tick, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(w.get(a.id).energy, 20)
        self.balance(w)

    def test_shuffle_occurs_immediately_before_each_live_phase(self):
        w = self.world()
        p = w.create_plant(0, 0, 'grass', energy=1, minerals=1)
        a = w.create_organism(1, 1, tape(0))
        events = []
        original_shuffle, original_grow = w.rng.shuffle, w._grow
        def shuffle(ids):
            events.append(('shuffle', list(ids)))
            original_shuffle(ids)
        def grow(entity):
            events.append(('grow', entity.id))
            original_grow(entity)
        with patch.object(w.rng, 'shuffle', side_effect=shuffle), patch.object(w, '_grow', side_effect=grow):
            w.step()
        self.assertEqual(events, [('shuffle', [p.id]), ('grow', p.id), ('shuffle', [a.id])])

    def test_age_and_move_once(self):
        w = self.world()
        a = w.create_organism(8, 5, tape(1))
        results = w.step()
        self.assertEqual([i for i, _ in results], [a.id])
        a = w.get(a.id)
        self.assertEqual((a.age, a.x, a.y, a.energy), (1, 8, 4, 251))
        self.balance(w)

    def test_death_before_vm_by_age_resources_and_metabolism(self):
        cases = [(RulesConfig(organism_max_age=1), 20, 10, (20, 10)),
                 (RulesConfig(), 0, 10, (0, 10)),
                 (RulesConfig(), 20, 0, (20, 0)),
                 (RulesConfig(), 1, 10, (0, 10)),
                 (RulesConfig(), 0, 0, None)]
        for config, energy, minerals, stocks in cases:
            w = self.world(config=config)
            a = w.create_organism(1, 1, tape(6), energy=energy, minerals=minerals)
            reserve = w.reserve
            self.assertEqual(w.step(), ())
            self.assertIsNone(w.get(a.id))
            remains = w.get_at(1, 1)
            if stocks:
                self.assertEqual((remains.energy, remains.minerals, remains.age), (*stocks, 0))
                self.assertGreater(remains.id, a.id)
            else:
                self.assertIsNone(remains)
            self.assertEqual(w.metrics['organism_deaths'], 1)
            self.assertEqual(w.reserve, reserve + int(energy == 1 and minerals > 0))
            self.balance(w)

    def test_fatal_turn_stops_vm_without_next_instruction(self):
        w = self.world()
        a = w.create_organism(1, 1, tape(2, 6), energy=2, minerals=3)
        result = w.step()[0][1]
        self.assertEqual((result.instructions_executed, result.last_pc, result.reason),
                         (1, 0, StopReason.ADAPTER_STOPPED))
        self.assertIsNone(w.get(a.id))
        self.assertEqual((w.get_at(1, 1).energy, w.get_at(1, 1).minerals), (0, 3))
        self.balance(w)

    def test_fatal_payment_has_no_effect_after_cost(self):
        for action, energy in ((Action.EAT, 1), (Action.MOVE, 4), (Action.TURN_RANDOM, 1)):
            w = self.world()
            a = w.create_organism(1, 1, tape(int(action)), energy=energy, minerals=3)
            if action == Action.EAT:
                target = w.create_organism(1, 0, tape(0), energy=50, minerals=10)
            before_rng = w.rng.getstate()
            self.assertFalse(w.perform(a.id, action))
            self.assertIsNone(w.get(a.id))
            self.assertEqual(w.get_at(1, 1).kind, Kind.REMAINS)
            if action == Action.EAT:
                self.assertEqual(w.get(target.id), target)
            self.assertEqual(w.rng.getstate(), before_rng)
            self.balance(w)

    def test_victim_dies_immediately_and_skips_future_vm(self):
        w = self.world()
        victim = w.create_organism(1, 0, tape(6), energy=20, minerals=10)
        eater = w.create_organism(1, 1, tape(5), energy=20, minerals=10)
        result = w.step()  # seed 42: [2, 1]
        self.assertEqual([i for i, _ in result], [eater.id])
        self.assertIsNone(w.get(victim.id))
        remains = w.get_at(1, 0)
        self.assertEqual((remains.energy, remains.minerals, remains.age), (0, 6, 0))
        self.assertEqual((w.get(eater.id).energy, w.get(eater.id).minerals), (38, 14))
        self.assertEqual(w.metrics['organism_deaths'], 1)
        self.balance(w)

    def test_conversion_death_keeps_transformed_resources(self):
        for action, energy, minerals, expected in (
                (Action.MINERALS_TO_ENERGY, 10, 8, (42, 0)),
                (Action.ENERGY_TO_MINERALS, 32, 1, (0, 9))):
            w = self.world()
            a = w.create_organism(1, 1, tape(int(action)), energy=energy, minerals=minerals)
            adapter = OrganismAdapter(w, a.id)
            result = execute(a.genome, sensors=adapter, perform=adapter.perform,
                             rng=w.rng, is_active=adapter.is_active)
            self.assertEqual(result.reason, StopReason.ADAPTER_STOPPED)
            self.assertEqual((w.get_at(1, 1).energy, w.get_at(1, 1).minerals), expected)
            self.balance(w)

    def test_new_remains_decay_after_exactly_ten_following_ticks(self):
        w = self.world(config=RulesConfig(organism_max_age=1))
        a = w.create_organism(1, 1, tape(0), energy=200, minerals=100)
        reserve = w.reserve
        w.step()
        r = w.get_at(1, 1)
        self.assertEqual((r.age, r.energy, r.minerals), (0, 200, 100))
        self.assertEqual(w.reserve, reserve)
        self.advance(w, 9)
        self.assertEqual(w.get(r.id).age, 9)
        w.step()
        self.assertIsNone(w.get_at(1, 1))
        self.assertEqual(w.reserve, reserve+600)
        self.assertEqual(w.tick, 11)
        self.balance(w)

    def test_fully_eaten_remains_removed_immediately(self):
        w = self.world()
        a = w.create_organism(1, 1, tape(5), energy=10, minerals=1)
        r = w.create_remains(1, 0, energy=5, minerals=3)
        self.assertTrue(w.perform(a.id, Action.EAT))
        self.assertIsNone(w.get(r.id))
        self.assertIsNone(w.get_at(1, 0))
        self.assertEqual((w.get(a.id).energy, w.get(a.id).minerals), (14, 4))
        self.balance(w)

    def test_organism_thresholds_and_age(self):
        for initial_e, initial_m, births in ((850, 52, 1), (849, 52, 0), (850, 51, 0)):
            w = self.world(config=RulesConfig(mutation_percent=0))
            a = w.create_organism(0, 0, tape(0), energy=initial_e, minerals=initial_m)
            self.advance(w, 29)
            self.assertEqual(w.metrics['organism_births'], 0)
            self.assertEqual(w.get(a.id).age, 29)
            w.step()
            self.assertEqual(w.metrics['organism_births'], births)
            self.balance(w)

    def test_no_space_no_split_no_id_or_mutation(self):
        w = self.world(width=2, height=2, config=RulesConfig(mutation_percent=100))
        a = w.create_organism(0, 0, tape(0), energy=851, minerals=53)
        for x, y in ((0, 1), (1, 0), (1, 1)):
            w.create_organism(x, y, tape(0), energy=100, minerals=10)
        next_id = w.next_id
        self.advance(w, 30)
        a = w.get(a.id)
        self.assertEqual((a.energy, a.minerals), (821, 53))
        self.assertEqual(w.next_id, next_id)
        self.assertEqual(w.metrics['organism_births'], 0)
        self.assertEqual(w.metrics['mutations'], 0)

    def test_odd_split_entire_genome_lineage_and_birth_deferral(self):
        genome = tape(0)
        genome[31] = 31  # Не достигается при бюджете 16.
        w = self.world(config=RulesConfig(mutation_percent=0))
        a = w.create_organism(0, 0, genome, energy=851, minerals=53, direction=7)
        self.advance(w, 30)
        parent = w.get(a.id)
        child = next(e for e in w.entities if e.id != a.id)
        self.assertEqual((parent.energy, parent.minerals), (411, 27))
        self.assertEqual((child.energy, child.minerals, child.age, child.direction), (410, 26, 0, 7))
        self.assertEqual(child.genome, tuple(genome))
        self.assertIsNot(child.genome, parent.genome)
        self.assertEqual((parent.parent_id, parent.founder_id, parent.generation), (None, a.id, 0))
        self.assertEqual((child.parent_id, child.founder_id, child.generation), (a.id, a.id, 1))
        genome[31] = 0
        self.assertEqual(child.genome[31], 31)
        self.assertEqual(w.metrics['mutations'], 0)
        w.step()
        self.assertEqual(w.get(child.id).age, 1)
        self.assertEqual(w.get(child.id).energy, 409)
        self.balance(w)

    def test_mutation_zero_and_hundred_percent_exactly_one_different_cell(self):
        for chance, expected in ((0, 0), (100, 1)):
            w = self.world(config=RulesConfig(mutation_percent=chance))
            a = w.create_organism(1, 1, tape(0), energy=850, minerals=52)
            self.advance(w, 30)
            child = next(e for e in w.entities if e.parent_id == a.id)
            differences = [(i, x, y) for i, (x, y) in enumerate(zip(a.genome, child.genome)) if x != y]
            self.assertEqual(len(differences), expected)
            self.assertTrue(all(0 <= v <= 31 for v in child.genome))
            self.assertEqual(w.get(a.id).genome, a.genome)
            self.assertEqual(w.metrics['mutations'], expected)

    def test_mutation_can_target_unused_last_cell_and_excludes_previous_value(self):
        w = self.world(config=RulesConfig(mutation_percent=100))
        genome = tape(0)
        genome[31] = 31
        a = w.create_organism(1, 1, genome, energy=850, minerals=52)
        self.advance(w, 29)
        original = w.rng.randrange
        def select(stop):
            if stop == 100:
                return 0
            if stop == 32:
                return 31
            if stop == 31:
                return 30
            return original(stop)
        with patch.object(w.rng, 'randrange', side_effect=select):
            w.step()
        child = next(e for e in w.entities if e.parent_id == a.id)
        self.assertEqual(child.genome[31], 30)
        self.assertEqual(w.get(a.id).genome[31], 31)
        self.assertEqual(sum(x != y for x, y in zip(child.genome, a.genome)), 1)

    def test_growth_all_profiles_and_age(self):
        for profile, energy, minerals in (('tree', 14, 14), ('bush', 16, 16), ('grass', 20, 20)):
            w = self.world()
            p = w.create_plant(1, 1, profile, energy=10, minerals=10)
            w.step()
            p = w.get(p.id)
            self.assertEqual((p.energy, p.minerals, p.age), (energy, minerals, 1))
            self.balance(w)

    def test_growth_energy_first_partial_reserve_and_capacity(self):
        # Начальная цена 5; оставшиеся 7: +4 E, на минерал не хватает.
        w = self.world(reserve=12)
        p = w.create_plant(1, 1, 'tree', energy=1, minerals=1)
        w.step()
        self.assertEqual((w.get(p.id).energy, w.get(p.id).minerals, w.reserve), (5, 1, 3))
        self.balance(w)
        w = self.world(reserve=16)
        p = w.create_plant(1, 1, 'tree', energy=1, minerals=1)
        w.step()
        self.assertEqual((w.get(p.id).energy, w.get(p.id).minerals, w.reserve), (5, 2, 3))
        self.balance(w)
        w = self.world(reserve=256+4*255+50)
        p = w.create_plant(1, 1, 'grass', energy=256, minerals=255)
        w.step()
        self.assertEqual((w.get(p.id).energy, w.get(p.id).minerals, w.reserve), (256, 256, 46))
        self.balance(w)

    def test_profile_capacity_validation_is_atomic(self):
        for profile, maximum in (('tree', 2048), ('bush', 1024), ('grass', 256)):
            w = self.world()
            before = (w.reserve, w.next_id, w.rng.getstate())
            for energy, minerals in ((maximum+1, 1), (1, maximum+1)):
                with self.assertRaises(ValueError):
                    w.create_plant(1, 1, profile, energy=energy, minerals=minerals)
                self.assertEqual((w.reserve, w.next_id, w.rng.getstate()), before)

    def test_plant_age_resource_death_and_no_growth_before_death(self):
        for profile in ('tree', 'bush', 'grass'):
            c = RulesConfig()
            c = replace(c, **{profile: replace(getattr(c, profile), max_age=1)})
            w = self.world(config=c)
            p = w.create_plant(1, 1, profile, energy=10, minerals=20)
            reserve = w.reserve
            w.step()
            self.assertIsNone(w.get(p.id))
            self.assertEqual((w.get_at(1, 1).energy, w.get_at(1, 1).minerals), (10, 20))
            self.assertEqual(w.reserve, reserve)
            self.assertEqual(w.metrics['plant_deaths'], 1)
            self.balance(w)
        w = self.world()
        p = w.create_plant(1, 1, 'grass', energy=0, minerals=1)
        w.step()
        self.assertIsNone(w.get(p.id))
        self.assertEqual(w.get_at(1, 1).age, 0)

    def test_plant_reproduction_profiles_odd_split_and_newborn_deferral(self):
        for profile, stock, radius in (('tree', 1435, 4), ('bush', 717, 3), ('grass', 181, 2)):
            w = self.world(reserve=5*stock, config=RulesConfig(plant_reproduction_percent=100))
            p = w.create_plant(0, 0, profile, energy=stock, minerals=stock)
            self.advance(w, 29)
            self.assertEqual(w.metrics['plant_births'], 0)
            w.step()
            children = [e for e in w.entities if e.id != p.id]
            self.assertEqual(len(children), 1)
            child = children[0]
            self.assertEqual((child.age, child.energy, child.minerals, child.profile),
                             (0, stock//2, stock//2, profile))
            self.assertLessEqual(child.x, radius)
            self.assertLessEqual(child.y, radius)
            self.assertEqual((w.get(p.id).energy, w.get(p.id).minerals), (stock-stock//2, stock-stock//2))
            w.step()
            self.assertEqual(w.get(child.id).age, 1)
            self.assertEqual(w.get(child.id).energy, stock//2)  # Нет резерва.
            self.balance(w)

    def test_plant_threshold_chance_and_no_space(self):
        for energy, minerals, chance, births in ((179, 180, 100, 0), (180, 179, 100, 0),
                                                (180, 180, 0, 0), (180, 180, 100, 1)):
            w = self.world(reserve=energy+4*minerals, config=RulesConfig(plant_reproduction_percent=chance))
            w.create_plant(1, 1, 'grass', energy=energy, minerals=minerals)
            self.advance(w, 30)
            self.assertEqual(w.metrics['plant_births'], births)
        w = self.world(reserve=900, width=1, height=1, config=RulesConfig(plant_reproduction_percent=100))
        p = w.create_plant(0, 0, 'grass', energy=180, minerals=180)
        self.advance(w, 30)
        self.assertEqual(w.next_id, 2)
        self.assertEqual((w.get(p.id).energy, w.get(p.id).minerals), (180, 180))
        self.assertEqual(w.metrics['plant_births'], 0)

    def test_event_metrics_snapshot_and_technical_operations(self):
        w = self.world()
        a = w.create_organism(1, 1, tape(0))
        p = w.create_plant(2, 2, 'tree', energy=1, minerals=1)
        w.create_plant(3, 3, 'bush', energy=1, minerals=1)
        w.create_plant(4, 4, 'grass', energy=1, minerals=1)
        r = w.create_remains(5, 5, energy=1, minerals=1)
        self.assertEqual(w.metrics, {'organism_births': 0, 'plant_births': 0, 'organism_deaths': 0,
                                    'plant_deaths': 0, 'mutations': 0, 'organisms': 1,
                                    'tree': 1, 'bush': 1, 'grass': 1, 'remains': 1})
        metrics = w.metrics
        metrics['organisms'] = 999
        w.remove(a.id)
        w.remove(p.id)
        w.remove(r.id)
        self.assertEqual(w.metrics['organism_deaths'], 0)
        self.assertEqual(w.metrics['plant_deaths'], 0)
        self.assertEqual(w.metrics['organisms'], 0)
        self.balance(w)

    def test_reproducible_full_lifecycle(self):
        def run():
            w = self.world(reserve=20000)
            w.create_organism(4, 4, tape(6), energy=900, minerals=100)
            w.create_organism(8, 8, tape(4, 1))
            for x, profile in enumerate(('tree', 'bush', 'grass')):
                w.create_plant(x, 0, profile, energy=180, minerals=180)
            self.advance(w, 150)
            return w.entities, w.reserve, w.metrics, w.rng.getstate(), w.tick, w.next_id
        self.assertEqual(run(), run())

    def test_founder_is_inherited_across_multiple_generations(self):
        w = self.world(reserve=20000, config=RulesConfig(mutation_percent=0))
        founder = w.create_organism(8, 5, tape(6), energy=900, minerals=256)
        self.advance(w, 100)
        descendants = [e for e in w.entities if e.generation == 2]
        self.assertTrue(descendants)
        for child in descendants:
            self.assertEqual(child.founder_id, founder.id)
            self.assertEqual(w.get(child.parent_id).generation, 1)

    def test_config_validation(self):
        for kwargs in ({'mutation_percent': -1}, {'mutation_percent': 101},
                       {'mutation_percent': True}, {'organism_max_age': 0}):
            with self.assertRaises((ValueError, TypeError)):
                RulesConfig(**kwargs)


if __name__ == '__main__':
    unittest.main()
