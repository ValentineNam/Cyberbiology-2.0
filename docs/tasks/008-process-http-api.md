# Задача 008: отдельный процесс и локальный HTTP API

Статус: **done**. FastAPI и multiprocessing spawn приняты пользователем. VM и биологические правила не изменяются. UI из исходной строки 008 остаётся отдельной будущей работой.

## Границы

Процесс симуляции единолично владеет SimulationRuntime и его миром/RNG. Цикл вызывает advance только в running. API владеет ограниченными каналами запросов/ответов, UUID correlation_id и ожиданием с дедлайном; команду не повторяет автоматически. Сопоставление ответов не использует RNG мира. Процесс создаётся в lifespan, не при импорте; shutdown сначала запрашивается штатно, затем bounded join и terminate/kill только как fallback.

Частота по умолчанию 10 TPS, целое 1–100. Планирование через monotonic: следующий advance не раньше периода, без накопления пропущенных тиков и бесконечного catch-up. Команды исполняются между тиками. Успешный pause отвечает после применения; до start/step дальнейших тиков нет. Ошибка тика сохраняет failed, процесс продолжает принимать status/reset; авария процесса — недоступность, не paused.

## HTTP и ограничения API

GET /api/status, /api/field, /api/entities/{id}; POST /api/start, /api/pause, /api/step, /api/reset, /api/speed. Изменяющий запрос требует expected_run_id; reset — также scenario, seed и полный config; speed — ticks_per_second. Все ответы состояния содержат run_id/status/tick/completed. Клиент не получает типы внутренних исключений, сообщения или traceback; они логируются на сервере.

Только 127.0.0.1, один Uvicorn worker, без reload; многопроцессный Uvicorn запуск не поддерживается. Без CORS, WebSocket, авторизации, БД, облака и frontend.

Консервативные ограничения именно API: сторона мира до 64, площадь до 4096, до 64 начальных сущностей, тело JSON до 16 KiB, seed в диапазоне signed 64-bit, ID сущности 1..2^63-1. Только именованные сценарии 006, без пользовательских геномов/размеров в HTTP. Конфигурация строго проверяется до отправки команды. Два IPC Queue ёмкостью 16; не более 16 ожидающих HTTP-команд, один обмен одновременно; обычный дедлайн 3 с, запуск 10 с, штатное завершение 3 с + join 2 с, fallback terminate/kill по 2 с. Параметры канала не являются правилами биологии.

Ошибки: неверный ввод 422/413, старый run_id/неверное состояние 409, заполнение/недоступность 503, timeout 504. Если запрос уже передан в IPC, исход timeout неизвестен (outcome=unknown), даже если команда ещё ждёт; до передачи — not_submitted. correlation_id возвращается для диагностики. После неизвестного исхода читать status и сверять run_id/tick; не повторять мутацию автоматически.

## Приёмка

- P01: HTTP контракты, строгое отклонение неверного ввода до IPC, старый run_id; размеры/конфигурация/тело ограничены.
- P02: реальный дочерний spawn; start→рост tick→pause→стабильный tick; step ровно один тик; speed меняет только управление.
- P03: reset новый run_id и paused/tick=0; failed доступен для status/reset, ошибка не раскрывает исключения.
- P04: очереди/ожидания ограничены; заполнение, timeout и смерть процесса дают объяснимые ответы без зависания и без автоматического повтора; поздние ответы сопоставляются по correlation_id.
- P05: lifespan создаёт/штатно завершает процесс; импорт не запускает его; fallback ограничен по времени.
- P06: HTTP smoke status→step→start→pause→field→entity→reset с реальным Uvicorn, затем сервер и дочерний процесс остановлены. Условные ожидания с дедлайном, без точного TPS.
- P07: весь unittest, воспроизводимые зависимости и git diff --check. F11 завершать только в HTTP/процессном объёме; F12 не завершать без UI.

Официальные источники проверены до реализации: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [FastAPI request body](https://fastapi.tiangolo.com/tutorial/body/), [Python multiprocessing](https://docs.python.org/3.13/library/multiprocessing.html), [Uvicorn settings](https://www.uvicorn.org/settings/), [Pydantic strict mode](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/).

## Фактическая приёмка

[API](../../backend/app.py), [IPC](../../backend/service.py), [worker](../../backend/worker.py), [14 проверок](../../tests/test_process_api.py), [HTTP smoke](../../scripts/smoke_http.py). P01–P05 покрыты реальными spawn и ASGI HTTP-тестами, включая bounded fallback зависшего процесса. Частоты 1/100/10 в paused дают те же биологические результаты пошагового сценария; правила и VM не изменены. ValueError внутри тика отдельно проверен как failed/500, а не 422. Перед реализацией прочитаны официальные источники выше.

Python 3.13.0/macOS arm64. FastAPI 0.143.0, Uvicorn 0.54.0; прямые версии в requirements.in, весь граф и SHA-256 wheel в requirements.lock. Реально выполнены установка, загрузка wheel, принудительная offline переустановка с --require-hashes и pip check. Команды установки и сервера — в README.

`.venv/bin/python -m unittest discover -s tests -q`: 124 теста, OK (110 прежних + 14 новых). `.venv/bin/python scripts/smoke_http.py`: настоящий Uvicorn и HTTP, status=0 → step=1 → running=2 → pause=2 стабилен → field=4 сущности → entity=1/32 ячейки → reset=0/paused/новый run_id. Сервер и процесс завершены штатно, лог в /tmp/cyberbiology-http-smoke.log. Доступ к сокету потребовал выполнения smoke вне сетевых ограничений песочницы. Runtime-пример также выполнен. git diff --check без ошибок.

F11 завершена в принятом HTTP-объёме. F12 остаётся planned, UI нет. Тайм-аут после передачи имеет неизвестный исход, автоматического повтора нет; ручные step не дедуплицируются. GET status возвращает текущие scenario/seed/configuration для подготовки reset. Настроенная скорость сохраняется при reset. Тело читается не более 3 с. Многопроцессный Uvicorn/reload отклоняется до spawn. Коммит не создан.

Выявленный дефект 008: сохранённые ссылки на закрытые Queue оставляли IPC-семафоры до завершения Uvicorn сигналом. Исправлены освобождение ссылок и bounded ожидание feeder до 2 с. Отдельная проверка Queue/feeder и smoke без leaked semaphore подтверждают исправление.
