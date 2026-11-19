"""Threshold boundary tests for wind, rain, and snow risk classification."""

import pytest

from .risk import (RISK_HIGH, RISK_LOW, RISK_MODERATE, RISK_NO_TRAVEL,
                   RISK_SEVERE, RISK_UNKNOWN, classify_checkpoint_risk,
                   rain_risk, snow_risk, wind_risk)

NO_LOAD = 0


# ---------- Wind ----------

@pytest.mark.parametrize('mph,expected', [
    (0, RISK_LOW), (24.9, RISK_LOW),
    (25, RISK_MODERATE), (34.9, RISK_MODERATE),
    (35, RISK_HIGH), (44.9, RISK_HIGH),
    (45, RISK_SEVERE), (54.9, RISK_SEVERE),
    (55, RISK_NO_TRAVEL), (80, RISK_NO_TRAVEL),
])
def test_wind_thresholds(mph, expected):
    assert wind_risk(mph) == expected


def test_wind_unknown():
    assert wind_risk(None) == RISK_UNKNOWN


# ---------- Rain (in/hr) ----------

@pytest.mark.parametrize('in_hr,expected', [
    (0, RISK_LOW), (0.099, RISK_LOW),
    (0.10, RISK_MODERATE), (0.249, RISK_MODERATE),
    (0.25, RISK_HIGH), (0.499, RISK_HIGH),
    (0.50, RISK_SEVERE), (1.00, RISK_SEVERE),
    (1.01, RISK_NO_TRAVEL), (5.0, RISK_NO_TRAVEL),
])
def test_rain_thresholds(in_hr, expected):
    assert rain_risk(in_hr) == expected


def test_rain_unknown():
    assert rain_risk(None) == RISK_UNKNOWN


# ---------- Snow (in/hr) ----------

@pytest.mark.parametrize('in_hr,expected', [
    (0, RISK_LOW), (0.49, RISK_LOW),
    (0.5, RISK_MODERATE), (0.99, RISK_MODERATE),
    (1.0, RISK_HIGH), (1.99, RISK_HIGH),
    (2.0, RISK_SEVERE), (3.0, RISK_SEVERE),
    (3.01, RISK_NO_TRAVEL), (10.0, RISK_NO_TRAVEL),
])
def test_snow_thresholds(in_hr, expected):
    assert snow_risk(in_hr) == expected


def test_snow_unknown():
    assert snow_risk(None) == RISK_UNKNOWN


# ---------- Combined classification ----------

def test_overall_level_is_worst_of_components():
    result = classify_checkpoint_risk(wind_mph=10, rain_in_hr=0.6, snow_in_hr=0.1,
                                      load_weight_lbs=NO_LOAD)
    assert result['level'] == RISK_SEVERE  # rain severe beats wind low


def test_all_unknown_is_unknown_not_low():
    result = classify_checkpoint_risk(None, None, None, NO_LOAD)
    assert result['level'] == RISK_UNKNOWN


def test_partially_unknown_uses_known_values():
    result = classify_checkpoint_risk(wind_mph=10, rain_in_hr=None, snow_in_hr=None,
                                      load_weight_lbs=NO_LOAD)
    assert result['level'] == RISK_LOW


# ---------- Load rules ----------

def test_load_rule_wind_55_no_travel_any_load():
    for load in (0, 30000, 40000, 80000):
        result = classify_checkpoint_risk(55, 0, 0, load)
        assert result['level'] == RISK_NO_TRAVEL
        assert result['load_rule'] == 'no_travel_wind_55'


def test_load_rule_wind_54_over_30k_no_travel():
    result = classify_checkpoint_risk(54, 0, 0, 30001)
    assert result['level'] == RISK_NO_TRAVEL
    assert result['load_rule'] == 'no_travel_wind_load'


def test_load_rule_wind_45_boundary_over_30k():
    result = classify_checkpoint_risk(45, 0, 0, 30001)
    assert result['level'] == RISK_NO_TRAVEL


def test_load_rule_wind_54_exactly_30k_stays_severe():
    # Boundary: load must be *greater than* 30,000 lb.
    result = classify_checkpoint_risk(54, 0, 0, 30000)
    assert result['level'] == RISK_SEVERE


def test_load_rule_wind_44_over_40k_severe():
    result = classify_checkpoint_risk(44, 0, 0, 40001)
    assert result['level'] == RISK_SEVERE
    assert result['load_rule'] == 'severe_wind_load'


def test_load_rule_wind_44_exactly_40k_stays_high():
    # Boundary: load must be *greater than* 40,000 lb.
    result = classify_checkpoint_risk(44, 0, 0, 40000)
    assert result['level'] == RISK_HIGH


def test_load_rule_wind_35_boundary_over_40k():
    result = classify_checkpoint_risk(35, 0, 0, 50000)
    assert result['level'] == RISK_SEVERE


def test_load_rule_wind_34_over_40k_stays_moderate():
    result = classify_checkpoint_risk(34, 0, 0, 50000)
    assert result['level'] == RISK_MODERATE


def test_load_rules_do_not_lower_weather_risk():
    # Heavy rain already severe; wind load rule must not downgrade.
    result = classify_checkpoint_risk(40, 0.8, 0, 45000)
    assert result['level'] == RISK_SEVERE
    assert result['load_rule'] == 'severe_wind_load'


def test_load_rule_never_overrides_no_travel():
    result = classify_checkpoint_risk(60, 2.0, 0, 1000)
    assert result['level'] == RISK_NO_TRAVEL
    assert result['load_rule'] == 'no_travel_wind_55'


def test_no_load_rule_when_wind_unknown():
    result = classify_checkpoint_risk(None, 0.05, 0, 90000)
    assert result['level'] == RISK_LOW
    assert result['load_rule'] == 'none'
