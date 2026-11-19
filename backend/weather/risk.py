"""Weather risk classification.

Thresholds (boundary values belong to the higher-risk category):

  Wind (mph):      Low <25 | Moderate 25-34 | High 35-44 | Severe 45-54 | No Travel >=55
  Rain (in/hr):    Low <0.10 | Moderate 0.10-0.25 | High 0.25-0.50 | Severe 0.50-1.00 | No Travel >1.00
  Snow (in/hr):    Low <0.5 | Moderate 0.5-1.0 | High 1.0-2.0 | Severe 2.0-3.0 | No Travel >3.0

Load rules (applied in addition to weather classification, never lowering it):
  - Wind >= 55 mph: No Travel for every load.
  - Wind 45-54 mph AND load > 30,000 lb: No Travel.
  - Wind 35-44 mph AND load > 40,000 lb: Severe.
"""

RISK_LOW = 'low'
RISK_MODERATE = 'moderate'
RISK_HIGH = 'high'
RISK_SEVERE = 'severe'
RISK_NO_TRAVEL = 'no_travel'
RISK_UNKNOWN = 'unknown'

RISK_ORDER = {
    RISK_LOW: 1,
    RISK_MODERATE: 2,
    RISK_HIGH: 3,
    RISK_SEVERE: 4,
    RISK_NO_TRAVEL: 5,
    RISK_UNKNOWN: 0,  # handled separately; never treated as low risk
}

WIND_NO_TRAVEL_MPH = 55.0
WIND_SEVERE_MIN_MPH = 45.0
WIND_HIGH_MIN_MPH = 35.0
RAIN_NO_TRAVEL_IN_HR = 1.00
RAIN_SEVERE_MIN_IN_HR = 0.50
RAIN_HIGH_MIN_IN_HR = 0.25
RAIN_MODERATE_MIN_IN_HR = 0.10
SNOW_NO_TRAVEL_IN_HR = 3.0
SNOW_SEVERE_MIN_IN_HR = 2.0
SNOW_HIGH_MIN_IN_HR = 1.0
SNOW_MODERATE_MIN_IN_HR = 0.5

LOAD_NO_TRAVEL_LBS = 30000
LOAD_SEVERE_LBS = 40000


def wind_risk(wind_mph):
    if wind_mph is None:
        return RISK_UNKNOWN
    if wind_mph >= WIND_NO_TRAVEL_MPH:
        return RISK_NO_TRAVEL
    if wind_mph >= WIND_SEVERE_MIN_MPH:
        return RISK_SEVERE
    if wind_mph >= WIND_HIGH_MIN_MPH:
        return RISK_HIGH
    if wind_mph >= 25:
        return RISK_MODERATE
    return RISK_LOW


def rain_risk(rain_in_hr):
    if rain_in_hr is None:
        return RISK_UNKNOWN
    if rain_in_hr > RAIN_NO_TRAVEL_IN_HR:
        return RISK_NO_TRAVEL
    if rain_in_hr >= RAIN_SEVERE_MIN_IN_HR:
        return RISK_SEVERE
    if rain_in_hr >= RAIN_HIGH_MIN_IN_HR:
        return RISK_HIGH
    if rain_in_hr >= RAIN_MODERATE_MIN_IN_HR:
        return RISK_MODERATE
    return RISK_LOW


def snow_risk(snow_in_hr):
    if snow_in_hr is None:
        return RISK_UNKNOWN
    if snow_in_hr > SNOW_NO_TRAVEL_IN_HR:
        return RISK_NO_TRAVEL
    if snow_in_hr >= SNOW_SEVERE_MIN_IN_HR:
        return RISK_SEVERE
    if snow_in_hr >= SNOW_HIGH_MIN_IN_HR:
        return RISK_HIGH
    if snow_in_hr >= SNOW_MODERATE_MIN_IN_HR:
        return RISK_MODERATE
    return RISK_LOW


def _worst_known(levels):
    """Worst level among known values; None if every input is unknown."""
    known = [level for level in levels if level != RISK_UNKNOWN]
    if not known:
        return RISK_UNKNOWN
    return max(known, key=lambda level: RISK_ORDER[level])


def classify_checkpoint_risk(wind_mph, rain_in_hr, snow_in_hr, load_weight_lbs):
    """Classify weather + load into an overall risk level.

    Returns a dict:
      level            - overall risk level
      wind_level       - wind-only classification
      rain_level       - rain-only classification
      snow_level       - snow-only classification
      load_rule        - 'none' | 'no_travel_wind_55' | 'no_travel_wind_load'
                         | 'severe_wind_load' | None when weather is unknown
      factors          - human-readable explanations for escalations
    """
    wind_level = wind_risk(wind_mph)
    rain_level = rain_risk(rain_in_hr)
    snow_level = snow_risk(snow_in_hr)

    level = _worst_known([wind_level, rain_level, snow_level])
    load_rule = 'none'
    factors = []

    if wind_mph is not None:
        if wind_mph >= WIND_NO_TRAVEL_MPH:
            # Universal rule: >=55 mph is No Travel for every load.
            load_rule = 'no_travel_wind_55'
            factors.append(f'Wind {wind_mph:.0f} mph >= 55 mph: No Travel for all loads')
            level = RISK_NO_TRAVEL
        elif wind_mph >= WIND_SEVERE_MIN_MPH and load_weight_lbs > LOAD_NO_TRAVEL_LBS:
            load_rule = 'no_travel_wind_load'
            factors.append(
                f'Wind {wind_mph:.0f} mph (45-54) with load {load_weight_lbs:,} lb '
                f'> 30,000 lb: No Travel')
            level = RISK_NO_TRAVEL
        elif wind_mph >= WIND_HIGH_MIN_MPH and load_weight_lbs > LOAD_SEVERE_LBS:
            load_rule = 'severe_wind_load'
            factors.append(
                f'Wind {wind_mph:.0f} mph (35-44) with load {load_weight_lbs:,} lb '
                f'> 40,000 lb: Severe')
            if RISK_ORDER.get(level, 0) < RISK_ORDER[RISK_SEVERE]:
                level = RISK_SEVERE

    return {
        'level': level,
        'wind_level': wind_level,
        'rain_level': rain_level,
        'snow_level': snow_level,
        'load_rule': load_rule,
        'factors': factors,
    }


def worse_risk(level_a, level_b):
    """Return the higher-risk of two levels. Unknown never beats a known level."""
    if level_a == RISK_UNKNOWN:
        return level_b
    if level_b == RISK_UNKNOWN:
        return level_a
    return level_a if RISK_ORDER[level_a] >= RISK_ORDER[level_b] else level_b
