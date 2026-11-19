from rest_framework import serializers


class CorridorPointSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    cumulative_distance_miles = serializers.FloatField(min_value=0)


class CorridorForecastRequestSerializer(serializers.Serializer):
    points = CorridorPointSerializer(many=True, min_length=1, max_length=200)
    departure_utc = serializers.DateTimeField()
    load_weight_lbs = serializers.IntegerField(min_value=0, max_value=200000)
    forecast_hours = serializers.IntegerField(min_value=1, max_value=49, default=49)
