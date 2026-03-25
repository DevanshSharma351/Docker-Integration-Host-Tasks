from django.urls import path

from .views import (
    ImagePullJobDetailCancelView,
    ImagePullJobListCreateView,
)

urlpatterns = [
    path("", ImagePullJobListCreateView.as_view(), name="image-pull-list-create"),
    path(
        "<uuid:job_id>/",
        ImagePullJobDetailCancelView.as_view(),
        name="image-pull-detail",
    ),
]
