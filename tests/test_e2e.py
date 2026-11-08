"""End-to-end runs of the Actor under the real Apify SDK, HTTP mocked."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KEY = 'qlk_e2e_SECRET_never_store_me_987654'


def run_actor(tmp_path: Path, actor_input: dict, api_key: str | None = KEY):
    kvs = tmp_path / 'storage' / 'key_value_stores' / 'default'
    kvs.mkdir(parents=True)
    (kvs / 'INPUT.json').write_text(json.dumps(actor_input), encoding='utf-8')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('APIFY_', 'ACTOR_', 'CRAWLEE_', 'QL_'))}
    env.update({
        'PYTHONPATH': str(ROOT),
        'ACTOR_TEST_PAY_PER_EVENT': 'true',
        'CRAWLEE_PURGE_ON_START': 'false',
        'PYTHONIOENCODING': 'utf-8',
    })
    if api_key is not None:
        env['QL_API_KEY'] = api_key
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'tests' / 'e2e_runner.py')],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120,
    )
    out = proc.stdout + proc.stderr
    m = re.search(r'E2E_CALLS=(\[.*\])', out)
    calls = json.loads(m.group(1)) if m else None
    return proc.returncode, out, calls


def dataset_items(tmp_path: Path, name: str = 'default'):
    d = tmp_path / 'storage' / 'datasets' / name
    if not d.exists():
        return []
    files = sorted(p for p in d.glob('*.json') if p.name != '__metadata__.json')
    return [json.loads(p.read_text(encoding='utf-8')) for p in files]


def tool_call_charges(tmp_path: Path):
    """tool-call rows in the local charging log.

    Locally the SDK also logs the synthetic apify-default-dataset-item event
    at a placeholder $1 for every pushed row (it has no pricing config). On the
    platform that event is free once removed from the pricing, which the
    README tells the owner to do; pricing_warnings() flags it if not.
    """
    return [c for c in dataset_items(tmp_path, 'charging-log') if c.get('event_name') == 'tool-call']


def all_storage_text(tmp_path: Path) -> str:
    return '\n'.join(
        p.read_text(encoding='utf-8', errors='replace')
        for p in (tmp_path / 'storage').rglob('*') if p.is_file()
    )


def test_batch_run_charges_successes_and_hides_key(tmp_path):
    actor_input = {
        'tool': 'commit_hygiene',
        'items': [
            {'commit': {'message': 'feat: add x'}, 'pattern': 'ok'},
            {'pattern': 'fail'},
            {'commit': {'message': 'fix: y'}},
        ],
    }
    code, out, calls = run_actor(tmp_path, actor_input)
    assert code == 0, out
    assert calls == ['https://api.quasslabs.com/v1/commit-hygiene'] * 3

    items = dataset_items(tmp_path)
    assert [(i['input_index'], i['status']) for i in items] == [(0, 'ok'), (1, 'error'), (2, 'ok')]
    assert all(i['tool'] == 'commit_hygiene' for i in items)
    assert items[1]['error']['http_status'] == 400

    charges = tool_call_charges(tmp_path)
    assert len(charges) == 2, charges
    assert sum(c['charged_count'] for c in charges) == 2

    assert KEY not in all_storage_text(tmp_path)
    assert KEY not in out


def test_single_input_run(tmp_path):
    code, out, calls = run_actor(tmp_path, {'tool': 'regex_lint', 'input': {'pattern': '(a+)+$'}})
    assert code == 0, out
    assert calls == ['https://api.quasslabs.com/v1/regex-lint']
    assert len(dataset_items(tmp_path)) == 1
    assert len(tool_call_charges(tmp_path)) == 1


@pytest.mark.parametrize('actor_input', [
    {'tool': 'definitely_not_a_tool', 'input': {'pattern': 'a'}},
    {'tool': 'buy_credits', 'input': {}},
    {'tool': 'regex_lint'},
])
def test_bad_input_fails_cleanly(tmp_path, actor_input):
    code, out, calls = run_actor(tmp_path, actor_input)
    assert code != 0
    assert 'Invalid input' in out
    assert 'Traceback' not in out
    assert calls == []
    assert dataset_items(tmp_path) == []
    assert tool_call_charges(tmp_path) == []
    assert KEY not in out


def test_missing_api_key_fails_cleanly(tmp_path):
    code, out, calls = run_actor(tmp_path, {'tool': 'regex_lint', 'input': {'pattern': 'a'}}, api_key=None)
    assert code != 0
    assert 'QL_API_KEY is not configured' in out
    assert 'Traceback' not in out
    assert calls == []
