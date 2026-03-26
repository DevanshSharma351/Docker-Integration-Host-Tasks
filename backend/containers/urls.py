from django.urls import path
from containers.views.container_views import (
    ContainerListCreateView,
    ContainerDetailView,
    ContainerStartView,
    ContainerStopView,
    ContainerRestartView,
    ContainerKillView,
    ContainerPauseView,
    ContainerUnpauseView,
)
from containers.views.stats_views import ContainerStatsView
from containers.views.log_views import (
    ContainerLogsView,
    ContainerLogStreamTicketView,
)
from containers.views.exec_views import ExecTicketView
from containers.views.event_views import ContainerEventListView


urlpatterns = [
    path(
        'hosts/<int:host_id>/containers/',
        ContainerListCreateView.as_view()
    ),
    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/',
        ContainerDetailView.as_view()
    ),

    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/start/',
        ContainerStartView.as_view()
    ),
    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/stop/',
        ContainerStopView.as_view()
    ),
    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/restart/',
        ContainerRestartView.as_view()
    ),
    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/kill/',
        ContainerKillView.as_view()
    ),
    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/pause/',
        ContainerPauseView.as_view()
    ),
    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/unpause/',
        ContainerUnpauseView.as_view()
    ),
    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/stats/',
        ContainerStatsView.as_view()
    ),
    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/logs/',
        ContainerLogsView.as_view()
    ),
    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/logs/stream/',
        ContainerLogStreamTicketView.as_view()
    ),
    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/exec/',
        ExecTicketView.as_view()
    ),

    # Audit log 
    path(
        'hosts/<int:host_id>/containers/<uuid:container_id>/events/',
        ContainerEventListView.as_view()
    ),
]