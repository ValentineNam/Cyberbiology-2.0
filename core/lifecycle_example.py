"""Ограниченная демонстрация и воспроизводимый длительный прогон без UI."""

import argparse

from .biology import BiologicalWorld


def build_world() -> BiologicalWorld:
    world = BiologicalWorld(17, 11, seed=42, reserve=30000)
    world.create_organism(8, 5, [6] + [0] * 31, energy=900, minerals=100)
    for x, profile, stock in ((1, 'tree', 1500), (5, 'bush', 750), (12, 'grass', 190)):
        world.create_plant(x, 1, profile, energy=stock, minerals=stock)
    return world


def run(ticks: int, *, report_every: int = 0) -> BiologicalWorld:
    world = build_world()
    for _ in range(ticks):
        world.step()
        if world.total_resources != world.initial_budget or world.reserve < 0:
            raise AssertionError(f"Нарушен ресурсный бюджет в тик {world.tick}")
        if any(e.energy < 0 or e.minerals < 0 for e in world.entities):
            raise AssertionError(f"Отрицательные ресурсы в тик {world.tick}")
        if report_every and world.tick % report_every == 0:
            print(f"tick={world.tick}, резерв={world.reserve}, R={world.total_resources}, "
                  f"метрики={world.metrics}")
    return world


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--long', action='store_true', help='Два одинаковых прогона по 2000 тиков')
    args = parser.parse_args()
    if args.long:
        first, second = run(2000), run(2000)
        def snapshot(world):
            return (world.entities, world.reserve, world.tick, world.next_id,
                    world.metrics, world.rng.getstate())
        if snapshot(first) != snapshot(second):
            raise AssertionError('Повторение не совпало')
        print(f"Два прогона совпали: tick={first.tick}, резерв={first.reserve}, "
              f"R={first.total_resources}, метрики={first.metrics}")
    else:
        run(140, report_every=10)
    print('Этот сценарий не доказывает устойчивую эволюцию или качество баланса.')


if __name__ == '__main__':
    main()
