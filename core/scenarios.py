"""Небольшие явные исходные условия, без изменения биологических правил."""

from dataclasses import dataclass

from .biology import BiologicalWorld, Kind, RulesConfig


def tape(*values: int) -> tuple[int, ...]:
    return tuple(values) + (0,) * (32 - len(values))


@dataclass(frozen=True)
class InitialEntity:
    kind: Kind
    x: int
    y: int
    energy: int
    minerals: int
    genome: tuple[int, ...] | None = None
    direction: int = 0
    profile: str | None = None


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    expected_behavior: str
    width: int
    height: int
    budget: int
    entities: tuple[InitialEntity, ...]

    def build(self, *, seed: int, config: RulesConfig | None = None,
              record_deaths: bool = False) -> BiologicalWorld:
        world = BiologicalWorld(self.width, self.height, seed=seed, reserve=self.budget,
                                config=config, record_deaths=record_deaths)
        for entity in self.entities:
            if entity.kind == Kind.ORGANISM:
                world.create_organism(entity.x, entity.y, entity.genome, energy=entity.energy,
                                      minerals=entity.minerals, direction=entity.direction)
            elif entity.kind == Kind.PLANT:
                world.create_plant(entity.x, entity.y, entity.profile,
                                   energy=entity.energy, minerals=entity.minerals)
            else:
                world.create_remains(entity.x, entity.y, energy=entity.energy, minerals=entity.minerals)
        return world


SCENARIOS = {
    'nop': Scenario(
        'nop', 'Контроль метаболизма: один неподвижный организм с лентой NOP.',
        'Расходует 1 E за ход, не добывает ресурсы. При E=20 ожидается смерть от метаболизма в тик 20.',
        7, 3, 1000,
        (InitialEntity(Kind.ORGANISM, 3, 1, 20, 64, tape(0)),)),
    'photosynthesis': Scenario(
        'photosynthesis', 'Один неподвижный организм с PHOTOSYNTHESIS.',
        'Берёт энергию из закрытого резерва после метаболизма. Возможны рождения при порогах; возраст и минералы ограничивают жизнь.',
        7, 3, 5000,
        (InitialEntity(Kind.ORGANISM, 3, 1, 256, 64, tape(6)),)),
    'branching': Scenario(
        'branching', 'IF_HUNGRY выбирает фотосинтез при голоде, иначе ENERGY_TO_MINERALS.',
        'В адресе 0: IF_HUNGRY; сытый переходит на 3 (минерализация), голодный на 4 (фотосинтез). Конверсия ограничена ёмкостью и запасами; программа не гарантирует выживания.',
        7, 3, 5000,
        (InitialEntity(Kind.ORGANISM, 3, 1, 256, 64, tape(10, 3, 4, 8, 6)),)),
    'mixed': Scenario(
        'mixed', 'Точный исходный смешанный сценарий задачи 004: добытчик и три профиля растений.',
        'Растения растут из общего резерва и размножаются. Добытчик также зависит от резерва, возраста и минералов; конкуренция не гарантирует сохранения организмов.',
        17, 11, 30000,
        (InitialEntity(Kind.ORGANISM, 8, 5, 900, 100, tape(6)),
         InitialEntity(Kind.PLANT, 1, 1, 1500, 1500, profile='tree'),
         InitialEntity(Kind.PLANT, 5, 1, 750, 750, profile='bush'),
         InitialEntity(Kind.PLANT, 12, 1, 190, 190, profile='grass'))),
}
