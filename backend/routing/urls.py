from django.urls import path

from .views import GeocodeView, PlanView

urlpatterns = [
    path('api/geocode/', GeocodeView.as_view(), name='geocode'),
    path('api/plan/', PlanView.as_view(), name='plan'),
]
