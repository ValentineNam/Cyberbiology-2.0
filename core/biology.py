"""Закрытый ресурсный мир и адаптер независимой VM. С фазами жизни и наследованием."""

from collections.abc import Sequence
from dataclasses import dataclass, fields, replace
from enum import StrEnum

from .vm import Action, ExecutionResult, GENOME_LENGTH, execute, validate_genome
from .world import World, UnknownEntityError, OutOfBoundsError, _require_int

# Север сверху; x растёт вправо, y вниз.
DIRECTIONS = ((0, -1), (1, -1), (1, 0), (1, 1),
              (0, 1), (-1, 1), (-1, 0), (-1, -1))


@dataclass(frozen=True)
class PlantRules:
    max_age: int
    energy_max: int
    minerals_max: int
    energy_growth: int
    mineral_growth: int
    radius: int

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            _require_int(value, item.name)
            if value <= 0:
                raise ValueError(f"{item.name} должен быть положительным")


@dataclass(frozen=True)
class RulesConfig:
    mineral_value: int = 4
    energy_max: int = 1024
    minerals_max: int = 256
    initial_energy: int = 256
    initial_minerals: int = 64
    turn_cost: int = 1
    straight_move_cost: int = 4
    diagonal_move_cost: int = 6
    blocked_move_cost: int = 1
    eat_cost: int = 1
    photosynthesis_gain: int = 14
    conversion_minerals: int = 8
    conversion_energy: int = 32
    organism_bite: int = 80
    organism_mineral_divisor: int = 5
    plant_bite: int = 120
    plant_mineral_divisor: int = 4
    remains_energy_bite: int = 80
    remains_mineral_bite: int = 20
    hunger_factor: int = 5
    relative_distance: int = 2

    organism_max_age: int = 128
    metabolism: int = 1
    reproduction_age: int = 30
    reproduction_energy: int = 820
    reproduction_minerals: int = 52
    mutation_percent: int = 15
    plant_reproduction_percent: int = 20
    plant_threshold_numerator: int = 7
    plant_threshold_denominator: int = 10
    probability_scale: int = 100
    remains_max_age: int = 10
    offspring_divisor: int = 2
    tree: PlantRules = PlantRules(512, 2048, 2048, 4, 4, 4)
    bush: PlantRules = PlantRules(256, 1024, 1024, 6, 6, 3)
    grass: PlantRules = PlantRules(64, 256, 256, 10, 10, 2)

    def __post_init__(self):
        adjustable = {"organism_max_age", "remains_max_age", "mutation_percent",
                      "plant_reproduction_percent"}
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name in ("tree", "bush", "grass"):
                if type(value) is not PlantRules:
                    raise TypeError("Профиль должен быть PlantRules")
                default = item.default
                if (value.max_age > default.max_age or
                        any(getattr(value, f.name) != getattr(default, f.name)
                            for f in fields(value) if f.name != "max_age")):
                    raise ValueError("Допустимо только уменьшение возраста профиля")
                continue
            _require_int(value, item.name)
            if item.name.endswith('_percent'):
                if not 0 <= value <= self.probability_scale:
                    raise ValueError("Вероятность должна быть от 0 до 100")
            elif item.name in adjustable:
                if not 1 <= value <= item.default:
                    raise ValueError("Допустимо только уменьшение предела возраста")
            elif value != item.default:
                raise ValueError(f"{item.name}: иной баланс пока не принят")

    def plant(self, profile: "PlantProfile") -> PlantRules:
        return getattr(self, profile.value)


class Kind(StrEnum):
    ORGANISM = "organism"
    PLANT = "plant"
    REMAINS = "remains"


class PlantProfile(StrEnum):
    TREE = "tree"
    BUSH = "bush"
    GRASS = "grass"


class InsufficientReserveError(ValueError):
    """Создание не может быть оплачено резервом."""


@dataclass(frozen=True)
class ResourceEntity:
    id: int
    x: int
    y: int
    kind: Kind
    energy: int
    minerals: int
    genome: tuple[int, ...] | None = None
    direction: int = 0
    profile: PlantProfile | None = None
    age: int = 0
    parent_id: int | None = None
    founder_id: int | None = None
    generation: int = 0


class DeathContext(StrEnum):
    TURN_START = "turn_start"
    METABOLISM = "metabolism"
    OWN_ACTION = "own_action"
    OTHER_FEEDING = "other_feeding"


@dataclass(frozen=True)
class DeathRecord:
    tick: int
    entity_id: int
    kind: Kind
    profile: PlantProfile | None
    age: int
    max_age: int
    energy: int
    minerals: int
    reasons: tuple[str, ...]
    context: DeathContext


class BiologicalWorld:
    def __init__(self, width: int, height: int, *, seed: int, reserve: int,
                 config: RulesConfig | None = None, record_deaths: bool = False):
        if type(record_deaths) is not bool:
            raise TypeError("record_deaths должен быть bool")
        self._record_deaths = record_deaths
        self._death_records: list[DeathRecord] = []
        self._nonnegative(reserve, "reserve")
        if config is not None and type(config) is not RulesConfig:
            raise TypeError("config должен быть RulesConfig")
        self._config = config if config is not None else RulesConfig()
        self._world = World(width, height, seed=seed)
        self._reserve = reserve
        self._budget = reserve
        self._entities: dict[int, ResourceEntity] = {}
        self._stepping = False
        self._events = {"organism_births": 0, "plant_births": 0,
                        "organism_deaths": 0, "plant_deaths": 0, "mutations": 0}

    @staticmethod
    def _nonnegative(value: int, name: str):
        _require_int(value, name)
        if value < 0:
            raise ValueError(f"{name} должен быть неотрицательным")

    @property
    def config(self):
        return self._config

    @property
    def width(self):
        return self._world.width

    @property
    def height(self):
        return self._world.height

    @property
    def tick(self):
        return self._world.tick

    @property
    def next_id(self):
        return self._world.next_id

    @property
    def rng(self):
        return self._world.rng

    @property
    def reserve(self):
        return self._reserve

    @property
    def initial_budget(self):
        return self._budget

    @property
    def total_resources(self):
        return self.reserve + sum(e.energy + self.config.mineral_value * e.minerals
                                  for e in self._entities.values())

    @property
    def entities(self):
        return tuple(self._entities[i] for i in sorted(self._entities))

    def get(self, entity_id: int) -> ResourceEntity | None:
        _require_int(entity_id, "entity_id")
        return self._entities.get(entity_id)

    def get_at(self, x: int, y: int) -> ResourceEntity | None:
        position = self._world.get_at(x, y)
        return None if position is None else self._entities[position.id]

    def _require(self, entity_id: int) -> ResourceEntity:
        entity = self.get(entity_id)
        if entity is None:
            raise UnknownEntityError(entity_id)
        return entity

    def _organism(self, entity_id: int) -> ResourceEntity:
        entity = self._require(entity_id)
        if entity.kind != Kind.ORGANISM:
            raise ValueError("Действие доступно только организму")
        return entity

    def create_organism(self, x: int, y: int, genome: Sequence[int], *,
                        energy: int | None = None, minerals: int | None = None,
                        direction: int = 0) -> ResourceEntity:
        tape = validate_genome(genome)
        energy = self.config.initial_energy if energy is None else energy
        minerals = self.config.initial_minerals if minerals is None else minerals
        self._nonnegative(energy, "energy")
        self._nonnegative(minerals, "minerals")
        if energy > self.config.energy_max or minerals > self.config.minerals_max:
            raise ValueError("Запасы организма превышают ёмкость")
        _require_int(direction, "direction")
        if not 0 <= direction < len(DIRECTIONS):
            raise ValueError("Направление должно быть от 0 до 7")
        return self._create(x, y, Kind.ORGANISM, energy, minerals,
                            genome=tape, direction=direction)

    def create_plant(self, x: int, y: int, profile: PlantProfile | str, *,
                     energy: int, minerals: int) -> ResourceEntity:
        profile = PlantProfile(profile)
        self._nonnegative(energy, "energy")
        self._nonnegative(minerals, "minerals")
        limits = self.config.plant(profile)
        if energy > limits.energy_max or minerals > limits.minerals_max:
            raise ValueError("Запасы растения превышают ёмкость профиля")
        return self._create(x, y, Kind.PLANT, energy, minerals, profile=profile)

    def create_remains(self, x: int, y: int, *, energy: int, minerals: int) -> ResourceEntity:
        return self._create(x, y, Kind.REMAINS, energy, minerals)

    def _create(self, x, y, kind, energy, minerals, **kwargs):
        self._nonnegative(energy, "energy")
        self._nonnegative(minerals, "minerals")
        cost = energy + self.config.mineral_value * minerals
        if cost > self.reserve:
            raise InsufficientReserveError("Недостаточно резерва для создания")
        position = self._world.place(x, y)  # Все проверки до изменения бюджета.
        entity = ResourceEntity(position.id, x, y, kind, energy, minerals, **kwargs)
        if kind == Kind.ORGANISM:
            entity = replace(entity, founder_id=entity.id)
        self._entities[entity.id] = entity
        self._reserve -= cost
        return entity

    def remove(self, entity_id: int) -> ResourceEntity:
        entity = self._require(entity_id)
        self._world.remove(entity_id)
        del self._entities[entity_id]
        self._reserve += entity.energy + self.config.mineral_value * entity.minerals
        return entity

    def move(self, entity_id: int, x: int, y: int) -> ResourceEntity:
        """Техническое перемещение, без цены игрового MOVE."""
        entity = self._require(entity_id)
        position = self._world.move(entity_id, x, y)
        entity = replace(entity, x=position.x, y=position.y)
        self._entities[entity_id] = entity
        return entity

    def _spend(self, entity: ResourceEntity, amount: int) -> ResourceEntity:
        changed = replace(entity, energy=entity.energy - amount)
        self._entities[entity.id] = changed
        self._reserve += amount
        return changed

    def _front_position(self, entity):
        dx, dy = DIRECTIONS[entity.direction]
        return entity.x + dx, entity.y + dy

    def _target(self, entity):
        try:
            return self.get_at(*self._front_position(entity)), False
        except OutOfBoundsError:
            return None, True

    def perform(self, entity_id: int, action: Action) -> bool:
        if not isinstance(action, Action):
            raise TypeError("action должен быть Action")
        self._organism(entity_id)
        if self._die_if_needed(entity_id):
            return False
        result = self._perform_action(entity_id, action)
        self._die_if_needed(entity_id)
        return result

    def _perform_action(self, entity_id: int, action: Action) -> bool:
        if not isinstance(action, Action):
            raise TypeError("action должен быть Action")
        entity = self._organism(entity_id)
        c = self.config
        if action in (Action.TURN_LEFT, Action.TURN_RIGHT, Action.TURN_RANDOM):
            if entity.energy < c.turn_cost:
                return False
            entity = self._spend(entity, c.turn_cost)
            if self._die_if_needed(entity.id):
                return False
            if action == Action.TURN_RANDOM:
                direction = self.rng.randrange(len(DIRECTIONS))
            else:
                direction = (entity.direction + (-1 if action == Action.TURN_LEFT else 1)) % len(DIRECTIONS)
            self._entities[entity.id] = replace(entity, direction=direction)
            return True
        if action == Action.MOVE:
            target, wall = self._target(entity)
            blocked = wall or target is not None
            dx, dy = DIRECTIONS[entity.direction]
            cost = (c.blocked_move_cost if blocked else
                    c.diagonal_move_cost if dx and dy else c.straight_move_cost)
            if entity.energy < cost:
                return False
            entity = self._spend(entity, cost)
            if self._die_if_needed(entity.id):
                return False
            if not blocked:
                self.move(entity.id, *self._front_position(entity))
            return not blocked
        if action == Action.EAT:
            if entity.energy < c.eat_cost:
                return False
            target, wall = self._target(entity)
            entity = self._spend(entity, c.eat_cost)
            if self._die_if_needed(entity.id):
                return False
            if wall or target is None:
                return False
            if target.kind == Kind.REMAINS:
                bite = c.remains_energy_bite
            elif target.kind == Kind.PLANT:
                bite = c.plant_bite
            else:
                bite = c.organism_bite
            energy = min(bite, target.energy, c.energy_max - entity.energy)
            if target.kind == Kind.REMAINS:
                mineral_bite = c.remains_mineral_bite
            else:
                divisor = (c.plant_mineral_divisor if target.kind == Kind.PLANT
                           else c.organism_mineral_divisor)
                mineral_bite = (energy + divisor - 1) // divisor
            minerals = min(mineral_bite, target.minerals, c.minerals_max - entity.minerals)
            self._entities[entity.id] = replace(entity, energy=entity.energy + energy,
                                                minerals=entity.minerals + minerals)
            self._entities[target.id] = replace(target, energy=target.energy - energy,
                                                minerals=target.minerals - minerals)
            self._die_if_needed(target.id, context=DeathContext.OTHER_FEEDING)
            return energy > 0 or minerals > 0
        if action == Action.PHOTOSYNTHESIS:
            gain = min(c.photosynthesis_gain, c.energy_max - entity.energy, self.reserve)
            self._entities[entity.id] = replace(entity, energy=entity.energy + gain)
            self._reserve -= gain
            return gain > 0
        if action == Action.MINERALS_TO_ENERGY:
            if (entity.minerals < c.conversion_minerals or
                    c.energy_max - entity.energy < c.conversion_energy):
                return False
            self._entities[entity.id] = replace(entity, energy=entity.energy + c.conversion_energy,
                                                minerals=entity.minerals - c.conversion_minerals)
            return True
        if action == Action.ENERGY_TO_MINERALS:
            if (entity.energy < c.conversion_energy or
                    c.minerals_max - entity.minerals < c.conversion_minerals):
                return False
            self._entities[entity.id] = replace(entity, energy=entity.energy - c.conversion_energy,
                                                minerals=entity.minerals + c.conversion_minerals)
            return True
        raise ValueError("Неизвестное действие")

    @property
    def metrics(self) -> dict[str, int]:
        counts = {"organisms": 0, "tree": 0, "bush": 0, "grass": 0, "remains": 0}
        for entity in self.entities:
            key = (entity.profile.value if entity.kind == Kind.PLANT else
                   "organisms" if entity.kind == Kind.ORGANISM else "remains")
            counts[key] += 1
        return {**self._events, **counts}

    @property
    def death_records(self) -> tuple[DeathRecord, ...]:
        return tuple(self._death_records)

    def _die_if_needed(self, entity_id: int, *,
                       context: DeathContext = DeathContext.OWN_ACTION) -> bool:
        entity = self.get(entity_id)
        if entity is None:
            return True
        if entity.kind == Kind.REMAINS:
            if entity.energy == 0 and entity.minerals == 0:
                self.remove(entity.id)
            return False
        maximum = (self.config.organism_max_age if entity.kind == Kind.ORGANISM
                   else self.config.plant(entity.profile).max_age)
        if entity.energy > 0 and entity.minerals > 0 and entity.age < maximum:
            return False
        if self._record_deaths:
            reasons = tuple(reason for reason, triggered in (
                ("age_limit", entity.age >= maximum),
                ("energy_depleted", entity.energy == 0),
                ("minerals_depleted", entity.minerals == 0),
            ) if triggered)
            self._death_records.append(DeathRecord(
                self.tick + int(self._stepping), entity.id, entity.kind, entity.profile,
                entity.age, maximum, entity.energy, entity.minerals, reasons, context))
        # Удаление технической записи: ресурсный remove здесь НЕ вызывается.
        self._world.remove(entity.id)
        del self._entities[entity.id]
        key = "organism_deaths" if entity.kind == Kind.ORGANISM else "plant_deaths"
        self._events[key] += 1
        if entity.energy or entity.minerals:
            position = self._world.place(entity.x, entity.y)
            self._entities[position.id] = ResourceEntity(
                position.id, entity.x, entity.y, Kind.REMAINS, entity.energy, entity.minerals)
        return True

    def _grow(self, entity: ResourceEntity) -> None:
        limits = self.config.plant(entity.profile)
        energy = min(limits.energy_growth, limits.energy_max - entity.energy, self.reserve)
        self._reserve -= energy
        minerals = min(limits.mineral_growth, limits.minerals_max - entity.minerals,
                       self.reserve // self.config.mineral_value)
        self._reserve -= minerals * self.config.mineral_value
        self._entities[entity.id] = replace(entity, energy=entity.energy + energy,
                                            minerals=entity.minerals + minerals)

    def _reproduce(self, entity: ResourceEntity) -> None:
        c = self.config
        if entity.age < c.reproduction_age:
            return
        if entity.kind == Kind.ORGANISM:
            if entity.energy < c.reproduction_energy or entity.minerals < c.reproduction_minerals:
                return
            cells = [(entity.x + dx, entity.y + dy) for dx, dy in DIRECTIONS]
            self.rng.shuffle(cells)
            cells = [(x, y) for x, y in cells if 0 <= x < self.width and 0 <= y < self.height
                     and self.get_at(x, y) is None]
        else:
            limits = c.plant(entity.profile)
            if (c.plant_threshold_denominator * entity.energy < c.plant_threshold_numerator * limits.energy_max
                    or c.plant_threshold_denominator * entity.minerals < c.plant_threshold_numerator * limits.minerals_max):
                return
            if self.rng.randrange(c.probability_scale) >= c.plant_reproduction_percent:
                return
            cells = [(x, y) for x in range(max(0, entity.x-limits.radius), min(self.width, entity.x+limits.radius+1))
                     for y in range(max(0, entity.y-limits.radius), min(self.height, entity.y+limits.radius+1))
                     if (x, y) != (entity.x, entity.y) and self.get_at(x, y) is None]
            if cells:
                self.rng.shuffle(cells)
        if not cells:
            return
        energy, minerals = entity.energy // c.offspring_divisor, entity.minerals // c.offspring_divisor
        genome = entity.genome
        mutated = False
        if entity.kind == Kind.ORGANISM:
            genome = list(genome)
            if self.rng.randrange(c.probability_scale) < c.mutation_percent:
                index = self.rng.randrange(len(genome))
                value = self.rng.randrange(GENOME_LENGTH - 1)
                genome[index] = value if value < genome[index] else value + 1
                mutated = True
            genome = tuple(genome)
        position = self._world.place(*cells[0])
        child = ResourceEntity(position.id, position.x, position.y, entity.kind, energy, minerals,
                               genome=genome, direction=entity.direction, profile=entity.profile,
                               parent_id=entity.id if entity.kind == Kind.ORGANISM else None,
                               founder_id=entity.founder_id,
                               generation=entity.generation + 1 if entity.kind == Kind.ORGANISM else 0)
        self._entities[child.id] = child
        self._entities[entity.id] = replace(entity, energy=entity.energy-energy, minerals=entity.minerals-minerals)
        key = "organism_births" if entity.kind == Kind.ORGANISM else "plant_births"
        self._events[key] += 1
        self._events["mutations"] += int(mutated)

    def step(self) -> tuple[tuple[int, ExecutionResult], ...]:
        if self._stepping:
            raise RuntimeError("Вложенный биологический step запрещён")
        self._stepping = True
        try:
            initial = self.entities
            remains = [e.id for e in initial if e.kind == Kind.REMAINS]
            plants = [e.id for e in initial if e.kind == Kind.PLANT]
            organisms = [e.id for e in initial if e.kind == Kind.ORGANISM]
            results = []

            def update():
                for entity_id in remains:
                    entity = self.get(entity_id)
                    if entity is None or entity.kind != Kind.REMAINS:
                        continue
                    entity = replace(entity, age=entity.age + 1)
                    self._entities[entity.id] = entity
                    if entity.age >= self.config.remains_max_age or not (entity.energy or entity.minerals):
                        self.remove(entity.id)
                for kind, ids in ((Kind.PLANT, plants), (Kind.ORGANISM, organisms)):
                    self.rng.shuffle(ids)
                    for entity_id in ids:
                        entity = self.get(entity_id)
                        if entity is None or entity.kind != kind:
                            continue
                        entity = replace(entity, age=entity.age + 1)
                        self._entities[entity.id] = entity
                        if self._die_if_needed(entity.id, context=DeathContext.TURN_START):
                            continue
                        if kind == Kind.PLANT:
                            self._grow(entity)
                        else:
                            self._spend(entity, self.config.metabolism)
                            if self._die_if_needed(entity.id, context=DeathContext.METABOLISM):
                                continue
                            adapter = OrganismAdapter(self, entity.id)
                            result = execute(entity.genome, sensors=adapter, perform=adapter.perform,
                                             rng=self.rng, is_active=adapter.is_active)
                            results.append((entity.id, result))
                            if self._die_if_needed(entity.id):
                                continue
                        self._reproduce(self._require(entity.id))

            self._world.run_tick(update)
            return tuple(results)
        finally:
            self._stepping = False


class OrganismAdapter:
    def __init__(self, world: BiologicalWorld, entity_id: int):
        world._organism(entity_id)
        self._world = world
        self._id = entity_id

    def is_active(self) -> bool:
        entity = self._world.get(self._id)
        return entity is not None and entity.kind == Kind.ORGANISM

    def front(self) -> int:
        entity = self._world._organism(self._id)
        target, wall = self._world._target(entity)
        if wall:
            return 5
        if target is None:
            return 0
        if target.kind == Kind.PLANT:
            return 3
        if target.kind == Kind.REMAINS:
            return 4
        distance = sum(a != b for a, b in zip(entity.genome, target.genome))
        return 1 if distance <= self._world.config.relative_distance else 2

    def hungry(self) -> bool:
        entity = self._world._organism(self._id)
        return self._world.config.hunger_factor * entity.energy <= self._world.config.energy_max

    def perform(self, action: Action) -> bool:
        return self._world.perform(self._id, action)
