import numpy as np
import pytest

from satellite.models import (
    ACSState,
    BatteryState,
    CommsState,
    ImagingTask,
    SatelliteTelemetry,
    SlewTask,
    SolarPanelState,
)
from satellite.validation import (
    check_telemetry,
    validate_subsystem_diagnostics,
    validate_task,
)
from validated import ValidationError


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
    with pytest.raises(ValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "panels_deployed"
    assert "all solar panels must be deployed" in excinfo.value.message

    # 2. Net power is negative/zero
    telemetry.panels[1].deployed = True
    telemetry.panels[0].power_generated = 5.0
    telemetry.panels[1].power_generated = 5.0
    telemetry.battery.current_draw = 15.0  # generated (10) < draw (15)
    with pytest.raises(ValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "net_power"

    # 3. Battery status not charging
    telemetry.panels[0].power_generated = 40.0
    telemetry.panels[1].power_generated = 40.0
    telemetry.battery.current_draw = 10.0
    telemetry.battery.status = "discharging"
    with pytest.raises(ValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "battery_status"

    # 4. Charge level too low (< 50)
    telemetry.battery.status = "charging"
    telemetry.battery.charge_level = 45.0
    with pytest.raises(ValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "battery_charge_level"

    # 5. Sun deviation too high (>= 5.0)
    telemetry.battery.charge_level = 75.0
    telemetry.acs.pointing_deviation = 5.1
    with pytest.raises(ValidationError) as excinfo:
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
    with pytest.raises(ValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "battery_temperature"

    # 2. Ground station not visible
    telemetry.battery.temperature = 25.0
    telemetry.comms.ground_station_visible = False
    with pytest.raises(ValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "ground_station_visible"

    # 3. Draw limit exceeded (> 150.0)
    telemetry.comms.ground_station_visible = True
    telemetry.battery.current_draw = 160.0
    with pytest.raises(ValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "power_margin"

    # 4. Pointing deviation too high (>= 1.0)
    telemetry.battery.current_draw = 80.0
    telemetry.acs.pointing_deviation = 1.2
    with pytest.raises(ValidationError) as excinfo:
        check_telemetry(telemetry)
    assert excinfo.value.parameter_name == "target_pointing_deviation"


def test_acs_numpy_constraints():
    from pydantic import ValidationError as PydanticValidationError

    # Shape mismatch (4 dimensions instead of 3)
    with pytest.raises(PydanticValidationError) as excinfo:
        ACSState(
            reaction_wheel_speeds=np.array([100.0, 200.0, 300.0, 400.0], dtype=np.float64),
            momentum_wheel_speed=2000.0,
            pointing_deviation=0.8,
        )
    assert "does not match expected shape" in str(excinfo.value)

    # DType mismatch (float32 instead of float64)
    with pytest.raises(PydanticValidationError) as excinfo:
        ACSState(
            reaction_wheel_speeds=np.array([100.0, 200.0, 300.0], dtype=np.float32),
            momentum_wheel_speed=2000.0,
            pointing_deviation=0.8,
        )
    assert "does not match expected dtype" in str(excinfo.value)


def test_selective_validation():
    # 1. Valid inputs (with coercion)
    # "ACS-101" is matched to pattern; "25" is coerced to float; raw_telemetry is Any
    assert validate_subsystem_diagnostics("ACS-101", "25", {"some": "data"}) is True

    # 2. Invalid inputs on full validation parameter (pattern mismatch)
    with pytest.raises(ValidationError) as excinfo:
        validate_subsystem_diagnostics("ACS-INVALID", 25.0, "ignored")
    assert excinfo.value.parameter_name == "subsystem_id"
    assert "must match pattern" in excinfo.value.message

    # 3. Invalid inputs on type-only validation parameter (not coercible to float)
    with pytest.raises(ValidationError) as excinfo:
        validate_subsystem_diagnostics("ACS-101", "not-a-float", "ignored")
    assert excinfo.value.parameter_name == "temperature_offset"
    assert "type validation failed" in excinfo.value.message

    # 4. Any input on unvalidated parameter (even completely invalid type/data)
    assert validate_subsystem_diagnostics("ACS-101", 25.0, None) is True
    assert validate_subsystem_diagnostics("ACS-101", 25.0, 12345) is True


def test_task_validation():
    # 1. Valid Slew Task — construction succeeds (validation passes)
    valid_slew = SlewTask(
        poi_name="Paris_Observation",
        target_yaw=12.5,
        target_pitch=-45.0,
        duration_seconds=30.0,
        max_predicted_slew_speed=1.5,  # 1.5 < 2.0
        predicted_coverage=92.5,  # 92.5 in [80.0, 100.0]
    )
    assert validate_task(valid_slew) is True

    # 2. Slew Task with exceeded slew speed — fails at construction time
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError) as excinfo:
        SlewTask(
            poi_name="Paris_Observation",
            target_yaw=12.5,
            target_pitch=-45.0,
            duration_seconds=30.0,
            max_predicted_slew_speed=2.5,  # 2.5 > 2.0! (Violates LessThan(2.0))
            predicted_coverage=92.5,
        )
    assert "must be less than 2.0" in str(excinfo.value)

    # 3. Slew Task with poor coverage — fails at construction time
    with pytest.raises(PydanticValidationError) as excinfo:
        SlewTask(
            poi_name="Paris_Observation",
            target_yaw=12.5,
            target_pitch=-45.0,
            duration_seconds=30.0,
            max_predicted_slew_speed=1.5,
            predicted_coverage=75.0,  # 75.0 < 80.0! (Violates InRange(80.0, 100.0))
        )
    assert "must be in range [80.0, 100.0]" in str(excinfo.value)

    # 4. Valid Imaging Task — construction succeeds
    valid_imaging = ImagingTask(
        target_poi="London_POI",
        exposure_time=1.2,  # in [0.01, 5.0]
        cloud_cover_limit=15.0,  # < 20.0
        spectral_bands=["Red", "Green", "Blue", "NIR"],  # length 4, in [1, 5]
    )
    assert validate_task(valid_imaging) is True

    # 5. Imaging Task with too many spectral bands — fails at construction time
    with pytest.raises(PydanticValidationError) as excinfo:
        ImagingTask(
            target_poi="London_POI",
            exposure_time=1.2,
            cloud_cover_limit=15.0,
            spectral_bands=[
                "Band1",
                "Band2",
                "Band3",
                "Band4",
                "Band5",
                "Band6",
            ],  # 6 bands > 5!
        )
    assert "length must be between 1 and 5" in str(excinfo.value)
