from django.urls import path, include

urlpatterns = [
    path('api/', include('todoapp.todos.urls')),
]