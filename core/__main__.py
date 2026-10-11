"""Запуск: python3 -m core. Демонстрация планирования без игровых действий."""

from .world import World


def main() -> None:
    world = World(17, 11, seed=42)
    world.place(0, 0)
    world.place(16, 10)
    print(f"Мир {world.width}×{world.height}, сущности: {world.entities}")
    for _ in range(3):
        updated: list[int] = []
        world.step(lambda _, entity: updated.append(entity.id))
        print(f"tick={world.tick}, обновлены ID: {updated}")


if __name__ == "__main__":
    main()
