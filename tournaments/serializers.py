from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Tournament


class TournamentSerializer(serializers.Serializer):
    """Ręczny serializator modelu Tournament."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(required=True, max_length=150)
    slug = serializers.SlugField(required=True, max_length=160)
    organizer_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="organizer",
    )
    start_date = serializers.DateTimeField(required=True)
    max_participants = serializers.IntegerField(required=True, min_value=2)
    is_active = serializers.BooleanField(default=True)
    created_at = serializers.DateTimeField(read_only=True)

    def create(self, validated_data):
        return Tournament.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get("name", instance.name)
        instance.slug = validated_data.get("slug", instance.slug)
        instance.organizer = validated_data.get("organizer", instance.organizer)
        instance.start_date = validated_data.get(
            "start_date",
            instance.start_date,
        )
        instance.max_participants = validated_data.get(
            "max_participants",
            instance.max_participants,
        )
        instance.is_active = validated_data.get("is_active", instance.is_active)
        instance.save()
        return instance
