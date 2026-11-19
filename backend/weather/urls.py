from django.urls import path

from .views import CorridorForecastView

urlpatterns = [
    path('api/corridor-forecast/', CorridorForecastView.as_view(), name='corridor-forecast'),
]
