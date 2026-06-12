import pytest
import numpy as np
from constraints import ConstraintValidationError
from satellite.models import (
    BatteryState,
    SolarPanelState,
    ACSState,
    CommsState,
    SatelliteTelemetry,
)
from satellite.validation import check_telemetry


def test_valid_charging_mode():
    telemetry = SatelliteTelemetry(
        mode="charging",
        battery=BatteryState(charge_level=80.0, status="charging", temperature=20.0, current_draw=10.0),
        panels=[
            SolarPanelState(deployed=True, power_generated=40.0),
            SolarPanelState(deployed=True, power_generated=40.0),
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([100.0, 200.0, 300.0], dtype=np.float64),
            momentum_wheel_speed=1500.0,
            pointing_deviation=2.0,
        ),
        comms=CommsState(ground_station_visible=False, signal_strength=-100.0),
    )
    assert check_telemetry(telemetry) is True


def test_charging_mode_violations():
    # 1. Panels folded
    telemetry = SatelliteTelemetry(
        mode="charging",
        battery=BatteryState(charge_level=80.0, status="charging", temperature=20.0, current_draw=10.0),
        panels=[
            SolarPanelState(deployed=True, power_generated=40.0),
            SolarPanelState(deployed=False, power_generated=0.0),
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([100.0, 200.0, 300.0], dtype=np.float64),
            momentum_wheel_speed=1500.0,
            pointing_deviation=2.0,
        ),
        comms=CommsState(ground_station_visible=False, signal_strength=-100.0),
    )
    with pytest.raises(ConstraintValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "panels_deployed"
    assert "all solar panels must be deployed" in excinfo.value.message

    # 2. Net power is negative/zero
    telemetry.panels[1].deployed = True
    telemetry.panels[0].power_generated = 5.0
    telemetry.panels[1].power_generated = 5.0
    telemetry.battery.current_draw = 15.0  # generated (10) < draw (15)
    with pytest.raises(ConstraintValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "net_power"

    # 3. Battery status not charging
    telemetry.panels[0].power_generated = 40.0
    telemetry.panels[1].power_generated = 40.0
    telemetry.battery.current_draw = 10.0
    telemetry.battery.status = "discharging"
    with pytest.raises(ConstraintValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "battery_status"

    # 4. Charge level too low (< 50)
    telemetry.battery.status = "charging"
    telemetry.battery.charge_level = 45.0
    with pytest.raises(ConstraintValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "battery_charge_level"

    # 5. Sun deviation too high (>= 5.0)
    telemetry.battery.charge_level = 75.0
    telemetry.acs.pointing_deviation = 5.1
    with pytest.raises(ConstraintValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "sun_pointing_deviation"


def test_valid_data_collection_mode():
    telemetry = SatelliteTelemetry(
        mode="data_collection",
        battery=BatteryState(charge_level=90.0, status="discharging", temperature=15.0, current_draw=80.0),
        panels=[
            SolarPanelState(deployed=True, power_generated=0.0),
            SolarPanelState(deployed=True, power_generated=0.0),
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([-50.0, 150.0, 250.0], dtype=np.float64),
            momentum_wheel_speed=2000.0,
            pointing_deviation=0.8,
        ),
        comms=CommsState(ground_station_visible=True, signal_strength=-70.0),
    )
    assert check_telemetry(telemetry) is True


def test_data_collection_mode_violations():
    # 1. Temperature too high (> 40.0)
    telemetry = SatelliteTelemetry(
        mode="data_collection",
        battery=BatteryState(charge_level=90.0, status="discharging", temperature=41.0, current_draw=80.0),
        panels=[
            SolarPanelState(deployed=True, power_generated=0.0),
            SolarPanelState(deployed=True, power_generated=0.0),
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([-50.0, 150.0, 250.0], dtype=np.float64),
            momentum_wheel_speed=2000.0,
            pointing_deviation=0.8,
        ),
        comms=CommsState(ground_station_visible=True, signal_strength=-70.0),
    )
    with pytest.raises(ConstraintValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "battery_temperature"

    # 2. Ground station not visible
    telemetry.battery.temperature = 25.0
    telemetry.comms.ground_station_visible = False
    with pytest.raises(ConstraintValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "ground_station_visible"

    # 3. Draw limit exceeded (> 150.0)
    telemetry.comms.ground_station_visible = True
    telemetry.battery.current_draw = 160.0
    with pytest.raises(ConstraintValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "power_margin"

    # 4. Pointing deviation too high (>= 1.0)
    telemetry.battery.current_draw = 80.0
    telemetry.acs.pointing_deviation = 1.2
    with pytest.raises(ConstraintValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "target_pointing_deviation"


def test_acs_numpy_constraints():
    # Shape mismatch (4 dimensions instead of 3)
    telemetry = SatelliteTelemetry(
        mode="data_collection",
        battery=BatteryState(charge_level=90.0, status="discharging", temperature=15.0, current_draw=80.0),
        panels=[
            SolarPanelState(deployed=True, power_generated=0.0),
            SolarPanelState(deployed=True, power_generated=0.0),
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([100.0, 200.0, 300.0, 400.0], dtype=np.float64),
            momentum_wheel_speed=2000.0,
            pointing_deviation=0.8,
        ),
        comms=CommsState(ground_station_visible=True, signal_strength=-70.0),
    )
    with pytest.raises(ConstraintValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "wheel_speeds"
    assert "does not match expected shape" in excinfo.value.message

    # DType mismatch (float32 instead of float64)
    telemetry.acs.reaction_wheel_speeds = np.array([100.0, 200.0, 300.0], dtype=np.float32)
    with pytest.raises(ConstraintValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "wheel_speeds"
    assert "does not match expected dtype" in excinfo.value.message
