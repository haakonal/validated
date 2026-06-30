# Database Design: Polymorphic Document Table vs. Schema-Strict Tables

> **This is the authoritative design reference** for integrating the `validated` library with a relational database. The SQL schemas, Python modules (`rules.py`, `main.py`), and architectural patterns shown here are illustrative examples — they are not shipped as part of this package. See the [README](README.md) for the library API and satellite validation examples.

When designing a database schema to store operational constraints (flight rules) for satellite subsystems, we face a classic architectural choice:

1. **Single Polymorphic Table (EAV / Document Style)**: Store all constraints in a single table, using a JSONB column to hold the varying parameters of each rule.
2. **Concrete Table-per-Type (Schema-Strict Style)**: Create a dedicated table with specific columns for each constraint type (e.g. `less_than_constraints`, `in_range_constraints`).

This document analyzes the differences, lists the pros and cons of each, and explains the rationale behind choosing the Polymorphic Document style for this project.

---

## 1. Approach Comparison

### Approach A: Single Polymorphic Table (Document Style)
All rules share a single table. Specific settings for the rule are encapsulated inside a JSON document.

```sql
CREATE TABLE operational_constraints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    satellite_norad_id INT REFERENCES satellites(norad_id),
    task_id UUID REFERENCES task_definitions(id),
    context_name VARCHAR(100) NOT NULL,
    parameter_name VARCHAR(100) NOT NULL,
    constraint_type VARCHAR(50) NOT NULL,
    parameters JSONB NOT NULL
);
```

#### Pros:
* **No Database Migrations**: Adding a new constraint type (e.g., `StandardDeviationLimit` or `MedianCheck`) requires no SQL schema changes. You simply write the Python validation class and insert rows.
* **Trivial Queries**: Retrieving all constraints for a specific satellite or task requires a single, fast lookup (`SELECT * WHERE satellite_norad_id = 25544`). No joins or unions are required.
* **Unified Tooling**: Writing Admin APIs, dashboard configuration forms, or rule sync operations is straightforward because you are dealing with a single, uniform dataset.

#### Cons:
* **No Native Column-Level Types**: Values inside JSON are schemaless. Without extra database checks, the database engine cannot ensure that `"min_val"` is a float or that `"max_val"` is present.

---

## 2. Approach B: Concrete Table-per-Type (Schema-Strict Style)
Each constraint class gets its own table containing columns matched specifically to its validation criteria.

```sql
CREATE TABLE less_than_constraints (
    id UUID PRIMARY KEY,
    satellite_norad_id INT REFERENCES satellites(norad_id),
    parameter_name VARCHAR(100) NOT NULL,
    threshold DOUBLE PRECISION NOT NULL
);

CREATE TABLE in_range_constraints (
    id UUID PRIMARY KEY,
    satellite_norad_id INT REFERENCES satellites(norad_id),
    parameter_name VARCHAR(100) NOT NULL,
    min_val DOUBLE PRECISION NOT NULL,
    max_val DOUBLE PRECISION NOT NULL,
    CHECK (min_val <= max_val)
);
```

#### Pros:
* **Strong Database Integrity**: Types, columns, and logical checks (e.g., `min_val <= max_val`) are strictly validated by the database engine at write-time.
* **Simple Indexing**: You can natively index fields directly without needing special document indices (like Postgres GIN).

#### Cons:
* **Heavy Schema Migration Cost**: Every time you define a new validator class in code, you must execute an SQL migration to create a corresponding table.
* **Extremely Complex Queries (Polymorphism)**: Querying the complete constraint set for a satellite requires either:
  1. Performing separate database queries for every single constraint table.
  2. Writing a query with a `UNION` or dozens of `LEFT JOIN`s, which is highly inefficient and harder to maintain as new constraint tables are added.

---

## 3. Head-to-Head Comparison

| Attribute | Single Polymorphic Table (Document) | Concrete Table-per-Type (Schema-Strict) |
| :--- | :--- | :--- |
| **Schema Evolution** | Extremely Easy (0 migrations) | Difficult (requires database migrations) |
| **Query Complexity** | Very Low (single table query) | High (requires joins or multiple queries) |
| **Write Integrity** | Application-Level / JSON Check Validators | Native Database Engine Level |
| **Performance (Retrieval)**| Fast (single index seek) | Moderate to Slow (multiple joins/queries) |
| **Operational Simplicity** | Very High | Low |

---

## 4. Rationale: Why We Chose the Document Style

For spacecraft flight rules, **the Single Polymorphic Table (Document Style)** was chosen for three key architectural reasons:

### 1. The Polymorphism of Rules
Validators are inherently polymorphic—they share the same metadata headers (`satellite_norad_id`, `context_name`, `parameter_name`) but vary in parameters. Querying them polymorphically using Table-per-Type results in messy code and query degradation. A single table with JSON serialization allows the database to remain simple while Python handles the polymorphic object generation.

### 2. Caching at Application Startup
Because our validation architecture fetches rules at application startup (or uses *Before-Import Initialization*), **we only read constraints from the database once**. 
Since the lookup is not performed in the telemetry processing hot loop, minor indexing gains of strict relational columns are irrelevant. Instead, we benefit from the simplicity of a single database query during boot.

### 3. Combining Safety with Flexibility
We can achieve "the best of both worlds" by combining JSON serialization with structural validation:
* **Database-Level JSON Checks**: Using Postgres `CHECK` constraints, we enforce structural rules on the JSON column directly in SQL (ensuring `LessThan` records contain a `threshold` key):
  ```sql
  ALTER TABLE operational_constraints
  ADD CONSTRAINT check_parameter_integrity CHECK (
      (constraint_type = 'LessThan' AND parameters ? 'threshold') OR
      (constraint_type = 'GreaterThan' AND parameters ? 'threshold') OR
      (constraint_type = 'InRange' AND parameters ? 'min_val' AND parameters ? 'max_val') OR
      (constraint_type = 'Length' AND (parameters ? 'min_len' OR parameters ? 'max_len')) OR
      (constraint_type = 'MatchesPattern' AND parameters ? 'pattern') OR
      (constraint_type = 'Check' AND parameters ? 'predicate_key') OR
      (constraint_type = 'Shape' AND parameters ? 'dims') OR
      (constraint_type = 'DType' AND parameters ? 'dtype')
  );
  ```
* **Pydantic Validation**: When loading rules at startup, the parameters are unpacked and validated by Pydantic constraint classes. Any typo in the database config is caught and rejected immediately on application boot, preventing invalid rules from entering the validation engine.

---

## 5. Serializing the `Check` (Predicate) Validator Safely

The `Check` constraint accepts a Python `Callable` (predicate) e.g. `lambda x: x is True`. Since we cannot safely store raw Python code or lambdas directly in a database due to **Remote Code Execution (RCE) vulnerabilities** (avoiding functions like `eval()` or `pickle`), we represent predicates using a **Named Predicate Registry**.

### How the Registry Translation Works
Instead of storing code, the database stores a *reference key*. During startup, Python maps this key to a hardcoded lambda.

```
[ Database Row ]
parameters: {"predicate_key": "is_true", "description": "must be visible"}
       │
       ▼ (Deserilization Query)
[ Python Rules Engine ]
Looks up "is_true" in PREDICATE_REGISTRY -> lambda x: x is True
       │
       ▼ (Instantiation)
Check(lambda x: x is True, "must be visible")
```

### Supporting Parameterized Predicates (Operator Adjustments)
Operators often need to customize calculation parameters dynamically (e.g. checking if a calculated value exceeds a threshold, like `slew_speed * multiplier + offset < limit`). 

To support this safely without database RCE risks, you map the `predicate_key` to a **Factory Function** in Python that receives the database JSON parameters and returns a custom-configured lambda:

```python
# src/satellite/rules.py
from validated import Check

# Parameterized predicate factories
PREDICATE_FACTORIES = {
    # Expects JSON parameters: {"multiplier": 1.5, "limit": 2.0}
    "slew_thermal_calculation": lambda params: (
        lambda speed: speed * params.get("multiplier", 1.0) < params.get("limit", 2.0)
    ),
    
    # Static predicates
    "all_panels_deployed": lambda params: (lambda panels: all(p.deployed for p in panels)),
    "battery_is_charging": lambda params: (lambda status: status == "charging"),
}

def load_constraint(constraint_type: str, parameters: dict) -> Validator:
    if constraint_type == "Check":
        pred_key = parameters.get("predicate_key")
        description = parameters.get("description")
        
        # Resolve the predicate factory using the parameters JSON row
        factory = PREDICATE_FACTORIES.get(pred_key)
        if not factory:
            raise ValueError(f"Unknown predicate key: {pred_key}")
            
        predicate = factory(parameters) # Generates the custom lambda securely!
        return Check(predicate, description)
        
    cls = VALIDATOR_REGISTRY.get(constraint_type)
    return cls(**parameters)
```

---

## 6. The "Hybrid" Architecture: Separating Data Rules from Code Rules

While representing constraints in a database is highly effective for numeric bounds (`LessThan`, `InRange`), it is often a design anti-pattern to store procedural rules (like `Check` lambdas) in database tables. 

Instead, a production satellite system uses a **Hybrid Architecture** that divides constraints into two categories:

### A. Data-Driven Rules (Database)
Dynamic values that operators adjust during orbit to account for hardware degradation, seasonal deviations, or mission changes.
* **Examples**: Max temperatures, minimum battery charges, max slew speeds.
* **Storage**: Single Polymorphic JSONB Database Table.

### B. Structural System Invariants (Code-Only)
Core logical rules built into the spacecraft's design that *never* change. 
* **Examples**: "Solar panels must be deployed in charging mode", "ground station must be visible during downlinks".
* **Storage**: Hardcoded directly inside the Python decorators (e.g. `Check(lambda x: x is True)`) in `validation.py`. This ensures core safety logic is protected from database typos.

### C. Pydantic BaseModel Integration (Model-Level Validation)
Because all `Validator` classes implement Pydantic v2's `__get_pydantic_core_schema__` protocol, database-loaded validators can be applied directly to Pydantic `BaseModel` field definitions — not just to `@validated` function parameters.

This enables a powerful pattern: **task and configuration models that self-validate at construction time**. For example, the satellite domain uses this to enforce constraints on `SlewTask` and `ImagingTask` models:

```python
from pydantic import BaseModel
from validated import Validated, LessThan, InRange, Length

class SlewTask(BaseModel):
    poi_name: Validated[str, Length(min_len=1)]
    max_predicted_slew_speed: Validated[float, LessThan(2.0)]
    predicted_coverage: Validated[float, InRange(80.0, 100.0)]

# Invalid tasks are rejected at construction — before they ever reach the command queue
task = SlewTask(poi_name="Target", max_predicted_slew_speed=3.0, predicted_coverage=92.5)
# → pydantic.ValidationError: must be less than 2.0
```

This pattern complements the decorator-based approach:
* **`@validated` decorator**: Best for functions that process telemetry streams, where parameters come from runtime calculations (e.g. `net_power`, `power_margin`) and NumPy arrays need validation.
* **`BaseModel` fields**: Best for data models like tasks, configurations, and API payloads that should be validated at the point of creation.

---


## 7. Database Payloads for All Validator Models

Here is the complete reference of how each of the 8 constraint types in the `validated` library maps to the JSON `parameters` column in the database:

### 1. `GreaterThan`
* **Python Representation**: `GreaterThan(threshold=0.0)`
* **Database JSON**: `{"threshold": 0.0}`

### 2. `LessThan`
* **Python Representation**: `LessThan(threshold=2.0)`
* **Database JSON**: `{"threshold": 2.0}`

### 3. `InRange`
* **Python Representation**: `InRange(min_val=-10.0, max_val=40.0)`
* **Database JSON**: `{"min_val": -10.0, "max_val": 40.0}`

### 5. `Length`
* **Python Representation**: `Length(min_len=1, max_len=5)`
* **Database JSON**: `{"min_len": 1, "max_len": 5}` (Either key can be omitted if only enforcing a minimum or maximum boundary)

### 5. `MatchesPattern`
* **Python Representation**: `MatchesPattern(pattern=r"^(ACS|PWR|COM)-\d{3}$")`
* **Database JSON**: `{"pattern": "^(ACS|PWR|COM)-\\\\d{3}$"}`

### 6. `Check` (Custom Predicates)
* **Python Representation**: `Check(predicate=PREDICATE_REGISTRY["is_even"], description="must be even")`
* **Database JSON**: `{"predicate_key": "is_even", "description": "must be even"}`

### 7. `Shape` (NumPy Array Dimensions)
* **Python Representation**: `Shape(None, 3)` or `Shape(3)`
* **Database JSON**: `{"dims": [null, 3]}` or `{"dims": [3]}` (Wildcard dimensions are represented as `null`, `*`, or `-1`)

### 8. `DType` (NumPy Array Data Type)
* **Python Representation**: `DType("float64")`
* **Database JSON**: `{"dtype": "float64"}`

---

## 8. Runtime Hot-Reloading in Docker (Proxy Validator Pattern)

A major limitation of the **Before-Import Initialization** pattern is that Python decorators evaluate annotations exactly **once** (at import-time). 

If your application is running inside a Docker container, modifying thresholds in the database will have **no effect** on the compiled functions unless you reboot the container/process. 

To support real-time **hot-reloading without restarts**, we can implement a **Proxy Validator Pattern**. Instead of binding the concrete database constraint to the decorator statically, we bind a static `Proxy` constraint that queries our in-memory cache dynamically on every execution call.

```
[ validate_slew_task() called ]
              │
              ▼ (decorator triggers check)
[ ProxyValidator.validate(value) ]
              │
              ▼ (looks up current version)
[ Fetch rules.get_rule(norad_id, context, param) ] ── (Can be updated live in memory!)
              │
              ▼ (delegates check)
[ LessThan(2.5).validate(value) ]
```

### Step 1: Implement the `ProxyValidator` Class
```python
# src/constraints/models.py or src/satellite/rules.py
class ProxyValidator(Validator):
    def __init__(self, context_name: str, parameter_name: str, get_active_sat_id_fn):
        self.context_name = context_name
        self.parameter_name = parameter_name
        self.get_active_sat_id_fn = get_active_sat_id_fn

    def _get_active_constraint(self) -> Validator:
        # 1. Fetch current active spacecraft ID from thread/execution context
        norad_id = self.get_active_sat_id_fn()
        # 2. Fetch the active compiled constraint object from the memory cache
        rule = rules.get_rule(norad_id, self.context_name, self.parameter_name)
        if not rule:
            raise ValueError(f"No active constraint configured for {norad_id}:{self.context_name}:{self.parameter_name}")
        return rule

    def validate(self, value: Any) -> bool:
        return self._get_active_constraint().validate(value)

    def error_message(self, value: Any) -> str:
        return self._get_active_constraint().error_message(value)
```

### Step 2: Annotate Functions statically using Proxies
Because the proxy object itself is created once at class import-time, the decorator signature remains static, but the checks are fully dynamic:

```python
# src/satellite/validation.py
import contextvars
from typing import Annotated
from validated import validated

# ContextVar tracking active satellite ID in the current execution thread
active_sat_id = contextvars.ContextVar("active_sat_id")

# Static proxies pointing to dynamic lookups
slew_speed_proxy = ProxyValidator("slew_task", "max_slew_speed", active_sat_id.get)

@validated
def validate_slew_task(
    poi_name: str,
    max_slew_speed: Annotated[float, slew_speed_proxy],
) -> bool:
    return True
```

### Step 3: Hot-Reloading Live in Memory
When operators change database thresholds, the API triggers a refresh to update the `rules.ACTIVE_VALIDATORS` dictionary in memory:

```python
def on_database_update_event(db_connection):
    """Event handler triggered when database rules change. Zero downtime, zero restarts."""
    # Re-fetches database rows and overwrites the in-memory cache dictionary
    rules.load_all_from_database(db_connection)
```
Using this pattern, the Docker container runs continuously, and database updates take effect instantly on the very next validation call.
