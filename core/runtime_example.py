"""Запуск: python3 -m core.runtime_example, без ожиданий реального времени."""

from .biology import RulesConfig
from .runtime import SimulationRuntime


def main() -> None:
    runtime = SimulationRuntime(scenario='mixed', seed=42, config=RulesConfig())
    initial = runtime.status()
    run_id = initial['run_id']
    print(f"Создан: {initial['status']}, tick={initial['tick']}, run_id={run_id}")
    runtime.step(expected_run_id=run_id)
    runtime.start(expected_run_id=run_id)
    for _ in range(3):
        runtime.advance(expected_run_id=run_id)
    runtime.pause(expected_run_id=run_id)
    snapshot = runtime.field_snapshot(expected_run_id=run_id)
    print(f"После управления: {snapshot['status']}, tick={snapshot['tick']}, "
          f"R={snapshot['metrics']['R']}, сущностей={len(snapshot['entities'])}")
    detail = runtime.entity_details(1, expected_run_id=run_id)
    print(f"Организм 1: возраст={detail['entity']['age']}, поколение={detail['entity']['generation']}")
    reset = runtime.reset(scenario='mixed', seed=42, config=RulesConfig(), expected_run_id=run_id)
    print(f"Reset: {reset['status']}, tick={reset['tick']}, новый run_id={reset['run_id']}")


if __name__ == '__main__':
    main()
