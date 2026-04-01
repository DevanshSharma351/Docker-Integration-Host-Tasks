from django.urls import re_path
from containers.consumers.exec_consumer import ExecConsumer
from containers.consumers.log_consumer import LogConsumer

websocket_urlpatterns = [
    re_path(
        r'^ws/hosts/(?P<host_id>\d+)/containers/(?P<container_id>[^/]+)/exec/$',
        ExecConsumer.as_asgi()
    ),
    re_path(
        r'^ws/hosts/(?P<host_id>\d+)/containers/(?P<container_id>[^/]+)/logs/$',
        LogConsumer.as_asgi()
    ),
]