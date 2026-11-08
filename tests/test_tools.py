import json
import re
from pathlib import Path

import pytest

from ql_actor.tools import EXCLUDED, TOOLS, endpoint_for

ROOT = Path(__file__).resolve().parents[1]
INPUT_SCHEMA = ROOT / '.actor' / 'input_schema.json'
PLATFORM_TOOLS_JS = Path(
    'G:/Code/Apps/QuassLabs/quasslabs-api-platform--deploy-main/src/mcp/tools.js'
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
    pairs = dict(re.findall(r"name: '([a-z_]+)',(?:\s*//[^\n]*|\s*scopes:[^\n]*)*\s*endpoint: '([^']+)'", src))
    for tool, path in TOOLS.items():
        assert pairs.get(tool) == path, f'{tool}: actor={path} platform={pairs.get(tool)}'
