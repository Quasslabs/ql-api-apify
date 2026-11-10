## What is QuassLabs Dev QA Tools?

**QuassLabs Dev QA Tools** is a set of **deterministic developer and QA linters** you can run on Apify. Use it to lint regexes for ReDoS risk, find breaking changes between two OpenAPI specs, check commit messages, PR descriptions, Jira tickets, user stories and acceptance criteria, and score text, logs, dependency manifests, SaaS metrics, estimates and sprints. It also audits GitHub Actions workflows and SQL migrations, lints A2A agent cards and SKILL.md files, checks requirements coverage and triages bug reports.

Pick a **tool**, paste one JSON **input**, or send a batch of **items** to lint hundreds of things in one run. Every check is rule-based, with **no LLM**, so the same input always gives the same answer. That makes it a good fit for CI pipelines, scheduled audits, and AI agents that need a repeatable check.

It is the same engine as the **QuassLabs API** (https://quasslabs.com/api) and the **QuassLabs MCP server** (`api.quasslabs.com/mcp`). Full field-by-field reference for every tool: https://docs.quasslabs.com

## What can this Actor do?

| Tool | What it checks |
| --- | --- |
| `regex_lint` | ReDoS / catastrophic-backtracking risk in a regular expression, plus a plain-English explanation of what it matches. |
| `mcp_tool_lint` | MCP tool definitions (from `tools/list`) for how well a model can pick and call them, and for tool-poisoning patterns. |
| `openapi_diff` | Breaking changes between a base and head OpenAPI 3.x spec, with a suggested semver bump. |
| `commit_hygiene` | Commit messages: conventional-commit format, vague subjects, subject length, leaked-secret patterns, oversized commits. |
| `pr_description_lint` | PR descriptions: missing body, no test evidence, no rationale, unstructured long text. |
| `ticket_lint` | Whole Jira tickets: summary, description, AC, estimate, priority, labels and links (one ticket or up to 50). |
| `story_lint` | User stories: As-a / I-want / So-that completeness, dependencies, duplicates (up to 50 per call). |
| `acceptance_criteria_validator` | Acceptance criteria: vague or untestable, non-atomic, no observable outcome, missing failure path; 0-100 score. |
| `readability_grade` | Flesch Reading Ease and Flesch-Kincaid grade level for prose. |
| `humanizer_score` | AI-writing tells in text: a 0-1 score and the exact patterns that fired. |
| `log_analyzer` | Raw logs: level breakdown, time range, normalised error clusters. |
| `dependency_check` | Dependency manifests (package.json, requirements.txt, pyproject.toml, go.mod, ...): unpinned versions and other hygiene issues. |
| `saas_metrics` | ARR, ARPA, LTV, CAC payback, Rule of 40, NRR/GRR from your MRR and customer numbers, each with a health tag. |
| `estimate_sanity` | Hour estimates against benchmark ranges or your own historical actuals. |
| `sprint_health` | Velocity, commitment reliability and spillover across 1-24 sprints. |
| `actions_audit` | GitHub Actions workflows: script injection, unpinned actions, risky triggers and token permissions. |
| `sql_migration_lint` | Postgres or MySQL migrations that lock or rewrite large tables, with a zero-downtime alternative. |
| `coverage_check` | Which requirements your user stories cover, which have gaps, and which stories trace to nothing. |
| `defect_triage` | Bug reports: severity, missing repro details, and a structured summary (one report or up to 50). |
| `agent_card_lint` | A2A Agent Cards: spec conformance, discoverability and injection patterns. |
| `skill_lint` | SKILL.md and AGENTS.md files: spec conformance, discoverability and injection patterns. |
| `log_audit_creator` | An audit-log event catalog, schema and storage plan for your features (SOC 2, HIPAA, GDPR, PCI). |

## How to use it

1. Click **Try for free** (or **Start**).
2. Choose a **Tool** from the dropdown.
3. For one check, put the tool's JSON body in **Tool input**. For many checks, put a list of bodies in **Batch of tool inputs** (`items`, up to 1,000 per run). When `items` is set, `input` is ignored.
4. Run the Actor and open the **Output** tab, or fetch the dataset through the Apify API.

You can call it from the Apify API, schedule it, chain it with webhooks, or hand it to an AI agent through the Apify MCP server.

## Input examples

### Lint one regex

```json
{
  "tool": "regex_lint",
  "input": { "pattern": "(a+)+$" }
}
```

### Lint a batch of commit messages (one event per commit)

```json
{
  "tool": "commit_hygiene",
  "items": [
    { "commit": { "message": "feat(auth): add refresh-token rotation" } },
    { "commit": { "message": "fix stuff" } },
    { "commit": { "message": "wip" } }
  ]
}
```

### Diff two OpenAPI specs

```json
{
  "tool": "openapi_diff",
  "input": {
    "base": "openapi: 3.0.0\ninfo: {title: Pets, version: 1.0.0}\npaths:\n  /pets: {get: {responses: {'200': {description: ok}}}}",
    "head": "openapi: 3.0.0\ninfo: {title: Pets, version: 1.0.0}\npaths: {}"
  }
}
```

### More one-line inputs

| Tool | Example `input` |
| --- | --- |
| `pr_description_lint` | `{"pr": {"title": "Fix login bug", "body": "Fixes the redirect loop."}}` |
| `ticket_lint` | `{"ticket": {"key": "APP-12", "summary": "Login", "description": "...", "acceptance_criteria": ["..."]}}` |
| `story_lint` | `{"story": {"id": "S1", "title": "Reset password", "story": {"as_a": "user", "i_want_to": "reset my password", "so_that": "I can sign in"}}}` |
| `acceptance_criteria_validator` | `{"acceptance_criteria": ["User sees an error when the password is wrong"]}` |
| `readability_grade` | `{"text": "Your paragraph here.", "target_grade": 8}` |
| `humanizer_score` | `{"text": "Your paragraph here."}` |
| `log_analyzer` | `{"text": "2026-01-01T00:00:00Z ERROR db timeout id=42\n..."}` |
| `dependency_check` | `{"manifests": [{"filename": "package.json", "content": "{\"dependencies\": {\"left-pad\": \"*\"}}"}]}` |
| `saas_metrics` | `{"mrr": 42000, "customers": 310, "churned_mrr": 900, "cac": 1200}` |
| `estimate_sanity` | `{"estimates": [{"id": "T1", "type": "api_endpoint", "hours": 30}], "benchmarks": {"api_endpoint": {"min": 4, "max": 16}}}` |
| `sprint_health` | `{"sprints": [{"name": "S1", "committed_points": 30, "completed_points": 24}, {"name": "S2", "committed_points": 28, "completed_points": 27}]}` |
| `mcp_tool_lint` | `{"tools": [{"name": "search", "description": "Search.", "inputSchema": {"type": "object"}}]}` |
| `actions_audit` | `{"workflow": "on: pull_request_target\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo \"${{ github.event.pull_request.title }}\""}` |
| `sql_migration_lint` | `{"sql": "ALTER TABLE orders ADD COLUMN status text NOT NULL DEFAULT 'new';", "dialect": "postgres"}` |
| `coverage_check` | `{"requirements": ["Users can reset a password", "Admins can export reports"], "stories": ["As a user I want to reset my password so that I can sign in"]}` |
| `defect_triage` | `{"report": "App crashes on login after the 2.3 update. Steps: open the app, tap Sign in. Expected: home screen."}` |
| `agent_card_lint` | `{"agent_card": {"name": "Weather agent", "description": "Forecasts by city.", "url": "https://agent.example.com", "skills": []}}` |
| `skill_lint` | `{"text": "---\nname: pdf-merge\ndescription: Merge PDF files\n---\n# PDF merge\n"}` |
| `log_audit_creator` | `{"features": ["login", "password reset", "admin user management"], "compliance": ["soc2"]}` |

File inputs must be inline. `upload_id` is not supported in this Actor.

## Output

One dataset item per input, in input order:

```json
{ "tool": "regex_lint", "input_index": 0, "status": "ok", "result": { "...": "the tool's JSON response" } }
{ "tool": "regex_lint", "input_index": 1, "status": "error", "error": { "code": "validation_error", "http_status": 400, "message": "..." } }
```

Export as JSON, CSV, Excel or HTML, or read it with the Apify API.

## How much does it cost?

This Actor uses **pay-per-event** pricing with two events:

| Event | Price | When it is charged |
| --- | --- | --- |
| `tool-call` | **$0.02** | Once for each input processed successfully, for every tool except `log_analyzer` and `log_audit_creator`. |
| `heavy-tool-call` | **$0.08** | Once for each input `log_analyzer` or `log_audit_creator` processed successfully. |

- A batch of 100 commits costs $2.00. A single regex check costs $0.02. Analysing one log costs $0.08.
- **Failed items are free.** If an input is rejected (bad JSON, a 4xx or 5xx from the API, a network error), it is written to the dataset with `status: "error"` and not charged.
- Set a **maximum cost per run** and the Actor stops before doing work it cannot bill, so you never pay more than your limit.
- One item can carry a tool's own batch (for example `ticket_lint` with `tickets: [...]` up to 50). That is still one event.

## FAQ

### Is an LLM involved?

No. Every tool here is deterministic and rule-based. The same input gives the same output.

### Can I call the same tools without Apify?

Yes. The QuassLabs REST API (https://quasslabs.com/api) and the MCP server at `api.quasslabs.com/mcp` run the same engine. Docs: https://docs.quasslabs.com

### Where does my input go?

Each input is sent over HTTPS to `api.quasslabs.com`, the QuassLabs API, to be checked. The result is written to your Apify run's dataset and follows your Apify data retention settings. For QuassLabs' own data handling, see https://docs.quasslabs.com.

### Something looks wrong

Check the `error.message` in the dataset item first; it carries the API's validation message. Field definitions for every tool are at https://docs.quasslabs.com. For anything else, open an issue on this Actor's **Issues** tab.
