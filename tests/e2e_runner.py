"""Runs the real Actor entry point with the QuassLabs API mocked.

Used by test_e2e.py as a subprocess so the Apify SDK runs exactly as it does in
production (local storage in the cwd, ACTOR_TEST_PAY_PER_EVENT charging log).
The mock answers 200 unless the item's `pattern` is "fail", which gets a 400.
It echoes the Authorization header in error bodies on purpose, to prove the
Actor redacts the key before storing anything.
"""

import asyncio
import json
import sys

import httpx

import ql_actor.main as actor_main

calls = []


def handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content or b'{}')
    calls.append(str(request.url))
    if body.get('pattern') == 'fail':
        return httpx.Response(400, json={'error': 'bad_pattern', 'echo': request.headers.get('authorization')})
    return httpx.Response(200, json={'echo_path': request.url.path, 'ok': True})


actor_main._transport = lambda: httpx.MockTransport(handler)

if __name__ == '__main__':
    code = 0
    try:
        asyncio.run(actor_main.main())
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    print('E2E_CALLS=' + json.dumps(calls), flush=True)
    sys.exit(code)
