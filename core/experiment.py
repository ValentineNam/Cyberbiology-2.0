"""CLI ограниченных экспериментов: python3 -m core.experiment --help."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import platform
import tempfile

from .biology import BiologicalWorld, Kind, RulesConfig
from .scenarios import SCENARIOS
from .world import _require_int
from .vm import GENOME_LENGTH, INSTRUCTION_BUDGET

RULES_VERSION = '004-v1'
REPORT_VERSION = 1


@dataclass
class ExperimentResult:
    world: BiologicalWorld
    report: dict | None


def check_invariants(world: BiologicalWorld) -> None:
    if world.total_resources != world.initial_budget:
        raise AssertionError(f"Нарушен R в тик {world.tick}")
    if world.reserve < 0 or any(e.energy < 0 or e.minerals < 0 for e in world.entities):
        raise AssertionError(f"Отрицательные ресурсы в тик {world.tick}")


def observe(world: BiologicalWorld) -> dict:
    generations = [e.generation for e in world.entities if e.kind == Kind.ORGANISM]
    return {'tick': world.tick, **world.metrics, 'reserve': world.reserve,
            'R': world.total_resources, 'max_generation': max(generations, default=None)}


def run_experiment(*, scenario: str, seed: int, ticks: int, interval: int,
                   config: RulesConfig | None = None, collect_report: bool = True) -> ExperimentResult:
    for name, value in (('seed', seed), ('ticks', ticks), ('interval', interval)):
        _require_int(value, name)
    if ticks < 0:
        raise ValueError('ticks должен быть неотрицательным')
    if interval <= 0:
        raise ValueError('interval должен быть положительным')
    if type(scenario) is not str or scenario not in SCENARIOS:
        raise ValueError(f"Неизвестный сценарий: {scenario!r}")
    if type(collect_report) is not bool:
        raise TypeError('collect_report должен быть bool')
    definition = SCENARIOS[scenario]
    world = definition.build(seed=seed, config=config, record_deaths=collect_report)
    check_invariants(world)
    initial = observe(world)
    history = [initial] if collect_report else []
    extinction_tick = 0 if initial['organisms'] == 0 else None
    max_generation = initial['max_generation']
    for _ in range(ticks):
        world.step()
        # Эти проверки не зависят от интервала истории.
        check_invariants(world)
        current = observe(world)
        if extinction_tick is None and current['organisms'] == 0:
            extinction_tick = world.tick
        if current['max_generation'] is not None:
            max_generation = max(max_generation or 0, current['max_generation'])
        if collect_report and (world.tick % interval == 0 or world.tick == ticks):
            history.append(current)
    if not collect_report:
        return ExperimentResult(world, None)
    deaths = [asdict(record) for record in world.death_records]
    reason_counts = Counter(reason for record in world.death_records for reason in record.reasons)
    context_counts = Counter(record.context.value for record in world.death_records)
    report = {
        'report_version': REPORT_VERSION, 'rules_version': RULES_VERSION,
        'python_version': platform.python_version(), 'seed': seed,
        'configuration': {'world': {'width': world.width, 'height': world.height,
                                     'initial_budget': world.initial_budget},
                          'rules': asdict(world.config),
                          'vm': {'genome_length': GENOME_LENGTH, 'instruction_budget': INSTRUCTION_BUDGET}},
        'scenario': asdict(definition),
        'requested_ticks': ticks, 'executed_ticks': world.tick, 'metrics_interval': interval,
        'history': history, 'final': history[-1].copy(),
        'diagnostics': {'organism_extinction_tick': extinction_tick,
                        'max_generation_observed': max_generation,
                        'death_reason_counts': dict(sorted(reason_counts.items())),
                        'death_context_counts': dict(sorted(context_counts.items())),
                        'deaths': deaths},
    }
    return ExperimentResult(world, report)


def write_report(report: dict, path: Path) -> None:
    """JSON в той же папке, затем атомарная замена итогового файла."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.experiment-', suffix='.json', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _nonnegative(text: str) -> int:
    try:
        value = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError('нужно целое число') from error
    if value < 0:
        raise argparse.ArgumentTypeError('нужно неотрицательное число')
    return value


def _positive(text: str) -> int:
    value = _nonnegative(text)
    if value == 0:
        raise argparse.ArgumentTypeError('нужно положительное число')
    return value


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, required=True, help='Явный seed RNG мира')
    parser.add_argument('--scenario', choices=SCENARIOS, required=True, help='Готовый сценарий')
    parser.add_argument('--ticks', type=_nonnegative, required=True, help='Число тиков, включая период после вымирания')
    parser.add_argument('--interval', type=_positive, required=True, help='Интервал записи метрик')
    parser.add_argument('--output', type=Path, required=True, help='Итоговый JSON; папка должна существовать')
    args = parser.parse_args(argv)
    if not args.output.parent.is_dir() or args.output.is_dir():
        parser.error('путь отчёта должен указывать файл в существующей папке')
    try:
        result = run_experiment(scenario=args.scenario, seed=args.seed, ticks=args.ticks, interval=args.interval)
        write_report(result.report, args.output)
    except OSError as error:
        parser.error(f'не удалось записать отчёт: {error}')
    print(f"Сценарий {args.scenario}, seed={args.seed}, тиков={result.world.tick}, "
          f"R={result.world.total_resources}, отчёт: {args.output}")


if __name__ == '__main__':
    main()
