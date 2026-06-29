import numpy as np
from validated import ValidationError
from satellite.models import (
    BatteryState,
    SolarPanelState,
    ACSState,
    CommsState,
    SatelliteTelemetry,
    SlewTask,
    ImagingTask,
)
from satellite.validation import (
    check_telemetry,
    validate_subsystem_diagnostics,
    validate_task,
)


def print_header(title: str):
    print("\n" + "=" * 80)
    print(f" SCENARIO: {title}".center(80))
    print("=" * 80)


def print_validation_error(e: ValidationError):
    if len(e.errors) > 1:
        print(f"  - Total violations: {len(e.errors)}")
        for idx, err in enumerate(e.errors, 1):
            print(f"    {idx}. Parameter '{err.parameter_name}': value={err.value!r}, violation={err.message}")
    else:
        print(f"  - Parameter in error: {e.parameter_name}")
        print(f"  - Value received: {e.value!r}")
        print(f"  - Violation details: {e.message}")


def run_scenario(title: str, telemetry: SatelliteTelemetry):
    print_header(title)
    print(f"Mode: {telemetry.mode.upper()}")
    print(f"Battery: charge={telemetry.battery.charge_level}%, status={telemetry.battery.status}, temp={telemetry.battery.temperature} C, draw={telemetry.battery.current_draw} W")
    print(f"Solar Panels: {[('Deployed' if p.deployed else 'Folded', f'{p.power_generated}W') for p in telemetry.panels]}")
    print(f"ACS: pointing_dev={telemetry.acs.pointing_deviation} deg, reaction_wheel_speeds={telemetry.acs.reaction_wheel_speeds.tolist()}")
    print(f"Comms: visible={telemetry.comms.ground_station_visible}")
    print("-" * 80)
    
    try:
        check_telemetry(telemetry)
        print("RESULT: [PASS] Telemetry successfully validated! All constraints SATISFIED.")
    except ValidationError as e:
        print("RESULT: [FAIL] Telemetry validation FAILED!")
        print_validation_error(e)
    except Exception as e:
        print(f"RESULT: [ERROR] Unexpected exception: {type(e).__name__}: {e}")


def main():
    # 1. Healthy Charging Mode Scenario
    healthy_charging = SatelliteTelemetry(
        mode="charging",
        battery=BatteryState(charge_level=75.0, status="charging", temperature=22.0, current_draw=20.0),
        panels=[
            SolarPanelState(deployed=True, power_generated=50.0),
            SolarPanelState(deployed=True, power_generated=50.0),
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([1200.0, -800.0, 450.0], dtype=np.float64),
            momentum_wheel_speed=3000.0,
            pointing_deviation=1.5,
        ),
        comms=CommsState(ground_station_visible=False, signal_strength=-90.0),
    )
    run_scenario("Healthy Charging Mode", healthy_charging)

    # 2. Charging Mode with panels folded
    folded_panels_charging = SatelliteTelemetry(
        mode="charging",
        battery=BatteryState(charge_level=75.0, status="charging", temperature=22.0, current_draw=20.0),
        panels=[
            SolarPanelState(deployed=True, power_generated=50.0),
            SolarPanelState(deployed=False, power_generated=0.0),  # One is folded!
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([1200.0, -800.0, 450.0], dtype=np.float64),
            momentum_wheel_speed=3000.0,
            pointing_deviation=1.5,
        ),
        comms=CommsState(ground_station_visible=False, signal_strength=-90.0),
    )
    run_scenario("Charging Mode with Folded Panel", folded_panels_charging)

    # 3. Charging Mode with negative net power (consuming more than generating)
    negative_net_power_charging = SatelliteTelemetry(
        mode="charging",
        battery=BatteryState(charge_level=75.0, status="charging", temperature=22.0, current_draw=120.0),  # drawing 120W
        panels=[
            SolarPanelState(deployed=True, power_generated=40.0),
            SolarPanelState(deployed=True, power_generated=40.0),  # total generated = 80W < 120W
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([1200.0, -800.0, 450.0], dtype=np.float64),
            momentum_wheel_speed=3000.0,
            pointing_deviation=1.5,
        ),
        comms=CommsState(ground_station_visible=False, signal_strength=-90.0),
    )
    run_scenario("Charging Mode with Negative Net Power", negative_net_power_charging)

    # 4. Healthy Data Collection Mode Scenario
    healthy_data = SatelliteTelemetry(
        mode="data_collection",
        battery=BatteryState(charge_level=85.0, status="discharging", temperature=28.0, current_draw=90.0),
        panels=[
            SolarPanelState(deployed=True, power_generated=10.0),
            SolarPanelState(deployed=True, power_generated=10.0),
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([-500.0, 1100.0, -250.0], dtype=np.float64),
            momentum_wheel_speed=3200.0,
            pointing_deviation=0.4,  # pointing error < 1.0 degree
        ),
        comms=CommsState(ground_station_visible=True, signal_strength=-65.0),
    )
    run_scenario("Healthy Data Collection Mode", healthy_data)

    # 5. Data Collection Mode - Battery Overheating
    overheating_data = SatelliteTelemetry(
        mode="data_collection",
        battery=BatteryState(charge_level=85.0, status="discharging", temperature=45.0, current_draw=90.0), # 45°C > 40°C limit
        panels=[
            SolarPanelState(deployed=True, power_generated=10.0),
            SolarPanelState(deployed=True, power_generated=10.0),
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([-500.0, 1100.0, -250.0], dtype=np.float64),
            momentum_wheel_speed=3200.0,
            pointing_deviation=0.4,
        ),
        comms=CommsState(ground_station_visible=True, signal_strength=-65.0),
    )
    run_scenario("Data Collection Mode - Battery Overheating", overheating_data)

    # 6. Data Collection Mode - Exceeding Battery Draw Limit
    high_draw_data = SatelliteTelemetry(
        mode="data_collection",
        battery=BatteryState(charge_level=85.0, status="discharging", temperature=28.0, current_draw=180.0), # 180W > 150W limit
        panels=[
            SolarPanelState(deployed=True, power_generated=10.0),
            SolarPanelState(deployed=True, power_generated=10.0),
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([-500.0, 1100.0, -250.0], dtype=np.float64),
            momentum_wheel_speed=3200.0,
            pointing_deviation=0.4,
        ),
        comms=CommsState(ground_station_visible=True, signal_strength=-65.0),
    )
    run_scenario("Data Collection Mode - High Current Draw", high_draw_data)

    # 7. Faulty ACS Reaction Wheel Speeds Dimension (Shape Constraint)
    faulty_acs_shape = SatelliteTelemetry(
        mode="data_collection",
        battery=BatteryState(charge_level=85.0, status="discharging", temperature=28.0, current_draw=90.0),
        panels=[
            SolarPanelState(deployed=True, power_generated=10.0),
            SolarPanelState(deployed=True, power_generated=10.0),
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([-500.0, 1100.0], dtype=np.float64), # Only 2 wheels instead of 3!
            momentum_wheel_speed=3200.0,
            pointing_deviation=0.4,
        ),
        comms=CommsState(ground_station_visible=True, signal_strength=-65.0),
    )
    run_scenario("Faulty ACS Reaction Wheel Speed Shape", faulty_acs_shape)

    # 8. Faulty ACS Reaction Wheel Speeds DType (DType Constraint)
    faulty_acs_dtype = SatelliteTelemetry(
        mode="data_collection",
        battery=BatteryState(charge_level=85.0, status="discharging", temperature=28.0, current_draw=90.0),
        panels=[
            SolarPanelState(deployed=True, power_generated=10.0),
            SolarPanelState(deployed=True, power_generated=10.0),
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([-500, 1100, -250], dtype=np.int32), # int32 instead of float64!
            momentum_wheel_speed=3200.0,
            pointing_deviation=0.4,
        ),
        comms=CommsState(ground_station_visible=True, signal_strength=-65.0),
    )
    run_scenario("Faulty ACS Reaction Wheel Speed DType", faulty_acs_dtype)

    # 8.5. Charging Mode with Multiple Concurrent Failures
    multiple_failures_charging = SatelliteTelemetry(
        mode="charging",
        battery=BatteryState(charge_level=40.0, status="discharging", temperature=22.0, current_draw=60.0), # low charge level, wrong status
        panels=[
            SolarPanelState(deployed=True, power_generated=10.0),
            SolarPanelState(deployed=False, power_generated=0.0), # One folded panel (total 10W gen < 60W draw = negative net power)
        ],
        acs=ACSState(
            reaction_wheel_speeds=np.array([1200.0, -800.0, 450.0], dtype=np.float64),
            momentum_wheel_speed=3000.0,
            pointing_deviation=6.5, # deviation >= 5.0
        ),
        comms=CommsState(ground_station_visible=False, signal_strength=-90.0),
    )
    run_scenario("Charging Mode with Multiple Failures", multiple_failures_charging)

    # 9. Selective validation demo (Full vs Type-only vs Bypassed)
    print_header("Selective Validation Diagnostic Scenarios")
    
    # 9a. Successful case
    try:
        print("Running validate_subsystem_diagnostics('PWR-002', '12.4', {'voltage': 28.5})")
        validate_subsystem_diagnostics("PWR-002", "12.4", {"voltage": 28.5})
        print("RESULT: [PASS] All inputs validated and coerced successfully!")
    except ConstraintValidationError as e:
        print(f"RESULT: [FAIL] {e}")
        
    # 9b. Failing constraint check (Full validation parameter pattern mismatch)
    print("-" * 80)
    try:
        print("Running validate_subsystem_diagnostics('INVALID-ID', 12.4, {'voltage': 28.5})")
        validate_subsystem_diagnostics("INVALID-ID", 12.4, {"voltage": 28.5})
    except ConstraintValidationError as e:
        print(f"RESULT: [FAIL] Telemetry validation FAILED!")
        print_validation_error(e)

    # 9c. Failing type coercion (Type-only validation parameter not a float)
    print("-" * 80)
    try:
        print("Running validate_subsystem_diagnostics('PWR-002', 'not-a-float', {'voltage': 28.5})")
        validate_subsystem_diagnostics("PWR-002", "not-a-float", {"voltage": 28.5})
    except ConstraintValidationError as e:
        print(f"RESULT: [FAIL] Telemetry validation FAILED!")
        print_validation_error(e)

    # 10. Pre-Commit Task Validation Demo (Slew speed and Coverage constraints)
    print_header("Pre-Commit Task Validation Scenarios")
    
    # 10a. Successful Slew Task
    slew_ok = SlewTask(
        poi_name="Sydney_Station",
        target_yaw=45.2,
        target_pitch=-10.5,
        duration_seconds=15.0,
        max_predicted_slew_speed=1.2, # 1.2 deg/s < 2.0 limit
        predicted_coverage=88.5,      # 88.5% in [80.0, 100.0]
    )
    try:
        print(f"Validating SlewTask to {slew_ok.poi_name} (speed={slew_ok.max_predicted_slew_speed} deg/s, coverage={slew_ok.predicted_coverage}%)")
        validate_task(slew_ok)
        print("RESULT: [PASS] Slew task passes pre-commit checks! Ready to upload to command queue.")
    except ConstraintValidationError as e:
        print(f"RESULT: [FAIL] Slew task rejected: {e}")

    # 10b. Slew Task exceeding speed limit
    print("-" * 80)
    slew_too_fast = SlewTask(
        poi_name="Sydney_Station",
        target_yaw=45.2,
        target_pitch=-10.5,
        duration_seconds=5.0,
        max_predicted_slew_speed=3.1, # 3.1 deg/s > 2.0 limit!
        predicted_coverage=95.0,
    )
    try:
        print(f"Validating SlewTask to {slew_too_fast.poi_name} (speed={slew_too_fast.max_predicted_slew_speed} deg/s, coverage={slew_too_fast.predicted_coverage}%)")
        validate_task(slew_too_fast)
    except ConstraintValidationError as e:
        print("RESULT: [FAIL] Slew task REJECTED! Violation of safety threshold.")
        print_validation_error(e)

    # 10c. Slew Task with poor coverage
    print("-" * 80)
    slew_low_coverage = SlewTask(
        poi_name="Sydney_Station",
        target_yaw=45.2,
        target_pitch=-10.5,
        duration_seconds=20.0,
        max_predicted_slew_speed=0.8,
        predicted_coverage=71.2,      # 71.2% < 80.0% min required!
    )
    try:
        print(f"Validating SlewTask to {slew_low_coverage.poi_name} (speed={slew_low_coverage.max_predicted_slew_speed} deg/s, coverage={slew_low_coverage.predicted_coverage}%)")
        validate_task(slew_low_coverage)
    except ConstraintValidationError as e:
        print("RESULT: [FAIL] Slew task REJECTED! Violation of safety threshold.")
        print_validation_error(e)

    # 10d. Slew Task with Multiple Violations (speed too high and coverage too low)
    print("-" * 80)
    slew_multiple_fails = SlewTask(
        poi_name="Sydney_Station",
        target_yaw=45.2,
        target_pitch=-10.5,
        duration_seconds=5.0,
        max_predicted_slew_speed=3.5, # 3.5 deg/s > 2.0 limit!
        predicted_coverage=75.0,      # 75% < 80% min required!
    )
    try:
        print(f"Validating SlewTask to {slew_multiple_fails.poi_name} (speed={slew_multiple_fails.max_predicted_slew_speed} deg/s, coverage={slew_multiple_fails.predicted_coverage}%)")
        validate_task(slew_multiple_fails)
    except ConstraintValidationError as e:
        print("RESULT: [FAIL] Slew task REJECTED! Violation of safety threshold.")
        print_validation_error(e)


if __name__ == "__main__":
    main()
