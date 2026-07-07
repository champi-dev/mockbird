import json

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase

from mocks.matching import find_endpoint
from mocks.models import Endpoint, Project, Resource


def make_project(name="Shop"):
    user = User.objects.create_user(name.lower(), password="pw123456")
    return Project.objects.create(owner=user, name=name)


class PathParamMatchingTests(TestCase):
    def setUp(self):
        self.project = make_project()
        self.detail = Endpoint.objects.create(
            project=self.project,
            method="GET",
            path="/products/{id}",
            response_body={"id": "{{params.id}}", "name": "Widget"},
        )
        self.exact = Endpoint.objects.create(
            project=self.project,
            method="GET",
            path="/products/special",
            response_body={"special": True},
        )

    def test_exact_match_wins_over_pattern(self):
        ep, params = find_endpoint(self.project, "GET", "/products/special")
        self.assertEqual(ep, self.exact)
        self.assertEqual(params, {})

    def test_pattern_match_captures_params(self):
        ep, params = find_endpoint(self.project, "GET", "/products/7")
        self.assertEqual(ep, self.detail)
        self.assertEqual(params, {"id": "7"})

    def test_no_match(self):
        ep, _ = find_endpoint(self.project, "GET", "/products/7/reviews")
        self.assertIsNone(ep)

    def test_template_substitution_in_response(self):
        r = self.client.get(f"/m/{self.project.slug}/products/7")
        self.assertEqual(
            json.loads(r.content), {"id": "7", "name": "Widget"}
        )


class StatefulCrudTests(TestCase):
    def setUp(self):
        self.project = make_project()
        seed = [
            {"id": 1, "name": "Widget A"},
            {"id": 2, "name": "Widget B"},
        ]
        self.resource = Resource.objects.create(
            project=self.project,
            name="products",
            initial_items=seed,
            items=seed,
        )
        for method, path in [
            ("GET", "/products"),
            ("GET", "/products/{id}"),
            ("POST", "/products"),
            ("PATCH", "/products/{id}"),
            ("DELETE", "/products/{id}"),
        ]:
            Endpoint.objects.create(
                project=self.project,
                method=method,
                path=path,
                mode="stateful",
                resource="products",
            )

    def url(self, path):
        return f"/m/{self.project.slug}{path}"

    def test_list_returns_current_state(self):
        r = self.client.get(self.url("/products"))
        self.assertEqual(len(json.loads(r.content)), 2)

    def test_detail_found_and_missing(self):
        r = self.client.get(self.url("/products/1"))
        self.assertEqual(json.loads(r.content)["name"], "Widget A")
        self.assertEqual(
            self.client.get(self.url("/products/99")).status_code, 404
        )

    def test_post_creates_with_next_id(self):
        r = self.client.post(
            self.url("/products"),
            data=json.dumps({"name": "Widget C"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(json.loads(r.content)["id"], 3)
        r = self.client.get(self.url("/products"))
        self.assertEqual(len(json.loads(r.content)), 3)

    def test_patch_merges_fields(self):
        r = self.client.patch(
            self.url("/products/2"),
            data=json.dumps({"name": "Renamed"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.content)
        self.assertEqual(body["name"], "Renamed")
        self.assertEqual(body["id"], 2)

    def test_delete_removes_then_404(self):
        r = self.client.delete(self.url("/products/1"))
        self.assertEqual(r.status_code, 204)
        self.assertEqual(
            self.client.get(self.url("/products/1")).status_code, 404
        )

    def test_state_survives_across_requests(self):
        self.client.delete(self.url("/products/1"))
        self.client.post(
            self.url("/products"),
            data=json.dumps({"name": "Widget C"}),
            content_type="application/json",
        )
        r = self.client.get(self.url("/products"))
        names = [i["name"] for i in json.loads(r.content)]
        self.assertEqual(names, ["Widget B", "Widget C"])


class ResourceApiTests(APITestCase):
    def setUp(self):
        self.project = make_project()
        self.client.force_authenticate(self.project.owner)
        self.resource = Resource.objects.create(
            project=self.project,
            name="products",
            initial_items=[{"id": 1}],
            items=[{"id": 1}, {"id": 2}],
        )

    def test_list_resources(self):
        r = self.client.get(f"/api/projects/{self.project.id}/resources/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data[0]["name"], "products")
        self.assertEqual(len(r.data[0]["items"]), 2)

    def test_reset_restores_seed(self):
        r = self.client.post(
            f"/api/projects/{self.project.id}/resources/"
            f"{self.resource.id}/reset/"
        )
        self.assertEqual(r.status_code, 200)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.items, [{"id": 1}])

    def test_stateful_endpoint_creation_seeds_resource(self):
        r = self.client.post(
            f"/api/projects/{self.project.id}/endpoints/",
            {
                "method": "GET",
                "path": "/orders",
                "mode": "stateful",
                "resource": "orders",
                "response_body": [{"id": 1, "total": 9.5}],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        res = Resource.objects.get(project=self.project, name="orders")
        self.assertEqual(res.items, [{"id": 1, "total": 9.5}])

    def test_stateful_requires_resource_name(self):
        r = self.client.post(
            f"/api/projects/{self.project.id}/endpoints/",
            {"method": "GET", "path": "/x", "mode": "stateful"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
