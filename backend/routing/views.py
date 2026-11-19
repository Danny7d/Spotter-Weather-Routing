from rest_framework.response import Response
from rest_framework.views import APIView

from . import mapbox_client
from .serializers import GeocodeResultSerializer, PlanRequestSerializer
from .services import build_trip_plan


class GeocodeView(APIView):
    """GET /api/geocode/?q=<place> -> {results: [...]}."""

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({'error': 'Query parameter "q" is required.'}, status=400)
        results = mapbox_client.geocode(query, limit=5)
        return Response({'results': GeocodeResultSerializer(results, many=True).data})


class PlanView(APIView):
    """POST /api/plan/ -> full trip plan with routes, weather, risk, ranking."""

    def post(self, request):
        serializer = PlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        plan = build_trip_plan(
            origin_query=data['origin'],
            destination_query=data['destination'],
            departure_local=data['departure_local'],
            load_weight_lbs=data['load_weight_lbs'],
            interval_miles=data['checkpoint_interval_miles'],
        )
        return Response(plan)
