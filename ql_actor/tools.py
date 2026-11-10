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

import os

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
    'actions_audit': '/v1/actions-audit',
    'sql_migration_lint': '/v1/sql-migration-lint',
    'coverage_check': '/v1/coverage-check',
    'defect_triage': '/v1/defect-triage',
    'agent_card_lint': '/v1/agent-card-lint',
    'skill_lint': '/v1/skill-lint',
    'log_audit_creator': '/v1/log-audit-creator',
}

# Tools offered by the separate "QuassLabs Data Cleanup" Actor
# (actors/data-cleanup). Same code, different QL_ACTOR_PROFILE.
DATA_TOOLS: dict[str, str] = {
    'data_transform': '/v1/data-transform',
}

PROFILE_ENV = 'QL_ACTOR_PROFILE'
DEFAULT_PROFILE = 'dev-qa'
PROFILES: dict[str, dict[str, str]] = {
    'dev-qa': TOOLS,
    'data-cleanup': DATA_TOOLS,
}

# Tools that cost QuassLabs more than one credit per call on the direct API.
# They charge the `heavy-tool-call` event instead of `tool-call`, so the
# Apify price stays above the direct price. tests/test_tools.py checks this
# set against the platform's endpoint_credits when that checkout is present.
HEAVY_TOOLS: frozenset[str] = frozenset({
    'log_analyzer',
    'log_audit_creator',
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


def active_tools(profile: str | None = None) -> dict[str, str]:
    """The tool table for a profile (default: the QL_ACTOR_PROFILE env var)."""
    if profile is None:
        profile = os.environ.get(PROFILE_ENV, '').strip() or DEFAULT_PROFILE
    if profile not in PROFILES:
        raise ValueError(f'Unknown {PROFILE_ENV} {profile!r}. Use one of: {", ".join(sorted(PROFILES))}.')
    return PROFILES[profile]


def endpoint_for(tool: str, tools: dict[str, str] | None = None) -> str:
    """Return the REST path for a tool, or raise ValueError for an unknown tool."""
    if tools is None:
        tools = active_tools()
    if not isinstance(tool, str) or tool not in tools:
        raise ValueError(
            f'Unknown tool {tool!r}. Pick one of: {", ".join(sorted(tools))}.'
        )
    return tools[tool]
