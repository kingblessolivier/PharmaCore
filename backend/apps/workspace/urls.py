from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.workspace.views import (
    CommentViewSet,
    MentionableUsersView,
    MyWorkView,  # noqa: F401
    NotificationViewSet,
)
from apps.workspace.views_connect import (
    ConnectSearchView,
    MailViewSet,
    MessageActionsView,
    SpaceViewSet,
)

router = DefaultRouter()
router.register("comments", CommentViewSet, basename="comment")
router.register("notifications", NotificationViewSet, basename="notification")
# Connect — chat and mail.
router.register("spaces", SpaceViewSet, basename="space")
router.register("mail", MailViewSet, basename="mail")

urlpatterns = [
    path("my-work/", MyWorkView.as_view(), name="my-work"),
    path("mentionable-users", MentionableUsersView.as_view(), name="mentionable-users"),
    path("messages/<int:pk>/<str:verb>/", MessageActionsView.as_view(), name="message-actions"),
    path("search/", ConnectSearchView.as_view(), name="connect-search"),
    *router.urls,
]
