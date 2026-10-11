"""Закрытый ресурсный мир и адаптер независимой VM. Без жизненного цикла."""

from collections.abc import Sequence
from dataclasses import dataclass, fields, replace
from enum import StrEnum

from .vm import Action, ExecutionResult, execute, validate_genome
from .world import World, UnknownEntityError, OutOfBoundsError, _require_int

# Север сверху; x растёт вправо, y вниз.
DIRECTIONS = ((0, -1), (1, -1), (1, 0), (1, 1),
              (0, 1), (-1, 1), (-1, 0), (-1, -1))


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

    def __post_init__(self):
        # 003 хранит утверждённые параметры, не предлагает иной баланс.
        for field in fields(self):
            value = getattr(self, field.name)
            _require_int(value, field.name)
            if value != field.default:
                raise ValueError(f"{field.name}: иной баланс пока не принят")


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


class BiologicalWorld:
    def __init__(self, width: int, height: int, *, seed: int, reserve: int,
                 config: RulesConfig | None = None):
        self._nonnegative(reserve, "reserve")
        if config is not None and type(config) is not RulesConfig:
            raise TypeError("config должен быть RulesConfig")
        self._config = config if config is not None else RulesConfig()
        self._world = World(width, height, seed=seed)
        self._reserve = reserve
        self._budget = reserve
        self._entities: dict[int, ResourceEntity] = {}
        self._stepping = False

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
        entity = self._organism(entity_id)
        c = self.config
        if action in (Action.TURN_LEFT, Action.TURN_RIGHT, Action.TURN_RANDOM):
            if entity.energy < c.turn_cost:
                return False
            if action == Action.TURN_RANDOM:
                direction = self.rng.randrange(len(DIRECTIONS))
            else:
                direction = (entity.direction + (-1 if action == Action.TURN_LEFT else 1)) % len(DIRECTIONS)
            entity = self._spend(entity, c.turn_cost)
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
            if not blocked:
                entity = self.move(entity.id, *self._front_position(entity))
            self._spend(entity, cost)
            return not blocked
        if action == Action.EAT:
            if entity.energy < c.eat_cost:
                return False
            target, wall = self._target(entity)
            entity = self._spend(entity, c.eat_cost)
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

    def step(self) -> tuple[tuple[int, ExecutionResult], ...]:
        if self._stepping:
            raise RuntimeError("Вложенный биологический step запрещён")
        self._stepping = True
        try:
            order = [e.id for e in self.entities if e.kind == Kind.ORGANISM]
            self.rng.shuffle(order)
            results = []

            def update(_, position):
                entity = self._organism(position.id)
                adapter = OrganismAdapter(self, entity.id)
                result = execute(entity.genome, sensors=adapter, perform=adapter.perform, rng=self.rng)
                results.append((entity.id, result))

            self._world.step(update, order=order)
            return tuple(results)
        finally:
            self._stepping = False


class OrganismAdapter:
    def __init__(self, world: BiologicalWorld, entity_id: int):
        world._organism(entity_id)
        self._world = world
        self._id = entity_id

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
