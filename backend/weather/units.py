"""Unit conversions for weather variables.

Open-Meteo is queried with its default units:
  wind_speed_10m  -> km/h      -> mph
  rain, showers   -> mm/hour   -> in/hr  (summed: rain + showers)
  snowfall        -> cm/hour   -> in/hr
  temperature_2m  -> degC      -> degF
"""

KMH_TO_MPH = 0.621371192237334
MM_TO_INCHES = 1.0 / 25.4
CM_TO_INCHES = 1.0 / 2.54


def kmh_to_mph(kmh):
    return None if kmh is None else kmh * KMH_TO_MPH


def mm_per_hour_to_inches_per_hour(mm):
    return None if mm is None else mm * MM_TO_INCHES


def cm_per_hour_to_inches_per_hour(cm):
    return None if cm is None else cm * CM_TO_INCHES


def celsius_to_fahrenheit(celsius):
    return None if celsius is None else celsius * 9.0 / 5.0 + 32.0
