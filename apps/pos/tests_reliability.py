"""Регрессии устойчивости: health без сессии, замок процесса, журнал."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingTCPServer
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import connection
from django.test import Client, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.orders.models import Shift


def _session_writes(queries) -> list[str]:
    found = []
    for query in queries:
        sql = query["sql"].lstrip().lower()
        if "django_session" not in sql:
            continue
        if sql.startswith(("insert", "update", "delete")):
            found.append(sql.split()[0])
    return found


class HealthAndQueueTests(TestCase):
    def test_health_does_not_open_a_session(self) -> None:
        before = Session.objects.count()
        for _ in range(5):
            client = Client()
            with CaptureQueriesContext(connection) as ctx:
                response = client.get(reverse("pos:health"))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content.startswith(b"ok "))
            self.assertEqual(response["Cache-Control"], "no-store")
            self.assertEqual(_session_writes(ctx.captured_queries), [])
        self.assertEqual(Session.objects.count(), before)

    def test_queue_poll_does_not_write_the_session_or_orders(self) -> None:
        user = get_user_model().objects.create_user(username="cashier", password="cashier")
        Shift.objects.create(
            business_date=date(2026, 11, 6),
            is_open=True,
            opened_by=user,
            cashier_name="Аня",
        )
        client = Client()
        client.force_login(user)
        url = reverse("pos:queue_fragment")
        self.assertEqual(client.get(url, {"queue": "active"}).status_code, 200)
        with CaptureQueriesContext(connection) as ctx:
            response = client.get(url, {"queue": "active"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_session_writes(ctx.captured_queries), [])
        writes = [
            query["sql"].lstrip().split()[0].lower()
            for query in ctx.captured_queries
            if query["sql"].lstrip().lower().startswith(("insert", "update", "delete"))
        ]
        self.assertEqual(writes, [])


class ProcessGuardTests(SimpleTestCase):
    def test_second_lock_is_refused_until_the_holder_closes_it(self) -> None:
        from desktop.runtime import acquire_instance_lock

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cashmachine.instance.lock"
            first = acquire_instance_lock(path)
            self.assertIsNotNone(first)
            try:
                self.assertIsNone(acquire_instance_lock(path))
            finally:
                first.close()
            third = acquire_instance_lock(path)
            self.assertIsNotNone(third)
            third.close()

    def test_health_url_is_not_the_shift_page(self) -> None:
        from desktop.runtime import health_url

        self.assertEqual(
            health_url("http://127.0.0.1:8765/"),
            "http://127.0.0.1:8765/pos/health/",
        )

    def test_wait_accepts_a_slow_200_without_a_second_request(self) -> None:
        from desktop.runtime import wait_for_http

        state = {"in_flight": 0, "max": 0, "count": 0}
        lock = threading.Lock()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                with lock:
                    state["in_flight"] += 1
                    state["count"] += 1
                    state["max"] = max(state["max"], state["in_flight"])
                try:
                    time.sleep(0.4)
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"ok")
                finally:
                    with lock:
                        state["in_flight"] -= 1

            def log_message(self, fmt: str, *args) -> None:
                return

        server = ThreadingTCPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            ok, detail = wait_for_http(f"http://127.0.0.1:{port}/pos/health/", timeout=3)
        finally:
            server.shutdown()
            server.server_close()
        self.assertTrue(ok)
        self.assertEqual(detail, "200")
        self.assertEqual(state["count"], 1)
        self.assertEqual(state["max"], 1)

    def test_wall_clock_is_not_the_wait_deadline(self) -> None:
        from desktop.runtime import wait_for_http

        # Первые чтения держат срок открытым, следующее уезжает вперёд.
        # Так видно, что цикл смотрит на переданные часы, а не на time.time.
        # Часы по умолчанию — monotonic: прыжок ноутбука ожидание не обрывает.
        reads = {"n": 0}

        def jumping_clock() -> float:
            reads["n"] += 1
            if reads["n"] < 3:
                return 0.0
            return 10_000.0

        self.assertIs(wait_for_http.__defaults__[-1], time.monotonic)
        ok, detail = wait_for_http(
            "http://127.0.0.1:9/pos/health/",
            timeout=30,
            clock=jumping_clock,
        )
        self.assertFalse(ok)
        self.assertNotEqual(detail, "200")
        self.assertGreaterEqual(reads["n"], 3)

    def test_wait_stops_when_the_server_thread_is_already_dead(self) -> None:
        from desktop.runtime import wait_for_http

        def _dead() -> None:
            return None

        server = threading.Thread(target=_dead)
        server.start()
        server.join()
        ok, detail = wait_for_http("http://127.0.0.1:9/pos/health/", timeout=5, server=server)
        self.assertFalse(ok)
        self.assertEqual(detail, "server_thread_dead")

    def test_boot_line_names_the_build_and_stays_bounded(self) -> None:
        from desktop.bootlog import write_boot

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cashmachine.sqlite3"
            with patch.dict(os.environ, {"CASHMACHINE_DB_PATH": str(db)}):
                write_boot("runtime_hook_ok")
                text = (Path(tmp) / "cashmachine-boot.log").read_text(encoding="utf-8")
                for _ in range(30):
                    write_boot("runtime_hook_ok", limit=180, keep=70)
                size = (Path(tmp) / "cashmachine-boot.log").stat().st_size
        self.assertIn("event=runtime_hook_ok", text)
        self.assertIn(f"pid={os.getpid()}", text)
        self.assertIn("version=", text)
        self.assertIn("commit=", text)
        self.assertIn("wall=", text)
        self.assertIn("wall_clock=unreliable", text)
        self.assertIn("mono=", text)
        self.assertLess(size, 400)

    def test_identity_tokens_have_no_whitespace(self) -> None:
        from desktop.identity import runtime_identity

        ident = runtime_identity()
        self.assertTrue(ident["version"])
        self.assertTrue(ident["commit"])
        self.assertNotIn(" ", ident["version"])
        self.assertNotIn(" ", ident["commit"])
        self.assertNotIn("\n", ident["commit"])

    def test_dead_webview_profiles_are_removed(self) -> None:
        from desktop.runtime import prepare_webview_storage

        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            root = app_dir / "webview"
            root.mkdir()
            (root / "999999").mkdir()
            (root / "999999" / "cache").write_text("x", encoding="utf-8")
            (root / str(os.getpid())).mkdir()
            (root / "notes").mkdir()
            path = prepare_webview_storage(app_dir)
            self.assertEqual(path, root / str(os.getpid()))
            self.assertFalse((root / "999999").exists())
            self.assertTrue((root / "notes").is_dir())
            self.assertTrue(path.is_dir())

    def test_access_filter_drops_queue_200_and_keeps_errors(self) -> None:
        from desktop.logsetup import QuietAccessFilter

        filt = QuietAccessFilter()
        ok = logging.LogRecord(
            "django.server",
            logging.INFO,
            "",
            0,
            '"GET /pos/queue/?queue=active HTTP/1.1" 200 1008',
            None,
            None,
        )
        failed = logging.LogRecord(
            "django.server",
            logging.ERROR,
            "",
            0,
            '"GET /pos/queue/?queue=active HTTP/1.1" 500 145',
            None,
            None,
        )
        shift = logging.LogRecord(
            "django.server",
            logging.INFO,
            "",
            0,
            '"GET /pos/shift/ HTTP/1.1" 200 3103',
            None,
            None,
        )
        self.assertFalse(filt.filter(ok))
        self.assertTrue(filt.filter(failed))
        self.assertTrue(filt.filter(shift))

    def test_log_rotation_bounds_the_file(self) -> None:
        from desktop.logsetup import configure_process_logging

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cashmachine.log"
            handler = configure_process_logging(path, max_bytes=600, backup_count=1)
            logger = logging.getLogger("cashmachine.testrot")
            try:
                for index in range(40):
                    logger.info("event=pad %s %s", index, "x" * 80)
                handler.flush()
                self.assertTrue(path.exists())
                self.assertLessEqual(path.stat().st_size, 2000)
                backups = list(Path(tmp).glob("cashmachine.log*"))
                self.assertGreaterEqual(len(backups), 2)
            finally:
                logging.getLogger().removeHandler(handler)
                handler.close()
