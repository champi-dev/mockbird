from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from mocks.models import Endpoint, Project, RequestLog
from mocks.streaming import iter_log_events


class LogStreamTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw123456")
        self.project = Project.objects.create(owner=self.user, name="S")
        self.token = str(AccessToken.for_user(self.user))
        self.url = f"/api/projects/{self.project.id}/logs/stream/"

    def test_rejects_missing_or_bad_token(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(
            self.client.get(self.url, {"token": "junk"}).status_code, 401
        )

    def test_404_for_foreign_project(self):
        eve = User.objects.create_user("eve", password="pw123456")
        token = str(AccessToken.for_user(eve))
        r = self.client.get(self.url, {"token": token})
        self.assertEqual(r.status_code, 404)

    def test_stream_response_headers(self):
        r = self.client.get(self.url, {"token": self.token})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/event-stream")
        r.close()

    @patch("mocks.streaming.time.sleep")
    def test_iterator_emits_new_logs(self, _sleep):
        RequestLog.objects.create(
            project=self.project, method="GET", path="/a", status_code=200
        )
        gen = iter_log_events(self.project, last_id=0, max_seconds=1)
        first = next(gen)
        self.assertTrue(first.startswith("data: "))
        self.assertIn('"path": "/a"', first)
        self.assertEqual(next(gen), ": keepalive\n\n")


class PublicDocsTests(APITestCase):
    def setUp(self):
        user = User.objects.create_user("alice", password="pw123456")
        self.project = Project.objects.create(owner=user, name="Shop")
        Endpoint.objects.create(
            project=self.project,
            method="GET",
            path="/products",
            description="List products",
        )

    def test_docs_are_public(self):
        r = self.client.get(f"/api/docs/{self.project.slug}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "Shop")
        self.assertEqual(r.data["endpoints"][0]["path"], "/products")

    def test_unknown_slug_404(self):
        self.assertEqual(
            self.client.get("/api/docs/nope-000000/").status_code, 404
        )

    def test_no_sensitive_fields(self):
        r = self.client.get(f"/api/docs/{self.project.slug}/")
        self.assertNotIn("owner", r.data)
        self.assertNotIn("logs", r.data)
