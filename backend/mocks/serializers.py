from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Endpoint, Project, RequestLog


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class EndpointSerializer(serializers.ModelSerializer):
    error_rate = serializers.IntegerField(
        min_value=0, max_value=100, required=False
    )

    class Meta:
        model = Endpoint
        fields = [
            "id",
            "method",
            "path",
            "status_code",
            "response_body",
            "headers",
            "delay_ms",
            "error_rate",
            "error_status",
            "created_at",
        ]


class ProjectSerializer(serializers.ModelSerializer):
    endpoint_count = serializers.IntegerField(
        source="endpoints.count", read_only=True
    )

    class Meta:
        model = Project
        fields = ["id", "name", "slug", "created_at", "endpoint_count"]
        read_only_fields = ["slug"]


class RequestLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestLog
        fields = [
            "id",
            "method",
            "path",
            "body",
            "status_code",
            "matched",
            "created_at",
        ]
