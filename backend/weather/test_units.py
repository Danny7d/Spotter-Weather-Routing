"""Unit conversion tests."""

from .units import (celsius_to_fahrenheit, cm_per_hour_to_inches_per_hour,
                    kmh_to_mph, mm_per_hour_to_inches_per_hour)


def test_kmh_to_mph():
    assert kmh_to_mph(0) == 0
    assert abs(kmh_to_mph(100) - 62.137) < 0.01
    assert kmh_to_mph(None) is None


def test_mm_to_inches_per_hour():
    # 25.4 mm = 1 inch
    assert abs(mm_per_hour_to_inches_per_hour(25.4) - 1.0) < 1e-6
    assert mm_per_hour_to_inches_per_hour(0) == 0
    assert mm_per_hour_to_inches_per_hour(None) is None


def test_cm_to_inches_per_hour():
    # 2.54 cm = 1 inch
    assert abs(cm_per_hour_to_inches_per_hour(2.54) - 1.0) < 1e-6
    assert cm_per_hour_to_inches_per_hour(None) is None


def test_celsius_to_fahrenheit():
    assert celsius_to_fahrenheit(0) == 32.0
    assert celsius_to_fahrenheit(100) == 212.0
    assert celsius_to_fahrenheit(None) is None
