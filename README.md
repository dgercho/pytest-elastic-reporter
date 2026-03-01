# pytest-elastic-reporter

A pytest plugin that post results to **Elasticsearch**.

Each test result is stored as its own document, giving you full flexibility to build dashboards - pass rates over time, slowest tests, fixture failures per project, and more.

---

## Installation

```bash
uv pip install pytest-elastic-reporter
```

> **Important:** Pin the `elasticsearch` client to match your server's major version or you will get a `media_type_header_exception`:
>
> ```bash
> pip install "elasticsearch>=8,<9"   # for Elasticsearch 8.x
> pip install "elasticsearch>=7,<8"   # for Elasticsearch 7.x
> ```

---

## Configuration

Options can be set as CLI flags or in `pytest.ini` / `pyproject.toml`. CLI flags take priority over ini values.

| CLI flag | `pytest.ini` key | Required | Description |
|---|---|---|---|
| `--es-url` | `es_url` | V | Elasticsearch base URL |
| `--es-index` | `es_index` | V | Index name to write to |
| `--api-project` | `api_project` | V | Project name, used to group runs |
| `--es-username` | `es_username` | — | Basic-auth username |
| `--es-password` | `es_password` | — | Basic-auth password |
| `--es-api-key` | `es_api_key` | — | API key in `<id>:<key>` format |

Authentication priority: **API Key > Basic Auth > none**

---

## Usage

```bash
# Or pass everything via CLI
pytest --es-url http://elastic-cluster:9200 \
       --es-index pytest-results \
       --api-project my-app-tests \
       --es-username elastic \
       --es-password changeme
```

---

### Outcome values

| Value | Meaning |
|---|---|
| `passed` | Test passed |
| `failed` | Test raised an exception or assertion error |
| `skipped` | `@pytest.mark.skip` or `pytest.skip()` was used |
| `xfailed` | Expected failure, and it failed |
| `xpassed` | Expected failure, but it passed |

### `fixture_error: true`

When a fixture raises an exception during `setup`, the test body never runs. These results will have `phase: "setup"`, `outcome: "failed"`, and `fixture_error: true` — making them easy to filter separately in Kibana.

---
