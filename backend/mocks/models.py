import secrets

from django.conf import settings
from django.db import models
from django.utils.text import slugify

HTTP_METHODS = [
    ("GET", "GET"),
    ("POST", "POST"),
    ("PUT", "PUT"),
    ("PATCH", "PATCH"),
    ("DELETE", "DELETE"),
]


def _unique_slug(name: str) -> str:
    base = slugify(name)[:32] or "project"
    return f"{base}-{secrets.token_hex(3)}"


class Project(models.Model):
    """A named collection of mock endpoints owned by one user."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=48, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.slug})"


class Endpoint(models.Model):
    """One mock route: method + path -> configured response."""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="endpoints"
    )
    method = models.CharField(max_length=7, choices=HTTP_METHODS)
    path = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, default="")
    request_example = models.JSONField(
        default=dict,
        blank=True,
        help_text="Documents expected query params / request body",
    )
    status_code = models.PositiveSmallIntegerField(default=200)
    response_body = models.JSONField(default=dict, blank=True)
    headers = models.JSONField(default=dict, blank=True)
    delay_ms = models.PositiveIntegerField(default=0)
    error_rate = models.PositiveSmallIntegerField(
        default=0, help_text="0-100 % of requests forced to error_status"
    )
    error_status = models.PositiveSmallIntegerField(default=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["path", "method"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "method", "path"],
                name="unique_route_per_project",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.path.startswith("/"):
            self.path = "/" + self.path
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.method} {self.path}"


class RequestLog(models.Model):
    """A record of one incoming request to a live mock URL."""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="logs"
    )
    method = models.CharField(max_length=7)
    path = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    status_code = models.PositiveSmallIntegerField()
    matched = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
