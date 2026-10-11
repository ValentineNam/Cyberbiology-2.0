"""Запуск: python3 -m core.biology_example. Пять тиков ресурсных действий с текущими правилами жизни."""

from .biology import BiologicalWorld


def main() -> None:
    world = BiologicalWorld(17, 11, seed=42, reserve=4096)
    world.create_organism(3, 5, [6] + [0] * 31)  # Добытчик из резерва.
    world.create_organism(8, 5, [4, 1] + [0] * 30)  # Случайный поворот и шаг.
    world.create_organism(12, 5, [5] + [0] * 31)  # Потребитель.
    world.create_plant(12, 4, 'grass', energy=150, minerals=40)
    world.create_remains(0, 0, energy=0, minerals=20)
    for _ in range(5):
        results = world.step()
        stocks = [(e.id, e.energy, e.minerals) for e in world.entities]
        print(f"tick={world.tick}, порядок={[i for i, _ in results]}, "
              f"резерв={world.reserve}, R={world.total_resources}, запасы={stocks}")
    print("Пример показывает действия и смерть; для рождения и трёх растений: python3 -m core.lifecycle_example.")


if __name__ == '__main__':
    main()
