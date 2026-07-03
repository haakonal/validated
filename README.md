# Validated

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Validated** is a lightweight, incredibly fast data validation and type coercion library using Pydantic and NumPy under the hood. It allows you to attach extremely expressive, parameterized constraint rules directly to your function signatures using standard Python `typing.Annotated`.

> 🚀 **Read the full documentation at: [https://haakonal.github.io/validated/](https://haakonal.github.io/validated/)**

## Installation

```bash
pip install .
```

To install the documentation tools, use:
```bash
pip install .[docs]
```

## Quick Start

Instead of cluttering your code with `if/else` constraint checks, handle them elegantly at the boundary layer:

```python
import numpy as np
from validated import validated, Validated, LessThan, InRange, MatchesPattern, Shape, DType

@validated
def validate_telemetry(
    # Type coercion and numeric boundaries
    battery_charge: Validated[float, InRange(50.0, 100.0)],
    
    # String regex matching
    subsystem_id: Validated[str, MatchesPattern(r"^(ACS|PWR|COM)-\d{3}$")],
    
    # Deep NumPy array structural validation!
    reaction_wheel_speeds: Validated[np.ndarray, Shape(3), DType(np.float64)],
) -> bool:
    print(f"Validated Telemetry for {subsystem_id}!")
    return True

# Valid:
validate_telemetry(80.5, "ACS-101", np.array([1.1, 2.2, 3.3], dtype=np.float64))

# Invalid (raises ValidationError):
validate_telemetry(40.0, "ACS-101", np.array([1.1, 2.2, 3.3], dtype=np.float64))
# -> "Value error, must be between 50.0 and 100.0"
```

## Documentation

For a complete guide, including:
- How to configure constraints inside Pydantic BaseModels
- Database Architecture (Storing and hot-reloading rules from PostgreSQL)
- The Satellite Demo Application

Please visit our [Documentation Site](https://haakonal.github.io/validated/).

## Testing

```bash
pytest tests
```

## License

This project is licensed under the MIT License.
