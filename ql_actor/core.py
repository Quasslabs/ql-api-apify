"""Actor logic, kept free of the Apify runtime so it can be unit tested.

`run_batch` takes injected callables for pushing a dataset item, charging an
event and checking the spending limit; `main.py` wires them to the Apify SDK.

Billing rules (pay-per-event):
- One event per item that our API answered with a 2xx: `tool-call` for most
  tools, `heavy-tool-call` for the tools in tools.HEAVY_TOOLS.
- The charge happens AFTER the result is pushed to the dataset, so a user is
  never billed for a result they cannot see.
- 4xx / 5xx answers, network failures and inputs rejected locally are pushed
  as status "error" and are NOT charged.
- Before each API call we check the user's spending limit and stop if another
  event cannot be charged, so we do not spend QuassLabs credits on unpaid work.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

from .tools import HEAVY_TOOLS, endpoint_for

# Event prices live in Apify Console (Publishing > Monetization), not in code.
# Launch prices: tool-call $0.02, heavy-tool-call $0.08.
EVENT_NAME = 'tool-call'
HEAVY_EVENT_NAME = 'heavy-tool-call'
DEFAULT_BASE_URL = 'https://api.quasslabs.com'
MAX_ITEMS = 1000
REQUEST_TIMEOUT_S = 60.0
RETRY_STATUSES = frozenset({429, 502, 503, 504})
MAX_ATTEMPTS = 3
ERROR_TEXT_LIMIT = 2000

log = logging.getLogger('ql_actor')

PushFn = Callable[[dict], Awaitable[Any]]
ChargeFn = Callable[[], Awaitable[Any]]
LimitFn = Callable[[], bool]


class InputError(ValueError):
    """The run input is unusable as a whole (bad tool, bad shape)."""


@dataclass
class BatchSummary:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    charged: int = 0
    stopped_on_limit: bool = False
    statuses: list[str] = field(default_factory=list)


def redact(text: str, secret: str | None) -> str:
    """Remove the API key from any text before it is logged or stored."""
    if not secret:
        return text
    return text.replace(secret, '[REDACTED]')


SYNTHETIC_DATASET_EVENT = 'apify-default-dataset-item'


def event_for(tool: str) -> str:
    """The pay-per-event name charged for one successful call of `tool`."""
    return HEAVY_EVENT_NAME if tool in HEAVY_TOOLS else EVENT_NAME


def pricing_warnings(is_pay_per_event: bool, per_event_prices: dict) -> list[str]:
    """Owner-facing warnings about a pricing setup that breaks the billing rules.

    The SDK charges the synthetic `apify-default-dataset-item` event on every
    push to the default dataset, error rows included. If that event carries a
    price, failed items get billed - so it must be removed in Apify Console.
    """
    if not is_pay_per_event:
        return []
    out = []
    if (per_event_prices.get(SYNTHETIC_DATASET_EVENT) or 0) > 0:
        out.append(
            f'Pricing includes a priced "{SYNTHETIC_DATASET_EVENT}" event, so failed items are billed too. '
            'Remove that synthetic event in Publishing > Monetization.'
        )
    if EVENT_NAME not in per_event_prices:
        out.append(f'Pricing has no "{EVENT_NAME}" event, so successful calls are not billed.')
    if HEAVY_EVENT_NAME not in per_event_prices:
        heavy = ', '.join(sorted(HEAVY_TOOLS))
        out.append(f'Pricing has no "{HEAVY_EVENT_NAME}" event, so {heavy} calls are not billed.')
    return out


def parse_input(actor_input: dict | None) -> tuple[str, str, list[dict]]:
    """Validate the run input. Returns (tool, endpoint, items).

    `items` (batch) wins over `input` (single call) when it is non-empty.
    """
    if not isinstance(actor_input, dict):
        raise InputError('Actor input must be a JSON object.')
    tool = actor_input.get('tool')
    try:
        path = endpoint_for(tool)
    except ValueError as exc:
        raise InputError(str(exc)) from None

    items = actor_input.get('items')
    if items not in (None, []):
        if not isinstance(items, list):
            raise InputError('`items` must be an array of JSON objects.')
        if len(items) > MAX_ITEMS:
            raise InputError(f'`items` has {len(items)} entries; the limit is {MAX_ITEMS} per run.')
        return tool, path, list(items)

    single = actor_input.get('input')
    if single is None:
        raise InputError('Provide either `input` (one call) or `items` (a batch of calls).')
    return tool, path, [single]


def item_problem(item: Any) -> str | None:
    """Local checks on one item. Returns an error message, or None if OK."""
    if not isinstance(item, dict):
        return 'Each item must be a JSON object matching the tool input.'
    # The uploads tool is not offered here, and every Actor user shares one
    # QuassLabs key, so an upload_id would let one user read another's upload.
    if 'upload_id' in item:
        return '`upload_id` is not supported in this Actor; pass the content inline instead.'
    return None


def _error(code: str, message: str, http_status: int | None = None) -> dict:
    err: dict[str, Any] = {'code': code, 'message': message}
    if http_status is not None:
        err['http_status'] = http_status
    return err


def _body_of(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError):
        return resp.text


async def call_tool(
    client: httpx.AsyncClient,
    base_url: str,
    path: str,
    payload: dict,
    api_key: str,
) -> tuple[bool, Any]:
    """POST one tool input. Returns (ok, result_or_error)."""
    url = base_url.rstrip('/') + path
    headers = {
        'authorization': f'Bearer {api_key}',
        'content-type': 'application/json',
        'user-agent': 'quasslabs-apify-actor/0.1',
    }
    last_err: dict | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_S)
        except httpx.HTTPError as exc:
            last_err = _error('network_error', redact(f'{type(exc).__name__}: {exc}', api_key))
        else:
            if 200 <= resp.status_code < 300:
                return True, _body_of(resp)
            body = _body_of(resp)
            if isinstance(body, dict):
                code = str(body.get('error') or f'http_{resp.status_code}')
                message = redact(json.dumps(body)[:ERROR_TEXT_LIMIT], api_key)
            else:
                code = f'http_{resp.status_code}'
                message = redact(str(body)[:ERROR_TEXT_LIMIT], api_key)
            last_err = _error(code, message, resp.status_code)
            if resp.status_code not in RETRY_STATUSES:
                return False, last_err
        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
    return False, last_err


async def run_batch(
    *,
    tool: str,
    path: str,
    items: list,
    api_key: str,
    base_url: str,
    client: httpx.AsyncClient,
    push: PushFn,
    charge: ChargeFn,
    limit_reached: LimitFn,
    event_name: str = EVENT_NAME,
) -> BatchSummary:
    summary = BatchSummary()
    for index, item in enumerate(items):
        if limit_reached():
            summary.stopped_on_limit = True
            log.info('Spending limit reached before item %d; stopping.', index)
            break

        record: dict[str, Any] = {'tool': tool, 'input_index': index}
        problem = item_problem(item)
        if problem:
            ok, payload = False, _error('invalid_item', problem)
        else:
            ok, payload = await call_tool(client, base_url, path, item, api_key)

        if ok:
            record['status'] = 'ok'
            record['result'] = payload
        else:
            record['status'] = 'error'
            record['error'] = payload

        await push(record)
        summary.processed += 1
        summary.statuses.append(record['status'])

        if ok:
            summary.succeeded += 1
            result = await charge()
            summary.charged += 1
            log.info('Item %d: ok (charged %s).', index, event_name)
            if getattr(result, 'event_charge_limit_reached', False) and index < len(items) - 1:
                summary.stopped_on_limit = True
                log.info('Spending limit reached after item %d; stopping.', index)
                break
        else:
            summary.failed += 1
            log.info('Item %d: error %s (not charged).', index, payload.get('code'))
    return summary
