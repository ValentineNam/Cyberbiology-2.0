"""Контрольные программы управляющей VM с подставными адаптерами."""

from random import Random
import unittest
from unittest.mock import Mock

from core.vm import Action, StopReason, execute


class VMTests(unittest.TestCase):
    def setUp(self):
        self.sensors = Mock()
        self.sensors.front.return_value = 0
        self.sensors.hungry.return_value = False
        self.perform = Mock(return_value=True)
        self.rng = Random(42)

    def run_tape(self, tape):
        return execute(tape, sensors=self.sensors, perform=self.perform, rng=self.rng)

    def tape(self, *values):
        return list(values) + [0] * (32 - len(values))

    def test_every_call_restarts_at_zero(self):
        tape = self.tape(2, 1)
        for _ in range(2):
            result = self.run_tape(tape)
            self.assertEqual((result.instructions_executed, result.last_pc), (2, 1))
        self.assertEqual([c.args[0] for c in self.perform.call_args_list],
                         [Action.TURN_LEFT, Action.MOVE] * 2)

    def test_budget_and_all_nop_values(self):
        for opcode in [0, *range(12, 32)]:
            with self.subTest(opcode=opcode):
                result = self.run_tape([opcode] * 32)
                self.assertEqual((result.instructions_executed, result.last_pc), (16, 15))
                self.assertEqual(result.reason, StopReason.BUDGET_EXHAUSTED)
        self.perform.assert_not_called()
        self.sensors.front.assert_not_called()
        self.sensors.hungry.assert_not_called()

    def test_each_terminal_action_stops_on_success_and_failure(self):
        for opcode in (1, 5, 6, 7, 8):
            for success in (True, False):
                with self.subTest(opcode=opcode, success=success):
                    self.perform.reset_mock()
                    self.perform.return_value = success
                    result = self.run_tape(self.tape(opcode, 2, 1))
                    self.assertEqual((result.instructions_executed, result.last_pc), (1, 0))
                    self.assertEqual(result.reason, StopReason.TERMINAL_ACTION)
                    self.perform.assert_called_once_with(Action(opcode))

    def test_all_turns_continue_even_on_failure(self):
        for success in (True, False):
            self.perform.reset_mock()
            self.perform.return_value = success
            result = self.run_tape(self.tape(2, 3, 4, 1))
            self.assertEqual((result.instructions_executed, result.last_pc), (4, 3))
            self.assertEqual([c.args[0] for c in self.perform.call_args_list],
                             [Action.TURN_LEFT, Action.TURN_RIGHT, Action.TURN_RANDOM, Action.MOVE])

    def test_front_categories_select_exact_operand(self):
        for category in range(6):
            with self.subTest(category=category):
                tape = self.tape(9, 12, 13, 14, 15, 16, 17)
                tape[12 + category] = 1
                self.sensors.front.return_value = category
                result = self.run_tape(tape)
                self.assertEqual((result.instructions_executed, result.last_pc), (2, 12 + category))

    def test_both_hunger_outcomes(self):
        for hungry, target in ((False, 12), (True, 13)):
            tape = self.tape(10, 12, 13)
            tape[target] = 1
            self.sensors.hungry.return_value = hungry
            result = self.run_tape(tape)
            self.assertEqual((result.instructions_executed, result.last_pc), (2, target))

    def test_wrapped_front_operand_and_target_without_extra_increment(self):
        # 0 → 30; IF_FRONT wall читает (30+1+5)%32=4, переход 30+5→3.
        tape = self.tape(9, 30)
        tape[30], tape[4], tape[3] = 9, 5, 1
        self.sensors.front.side_effect = [0, 5]
        result = self.run_tape(tape)
        self.assertEqual((result.instructions_executed, result.last_pc), (3, 3))

    def test_wrapped_hunger_operand_and_target(self):
        tape = self.tape(10, 31)
        tape[31], tape[2] = 10, 1
        # В адресе 31 hungry=True читает адрес 1 (31), переход →30.
        tape[30] = 1
        self.sensors.hungry.side_effect = [False, True]
        result = self.run_tape(tape)
        self.assertEqual((result.instructions_executed, result.last_pc), (3, 30))

    def test_zero_conditional_operand_means_one_and_operand_is_executed(self):
        for opcode in (9, 10):
            tape = self.tape(opcode, 0, 1)
            result = self.run_tape(tape)
            self.assertEqual((result.instructions_executed, result.last_pc), (3, 2))
        # Операнд 2 становится TURN_LEFT, а не автоматически пропускается.
        self.perform.reset_mock()
        self.sensors.front.return_value = 1
        result = self.run_tape(self.tape(9, 2, 1))
        self.assertEqual((result.instructions_executed, result.last_pc), (3, 2))
        self.assertEqual([c.args[0] for c in self.perform.call_args_list],
                         [Action.TURN_LEFT, Action.MOVE])

    def test_large_values_are_numeric_operands(self):
        for value in range(12, 32):
            tape = self.tape(9, value)
            tape[value] = 1
            result = self.run_tape(tape)
            self.assertEqual((result.instructions_executed, result.last_pc), (2, value))

    def test_random_jump_reproduces_same_rng_state(self):
        tape = self.tape(11, 31)
        for i in range(2, 32):
            tape[i] = 1
        self.rng.random()  # Проверяем продолжение состояния, а не только seed.
        state = self.rng.getstate()
        first = self.run_tape(tape)
        end_state = self.rng.getstate()
        self.rng.setstate(state)
        self.assertEqual(self.run_tape(tape), first)
        self.assertEqual(self.rng.getstate(), end_state)

    def test_random_bounds_and_wrapped_operand(self):
        # Переход к 31; JUMP_RANDOM читает адрес 0 (9); 31+2→1 (MOVE).
        tape = self.tape(9, 1, 31)
        tape[31] = 11
        self.sensors.front.return_value = 1
        rng = Mock()
        rng.randint.return_value = 2
        result = execute(tape, sensors=self.sensors, perform=self.perform, rng=rng)
        rng.randint.assert_called_once_with(1, 9)
        self.assertEqual((result.instructions_executed, result.last_pc), (3, 1))
        # Нижняя и верхняя границы приводят ровно к выбранному адресу.
        for offset in (1, 31):
            tape = self.tape(11, 31)
            tape[offset] = 1
            limit = tape[1]
            rng.randint.reset_mock()
            rng.randint.return_value = offset
            result = execute(tape, sensors=self.sensors, perform=self.perform, rng=rng)
            rng.randint.assert_called_once_with(1, limit)
            self.assertEqual(result.last_pc, offset)

    def test_zero_random_operand_uses_limit_one(self):
        tape = self.tape(11, 0, 1)
        result = self.run_tape(tape)
        self.assertEqual((result.instructions_executed, result.last_pc), (3, 2))
        reference = Random(42)
        reference.randint(1, 1)
        self.assertEqual(self.rng.getstate(), reference.getstate())

    def test_terminal_action_on_last_budget_unit(self):
        tape = self.tape(*([0] * 15), 1, 2)
        result = self.run_tape(tape)
        self.assertEqual((result.instructions_executed, result.last_pc), (16, 15))
        self.assertEqual(result.reason, StopReason.TERMINAL_ACTION)
        self.perform.assert_called_once_with(Action.MOVE)

    def test_random_lower_bound_executes_operand_as_nop(self):
        rng = Mock()
        rng.randint.return_value = 1
        result = execute(self.tape(11, 31, 1), sensors=self.sensors,
                         perform=self.perform, rng=rng)
        rng.randint.assert_called_once_with(1, 31)
        self.assertEqual((result.instructions_executed, result.last_pc), (3, 2))

    def test_genome_is_unchanged(self):
        tape = self.tape(11, 31, 2, 1)
        before = tape.copy()
        self.run_tape(tape)
        self.assertEqual(tape, before)
        self.run_tape(tuple(tape))
        self.assertEqual(tape, before)

    def test_invalid_genomes_fail_before_any_effects(self):
        cases = [(None, TypeError), ({}, TypeError), ([], ValueError),
                 ([0] * 31, ValueError), ([0] * 33, ValueError)]
        for value, error in ((True, TypeError), (1.0, TypeError), ('1', TypeError),
                             (None, TypeError), (-1, ValueError), (32, ValueError)):
            # Невалидный хвост обязан быть замечен до JUMP_RANDOM в начале.
            cases.append(([11, 31] + [0] * 29 + [value], error))
        for tape, error in cases:
            with self.subTest(tape=tape):
                before = self.rng.getstate()
                with self.assertRaises(error):
                    self.run_tape(tape)
                self.assertEqual(self.rng.getstate(), before)
        self.perform.assert_not_called()
        self.sensors.front.assert_not_called()
        self.sensors.hungry.assert_not_called()

    def test_adapter_exceptions_propagate_and_stop(self):
        for opcode, adapter in ((9, self.sensors.front), (10, self.sensors.hungry),
                                (2, self.perform), (1, self.perform)):
            with self.subTest(opcode=opcode):
                self.perform.reset_mock()
                failure = RuntimeError('Ошибка адаптера')
                adapter.side_effect = failure
                with self.assertRaises(RuntimeError) as caught:
                    self.run_tape(self.tape(opcode, 1))
                self.assertIs(caught.exception, failure)
                self.assertEqual(self.perform.call_count, int(opcode in (1, 2)))
                adapter.side_effect = None

    def test_invalid_adapter_results_are_errors(self):
        for value, error in ((True, TypeError), (6, ValueError), (-1, ValueError)):
            self.sensors.front.return_value = value
            with self.assertRaises(error):
                self.run_tape(self.tape(9, 1))
        self.sensors.hungry.return_value = 1
        with self.assertRaises(TypeError):
            self.run_tape(self.tape(10, 1))
        self.perform.return_value = None
        with self.assertRaises(TypeError):
            self.run_tape(self.tape(1))


if __name__ == '__main__':
    unittest.main()
