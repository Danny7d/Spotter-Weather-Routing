from rest_framework import serializers


class NaiveLocalDateTimeField(serializers.DateTimeField):
    """Accept local wall time as supplied and reject explicit UTC offsets."""

    default_error_messages = {
        **serializers.DateTimeField.default_error_messages,
        'timezone_offset': 'Departure time must be a local time without a timezone offset.',
    }

    def enforce_timezone(self, value):
        if value.utcoffset() is not None:
            self.fail('timezone_offset')
        return value


class GeocodeResultSerializer(serializers.Serializer):
    place_id = serializers.CharField()
    display_name = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class PlaceSerializer(serializers.Serializer):
    query = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    display_name = serializers.CharField(allow_blank=True, required=False)
    timezone = serializers.CharField(allow_blank=True, required=False)


class CheckpointSerializer(serializers.Serializer):
    index = serializers.IntegerField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    cumulative_distance_miles = serializers.FloatField()
    arrival_utc = serializers.DateTimeField()
    is_origin = serializers.BooleanField()
    is_destination = serializers.BooleanField()
    weather = serializers.DictField(allow_null=True, required=False)
    risk = serializers.DictField(required=False)


class RouteOptionSerializer(serializers.Serializer):
    id = serializers.CharField()
    geometry = serializers.DictField()
    distance_miles = serializers.FloatField()
    duration_seconds = serializers.FloatField()
    checkpoints = CheckpointSerializer(many=True)
    metrics = serializers.DictField()
    rank = serializers.IntegerField(allow_null=True, required=False)


class PlanRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=300)
    destination = serializers.CharField(max_length=300)
    # Naive local datetime at the origin (e.g. "2026-11-20T08:00").
    # Interpreted in the origin's IANA timezone resolved from coordinates.
    departure_local = NaiveLocalDateTimeField()
    load_weight_lbs = serializers.IntegerField(min_value=0, max_value=200000)
    checkpoint_interval_miles = serializers.ChoiceField(choices=[10, 25, 50])

    def validate_departure_local(self, value):
        raw = self.initial_data.get('departure_local')
        if isinstance(raw, str):
            time_part = raw.split('T')[-1] if 'T' in raw else raw.split(' ')[-1]
            if time_part.endswith('Z') or '+' in time_part or ('-' in time_part and not time_part.startswith('-')):
                raise serializers.ValidationError('Departure time must be a local time without a timezone offset.')
        return value.replace(tzinfo=None) if value.tzinfo else value
