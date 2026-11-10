import json
import re
from pathlib import Path

import pytest

from ql_actor.tools import EXCLUDED, HEAVY_TOOLS, TOOLS, endpoint_for

ROOT = Path(__file__).resolve().parents[1]
INPUT_SCHEMA = ROOT / '.actor' / 'input_schema.json'
PLATFORM_TOOLS_JS = Path(
    'G:/Code/Apps/QuassLabs/quasslabs-api-platform--deploy-main/src/mcp/tools.js'
)
PLATFORM_MAIN_TF = Path(
    'G:/Code/Apps/QuassLabs/quasslabs-api-platform--deploy-main/terraform/main.tf'
)


def _enum():
    schema = json.loads(INPUT_SCHEMA.read_text(encoding='utf-8'))
    return schema['properties']['tool']['enum'], schema['properties']['tool']['enumTitles']


def test_every_enum_value_maps_to_a_path():
    enum, _ = _enum()
    for tool in enum:
        path = endpoint_for(tool)
        assert re.fullmatch(r'/v1/[a-z0-9-]+', path), (tool, path)


def test_enum_and_mapping_are_the_same_set():
    enum, titles = _enum()
    assert sorted(enum) == sorted(TOOLS)
    assert len(enum) == len(set(enum)) == len(titles)


def test_excluded_tools_are_not_offered():
    enum, _ = _enum()
    assert not EXCLUDED & set(TOOLS)
    assert not EXCLUDED & set(enum)


@pytest.mark.parametrize('bad', ['nope', '', None, 'buy_credits', 'jwt_inspect', 'uploads', 42])
def test_unknown_tool_raises(bad):
    with pytest.raises(ValueError, match='Unknown tool'):
        endpoint_for(bad)


@pytest.mark.skipif(not PLATFORM_TOOLS_JS.exists(), reason='platform checkout not present')
def test_mapping_matches_platform_tools_js():
    src = PLATFORM_TOOLS_JS.read_text(encoding='utf-8')
    # Each tool block runs from one `name:` to the next; take its first endpoint.
    pairs = {}
    for block in re.split(r"\n\s*name: '", src)[1:]:
        m = re.match(r"([a-z_]+)'", block)
        e = re.search(r"\bendpoint: '([^']+)'", block)
        if m and e:
            pairs.setdefault(m.group(1), e.group(1))
    for tool, path in TOOLS.items():
        assert pairs.get(tool) == path, f'{tool}: actor={path} platform={pairs.get(tool)}'


def test_heavy_tools_are_offered_tools():
    assert HEAVY_TOOLS <= set(TOOLS)


@pytest.mark.skipif(not PLATFORM_MAIN_TF.exists(), reason='platform checkout not present')
def test_heavy_tools_match_platform_credit_costs():
    # Any offered tool that costs more than 1 credit on the direct API must
    # charge the heavy event, or Apify would undercut our own price.
    src = PLATFORM_MAIN_TF.read_text(encoding='utf-8')
    credits = {k: int(v) for k, v in re.findall(r'^\s*"([a-z0-9-]+)"\s*=\s*(\d+)\s*$', src, re.M)}
    for tool, path in TOOLS.items():
        slug = path.rsplit('/', 1)[-1]
        assert slug in credits, f'{tool}: no credit cost for {slug} in main.tf'
        if credits[slug] > 1:
            assert tool in HEAVY_TOOLS, f'{tool} costs {credits[slug]} credits; add it to HEAVY_TOOLS'
        else:
            assert tool not in HEAVY_TOOLS, f'{tool} costs {credits[slug]} credit(s); remove it from HEAVY_TOOLS'
