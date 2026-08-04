from __future__ import annotations

from rest_framework import serializers

from apps.workspace.models import Comment, Notification


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.username", read_only=True, default=None)
    mentions = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False, default=list
    )

    class Meta:
        model = Comment
        fields = [
            "id",
            "organization",
            "entity_type",
            "entity_id",
            "parent",
            "author_name",
            "body",
            "is_edited",
            "is_struck",
            "mentions",
            "created_at",
        ]
        read_only_fields = ["id", "author_name", "is_edited", "is_struck", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "title",
            "body",
            "link_entity_type",
            "link_entity_id",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields


class MentionableUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
