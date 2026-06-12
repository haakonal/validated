import numpy as np
from pydantic import BaseModel, ConfigDict

class BatteryState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    charge_level: float  # Percentage: 0.0 to 100.0
    status: str          # "charging", "discharging", "standby", "full", "empty"
    temperature: float   # degrees Celsius
    current_draw: float  # W

class SolarPanelState(BaseModel):
    deployed: bool
    power_generated: float # W

class ACSState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # 3 reaction wheels (fine control)
    reaction_wheel_speeds: np.ndarray # shape (3,), float64
    momentum_wheel_speed: float       # scalar, rpm
    pointing_deviation: float         # degrees

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


class SlewTask(BaseModel):
    poi_name: str
    target_yaw: float
    target_pitch: float
    duration_seconds: float
    max_predicted_slew_speed: float  # deg/s
    predicted_coverage: float        # percentage, 0.0 to 100.0


class ImagingTask(BaseModel):
    target_poi: str
    exposure_time: float             # seconds
    cloud_cover_limit: float         # percentage, 0.0 to 100.0
    spectral_bands: list[str]

