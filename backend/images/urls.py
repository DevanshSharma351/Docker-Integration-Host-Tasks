from django.urls import path

from .views import (
    ImagePullJobDetailCancelView,
    ImagePullJobListCreateView,
    ImagePushJobDetailCancelView,
    ImagePushJobListCreateView,
    ImageDeleteJobDetailCancelView,
    ImageDeleteJobListCreateView,
)

urlpatterns = [
    # Pull endpoints
    path("pull/", ImagePullJobListCreateView.as_view(), name="image-pull-list-create"),
    path(
        "pull/<uuid:job_id>/",
        ImagePullJobDetailCancelView.as_view(),
        name="image-pull-detail",
    ),
    # Push endpoints
    path("push/", ImagePushJobListCreateView.as_view(), name="image-push-list-create"),
    path(
        "push/<uuid:job_id>/",
        ImagePushJobDetailCancelView.as_view(),
        name="image-push-detail",
    ),
    # Delete endpoints
    path("delete/", ImageDeleteJobListCreateView.as_view(), name="image-delete-list-create"),
    path(
        "delete/<uuid:job_id>/",
        ImageDeleteJobDetailCancelView.as_view(),
        name="image-delete-detail",
    ),
]
