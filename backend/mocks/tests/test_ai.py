from unittest.mock import ANY, patch

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APITestCase

from mocks.ai import AiUnavailable, parse_endpoints
from mocks.models import Endpoint, Project

FAKE_ENDPOINTS = [
    {
        "method": "GET",
        "path": "/todos",
        "status_code": 200,
        "response_body": [{"id": 1, "title": "Buy milk", "done": False}],
    },
    {
        "method": "POST",
        "path": "/todos",
        "status_code": 201,
        "response_body": {"id": 2, "title": "New todo", "done": False},
    },
]


class ParseEndpointsTests(APITestCase):
    def test_accepts_valid_payload(self):
        parsed = parse_endpoints({"endpoints": FAKE_ENDPOINTS})
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["method"], "GET")

    def test_passes_description_and_request_example(self):
        parsed = parse_endpoints(
            {
                "endpoints": [
                    {
                        "method": "POST",
                        "path": "/todos",
                        "description": "Create a todo",
                        "request_example": {"body": {"title": "x"}},
                    },
                    {
                        "method": "GET",
                        "path": "/todos",
                        "request_example": "not a dict",
                    },
                ]
            }
        )
        self.assertEqual(parsed[0]["description"], "Create a todo")
        self.assertEqual(
            parsed[0]["request_example"], {"body": {"title": "x"}}
        )
        self.assertEqual(parsed[1]["request_example"], {})

    def test_rejects_bad_method_and_clamps_fields(self):
        parsed = parse_endpoints(
            {
                "endpoints": [
                    {"method": "TRACE", "path": "/x"},
                    {
                        "method": "get",
                        "path": "todos",
                        "status_code": 9999,
                        "delay_ms": 999999,
                    },
                ]
            }
        )
        self.assertEqual(len(parsed), 1)
        ep = parsed[0]
        self.assertEqual(ep["method"], "GET")
        self.assertEqual(ep["path"], "/todos")
        self.assertEqual(ep["status_code"], 200)
        self.assertLessEqual(ep["delay_ms"], 30000)


@override_settings(OPENAI_API_KEY="test-key")
class GenerateApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw123456")
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(owner=self.user, name="Todos")
        self.url = f"/api/projects/{self.project.id}/generate/"

    def test_requires_description(self):
        r = self.client.post(self.url, {}, format="json")
        self.assertEqual(r.status_code, 400)

    @patch("mocks.views.generate_endpoints", return_value=FAKE_ENDPOINTS)
    def test_creates_endpoints_from_ai(self, gen):
        r = self.client.post(
            self.url, {"description": "a todo API"}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.data), 2)
        self.assertEqual(Endpoint.objects.count(), 2)
        gen.assert_called_once_with("a todo API", ANY)

    @patch("mocks.views.generate_endpoints", return_value=FAKE_ENDPOINTS)
    def test_skips_duplicate_routes(self, gen):
        Endpoint.objects.create(
            project=self.project, method="GET", path="/todos"
        )
        r = self.client.post(
            self.url, {"description": "a todo API"}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Endpoint.objects.count(), 2)

    @patch(
        "mocks.views.generate_endpoints",
        side_effect=AiUnavailable("no key"),
    )
    def test_503_when_ai_unavailable(self, gen):
        r = self.client.post(
            self.url, {"description": "x"}, format="json"
        )
        self.assertEqual(r.status_code, 503)

    def test_cannot_generate_on_others_project(self):
        other = User.objects.create_user("eve", password="pw123456")
        theirs = Project.objects.create(owner=other, name="Secret")
        r = self.client.post(
            f"/api/projects/{theirs.id}/generate/",
            {"description": "x"},
            format="json",
        )
        self.assertEqual(r.status_code, 404)
