import json
import logging
from types import SimpleNamespace

import httpx
import pytest

from ql_actor import core
from ql_actor.core import InputError, parse_input, run_batch

KEY = 'qlk_test_SECRET_do_not_leak_123456'
BASE = 'https://api.test.invalid'


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def _sleep(_):
        return None
    monkeypatch.setattr(core.asyncio, 'sleep', _sleep)


class Harness:
    def __init__(self, handler, limit_after=None):
        self.requests = []
        self.pushed = []
        self.charges = 0
        self.limit_after = limit_after

        def _wrapped(request):
            self.requests.append(request)
            return handler(request)

        self.client = httpx.AsyncClient(transport=httpx.MockTransport(_wrapped))

    async def push(self, record):
        self.pushed.append(json.loads(json.dumps(record)))

    async def charge(self):
        self.charges += 1
        reached = self.limit_after is not None and self.charges >= self.limit_after
        return SimpleNamespace(event_charge_limit_reached=reached)

    def limit_reached(self):
        return self.limit_after is not None and self.charges >= self.limit_after

    async def run(self, items, tool='regex_lint'):
        path = core.endpoint_for(tool)
        async with self.client:
            return await run_batch(
                tool=tool, path=path, items=items, api_key=KEY, base_url=BASE,
                client=self.client, push=self.push, charge=self.charge,
                limit_reached=self.limit_reached,
            )


def by_pattern(request):
    body = json.loads(request.content)
    p = body.get('pattern')
    if p == 'bad-request':
        return httpx.Response(400, json={'error': 'validation_error', 'detail': 'pattern too long'})
    if p == 'no-credits':
        return httpx.Response(402, json={'error': 'insufficient_credits'})
    if p == 'boom':
        return httpx.Response(500, text='Internal Server Error')
    if p == 'net':
        raise httpx.ConnectError('connection refused')
    return httpx.Response(200, json={'pattern': p, 'risk': 'low'})


# --- input parsing ---------------------------------------------------------

def test_parse_single_input():
    tool, path, items = parse_input({'tool': 'regex_lint', 'input': {'pattern': 'a+'}})
    assert (tool, path, items) == ('regex_lint', '/v1/regex-lint', [{'pattern': 'a+'}])


def test_items_win_over_input():
    _, _, items = parse_input({'tool': 'regex_lint', 'input': {'pattern': 'x'}, 'items': [{'pattern': 'a'}, {'pattern': 'b'}]})
    assert items == [{'pattern': 'a'}, {'pattern': 'b'}]


@pytest.mark.parametrize('bad', [
    None,
    [],
    {'tool': 'not_a_tool', 'input': {}},
    {'tool': 'buy_credits', 'input': {}},
    {'input': {'pattern': 'a'}},
    {'tool': 'regex_lint'},
    {'tool': 'regex_lint', 'items': 'nope'},
    {'tool': 'regex_lint', 'items': [{}] * (core.MAX_ITEMS + 1)},
])
def test_bad_input_fails_cleanly(bad):
    with pytest.raises(InputError):
        parse_input(bad)


# --- calls, charging ------------------------------------------------------

async def test_mapping_used_for_url_and_bearer_header():
    h = Harness(by_pattern)
    await h.run([{'filename': 'package.json', 'content': '{}'}], tool='dependency_check')
    req = h.requests[0]
    assert str(req.url) == BASE + '/v1/dependency-check'
    assert req.method == 'POST'
    assert req.headers['authorization'] == f'Bearer {KEY}'
    assert json.loads(req.content) == {'filename': 'package.json', 'content': '{}'}


async def test_batch_charges_only_successes():
    items = [
        {'pattern': 'a+'},          # ok
        {'pattern': 'bad-request'}, # 400
        {'pattern': 'b+'},          # ok
        {'pattern': 'no-credits'},  # 402
        {'pattern': 'boom'},        # 500 (retried, still fails)
        {'pattern': 'net'},         # network error
        'not-an-object',            # rejected locally
        {'upload_id': 'u1'},        # rejected locally
        {'pattern': 'c+'},          # ok
    ]
    h = Harness(by_pattern)
    summary = await h.run(items)
    assert h.charges == 3
    assert summary.charged == 3 and summary.succeeded == 3 and summary.failed == 6
    assert [r['input_index'] for r in h.pushed] == list(range(len(items)))
    assert [r['status'] for r in h.pushed] == ['ok', 'error', 'ok', 'error', 'error', 'error', 'error', 'error', 'ok']
    assert h.pushed[1]['error']['http_status'] == 400
    assert h.pushed[1]['error']['code'] == 'validation_error'
    assert h.pushed[3]['error']['code'] == 'insufficient_credits'
    assert h.pushed[5]['error']['code'] == 'network_error'
    assert h.pushed[6]['error']['code'] == 'invalid_item'
    for r in h.pushed:
        assert set(r) == {'tool', 'input_index', 'status', 'result' if r['status'] == 'ok' else 'error'}
    # Locally rejected items never reach the API.
    sent = [json.loads(r.content) for r in h.requests]
    assert {'upload_id': 'u1'} not in sent


async def test_retry_on_503_then_success_charges_once():
    calls = {'n': 0}

    def flaky(request):
        calls['n'] += 1
        if calls['n'] < 3:
            return httpx.Response(503, json={'error': 'unavailable'})
        return httpx.Response(200, json={'ok': True})

    h = Harness(flaky)
    summary = await h.run([{'pattern': 'a'}])
    assert calls['n'] == 3
    assert h.charges == 1 and summary.succeeded == 1


async def test_4xx_is_not_retried():
    h = Harness(by_pattern)
    await h.run([{'pattern': 'bad-request'}])
    assert len(h.requests) == 1 and h.charges == 0


async def test_charge_happens_after_push():
    order = []
    h = Harness(by_pattern)
    orig_push, orig_charge = h.push, h.charge

    async def push(r):
        order.append('push')
        await orig_push(r)

    async def charge():
        order.append('charge')
        return await orig_charge()

    h.push, h.charge = push, charge
    await h.run([{'pattern': 'a'}, {'pattern': 'boom'}])
    assert order == ['push', 'charge', 'push']


async def test_stops_at_spending_limit_without_calling_api():
    h = Harness(by_pattern, limit_after=2)
    summary = await h.run([{'pattern': str(i)} for i in range(5)])
    assert h.charges == 2
    assert len(h.requests) == 2  # no unpaid API work after the limit
    assert summary.stopped_on_limit


# --- secret hygiene -------------------------------------------------------

async def test_api_key_never_in_dataset_or_logs(caplog):
    def echo_key(request):
        # Worst case: our API echoes the Authorization header back in an error.
        return httpx.Response(401, json={'error': 'unauthorized', 'got': request.headers['authorization']})

    def raises_with_key(request):
        raise httpx.ConnectError(f'failed with {request.headers["authorization"]}')

    caplog.set_level(logging.DEBUG)
    for handler in (echo_key, raises_with_key, by_pattern):
        h = Harness(handler)
        await h.run([{'pattern': 'a'}, {'pattern': 'boom'}])
        dumped = json.dumps(h.pushed)
        assert KEY not in dumped
        assert h.pushed  # something was written, so the check is meaningful
    assert KEY not in caplog.text


async def test_redaction_marks_echoed_key():
    def echo_key(request):
        return httpx.Response(401, json={'error': 'unauthorized', 'got': request.headers['authorization']})

    h = Harness(echo_key)
    await h.run([{'pattern': 'a'}])
    assert '[REDACTED]' in h.pushed[0]['error']['message']
    assert h.charges == 0


# --- pricing config sanity ------------------------------------------------

def test_pricing_warnings():
    from decimal import Decimal
    assert core.pricing_warnings(False, {}) == []
    assert core.pricing_warnings(True, {'tool-call': Decimal('0.01')}) == []
    w = core.pricing_warnings(True, {'tool-call': Decimal('0.01'), 'apify-default-dataset-item': Decimal('0.001')})
    assert len(w) == 1 and 'apify-default-dataset-item' in w[0]
    assert core.pricing_warnings(True, {'tool-call': Decimal('0.01'), 'apify-default-dataset-item': Decimal(0)}) == []
    w = core.pricing_warnings(True, {'apify-actor-start': Decimal('0.005')})
    assert len(w) == 1 and 'tool-call' in w[0]
