# Constraints & Satellite Validation Engine

This repository contains:
1. **`validated`**: A lightweight data validation and type coercion library using Pydantic and NumPy under the hood.
2. **`satellite`**: A realistic simulation domain package (located under `src/satellite`) demonstrating how to enforce operational constraints on complex satellite subsystems.

---

## 1. How the `validated` Package Works

The `validated` library leverages Python's PEP 593 (`typing.Annotated`) metadata to attach validation rules directly to function arguments. 

### File-by-File Implementation

```mermaid
graph TD
    A["Function Call"] --> B["@validated wrapper"]
    B --> C["pydantic.validate_call"]
    C --> D["Pydantic Type Coercion / Core Schema Generation"]
    D --> E["Custom Constraint Validation"]
    E --> F["Execute Original Function"]
    F --> G["Validate Return Value"]
    G --> H["Return Value"]
```

#### A. [src/validated/models.py](src/validated/models.py)
This file defines the class hierarchy of all validation rule classes.
* **`Validator` Base Class**:
  Defines the abstract interface: `validate(self, value) -> bool` and `error_message(self, value) -> str`.
* **Standard Constraints**:
  - `GreaterThan` & `LessThan`: Basic boundary checks.
  - `InRange`: Keeps numerical values inside a closed interval `[min_val, max_val]`.
  - `Length`: Asserts string or list length criteria.
  - `MatchesPattern`: Enforces regex constraints on strings.
  - `Check`: Accepts a custom predicate callable (like a lambda or function) and description, offering arbitrary custom checks.
* **NumPy-specific Constraints**:
  - `Shape`: Inspects a NumPy array's `.shape` attribute and matches it to a predefined tuple template (supporting wildcard constraints using `-1`, `*`, or `None`).
  - `DType`: Validates the NumPy array's data type.
* **Design Decision**: *Why class-based instead of pure functions?*
  Using objects allows constraints to be parameterizable (e.g., storing boundaries inside `min_val` and `max_val`). They seamlessly integrate with Pydantic's underlying core schema generation.

#### B. [src/validated/decorator.py](src/validated/decorator.py)
This is the core validation engine that exposes the `@validated` decorator.
* **Implementation Details**:
  The entire decorator is now a thin wrapper around Pydantic's `@validate_call`. Because our `Validator` classes natively implement Pydantic's `__get_pydantic_core_schema__`, Pydantic handles all the heavy lifting: signature parsing, variadic unpacking, and type coercion. 
  The `@validated` decorator simply configures `@validate_call` with `arbitrary_types_allowed=True` to seamlessly support NumPy arrays.
* **Design Decision**: *Why delegate to Pydantic?*
  Instead of writing manual type checkers and reflection logic (`inspect.signature`), we leverage Pydantic's underlying Rust validation engine. This handles extremely fast type coercion and validation, making the codebase incredibly clean, reliable, and performant.

### Selective Validation Levels

The `@validated` decorator supports three levels of validation on a parameter-by-parameter basis:

1. **Full Validation (Type Coercion + Value Constraints)**:
   Using `Validated[Type, Constraint]`. The parameter is type-checked (and coerced if possible), then all associated constraints are validated.
   ```python
   # E.g. subsystem_id: Validated[str, MatchesPattern(r"^(ACS|PWR|COM)-\d{3}$")]
   ```
2. **Type Validation Only (No Value Constraints)**:
   Using a plain type hint (e.g., `float`). The parameter is type-checked and coerced, but no custom constraints are run.
   ```python
   # E.g. temperature_offset: float
   ```
3. **No Validation (Bypassed)**:
   Using `Any` (or omitting annotations). The parameter is completely ignored by the decorator.
   ```python
   # E.g. raw_telemetry: Any
   ```

This is demonstrated in [src/satellite/validation.py](src/satellite/validation.py) via `validate_subsystem_diagnostics`.

### Standard Pydantic Integration

All `Validator` classes implement Pydantic v2's `__get_pydantic_core_schema__` protocol, meaning they work **natively** as `Annotated` metadata on Pydantic `BaseModel` fields — no `@validated` decorator needed:

```python
from pydantic import BaseModel
from validated import Validated, GreaterThan, LessThan, InRange, MatchesPattern

class SatelliteConfig(BaseModel):
    max_slew_speed: Validated[float, LessThan(2.0)]
    battery_charge: Validated[float, InRange(50.0, 100.0)]
    subsystem_id: Validated[str, MatchesPattern(r"^(ACS|PWR|COM)-\d{3}$")]

# Valid — passes all validators
config = SatelliteConfig(max_slew_speed=1.5, battery_charge=80.0, subsystem_id="ACS-101")

# Invalid — raises Pydantic's ValidationError with our custom messages
config = SatelliteConfig(max_slew_speed=3.0, battery_charge=80.0, subsystem_id="ACS-101")
# ValidationError: 1 validation error for SatelliteConfig
#   max_slew_speed
#     Value error, must be less than 2.0
```

Multiple validators can be stacked on a single field:
```python
class ScoreModel(BaseModel):
    score: Validated[float, GreaterThan(0.0), LessThan(100.0)]
```

Pydantic's type coercion still works transparently — string `"5"` is coerced to `int(5)` before the validator runs.

> **Note**: NumPy arrays are fully supported! The library provides a custom `ValidatorBaseModel` that automatically handles `arbitrary_types_allowed=True`. Just use standard Python type hints like `numpy.ndarray` or `numpy.typing.NDArray[np.float64]` wrapped in `Validated`!

---

## 2. The `satellite` Package & Subsystem Validation

Real-world systems, such as satellites, consist of numerous interconnected discrete and continuous states. Depending on the current operational mode of the satellite, different validation rules must hold true to prevent catastrophic failures.

The `satellite` package, located under `src/satellite`, models this telemetry stream.

### Subsystem Models ([src/satellite/models.py](src/satellite/models.py))
We use Pydantic models to represent the telemetry state:
* **`BatteryState`**: Continuous values like `charge_level`, `temperature`, `current_draw`, and discrete status (`"charging"`, `"discharging"`).
* **`SolarPanelState`**: `deployed` status and continuous `power_generated` values.
* **`ACSState` (Attitude Control System)**: Tracks orientation (`pointing_deviation` from target) and reaction wheels.
  - Crucially, reaction wheel speeds are represented as a 3D vector NumPy array (`shape=(3,)`), which must consist of double-precision floats.
* **`CommsState`**: Links visibility to the ground station.
* **`SatelliteTelemetry`**: A wrapper representing the aggregate state of the spacecraft along with its current `mode`.

### Subsystem Telemetry Validation ([src/satellite/validation.py](src/satellite/validation.py))
Instead of nesting complex `if/else` checks inside a single massive function, we divide and conquer using the `@validated` decorator:

#### A. Checking NumPy Arrays
The Attitude Control System controls orientation using 3 reaction wheels. If the telemetry lists only 2 wheels or uses the wrong encoding, it's a structural failure. We enforce this cleanly using annotations:
```python
@validated
def check_reaction_wheels(
    wheel_speeds: Validated[np.ndarray, Shape(3), DType(np.float64)]
) -> bool:
    return True
```

#### B. Charging Mode Rules
In `charging` mode, we assert that:
1. Solar panels are fully deployed.
2. The panels are facing the sun (deviation < 5.0 degrees).
3. The battery status is set to `"charging"`.
4. The battery charge level is in a safe region (`[50.0, 100.0]`).
5. Net power is positive (total generated - total drawn > 0).

```python
@validated
def validate_charging_telemetry(
    panels_deployed: Validated[bool, Check(lambda x: x is True, "all solar panels must be deployed")],
    net_power: Validated[float, GreaterThan(0.0)],
    battery_status: Validated[str, Check(lambda s: s == "charging", "battery status must be 'charging'")],
    battery_charge_level: Validated[float, InRange(50.0, 100.0)],
    sun_pointing_deviation: Validated[float, LessThan(5.0)],
    reaction_wheel_speeds: Validated[np.ndarray, Shape(3), DType(np.float64)],
) -> bool:
    return True
```

#### C. Data Collection Mode Rules
During science observations, requirements change:
1. Ground station contact must be active to stream scientific data.
2. The pointing deviation must be extremely precise (deviation < 1.0 degree).
3. The thermal subsystem must keep the batteries between `-10` and `40` degrees Celsius.
4. Current draw cannot exceed the safe battery limit (verified using a `power_margin > 0` constraint).

#### D. Pre-Commit Task Safety Checking
Before committing a planned spacecraft task (e.g., targeting a Point of Interest), we run pre-commit validations to prevent execution of rules that violate satellite thresholds (such as excessive slew speeds which could desaturate reaction wheels, or insufficient coverage):

```python
# From src/satellite/validation.py
@validated
def validate_slew_task(
    poi_name: Validated[str, Length(min_len=1)],
    max_slew_speed: Validated[float, LessThan(2.0)],             # Slew speed limit: 2.0 deg/s
    predicted_coverage: Validated[float, InRange(80.0, 100.0)],  # Min coverage requirement: 80%
) -> bool:
    return True
```

Tasks are modeled via `SlewTask` and `ImagingTask` and routed through `validate_task()`.

---

## 3. Database Configuration & Before-Import Initialization

In production spacecraft ground stations, constraint thresholds (e.g., maximum slew speeds, cloud cover limits, minimum battery states) are stored in databases. This allows operators to adjust safety guidelines on a per-satellite or per-task basis without redeploying code.

The database architecture for this project uses a **Single Polymorphic Table (Document Style)** — all constraint types share one table with a JSONB `parameters` column. This design supports:

* **Before-Import Initialization**: Loading constraint values from the database at startup, then binding them into the `@validated` decorator annotations before `validation.py` is imported.
* **Per-Satellite Rules**: Different thresholds for different spacecraft (e.g., an older satellite with degraded reaction wheels might use `LessThan(1.0)` for slew speed, while a newer one uses `LessThan(3.0)`).
* **Safe Predicate Serialization**: `Check` predicates are stored as registry keys (not raw code) and resolved to hardcoded lambdas at startup via a Named Predicate Registry.
* **Runtime Hot-Reloading (Docker)**: A Proxy Constraint pattern enables live threshold updates without container restarts.

> **Note**: The database schema, rules module, closure-based compilation, predicate factories, and the Proxy Constraint pattern are documented in detail in [DATABASE_DESIGN.md](DATABASE_DESIGN.md). The code examples in that document are a **design reference** for integrating the library with a real database — they are not shipped as part of this package.

---

## 4. How to Run & Verify the Code

Make sure your virtual environment is active:
```powershell
.venv\Scripts\Activate.ps1
```

### Running the Tests
To run all tests (including the core library tests and the satellite examples tests):
```bash
pytest tests
```

### Running the Telemetry Simulation Demo
Run the telemetry validation demo script from the root workspace:
```bash
python run_satellite_demo.py
```
This script runs a sequence of telemetry packages simulating normal operations, bad sensor dimensions, battery overheating, and pointing errors, showcasing how constraints elegantly isolate and catch exceptions.

