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


def print_header(title: str):
    print("\n" + "=" * 80)
    print(f" SCENARIO: {title}".center(80))
    print("=" * 80)


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
    except ConstraintValidationError as e:
        print("RESULT: [FAIL] Telemetry validation FAILED!")
        print(f"  - Parameter in error: {e.parameter_name}")
        print(f"  - Value received: {e.value!r}")
        print(f"  - Violation details: {e.message}")
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


if __name__ == "__main__":
    main()
