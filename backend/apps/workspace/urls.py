from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.workspace.views import CommentViewSet, MentionableUsersView, NotificationViewSet

router = DefaultRouter()
router.register("comments", CommentViewSet, basename="comment")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("mentionable-users", MentionableUsersView.as_view(), name="mentionable-users"),
    *router.urls,
]
