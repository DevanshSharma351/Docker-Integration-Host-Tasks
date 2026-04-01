from django.urls import path
from .views import (
    HostListCreateView,
    HostDetailView,
    AssignUserToHostView,
    HostUsersListView,
)

urlpatterns = [
    path('', HostListCreateView.as_view(), name='host-list-create'),
    path('<uuid:id>/', HostDetailView.as_view(), name='host-detail'),
    path('<uuid:id>/assign/', AssignUserToHostView.as_view(), name='host-assign'),
    path('<uuid:id>/assign/<int:user_id>/', AssignUserToHostView.as_view(), name='host-remove-user'),
    path('<uuid:id>/users/', HostUsersListView.as_view(), name='host-users'),
]
