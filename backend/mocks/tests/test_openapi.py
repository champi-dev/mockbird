from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from mocks.models import Endpoint, Project
from mocks.openapi_import import parse_openapi

SPEC = """
openapi: 3.0.0
info:
  title: Pet API
paths:
  /pets:
    get:
      summary: List pets
      parameters:
        - name: limit
          in: query
          schema: {type: integer, example: 10}
      responses:
        "200":
          content:
            application/json:
              example:
                - {id: 1, name: Rex}
                - {id: 2, name: Bella}
    post:
      summary: Create a pet
      requestBody:
        content:
          application/json:
            example: {name: Fido}
      responses:
        "201":
          content:
            application/json:
              example: {id: 3, name: Fido}
  /pets/{petId}:
    get:
      summary: Get one pet
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                properties:
                  id: {type: integer}
                  name: {type: string}
    delete:
      responses:
        "204": {description: deleted}
"""


class ParseOpenApiTests(APITestCase):
    def test_parses_paths_methods_and_examples(self):
        eps = parse_openapi(SPEC)
        routes = {(e["method"], e["path"]) for e in eps}
        self.assertEqual(
            routes,
            {
                ("GET", "/pets"),
                ("POST", "/pets"),
                ("GET", "/pets/{petId}"),
                ("DELETE", "/pets/{petId}"),
            },
        )

    def test_uses_examples_status_and_descriptions(self):
        eps = {(e["method"], e["path"]): e for e in parse_openapi(SPEC)}
        listed = eps[("GET", "/pets")]
        self.assertEqual(listed["status_code"], 200)
        self.assertEqual(listed["response_body"][0]["name"], "Rex")
        self.assertEqual(listed["description"], "List pets")
        self.assertEqual(
            listed["request_example"]["query_params"], {"limit": 10}
        )

        created = eps[("POST", "/pets")]
        self.assertEqual(created["status_code"], 201)
        self.assertEqual(
            created["request_example"]["body"], {"name": "Fido"}
        )

        deleted = eps[("DELETE", "/pets/{petId}")]
        self.assertEqual(deleted["status_code"], 204)

    def test_synthesizes_example_from_schema(self):
        eps = {(e["method"], e["path"]): e for e in parse_openapi(SPEC)}
        one = eps[("GET", "/pets/{petId}")]
        self.assertEqual(one["response_body"], {"id": 0, "name": "string"})

    def test_invalid_spec_raises(self):
        with self.assertRaises(ValueError):
            parse_openapi("not: a spec")
        with self.assertRaises(ValueError):
            parse_openapi(":::")


class ImportApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw123456")
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(owner=self.user, name="Pets")
        self.url = f"/api/projects/{self.project.id}/import-openapi/"

    def test_imports_spec(self):
        r = self.client.post(self.url, {"spec": SPEC}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Endpoint.objects.count(), 4)

    def test_skips_existing_routes(self):
        Endpoint.objects.create(
            project=self.project, method="GET", path="/pets"
        )
        r = self.client.post(self.url, {"spec": SPEC}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.data), 3)

    def test_rejects_garbage(self):
        r = self.client.post(self.url, {"spec": ":::"}, format="json")
        self.assertEqual(r.status_code, 400)
