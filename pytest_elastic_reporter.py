import uuid
import traceback
from datetime import datetime, timezone

import pytest
from elasticsearch import (
    Elasticsearch,
    helpers,
    AuthenticationException,
    ConnectionError
)


def pytest_addoption(parser):
    g = parser.getgroup("REPORTER", "Elasticsearch test reporter")
    g.addoption("--es-url",      default=None, help="Elasticsearch base URL")
    g.addoption("--es-index",    default=None, help="Index name")
    g.addoption("--es-username", default=None, help="Basic-auth username")
    g.addoption("--es-password", default=None, help="Basic-auth password")
    g.addoption("--es-api-key",  default=None, help="API key in id:key")
    g.addoption("--api-project", default=None, help="Project name")

    parser.addini("es_url",      default=None, help="Elasticsearch base URL")
    parser.addini("es_index",    default=None, help="Index name")
    parser.addini("es_username", default=None, help="Basic-auth username")
    parser.addini("es_password", default=None, help="Basic-auth password")
    parser.addini("es_api_key",  default=None, help="API key in id:key")
    parser.addini("api_project", default=None, help="Project name")


def pytest_configure(config):
    config.pluginmanager.register(
        ElasticsearchReporterPlugin(config),
        name="es_reporter",
    )


class ElasticsearchReporterPlugin:
    def __init__(self, config):
        def opt(flag, ini):
            return config.getoption(flag, default=None) or \
                config.getini(ini) or \
                None

        self.es_url = opt("--es-url", "es_url")
        self.index = opt("--es-index", "es_index")
        self.username = opt("--es-username", "es_username")
        self.password = opt("--es-password", "es_password")
        self.api_key = opt("--es-api-key", "es_api_key")
        self.project = opt("--api-project", "api_project")

        required = [self.es_url, self.index, self.project]
        if not all(required):
            missing = [name for name, value in zip(
                ["es_url", "es_index", "api_project"],
                required,
            ) if not value]
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}")

        self.run_id = str(uuid.uuid4())
        self._session_start: datetime | None = None
        self._results: list[dict] = []
        self._es: Elasticsearch | None = None

    def _build_client(self) -> Elasticsearch:
        kwargs = dict(
            hosts=[self.es_url],
            headers={
                "Accept":       "application/json",
                "Content-Type": "application/json",
            },
        )

        if self.api_key:
            kwargs["api_key"] = tuple(self.api_key.split(":", 1))
        elif self.username and self.password:
            kwargs["basic_auth"] = (self.username, self.password)

        return Elasticsearch(**kwargs)

    def pytest_sessionstart(self, session):
        self._session_start = datetime.now(timezone.utc)
        self._es = self._build_client()

    def pytest_sessionfinish(self, session, exitstatus):
        if not self._results:
            return

        finished_at = datetime.now(timezone.utc)
        duration_s = (
            (finished_at - self._session_start).total_seconds()
            if self._session_start else None
        )

        run_meta = {
            "run_id": self.run_id,
            "project": self.project,
            "run_started_at": self._session_start.isoformat() if
            self._session_start else None,
            "run_finished_at": finished_at.isoformat(),
            "run_duration_s": round(duration_s, 3) if
            duration_s is not None else None,
            "run_exit_code": exitstatus,
        }
        for r in self._results:
            r.update(run_meta)

        self._bulk_index(self._results)

        if self._es:
            self._es.close()

    def pytest_runtest_logreport(self, report: pytest.TestReport):
        if report.when == "call" or (
            report.when in ("setup", "teardown") and
            (report.failed or report.skipped)
        ):
            self._results.append(self._build_document(report))

    @staticmethod
    def _build_document(report: pytest.TestReport) -> dict:
        if report.passed:
            outcome = "passed"
        elif report.failed:
            outcome = "failed"
        elif report.skipped:
            outcome = "skipped"
        else:
            outcome = report.outcome

        error_message = None
        error_traceback = None
        if report.failed and report.longrepr:
            lr = report.longrepr
            if hasattr(lr, "reprcrash"):
                error_message = lr.reprcrash.message
                error_traceback = str(lr)
            elif isinstance(lr, tuple):
                error_message = lr[2]
            else:
                error_message = str(lr)

        skip_reason = None
        if report.skipped and report.longrepr:
            lr = report.longrepr
            skip_reason = lr[2] if isinstance(lr, tuple) else str(lr)

        node_id = report.nodeid
        parts = node_id.split("::")
        test_file = parts[0]
        test_name = "::".join(parts[1:]) if len(parts) > 1 else node_id

        return {
            "@timestamp":    datetime.now(timezone.utc).isoformat(),
            "node_id":       node_id,
            "test_file":     test_file,
            "test_name":     test_name,
            "phase":         report.when,
            "outcome":       outcome,
            "fixture_error": report.when == "setup" and report.failed,
            "duration_s":    round(report.duration, 6),
            "error_message": error_message,
            "traceback":     error_traceback,
            "skip_reason":   skip_reason,
        }

    def _bulk_index(self, docs: list[dict]):
        actions = ({"_index": self.index, "_source": doc} for doc in docs)
        try:
            success, errors = helpers.bulk(
                self._es,
                actions,
                raise_on_error=False,
                raise_on_exception=False,
            )

            if errors:
                print(f"\n[REPORTER] [X] {len(errors)}"
                      "document(s) failed to index:")
                for err in errors[:3]:  # show first 3 errors
                    print(err)
            else:
                print(
                    f"\n[REPORTER] [V] Indexed {success} result(s) "
                    f"-> {self.es_url}/{self.index}  [{self.run_id[:8]}]"
                )

        except AuthenticationException:
            print("\n[REPORTER] [X] Authentication failed.")
        except ConnectionError:
            print(f"\n[REPORTER] [X] Could not connect to {self.es_url}")
        except Exception:
            print(f"\n[REPORTER] [X] Unexpected error:\n"
                  f"{traceback.format_exc()}")
