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


# ANSI escape codes for styling console output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"

def print_header(title: str):
    banner = f"🛰️  SCENARIO: {title} "
    print(f"\n{BOLD}{CYAN}{'=' * 80}")
    print(f"{banner.center(80)}")
    print(f"{'=' * 80}{RESET}")


def print_validation_error(e: ValidationError):
    if len(e.errors) > 1:
        print(f"  {BOLD}{RED}❌ Total Violations: {len(e.errors)}{RESET}")
        for idx, err in enumerate(e.errors, 1):
            print(f"    {BOLD}{RED}{idx}.{RESET} Parameter {BOLD}{YELLOW}'{err.parameter_name}'{RESET}: "
                  f"value={BOLD}{RED}{err.value!r}{RESET}, violation={YELLOW}{err.message}{RESET}")
    else:
        print(f"  • Parameter in error: {BOLD}{YELLOW}{e.parameter_name}{RESET}")
        print(f"  • Value received:     {BOLD}{RED}{e.value!r}{RESET}")
        print(f"  • Violation details:  {YELLOW}{e.message}{RESET}")


def run_scenario(title: str, telemetry: SatelliteTelemetry):
    print_header(title)
    
    # Format Mode with color coding
    mode_color = CYAN if telemetry.mode == "charging" else (MAGENTA if telemetry.mode == "data_collection" else YELLOW)
    print(f"{BOLD}📊 TELEMETRY STATUS:{RESET}")
    print(f"  • {BOLD}Operational Mode:{RESET} {mode_color}{telemetry.mode.upper()}{RESET}")
    
    # Format Battery State
    bat = telemetry.battery
    bat_status_color = GREEN if bat.status == "charging" else (YELLOW if bat.status == "discharging" else RESET)
    print(f"  • {BOLD}Power & Battery:{RESET} charge={BOLD}{bat.charge_level}%{RESET} | "
          f"status={bat_status_color}{bat.status}{RESET} | "
          f"temp={bat.temperature}°C | draw={bat.current_draw}W")
    
    # Format Solar Panels
    panels_str = []
    for p in telemetry.panels:
        state = f"{GREEN}Deployed{RESET}" if p.deployed else f"{RED}Folded{RESET}"
        panels_str.append(f"[{state} ({p.power_generated}W)]")
    print(f"  • {BOLD}Solar Array:{RESET} " + " ".join(panels_str))
    
    # Format ACS System
    acs = telemetry.acs
    print(f"  • {BOLD}ACS State:{RESET} pointing_dev={BOLD}{acs.pointing_deviation}°{RESET} | "
          f"momentum_wheel={acs.momentum_wheel_speed} rpm | "
          f"reaction_wheels={acs.reaction_wheel_speeds.tolist()}")
    
    # Format Comms
    comms = telemetry.comms
    comms_status = f"{GREEN}VISIBLE{RESET}" if comms.ground_station_visible else f"{RED}OUT OF RANGE{RESET}"
    print(f"  • {BOLD}Communications:{RESET} ground_station={comms_status} | signal={comms.signal_strength} dBm")
    print(f"{CYAN}{'-' * 80}{RESET}")
    
    try:
        check_telemetry(telemetry)
        print(f"{BOLD}{GREEN}🟢 [PASS] Telemetry successfully validated! All constraints SATISFIED.{RESET}")
    except ValidationError as e:
        print(f"{BOLD}{RED}🔴 [FAIL] Telemetry validation FAILED!{RESET}")
        print_validation_error(e)
    except Exception as e:
        print(f"{BOLD}{RED}💥 [ERROR] Unexpected exception: {type(e).__name__}: {e}{RESET}")


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
        print(f"Running {BOLD}validate_subsystem_diagnostics('PWR-002', '12.4', {{'voltage': 28.5}}){RESET}...")
        validate_subsystem_diagnostics("PWR-002", "12.4", {"voltage": 28.5})
        print(f"RESULT: {BOLD}{GREEN}🟢 [PASS] All inputs validated and coerced successfully!{RESET}")
    except ValidationError as e:
        print(f"RESULT: {BOLD}{RED}🔴 [FAIL] Validation failed: {e}{RESET}")
        
    # 9b. Failing constraint check (Full validation parameter pattern mismatch)
    print(f"{CYAN}{'-' * 80}{RESET}")
    try:
        print(f"Running {BOLD}validate_subsystem_diagnostics('INVALID-ID', 12.4, {{'voltage': 28.5}}){RESET}...")
        validate_subsystem_diagnostics("INVALID-ID", 12.4, {"voltage": 28.5})
    except ValidationError as e:
        print(f"RESULT: {BOLD}{RED}🔴 [FAIL] Diagnostics validation FAILED!{RESET}")
        print_validation_error(e)

    # 9c. Failing type coercion (Type-only validation parameter not a float)
    print(f"{CYAN}{'-' * 80}{RESET}")
    try:
        print(f"Running {BOLD}validate_subsystem_diagnostics('PWR-002', 'not-a-float', {{'voltage': 28.5}}){RESET}...")
        validate_subsystem_diagnostics("PWR-002", "not-a-float", {"voltage": 28.5})
    except ValidationError as e:
        print(f"RESULT: {BOLD}{RED}🔴 [FAIL] Diagnostics validation FAILED!{RESET}")
        print_validation_error(e)

    # With Pydantic integration, tasks are validated at construction time.
    print_header("Pre-Commit Task Validation (Pydantic BaseModel Integration)")
    
    from pydantic import ValidationError as PydanticValidationError

    # 10a. Successful Slew Task — construction passes
    try:
        print(f"Attempting to construct healthy SlewTask (Sydney_Station, speed=1.2, coverage=88.5%)...")
        slew_ok = SlewTask(
            poi_name="Sydney_Station",
            target_yaw=45.2,
            target_pitch=-10.5,
            duration_seconds=15.0,
            max_predicted_slew_speed=1.2, # 1.2 deg/s < 2.0 limit
            predicted_coverage=88.5,      # 88.5% in [80.0, 100.0]
        )
        print(f"Validating SlewTask to {BOLD}{slew_ok.poi_name}{RESET} (speed={slew_ok.max_predicted_slew_speed} deg/s, coverage={slew_ok.predicted_coverage}%)")
        print(f"RESULT: {BOLD}{GREEN}🟢 [PASS] Slew task passes pre-commit checks! Ready to upload to command queue.{RESET}")
    except PydanticValidationError as e:
        print(f"RESULT: {BOLD}{RED}🔴 [FAIL] Slew task rejected at construction:\n{e}{RESET}")

    # 10b. Slew Task exceeding speed limit — fails at construction
    print(f"{CYAN}{'-' * 80}{RESET}")
    try:
        print(f"Attempting to construct SlewTask with {BOLD}speed=3.1 deg/s{RESET} (limit: 2.0 deg/s)...")
        slew_too_fast = SlewTask(
            poi_name="Sydney_Station",
            target_yaw=45.2,
            target_pitch=-10.5,
            duration_seconds=5.0,
            max_predicted_slew_speed=3.1, # 3.1 deg/s > 2.0 limit!
            predicted_coverage=95.0,
        )
    except PydanticValidationError as e:
        print(f"RESULT: {BOLD}{RED}🔴 [FAIL] Slew task REJECTED at construction! Pydantic caught the violation:{RESET}")
        print(f"{YELLOW}{e}{RESET}")

    # 10c. Slew Task with poor coverage — fails at construction
    print(f"{CYAN}{'-' * 80}{RESET}")
    try:
        print(f"Attempting to construct SlewTask with {BOLD}coverage=71.2%{RESET} (minimum: 80.0%)...")
        slew_low_coverage = SlewTask(
            poi_name="Sydney_Station",
            target_yaw=45.2,
            target_pitch=-10.5,
            duration_seconds=20.0,
            max_predicted_slew_speed=0.8,
            predicted_coverage=71.2,      # 71.2% < 80.0% min required!
        )
    except PydanticValidationError as e:
        print(f"RESULT: {BOLD}{RED}🔴 [FAIL] Slew task REJECTED at construction! Pydantic caught the violation:{RESET}")
        print(f"{YELLOW}{e}{RESET}")

    # 10d. Slew Task with Multiple Violations — Pydantic reports all errors at once
    print(f"{CYAN}{'-' * 80}{RESET}")
    try:
        print(f"Attempting to construct SlewTask with {BOLD}speed=3.5 AND coverage=75.0%{RESET} (both violate limits)...")
        slew_multiple_fails = SlewTask(
            poi_name="Sydney_Station",
            target_yaw=45.2,
            target_pitch=-10.5,
            duration_seconds=5.0,
            max_predicted_slew_speed=3.5, # 3.5 deg/s > 2.0 limit!
            predicted_coverage=75.0,      # 75% < 80% min required!
        )
    except PydanticValidationError as e:
        print(f"RESULT: {BOLD}{RED}🔴 [FAIL] Slew task REJECTED at construction! Multiple violations detected:{RESET}")
        print(f"{YELLOW}{e}{RESET}")



if __name__ == "__main__":
    main()
