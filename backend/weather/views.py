from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import CorridorForecastRequestSerializer
from .services import corridor_forecast


class CorridorForecastView(APIView):
    """POST /api/corridor-forecast/ -> hourly risk series along route points."""

    def post(self, request):
        serializer = CorridorForecastRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = corridor_forecast(
            points=data['points'],
            departure_utc=data['departure_utc'],
            forecast_hours=data['forecast_hours'],
            load_weight_lbs=data['load_weight_lbs'],
        )
        return Response({'points': result})
