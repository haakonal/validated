"""Experiment: Can we use @validate_call with our existing validators?

Run with:  python test_validate_call_experiment.py
"""

from typing import Annotated

import numpy as np
from pydantic import ConfigDict, validate_call
from pydantic import ValidationError as PydanticValidationError

from validated import Check, DType, GreaterThan, InRange, Length, LessThan, MatchesPattern, Shape

# ── Test 1: Basic numeric validators ──────────────────────────────────────
print("=" * 60)
print("Test 1: Basic numeric validators with @validate_call")
print("=" * 60)


@validate_call
def process_numbers(
    pos: Annotated[int, GreaterThan(0)],
    neg: Annotated[float, LessThan(0.0)],
    percent: Annotated[float, InRange(0.0, 100.0)],
) -> float:
    return pos + neg + percent


# Valid
try:
    result = process_numbers(5, -2.5, 50.0)
    print(f"  ✅ Valid call: {result}")
except Exception as e:
    print(f"  ❌ Valid call failed: {type(e).__name__}: {e}")

# Invalid — do we get multi-error collection?
try:
    process_numbers(-1, 5.0, 150.0)
    print("  ❌ Should have raised!")
except PydanticValidationError as e:
    print(f"  ✅ Multi-error collection: {e.error_count()} errors")
    for err in e.errors():
        print(f"     loc={err['loc']}, msg={err['msg']}")
except Exception as e:
    print(f"  ❌ Unexpected error type: {type(e).__name__}: {e}")

# Coercion
try:
    result = process_numbers("5", "-2.5", "50.0")
    print(f"  ✅ Coercion works: {result}")
except Exception as e:
    print(f"  ❌ Coercion failed: {type(e).__name__}: {e}")


# ── Test 2: String validators ─────────────────────────────────────────────
print()
print("=" * 60)
print("Test 2: String validators")
print("=" * 60)


@validate_call
def process_strings(
    username: Annotated[str, Length(min_len=3, max_len=10)],
    email: Annotated[str, MatchesPattern(r"^[^@]+@[^@]+\.[^@]+$")],
):
    return username, email


try:
    result = process_strings("alice", "alice@example.com")
    print(f"  ✅ Valid call: {result}")
except Exception as e:
    print(f"  ❌ Valid call failed: {type(e).__name__}: {e}")

try:
    process_strings("ab", "invalid-email")
except PydanticValidationError as e:
    print(f"  ✅ Multi-error: {e.error_count()} errors")
    for err in e.errors():
        print(f"     loc={err['loc']}, msg={err['msg']}")
except Exception as e:
    print(f"  ❌ Unexpected: {type(e).__name__}: {e}")


# ── Test 3: Check() validator ─────────────────────────────────────────────
print()
print("=" * 60)
print("Test 3: Check() validator")
print("=" * 60)


@validate_call
def process_even(x: Annotated[int, Check(lambda v: v % 2 == 0, "must be even")]):
    return x


try:
    result = process_even(4)
    print(f"  ✅ Valid call: {result}")
except Exception as e:
    print(f"  ❌ Valid call failed: {type(e).__name__}: {e}")

try:
    process_even(5)
except PydanticValidationError as e:
    print(f"  ✅ Check violation caught: {e.error_count()} error(s)")
    for err in e.errors():
        print(f"     loc={err['loc']}, msg={err['msg']}")
except Exception as e:
    print(f"  ❌ Unexpected: {type(e).__name__}: {e}")


# ── Test 4: NumPy with arbitrary_types_allowed ─────────────────────────────
print()
print("=" * 60)
print("Test 4: NumPy ndarray with arbitrary_types_allowed")
print("=" * 60)

try:

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def process_array(
        arr: Annotated[np.ndarray, Shape(None, 3), DType(np.float32)],
    ):
        return arr.shape

    a = np.ones((10, 3), dtype=np.float32)
    result = process_array(a)
    print(f"  ✅ Valid ndarray: shape={result}")

    # Wrong shape
    try:
        process_array(np.ones((10, 4), dtype=np.float32))
    except PydanticValidationError as e:
        print(f"  ✅ Shape violation caught: {e.error_count()} error(s)")
        for err in e.errors():
            print(f"     loc={err['loc']}, msg={err['msg']}")
    except Exception as e:
        print(f"  ❌ Shape check unexpected: {type(e).__name__}: {e}")

    # Wrong dtype
    try:
        process_array(np.ones((10, 3), dtype=np.float64))
    except PydanticValidationError as e:
        print(f"  ✅ DType violation caught: {e.error_count()} error(s)")
        for err in e.errors():
            print(f"     loc={err['loc']}, msg={err['msg']}")
    except Exception as e:
        print(f"  ❌ DType check unexpected: {type(e).__name__}: {e}")

    # Not an array
    try:
        process_array("not-an-array")
    except PydanticValidationError as e:
        print(f"  ✅ Not-array caught: {e.error_count()} error(s)")
        for err in e.errors():
            print(f"     loc={err['loc']}, msg={err['msg']}")
    except Exception as e:
        print(f"  ❌ Not-array unexpected: {type(e).__name__}: {e}")

except Exception as e:
    print(f"  ❌ Setup failed: {type(e).__name__}: {e}")


# ── Test 5: *args and **kwargs ─────────────────────────────────────────────
print()
print("=" * 60)
print("Test 5: *args and **kwargs")
print("=" * 60)

try:

    @validate_call
    def process_many(
        *items: Annotated[int, GreaterThan(0)],
        **options: Annotated[float, InRange(0.0, 1.0)],
    ):
        return items, options

    result = process_many(1, 2, 3, alpha=0.5)
    print(f"  ✅ Valid call: {result}")

    try:
        process_many(1, -2, 3, alpha=1.5)
    except PydanticValidationError as e:
        print(f"  ✅ Multi-error: {e.error_count()} errors")
        for err in e.errors():
            print(f"     loc={err['loc']}, msg={err['msg']}")
    except Exception as e:
        print(f"  ❌ Unexpected: {type(e).__name__}: {e}")

except Exception as e:
    print(f"  ❌ Failed: {type(e).__name__}: {e}")


# ── Test 6: Return value validation ───────────────────────────────────────
print()
print("=" * 60)
print("Test 6: Return value validation")
print("=" * 60)

try:

    @validate_call(validate_return=True)
    def get_positive(x: int) -> Annotated[int, GreaterThan(0)]:
        return x

    result = get_positive(5)
    print(f"  ✅ Valid return: {result}")

    try:
        get_positive(-5)
    except PydanticValidationError as e:
        print(f"  ✅ Return violation caught: {e.error_count()} error(s)")
        for err in e.errors():
            print(f"     loc={err['loc']}, msg={err['msg']}")
    except Exception as e:
        print(f"  ❌ Unexpected: {type(e).__name__}: {e}")

except Exception as e:
    print(f"  ❌ Failed: {type(e).__name__}: {e}")


# ── Test 7: Multiple validators on same param (both fail) ─────────────────
print()
print("=" * 60)
print("Test 7: Multiple validators on same Annotated (both fail)")
print("=" * 60)

try:

    @validate_call
    def func_multi(x: Annotated[int, GreaterThan(10), LessThan(5)]):
        return x

    # value 7 fails both GreaterThan(10) and LessThan(5)
    try:
        func_multi(7)
    except PydanticValidationError as e:
        print(f"  Result: {e.error_count()} error(s)  (do we get BOTH?)")
        for err in e.errors():
            print(f"     loc={err['loc']}, msg={err['msg']}")
    except ValueError as e:
        print(f"  ValueError (not PydanticValidationError): {e}")
    except Exception as e:
        print(f"  ❌ Unexpected: {type(e).__name__}: {e}")

except Exception as e:
    print(f"  ❌ Failed: {type(e).__name__}: {e}")


print()
print("=" * 60)
print("DONE — copy output and share with me!")
print("=" * 60)
