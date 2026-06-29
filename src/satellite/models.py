import numpy as np
from pydantic import BaseModel, ConfigDict
from validated import Validated, GreaterThan, LessThan, InRange, Length


class BatteryState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    charge_level: Validated[float, InRange(0.0, 100.0)]  # Percentage: 0.0 to 100.0
    status: str          # "charging", "discharging", "standby", "full", "empty"
    temperature: Validated[float, InRange(-40.0, 85.0)]   # degrees Celsius (hardware limits)
    current_draw: Validated[float, GreaterThan(-1.0)]     # W (negative would mean impossible reverse flow)

class SolarPanelState(BaseModel):
    deployed: bool
    power_generated: Validated[float, InRange(0.0, 500.0)] # W (0 to max panel capacity)

class ACSState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # 3 reaction wheels (fine control)
    reaction_wheel_speeds: np.ndarray # shape (3,), float64 — validated via @validated decorator
    momentum_wheel_speed: float       # scalar, rpm
    pointing_deviation: Validated[float, InRange(0.0, 180.0)]  # degrees (0 = perfect alignment)

class CommsState(BaseModel):
    ground_station_visible: bool
    signal_strength: float            # dBm

class SatelliteTelemetry(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    mode: str  # "charging" or "data_collection" or "safe"
    battery: BatteryState
    panels: list[SolarPanelState]
    acs: ACSState
    comms: CommsState


# --- Task models with built-in validation via Pydantic integration ---
# These models self-validate at construction time. Invalid tasks are rejected
# immediately without needing a separate validation function.

class SlewTask(BaseModel):
    poi_name: Validated[str, Length(min_len=1)]
    target_yaw: Validated[float, InRange(-180.0, 180.0)]
    target_pitch: Validated[float, InRange(-90.0, 90.0)]
    duration_seconds: Validated[float, GreaterThan(0.0)]
    max_predicted_slew_speed: Validated[float, LessThan(2.0)]  # Max 2 deg/s
    predicted_coverage: Validated[float, InRange(80.0, 100.0)]  # Min 80% coverage


class ImagingTask(BaseModel):
    target_poi: Validated[str, Length(min_len=1)]
    exposure_time: Validated[float, InRange(0.01, 5.0)]        # 10ms to 5s
    cloud_cover_limit: Validated[float, LessThan(20.0)]        # Max 20% cloud cover
    spectral_bands: Validated[list[str], Length(min_len=1, max_len=5)]  # 1 to 5 bands

