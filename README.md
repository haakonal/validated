# Constraints & Satellite Validation Engine

This repository contains:
1. **`constraints`**: A lightweight data validation and type coercion library using Pydantic and NumPy under the hood.
2. **`satellite`**: A realistic simulation domain package (located under `src/satellite`) demonstrating how to enforce operational constraints on complex satellite subsystems.

---

## 1. How the `constraints` Package Works

The `constraints` library leverages Python's PEP 593 (`typing.Annotated`) metadata to attach validation rules directly to function arguments. 

### File-by-File Implementation

```mermaid
graph TD
    A["Function Call"] --> B["@constrained wrapper"]
    B --> C["inspect.signature / typing.get_type_hints"]
    C --> D["Pydantic Type Coercion / Validation"]
    D --> E["Custom Constraint Validation"]
    E --> F["Execute Original Function"]
    F --> G["Validate Return Value"]
    G --> H["Return Value"]
```

#### A. [src/constraints/exceptions.py](src/constraints/exceptions.py)
This module defines the custom `ConstraintValidationError` exception.
* **Implementation**: Subclasses the standard `ValueError` and stores contextual information: `parameter_name`, `value` (that caused the violation), `constraint` (the constraint object violated), and the `message`.
* **Design Decision**: Explicitly tracking the failing parameter name and the rejected value allows upstream systems (like telemetry managers or REST APIs) to render targeted error messages, log failures, or trigger automatic safing procedures without guessing which argument failed.

#### B. [src/constraints/models.py](src/constraints/models.py)
This file defines the class hierarchy of all validation rule classes.
* **`Constraint` Base Class**:
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
  Using objects allows constraints to be parameterizable (e.g., storing boundaries inside `min_val` and `max_val`). When a validation fails, the constraint instance is returned along with the exception, allowing the caller to inspect metadata or build context-aware logs (e.g. `isinstance(e.constraint, Shape)`).

#### C. [src/constraints/decorator.py](src/constraints/decorator.py)
This is the core validation engine that implements the `@constrained` decorator.
* **Implementation Details**:
  1. **Signature Parsing**: Uses `inspect.signature(func)` to determine names and order of arguments.
  2. **Type Extraction**: Uses `typing.get_type_hints(func, include_extras=True)` to retrieve the type signatures. Passing `include_extras=True` ensures that metadata inside `Annotated[Type, Metadata]` is preserved.
  3. **Value Coercion**: For each argument, the decorator runs the value through Pydantic's `TypeAdapter(base_type).validate_python(val)`. This ensures that inputs (e.g. string `"5"`) are automatically coerced to their proper types (e.g. integer `5`).
  4. **Constraint Enforcement**: Iterates over any metadata constraints extracted from `Annotated` parameters and calls `.validate()` on them.
  5. **Variadic Support**: Special logic safely unpacks and validates positional arguments (`*args` / `VAR_POSITIONAL`) and keyword arguments (`**kwargs` / `VAR_KEYWORD`).
  6. **Return Value Checks**: Finally, it repeats this process on the return value of the function before sending it back.
* **Design Decision**: *Why Pydantic TypeAdapter?*
  Instead of writing manual type checkers for floats, dicts, lists, and model definitions, Pydantic's underlying Rust validation engine handles extremely fast type coercion and validation. By separating coercion (type safety) from custom constraints (value safety), the code remains incredibly clean.

### Selective Validation Levels

The `@constrained` decorator supports three levels of validation on a parameter-by-parameter basis:

1. **Full Validation (Type Coercion + Value Constraints)**:
   Using `Annotated[Type, Constraint]`. The parameter is type-checked (and coerced if possible), then all associated constraints are validated.
   ```python
   # E.g. subsystem_id: Annotated[str, MatchesPattern(r"^(ACS|PWR|COM)-\d{3}$")]
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
Instead of nesting complex `if/else` checks inside a single massive function, we divide and conquer using the `@constrained` decorator:

#### A. Checking NumPy Arrays
The Attitude Control System controls orientation using 3 reaction wheels. If the telemetry lists only 2 wheels or uses the wrong encoding, it's a structural failure. We enforce this cleanly using annotations:
```python
@constrained
def check_reaction_wheels(
    wheel_speeds: Annotated[np.ndarray, Shape(3), DType(np.float64)]
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
@constrained
def validate_charging_telemetry(
    panels_deployed: Annotated[bool, Check(lambda x: x is True, "all solar panels must be deployed")],
    net_power: Annotated[float, GreaterThan(0.0)],
    battery_status: Annotated[str, Check(lambda s: s == "charging", "battery status must be 'charging'")],
    battery_charge_level: Annotated[float, InRange(50.0, 100.0)],
    sun_pointing_deviation: Annotated[float, LessThan(5.0)],
    reaction_wheel_speeds: Annotated[np.ndarray, Shape(3), DType(np.float64)],
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
@constrained
def validate_slew_task(
    poi_name: Annotated[str, Length(min_len=1)],
    max_slew_speed: Annotated[float, LessThan(2.0)],             # Slew speed limit: 2.0 deg/s
    predicted_coverage: Annotated[float, InRange(80.0, 100.0)],  # Min coverage requirement: 80%
) -> bool:
    return True
```

Tasks are modeled via `SlewTask` and `ImagingTask` and routed through `validate_task()`.

---

## 3. Database Configuration (Dynamic Constraints)

In production satellite command and control systems, constraint thresholds (e.g. maximum slew speeds, temperature ranges) are frequently adjusted by mission operators. To avoid compiling new code for every operational change, constraints can be stored in a relational database (like PostgreSQL or SQLite) and loaded dynamically.

### A. Database Schema
You can store constraints in a `constraints` table with a JSON column for arguments:

```sql
CREATE TABLE operational_constraints (
    id SERIAL PRIMARY KEY,
    context_name VARCHAR(100) NOT NULL, -- e.g., "slew_task" or "charging_mode"
    parameter_name VARCHAR(100) NOT NULL, -- e.g., "max_slew_speed" or "battery_charge_level"
    constraint_type VARCHAR(50) NOT NULL, -- e.g., "LessThan", "InRange"
    parameters JSONB NOT NULL             -- e.g., '{"threshold": 2.0}' or '{"min_val": 50, "max_val": 100}'
);
```

### B. Rule Registry & Deserialization
In your validation engine, create a registry map that connects string keys from the database to the Python constraint classes:

```python
from constraints import GreaterThan, LessThan, InRange, Length, MatchesPattern, Constraint

# Map DB strings to Python classes
CONSTRAINT_REGISTRY = {
    "GreaterThan": GreaterThan,
    "LessThan": LessThan,
    "InRange": InRange,
    "Length": Length,
    "MatchesPattern": MatchesPattern,
}

def load_constraint(constraint_type: str, parameters: dict) -> Constraint:
    """Instantiates a constraint object dynamically from DB data."""
    constraint_class = CONSTRAINT_REGISTRY.get(constraint_type)
    if not constraint_class:
        raise ValueError(f"Unknown constraint type: {constraint_type}")
    return constraint_class(**parameters)
```

### C. Dynamic Run-Time Validation
Because decorators run at import-time, database-driven constraints are best checked in a validation loop inside your task manager before committing a command:

```python
from constraints import ConstraintValidationError

def validate_task_against_db(task_type: str, task_payload: dict, db_connection):
    """
    Queries constraints for the given task context from the DB,
    reconstructs the objects, and validates the task data at runtime.
    """
    # 1. Fetch rules from database (conceptual)
    cursor = db_connection.cursor()
    cursor.execute(
        "SELECT parameter_name, constraint_type, parameters FROM operational_constraints WHERE context_name = %s",
        (task_type,)
    )
    rules = cursor.fetchall()

    # 2. Iterate and validate each constraint
    for parameter_name, constraint_type, parameters in rules:
        if parameter_name not in task_payload:
            continue
        
        value = task_payload[parameter_name]
        constraint = load_constraint(constraint_type, parameters)

        # 3. Perform check
        if not constraint.validate(value):
            raise ConstraintValidationError(
                parameter_name=parameter_name,
                value=value,
                constraint=constraint,
                message=constraint.error_message(value)
            )
    return True
```

### D. Optimization: Caching Constraints at Startup
Querying the database and instantiating constraint objects on every validation call adds latency. In hot loops or real-time control streams, you can fetch all constraints at application **startup**, instantiate them once, and cache them in memory:

```python
# In-memory registry cache of loaded constraints
# Structure: { context_name: [(parameter_name, constraint_object), ...] }
ACTIVE_CONSTRAINTS: dict[str, list[tuple[str, Constraint]]] = {}

def initialize_constraints(db_connection):
    """Fetches all constraints from DB and caches their initialized Python objects in memory."""
    global ACTIVE_CONSTRAINTS
    cursor = db_connection.cursor()
    cursor.execute("SELECT context_name, parameter_name, constraint_type, parameters FROM operational_constraints")
    
    # Rebuild the cache dictionary
    temp_cache = {}
    for context, param, c_type, params in cursor.fetchall():
        constraint_obj = load_constraint(c_type, params)
        if context not in temp_cache:
            temp_cache[context] = []
        temp_cache[context].append((param, constraint_obj))
        
    ACTIVE_CONSTRAINTS = temp_cache

def validate_task_optimized(task_type: str, task_payload: dict) -> bool:
    """Validates the task using the pre-compiled in-memory constraint cache."""
    rules = ACTIVE_CONSTRAINTS.get(task_type, [])
    for parameter_name, constraint in rules:
        if parameter_name not in task_payload:
            continue
        
        value = task_payload[parameter_name]
        if not constraint.validate(value):
            raise ConstraintValidationError(
                parameter_name=parameter_name,
                value=value,
                constraint=constraint,
                message=constraint.error_message(value)
            )
    return True
```

#### Why use this approach?
1. **Performance**: Bypasses network and filesystem latency entirely during the verification phase. Checking constraints becomes a pure in-memory Python method call (taking nanoseconds instead of milliseconds).
2. **Zero Object Instantiation Overhead**: You instantiate constraint objects exactly once when the application boots up.
3. **Hot-Reloading**: If operators update rules in the database, you can dynamically update the active constraints in-memory without rebooting the system by simply re-running `initialize_constraints(db_connection)`.

### E. Advanced: Before-Import Initialization (Retaining the Decorator Syntax)

If you want to keep the clean, declarative `@constrained` decorator syntax in `validation.py` but still configure constraints from the database dynamically, you can use **Before-Import Initialization**. 

Because Python type hints and decorators are executed at **import-time**, you can initialize the database configurations *before* importing the module containing your validated functions.

#### 1. Define a Shared Config Module (`rules.py`)
```python
# src/satellite/rules.py
from constraints import Constraint, LessThan, InRange

# Global references for constraints (will be instantiated from DB on startup)
MAX_SLEW_SPEED_LIMIT: Constraint = None
BATTERY_CHARGE_RANGE: Constraint = None

def load_from_database(db_connection):
    global MAX_SLEW_SPEED_LIMIT, BATTERY_CHARGE_RANGE
    # Fetch parameters from the database...
    # For demonstration:
    MAX_SLEW_SPEED_LIMIT = LessThan(db_slew_threshold)
    BATTERY_CHARGE_RANGE = InRange(db_charge_min, 100.0)
```

#### 2. Declare Functions referencing the Config (`validation.py`)
In your validation module, import the config module. When Python executes `@constrained` at import-time, it will resolve the current instantiated constraint values:

```python
# src/satellite/validation.py
from typing import Annotated
from constraints import constrained
import satellite.rules as rules

@constrained
def validate_slew_task(
    poi_name: str,
    # References the dynamic object instantiated during startup
    max_slew_speed: Annotated[float, rules.MAX_SLEW_SPEED_LIMIT],
) -> bool:
    return True
```

#### 3. Initialize in Application Boot (`main.py`)
Initialize your rules *before* importing your validation routines:

```python
# main.py
import sqlite3
import satellite.rules as rules

# 1. Connect to database and load rules
conn = sqlite3.connect("spacecraft.db")
rules.load_from_database(conn)

# 2. NOW import validation routines (which compiles the decorator with the loaded values)
from satellite.validation import validate_slew_task

# 3. Call functions with fully active database-defined rules!
validate_slew_task("POI-452", 1.2)
```

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

