"""Mock-server tests: the nine behaviors that define /m/<slug>/...
— configured JSON/status/headers, 404s (path, project, method),
logging of matched AND unmatched hits, delay, forced errors, and
root-path endpoints.
"""
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from mocks.models import Endpoint, Project, RequestLog


class MockServerTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("alice", password="pw123456")
        self.project = Project.objects.create(owner=user, name="Shop")
        self.endpoint = Endpoint.objects.create(
            project=self.project,
            method="GET",
            path="/users/42",
            status_code=200,
            response_body={"id": 42, "name": "Ada"},
            headers={"X-Mock": "yes"},
        )

    def url(self, path=""):
        return f"/m/{self.project.slug}{path}"

    def test_returns_configured_json_status_and_headers(self):
        r = self.client.get(self.url("/users/42"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.content), {"id": 42, "name": "Ada"})
        self.assertEqual(r["X-Mock"], "yes")

    def test_unknown_path_returns_404_json(self):
        r = self.client.get(self.url("/nope"))
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", json.loads(r.content))

    def test_unknown_project_returns_404(self):
        r = self.client.get("/m/no-such-slug/users/42")
        self.assertEqual(r.status_code, 404)

    def test_method_must_match(self):
        r = self.client.post(self.url("/users/42"))
        self.assertEqual(r.status_code, 404)

    def test_request_is_logged(self):
        self.client.get(self.url("/users/42"))
        log = RequestLog.objects.get()
        self.assertEqual(log.method, "GET")
        self.assertEqual(log.path, "/users/42")
        self.assertEqual(log.status_code, 200)
        self.assertTrue(log.matched)

    def test_unmatched_request_is_logged_too(self):
        self.client.get(self.url("/nope"))
        self.assertFalse(RequestLog.objects.get().matched)

    def test_delay_is_applied(self):
        self.endpoint.delay_ms = 250
        self.endpoint.save()
        # patch() swaps time.sleep for a recording fake INSIDE the
        # with-block: the test proves sleep(0.25) was requested
        # without actually waiting 250ms. Note the patch target is
        # where it's USED (mocks.mock_server.time.sleep), not where
        # it's defined (time.sleep) — the golden rule of patching.
        with patch("mocks.mock_server.time.sleep") as sleep:
            self.client.get(self.url("/users/42"))
        sleep.assert_called_once_with(0.25)

    def test_error_rate_forces_error_status(self):
        # rate=100 makes the dice roll deterministic — always fail.
        self.endpoint.error_rate = 100
        self.endpoint.error_status = 503
        self.endpoint.save()
        r = self.client.get(self.url("/users/42"))
        self.assertEqual(r.status_code, 503)

    def test_root_path_endpoint(self):
        Endpoint.objects.create(
            project=self.project,
            method="GET",
            path="/",
            response_body={"ok": True},
        )
        r = self.client.get(self.url("/"))
        self.assertEqual(json.loads(r.content), {"ok": True})


class MockCorsTests(TestCase):
    """Mock endpoints must be consumable cross-origin from any app."""

    def setUp(self):
        from django.contrib.auth.models import User
        from mocks.models import Endpoint, Project
        user = User.objects.create_user('corsu', password='x')
        self.project = Project.objects.create(owner=user, name='cors')
        Endpoint.objects.create(
            project=self.project, method='GET', path='/things',
            response_body=[{'id': 1}], status_code=200,
        )
        self.base = f'/m/{self.project.slug}'

    def test_any_origin_allowed_on_mock_response(self):
        r = self.client.get(f'{self.base}/things', HTTP_ORIGIN='https://elsewhere.app')
        self.assertEqual(r['Access-Control-Allow-Origin'], '*')

    def test_preflight_succeeds_for_any_method_and_headers(self):
        r = self.client.options(
            f'{self.base}/things',
            HTTP_ORIGIN='https://elsewhere.app',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='DELETE',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='x-custom, content-type',
        )
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r['Access-Control-Allow-Origin'], '*')
        self.assertIn('DELETE', r['Access-Control-Allow-Methods'])
        self.assertIn('x-custom', r['Access-Control-Allow-Headers'])

    def test_dashboard_api_stays_restricted(self):
        r = self.client.get('/api/projects/', HTTP_ORIGIN='https://elsewhere.app')
        self.assertNotIn('Access-Control-Allow-Origin', r)
