from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Endpoint, Project, RequestLog, Resource


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
            "mode",
            "resource",
            "description",
            "request_example",
            "status_code",
            "response_body",
            "headers",
            "delay_ms",
            "error_rate",
            "error_status",
            "created_at",
        ]

    def validate(self, attrs):
        mode = attrs.get("mode", getattr(self.instance, "mode", "static"))
        resource = attrs.get(
            "resource", getattr(self.instance, "resource", "")
        )
        if mode == "stateful" and not resource:
            raise serializers.ValidationError(
                {"resource": ["Required for stateful endpoints."]}
            )
        return attrs


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ["id", "name", "items", "initial_items"]


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
