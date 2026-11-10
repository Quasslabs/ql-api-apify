## What is QuassLabs Data Cleanup?

**QuassLabs Data Cleanup** is a set of **deterministic data utilities** you can run on Apify. Use it to clean a messy CSV export, infer a JSON Schema from sample records, pull fields out of JSON with JSONPath, convert units exactly, and remove duplicate text.

It is built for the step after scraping or exporting: the data is there, but the delimiter is wrong, the headers are inconsistent, half the rows are duplicates, or you need a schema before loading it somewhere. Every operation is rule-based, with **no LLM**, and your data is never executed or evaluated. The same input always gives the same output.

It runs on the same engine as the **QuassLabs API** (https://quasslabs.com/api) and the **QuassLabs MCP server** (`api.quasslabs.com/mcp`). Full field reference: https://docs.quasslabs.com

## What can this Actor do?

Pick an `operation` in each input:

| Operation | What it does |
| --- | --- |
| `csv_normalize` | Sniffs the delimiter, strips the BOM, snake_cases headers (renaming duplicates), pads or trims ragged rows, drops empty and optionally duplicate rows. Returns CSV or JSON rows. Up to 200,000 cells. |
| `json_shape` | Infers a JSON Schema (draft 2020-12) from 1-1,000 sample documents. `required`, `enum` and `format` appear only where every sample supports them. |
| `json_extract` | Evaluates up to 50 JSONPath expressions (`$`, `.key`, `['key']`, `[n]`, `[*]`, `..key`) against a document. Filters and scripts are rejected. |
| `unit_convert` | Exact conversion within length, mass, volume, temperature, time, data, speed, area, pressure and energy. One value or up to 1,000 per call. |
| `text_dedupe` | Removes exact, normalized (case, whitespace, punctuation) or near-duplicate strings from up to 50,000 texts. |

## How to use it

1. Click **Try for free** (or **Start**).
2. Put one JSON body in **Input**, or a list of bodies in **Batch of inputs** (`items`, up to 1,000 per run). When `items` is set, `input` is ignored.
3. Run the Actor and open the **Output** tab, or fetch the dataset through the Apify API.

You can call it from the Apify API, schedule it after a scraper with a webhook, or hand it to an AI agent through the Apify MCP server.

## Input examples

### Clean a semicolon CSV and drop duplicate rows

```json
{
  "input": {
    "operation": "csv_normalize",
    "csv": "First Name;E-mail\nAda;ada@example.com\nAda;ada@example.com\n",
    "dedupe_rows": true,
    "output": "json"
  }
}
```

### Infer a JSON Schema from samples

```json
{
  "input": {
    "operation": "json_shape",
    "samples": [{ "id": 1, "email": "a@example.com" }, { "id": 2 }]
  }
}
```

### More one-line inputs

| Operation | Example `input` |
| --- | --- |
| `json_extract` | `{"operation": "json_extract", "json": {"orders": [{"id": 7}, {"id": 9}]}, "paths": ["$.orders[*].id"]}` |
| `unit_convert` | `{"operation": "unit_convert", "value": 26.2, "from": "mi", "to": "km"}` |
| `text_dedupe` | `{"operation": "text_dedupe", "items": ["Hello world", "hello  world!", "Other"], "mode": "normalized"}` |

Each request body can be up to 2 MB. File inputs must be inline.

## Output

One dataset item per input, in input order:

```json
{ "tool": "data_transform", "input_index": 0, "status": "ok", "result": { "...": "the operation's JSON response" } }
{ "tool": "data_transform", "input_index": 1, "status": "error", "error": { "code": "validation_error", "http_status": 400, "message": "..." } }
```

Export as JSON, CSV, Excel or HTML, or read it with the Apify API.

## How much does it cost?

This Actor uses **pay-per-event** pricing:

| Event | Price | When it is charged |
| --- | --- | --- |
| `tool-call` | **$0.02** | Once for each input processed successfully. |

- Cleaning 100 CSV files costs $2.00. One unit conversion batch of up to 1,000 values is one event.
- **Failed items are free.** If an input is rejected (bad JSON, a 4xx or 5xx from the API, a network error), it is written to the dataset with `status: "error"` and not charged.
- Set a **maximum cost per run** and the Actor stops before doing work it cannot bill.

## FAQ

### Is an LLM involved?

No. Every operation is deterministic and rule-based, and your data is never executed, evaluated or fetched from.

### Where does my data go?

Each input is sent over HTTPS to `api.quasslabs.com`, the QuassLabs API, to be processed. The result is written to your Apify run's dataset and follows your Apify data retention settings. For QuassLabs' own data handling, see https://docs.quasslabs.com.

### Can I call the same utilities without Apify?

Yes. The QuassLabs REST API (https://quasslabs.com/api) and the MCP server at `api.quasslabs.com/mcp` run the same engine.

### Something looks wrong

Check the `error.message` in the dataset item first; it carries the API's validation message. For anything else, open an issue on this Actor's **Issues** tab.
