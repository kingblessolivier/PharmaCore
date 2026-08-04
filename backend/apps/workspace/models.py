"""Workspace models: contextual comments (on any record) and notifications.

Comments attach to any entity via (entity_type, entity_id) and can be scoped to an
organization. A @mention creates a notification for the mentioned user.
See docs/10-collaboration-notifications-and-tools.md.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Comment(models.Model):
    organization = models.ForeignKey(
        "iam.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comments",
    )
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=64)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    body = models.TextField()
    is_edited = models.BooleanField(default=False)
    is_struck = models.BooleanField(default=False)  # soft delete; kept for traceability
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["entity_type", "entity_id", "created_at"])]

    def __str__(self) -> str:
        return f"comment on {self.entity_type}#{self.entity_id}"


class Notification(models.Model):
    class Type(models.TextChoices):
        MENTION = "MENTION", "Mention"
        SYSTEM = "SYSTEM", "System"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=30, choices=Type.choices, default=Type.MENTION)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    link_entity_type = models.CharField(max_length=50, blank=True, default="")
    link_entity_id = models.CharField(max_length=64, blank=True, default="")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read", "created_at"])]

    def __str__(self) -> str:
        return f"{self.type} -> {self.recipient_id}: {self.title}"
