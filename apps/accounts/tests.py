"""Автологин кассы не должен переписывать сессию на каждом запросе."""

from unittest.mock import patch

from django.contrib.auth import get_user_model, login as auth_login
from django.db import connection
from django.test import TestCase
from django.urls import reverse


class AutoAdminMiddlewareTests(TestCase):
    def test_anonymous_becomes_admin_once_and_keeps_the_session_key(self):
        url = reverse("pos:shift")
        with patch("apps.accounts.middleware.login", wraps=auth_login) as mocked:
            first = self.client.get(url)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(mocked.call_count, 1)
            key = self.client.session.session_key
            admin = get_user_model().objects.get(username="admin")
            self.assertEqual(str(self.client.session["_auth_user_id"]), str(admin.pk))

            second = self.client.get(url)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(mocked.call_count, 1)
            self.assertEqual(self.client.session.session_key, key)

    def test_existing_anonymous_session_is_stamped_without_login(self):
        session = self.client.session
        session["scratch"] = "1"
        session.save()
        key = self.client.session.session_key

        with patch("apps.accounts.middleware.login", wraps=auth_login) as mocked:
            response = self.client.get(reverse("pos:shift"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked.call_count, 0)
        self.assertEqual(self.client.session.session_key, key)
        self.assertEqual(self.client.session["scratch"], "1")
        admin = get_user_model().objects.get(username="admin")
        self.assertEqual(str(self.client.session["_auth_user_id"]), str(admin.pk))

    def test_already_logged_in_user_is_not_cycled_or_replaced(self):
        User = get_user_model()
        cashier = User.objects.create_user(
            username="cashier", password="pw", role=User.ROLE_CASHIER
        )
        self.client.force_login(cashier)
        key = self.client.session.session_key
        with patch("apps.accounts.middleware.login") as mocked:
            self.client.get(reverse("pos:shift"))
            self.client.get(reverse("pos:shift"))
        self.assertEqual(mocked.call_count, 0)
        self.assertEqual(str(self.client.session["_auth_user_id"]), str(cashier.pk))
        self.assertEqual(self.client.session.session_key, key)


class SqliteSetupTests(TestCase):
    def test_file_database_uses_wal_and_waits_on_locks(self):
        import copy
        import tempfile
        from pathlib import Path

        from django.db.backends.sqlite3.base import DatabaseWrapper

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA busy_timeout")
            live_busy = cursor.fetchone()[0]
        self.assertGreaterEqual(int(live_busy), 20_000)

        with tempfile.TemporaryDirectory() as tmp:
            settings_dict = copy.deepcopy(connection.settings_dict)
            settings_dict["NAME"] = str(Path(tmp) / "pos.sqlite3")
            wrapper = DatabaseWrapper(settings_dict, alias="walcheck")
            try:
                wrapper.ensure_connection()
                with wrapper.cursor() as cursor:
                    cursor.execute("PRAGMA journal_mode")
                    mode = cursor.fetchone()[0]
                    cursor.execute("PRAGMA busy_timeout")
                    busy = cursor.fetchone()[0]
                    cursor.execute("PRAGMA synchronous")
                    sync = cursor.fetchone()[0]
            finally:
                wrapper.close()
        self.assertEqual(str(mode).lower(), "wal")
        self.assertGreaterEqual(int(busy), 20_000)
        self.assertEqual(int(sync), 1)
