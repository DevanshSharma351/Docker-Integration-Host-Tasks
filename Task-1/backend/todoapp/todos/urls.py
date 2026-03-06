from django.urls import path
from .views import TodoListCreateView ,TodoDetailView,HealthCheckView
urlpatterns = [
    path('todos/', TodoListCreateView.as_view(), name='todo-list-create'),
    path('todos/<int:pk>/', TodoDetailView.as_view(), name='todo-detail'),
    path('health/', HealthCheckView.as_view(), name='health-check'),
]
 
