"""Apify Actor entry point: QuassLabs Dev QA Tools.

The QuassLabs API key is read from the QL_API_KEY environment variable, which
the Actor owner sets as a Secret in Apify Console. It is never accepted from
the run input, never logged, and never written to the dataset.
"""

from __future__ import annotations

import logging
import os

import httpx
from apify import Actor

from .core import (
    DEFAULT_BASE_URL,
    EVENT_NAME,
    InputError,
    parse_input,
    pricing_warnings,
    run_batch,
)

API_KEY_ENV = 'QL_API_KEY'
# Operator-only override (for staging). Not an input field on purpose: letting
# a run choose the host would let it send the owner's key anywhere.
BASE_URL_ENV = 'QL_API_BASE_URL'


def _transport() -> httpx.AsyncBaseTransport | None:
    """Hook for tests; production uses httpx's default transport."""
    return None


async def main() -> None:
    async with Actor:
        # httpx logs every request line at INFO. URLs carry no secret, but keep
        # the run log to our own messages.
        logging.getLogger('httpx').setLevel(logging.WARNING)

        api_key = os.environ.get(API_KEY_ENV, '').strip()
        if not api_key:
            await Actor.fail(
                status_message=(
                    f'{API_KEY_ENV} is not configured for this Actor. '
                    'The Actor owner must set it as a secret environment variable.'
                )
            )
            return

        try:
            tool, path, items = parse_input(await Actor.get_input())
        except InputError as exc:
            await Actor.fail(status_message=f'Invalid input: {exc}')
            return

        base_url = os.environ.get(BASE_URL_ENV, '').strip() or DEFAULT_BASE_URL
        charging = Actor.get_charging_manager()
        pricing = charging.get_pricing_info()
        for warning in pricing_warnings(pricing.is_pay_per_event, pricing.per_event_prices):
            Actor.log.warning(warning)

        async def push(record: dict) -> None:
            await Actor.push_data(record)

        async def charge():
            return await Actor.charge(event_name=EVENT_NAME)

        def limit_reached() -> bool:
            return charging.is_event_charge_limit_reached(EVENT_NAME)

        Actor.log.info('Running %s on %d item(s).', tool, len(items))
        async with httpx.AsyncClient(transport=_transport()) as client:
            summary = await run_batch(
                tool=tool,
                path=path,
                items=items,
                api_key=api_key,
                base_url=base_url,
                client=client,
                push=push,
                charge=charge,
                limit_reached=limit_reached,
            )

        message = (
            f'{tool}: {summary.succeeded} ok, {summary.failed} failed '
            f'(charged {summary.charged} x {EVENT_NAME}).'
        )
        if summary.stopped_on_limit:
            message += ' Stopped early: the run reached its maximum cost.'
        Actor.log.info(message)
        await Actor.set_status_message(message)
