"""Реальный HTTP smoke с запуском и завершением Uvicorn и его дочернего процесса."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from time import monotonic, sleep
from urllib.request import Request, urlopen
from urllib.error import URLError

# При запуске файлом добавить корень репозитория для стандартного Python.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    base = 'http://127.0.0.1:8765'
    log_path = Path('/tmp/cyberbiology-http-smoke.log')
    def request(path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = Request(base+path, data=data, headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=2) as response:
            return json.load(response)
    with log_path.open('w') as log:
        server = subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:app',
                                   '--host','127.0.0.1','--port','8765','--workers','1'],
                                  cwd=ROOT,stdout=log,stderr=log)
        child_pid = None
        try:
            deadline=monotonic()+15
            while monotonic()<deadline:
                if server.poll() is not None:
                    raise AssertionError(log_path.read_text())
                try:
                    initial=request('/api/status')
                    break
                except URLError:
                    sleep(0.03)
            else:
                raise AssertionError('HTTP startup deadline')
            match=re.search(r'Simulation process started pid=(\d+)',log_path.read_text())
            if not match:
                raise AssertionError('Не найден PID процесса симуляции')
            child_pid=int(match.group(1))
            args={'expected_run_id':initial['run_id']}
            step=request('/api/step',args)
            assert step['tick']==initial['tick']+1
            request('/api/start',args)
            deadline=monotonic()+5
            while monotonic()<deadline:
                running=request('/api/status')
                if running['tick']>step['tick']:
                    break
                sleep(0.02)
            else:
                raise AssertionError('Advance deadline')
            paused=request('/api/pause',args)
            deadline=monotonic()+0.25
            while monotonic()<deadline:
                assert request('/api/status')['tick']==paused['tick']
                sleep(0.02)
            field=request('/api/field')
            entity_id=next(e['id'] for e in field['entities'] if e['kind']=='organism')
            detail=request(f'/api/entities/{entity_id}')
            assert len(detail['entity']['genome'])==32
            reset=request('/api/reset',{**args,'scenario':'mixed','seed':42,'config':initial['configuration']})
            assert reset['run_id']!=initial['run_id'] and reset['status']=='paused' and reset['tick']==0
            print(f"HTTP smoke OK: status={initial['tick']} → step={step['tick']} → running={running['tick']} "
                  f"→ pause={paused['tick']} (stable) → field={len(field['entities'])} → entity={entity_id} → reset=0")
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=2)
        if child_pid is not None:
            deadline=monotonic()+5
            while monotonic()<deadline:
                try:
                    os.kill(child_pid,0)
                except ProcessLookupError:
                    assert 'leaked semaphore' not in log_path.read_text(), log_path.read_text()
                    print(f'Сервер и процесс симуляции PID={child_pid} завершены. Лог: {log_path}')
                    break
                sleep(0.03)
            else:
                raise AssertionError('После shutdown остался процесс симуляции')


if __name__=='__main__':
    main()
