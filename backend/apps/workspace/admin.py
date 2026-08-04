from __future__ import annotations

from django.contrib import admin

from apps.workspace.models import Comment, Notification


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("entity_type", "entity_id", "author", "is_struck", "created_at")
    list_filter = ("entity_type", "is_struck")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "type", "title", "is_read", "created_at")
    list_filter = ("type", "is_read")
