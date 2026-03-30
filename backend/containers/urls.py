from django.urls import path
from .views import ContainerCreateView

urlpatterns = [
	path('create/', ContainerCreateView.as_view(), name='container-create'),
]
