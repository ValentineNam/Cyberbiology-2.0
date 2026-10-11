"""Реактивная управляющая VM без состояния мира и игровых механик."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from random import Random
from typing import Protocol

GENOME_LENGTH = 32
INSTRUCTION_BUDGET = 16


class Action(IntEnum):
    MOVE = 1
    TURN_LEFT = 2
    TURN_RIGHT = 3
    TURN_RANDOM = 4
    EAT = 5
    PHOTOSYNTHESIS = 6
    MINERALS_TO_ENERGY = 7
    ENERGY_TO_MINERALS = 8


class Sensors(Protocol):
    def front(self) -> int: ...

    def hungry(self) -> bool: ...


class StopReason(StrEnum):
    TERMINAL_ACTION = "terminal_action"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ADAPTER_STOPPED = "adapter_stopped"


@dataclass(frozen=True)
class ExecutionResult:
    instructions_executed: int
    reason: StopReason
    last_pc: int


def validate_genome(genome: Sequence[int]) -> tuple[int, ...]:
    """Проверить всю ленту до эффектов; вернуть независимый снимок."""
    if not isinstance(genome, Sequence):
        raise TypeError("Геном должен быть последовательностью целых чисел")
    tape = tuple(genome)
    if len(tape) != GENOME_LENGTH:
        raise ValueError("Геном должен содержать ровно 32 ячейки")
    for value in tape:
        if type(value) is not int:
            raise TypeError("Ячейка должна быть целым числом (не bool)")
        if not 0 <= value <= 31:
            raise ValueError("Значение ячейки должно быть от 0 до 31")
    return tape


def execute(
    genome: Sequence[int],
    *,
    sensors: Sensors,
    perform: Callable[[Action], bool],
    rng: Random,
    is_active: Callable[[], bool] | None = None,
) -> ExecutionResult:
    """Исполнить один вызов. Исключения адаптеров не перехватываются."""
    tape = validate_genome(genome)
    pc = 0
    for count in range(1, INSTRUCTION_BUDGET + 1):
        last_pc = pc
        opcode = tape[pc]
        if 1 <= opcode <= 8:
            success = perform(Action(opcode))
            if type(success) is not bool:
                raise TypeError("Исполнитель должен вернуть bool")
            if is_active is not None:
                active = is_active()
                if type(active) is not bool:
                    raise TypeError("is_active должен вернуть bool")
                if not active:
                    return ExecutionResult(count, StopReason.ADAPTER_STOPPED, last_pc)
            if opcode in (1, 5, 6, 7, 8):
                return ExecutionResult(count, StopReason.TERMINAL_ACTION, last_pc)
            offset = 1
        elif opcode in (9, 10):
            if opcode == 9:
                category = sensors.front()
                if type(category) is not int:
                    raise TypeError("Категория впереди должна быть целым числом")
                if not 0 <= category <= 5:
                    raise ValueError("Категория впереди должна быть от 0 до 5")
            else:
                hungry = sensors.hungry()
                if type(hungry) is not bool:
                    raise TypeError("Сенсор голода должен вернуть bool")
                category = int(hungry)
            offset = max(1, tape[(pc + 1 + category) % GENOME_LENGTH])
        elif opcode == 11:
            limit = max(1, tape[(pc + 1) % GENOME_LENGTH])
            offset = rng.randint(1, limit)
        else:
            offset = 1
        pc = (pc + offset) % GENOME_LENGTH
    return ExecutionResult(INSTRUCTION_BUDGET, StopReason.BUDGET_EXHAUSTED, last_pc)
