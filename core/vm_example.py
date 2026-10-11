"""Запуск: python3 -m core.vm_example. Подставные адаптеры без механик."""

from random import Random

from .vm import Action, execute


class ExampleSensors:
    def front(self) -> int:
        return 0  # empty

    def hungry(self) -> bool:
        return False


def main() -> None:
    # IF_FRONT → адрес 4 → TURN_LEFT → MOVE (подставной отказ).
    genome = [9, 4, 0, 0, 2, 1] + [0] * 26
    actions = []

    def perform(action: Action) -> bool:
        actions.append(action.name)
        return action != Action.MOVE

    result = execute(genome, sensors=ExampleSensors(), perform=perform, rng=Random(42))
    print(f"Действия: {actions}")
    print(f"Инструкций: {result.instructions_executed}, "
          f"причина: {result.reason.value}, последний PC: {result.last_pc}")


if __name__ == '__main__':
    main()
