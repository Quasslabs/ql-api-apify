"""Tool catalog: Actor tool name -> QuassLabs REST path.

Mirrors the `name` / `endpoint` pairs in the platform's src/mcp/tools.js
(quasslabs-api-platform). Only deterministic, low-cost tools are listed.
Deliberately excluded: buy_credits, feedback, rate_call, uploads, jwt_inspect
(internal scope), and anything Bedrock-backed or container-based
(describe_diagram, compress, convert_diagram, supply_chain_scan, ...).

tests/test_tools.py checks this table against tools.js when the platform
checkout is present, and against .actor/input_schema.json always.
"""

from __future__ import annotations

TOOLS: dict[str, str] = {
    'regex_lint': '/v1/regex-lint',
    'mcp_tool_lint': '/v1/mcp-tool-lint',
    'openapi_diff': '/v1/openapi-diff',
    'commit_hygiene': '/v1/commit-hygiene',
    'pr_description_lint': '/v1/pr-description-lint',
    'ticket_lint': '/v1/ticket-lint',
    'story_lint': '/v1/story-lint',
    'acceptance_criteria_validator': '/v1/acceptance-criteria-validator',
    'readability_grade': '/v1/readability-grade',
    'humanizer_score': '/v1/humanizer-score',
    'log_analyzer': '/v1/log-analyzer',
    'dependency_check': '/v1/dependency-check',
    'saas_metrics': '/v1/saas-metrics',
    'estimate_sanity': '/v1/estimate-sanity',
    'sprint_health': '/v1/sprint-health',
}

# Tools that cost QuassLabs more than one credit per call on the direct API.
# They charge the `heavy-tool-call` event instead of `tool-call`, so the
# Apify price stays above the direct price. tests/test_tools.py checks this
# set against the platform's endpoint_credits when that checkout is present.
HEAVY_TOOLS: frozenset[str] = frozenset({
    'log_analyzer',
})

# Tools that must never be reachable through this Actor, even if someone adds
# them to TOOLS by mistake. Enforced by a test.
EXCLUDED: frozenset[str] = frozenset({
    'buy_credits',
    'feedback',
    'rate_call',
    'uploads',
    'jwt_inspect',
    'describe_diagram',
    'compress',
    'convert_diagram',
    'supply_chain_scan',
})


def endpoint_for(tool: str) -> str:
    """Return the REST path for a tool, or raise ValueError for an unknown tool."""
    if not isinstance(tool, str) or tool not in TOOLS:
        raise ValueError(
            f'Unknown tool {tool!r}. Pick one of: {", ".join(sorted(TOOLS))}.'
        )
    return TOOLS[tool]
