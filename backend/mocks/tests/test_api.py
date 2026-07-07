from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from mocks.models import Endpoint, Project


class AuthTests(APITestCase):
    def test_register_and_login(self):
        r = self.client.post(
            "/api/auth/register/",
            {"username": "bob", "password": "secret123!"},
        )
        self.assertEqual(r.status_code, 201)
        r = self.client.post(
            "/api/auth/token/",
            {"username": "bob", "password": "secret123!"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)

    def test_register_rejects_duplicate_username(self):
        User.objects.create_user(username="bob", password="x1234567")
        r = self.client.post(
            "/api/auth/register/",
            {"username": "bob", "password": "secret123!"},
        )
        self.assertEqual(r.status_code, 400)


class ProjectApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw123456")
        self.other = User.objects.create_user("eve", password="pw123456")
        self.client.force_authenticate(self.user)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/projects/").status_code, 401)

    def test_create_and_list_own_projects_only(self):
        Project.objects.create(owner=self.other, name="Not mine")
        r = self.client.post("/api/projects/", {"name": "Mine"})
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["slug"])
        r = self.client.get("/api/projects/")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["name"], "Mine")

    def test_cannot_access_others_project(self):
        p = Project.objects.create(owner=self.other, name="Secret")
        r = self.client.get(f"/api/projects/{p.id}/")
        self.assertEqual(r.status_code, 404)


class EndpointApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw123456")
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(owner=self.user, name="Shop")

    def test_crud_endpoint(self):
        r = self.client.post(
            f"/api/projects/{self.project.id}/endpoints/",
            {
                "method": "GET",
                "path": "/users/42",
                "status_code": 200,
                "response_body": {"id": 42, "name": "Ada"},
                "delay_ms": 100,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        ep_id = r.data["id"]

        r = self.client.patch(
            f"/api/projects/{self.project.id}/endpoints/{ep_id}/",
            {"status_code": 404},
            format="json",
        )
        self.assertEqual(r.data["status_code"], 404)

        r = self.client.delete(
            f"/api/projects/{self.project.id}/endpoints/{ep_id}/"
        )
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Endpoint.objects.count(), 0)

    def test_validates_error_rate_range(self):
        r = self.client.post(
            f"/api/projects/{self.project.id}/endpoints/",
            {"method": "GET", "path": "/x", "error_rate": 150},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
