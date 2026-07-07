from django.contrib.auth.models import User
from django.test import TestCase

from mocks.models import Endpoint, Project, RequestLog


def make_user(name="alice"):
    return User.objects.create_user(username=name, password="pass12345")


class ProjectModelTests(TestCase):
    def test_slug_is_auto_generated_and_unique(self):
        user = make_user()
        p1 = Project.objects.create(owner=user, name="My API")
        p2 = Project.objects.create(owner=user, name="My API")
        self.assertTrue(p1.slug)
        self.assertNotEqual(p1.slug, p2.slug)

    def test_str(self):
        user = make_user()
        p = Project.objects.create(owner=user, name="Billing")
        self.assertIn("Billing", str(p))


class EndpointModelTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(
            owner=make_user(), name="Shop"
        )

    def test_defaults(self):
        ep = Endpoint.objects.create(
            project=self.project, method="GET", path="/users"
        )
        self.assertEqual(ep.status_code, 200)
        self.assertEqual(ep.delay_ms, 0)
        self.assertEqual(ep.error_rate, 0)
        self.assertEqual(ep.response_body, {})

    def test_path_is_normalized_with_leading_slash(self):
        ep = Endpoint.objects.create(
            project=self.project, method="GET", path="users/42"
        )
        self.assertEqual(ep.path, "/users/42")

    def test_unique_method_path_per_project(self):
        Endpoint.objects.create(
            project=self.project, method="GET", path="/users"
        )
        with self.assertRaises(Exception):
            Endpoint.objects.create(
                project=self.project, method="GET", path="/users"
            )


class RequestLogModelTests(TestCase):
    def test_log_creation(self):
        project = Project.objects.create(owner=make_user(), name="Logs")
        log = RequestLog.objects.create(
            project=project,
            method="POST",
            path="/orders",
            body='{"a":1}',
            status_code=201,
        )
        self.assertIsNotNone(log.created_at)
