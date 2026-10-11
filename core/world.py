"""Независимый мир без игровых механик и транспорта."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random


class OutOfBoundsError(IndexError):
    """Координата находится вне мира."""


class OccupiedCellError(ValueError):
    """Целевая клетка занята другой сущностью."""


class UnknownEntityError(KeyError):
    """Сущность с указанным ID не существует."""


@dataclass(frozen=True)
class Entity:
    """Неизменяемый снимок технической сущности."""

    id: int
    x: int
    y: int


def _require_int(value: int, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} должен быть целым числом (не bool)")


class World:
    def __init__(self, width: int, height: int, *, seed: int) -> None:
        for name, value in (("width", width), ("height", height)):
            _require_int(value, name)
            if value <= 0:
                raise ValueError(f"{name} должен быть положительным")
        _require_int(seed, "seed")
        self._width = width
        self._height = height
        self._tick = 0
        self._next_id = 1
        self._rng = Random(seed)
        self._grid: list[list[int | None]] = [
            [None] * width for _ in range(height)
        ]
        self._entities: dict[int, Entity] = {}
        self._stepping = False

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def next_id(self) -> int:
        return self._next_id

    @property
    def rng(self) -> Random:
        """Единственный источник случайных выборов для этого мира."""
        return self._rng

    @property
    def entities(self) -> tuple[Entity, ...]:
        """Снимок реестра в возрастающем порядке ID."""
        return tuple(self._entities[i] for i in sorted(self._entities))

    def _check_position(self, x: int, y: int) -> None:
        _require_int(x, "x")
        _require_int(y, "y")
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise OutOfBoundsError(f"Координата ({x}, {y}) вне мира")

    def get_at(self, x: int, y: int) -> Entity | None:
        """Пустота — None; внешняя координата — OutOfBoundsError."""
        self._check_position(x, y)
        entity_id = self._grid[y][x]
        return None if entity_id is None else self._entities[entity_id]

    def get(self, entity_id: int) -> Entity | None:
        _require_int(entity_id, "entity_id")
        return self._entities.get(entity_id)

    def place(self, x: int, y: int) -> Entity:
        self._check_position(x, y)
        if self._grid[y][x] is not None:
            raise OccupiedCellError(f"Клетка ({x}, {y}) занята")
        entity = Entity(self._next_id, x, y)
        self._entities[entity.id] = entity
        self._grid[y][x] = entity.id
        self._next_id += 1
        return entity

    def _require_entity(self, entity_id: int) -> Entity:
        entity = self.get(entity_id)
        if entity is None:
            raise UnknownEntityError(entity_id)
        return entity

    def remove(self, entity_id: int) -> Entity:
        entity = self._require_entity(entity_id)
        self._grid[entity.y][entity.x] = None
        del self._entities[entity_id]
        return entity

    def move(self, entity_id: int, x: int, y: int) -> Entity:
        entity = self._require_entity(entity_id)
        self._check_position(x, y)
        occupant = self._grid[y][x]
        if occupant is not None and occupant != entity_id:
            raise OccupiedCellError(f"Клетка ({x}, {y}) занята")
        moved = Entity(entity_id, x, y)
        self._grid[entity.y][entity.x] = None
        self._grid[y][x] = entity_id
        self._entities[entity_id] = moved
        return moved

    def step(
        self, update: Callable[["World", Entity], None] | None = None,
        *, order: Sequence[int] | None = None,
    ) -> None:
        """Обновить начальные ID один раз. Ошибка обработчика не откатывает мир."""
        if self._stepping:
            raise RuntimeError("Вложенный step запрещён")
        if update is not None and not callable(update):
            raise TypeError("update должен быть вызываемым обработчиком или None")
        participants = sorted(self._entities) if order is None else list(order)
        for entity_id in participants:
            _require_int(entity_id, "entity_id")
        if len(set(participants)) != len(participants):
            raise ValueError("Порядок шага содержит повторные ID")
        for entity_id in participants:
            self._require_entity(entity_id)
        self._stepping = True
        try:
            for entity_id in participants:
                entity = self._entities.get(entity_id)
                if entity is not None and update is not None:
                    update(self, entity)
            self._tick += 1
        finally:
            self._stepping = False
