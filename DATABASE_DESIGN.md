# Database Design: Polymorphic Document Table vs. Schema-Strict Tables

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

### Approach B: Concrete Table-per-Type (Schema-Strict Style)
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

## 2. Head-to-Head Comparison

| Attribute | Single Polymorphic Table (Document) | Concrete Table-per-Type (Schema-Strict) |
| :--- | :--- | :--- |
| **Schema Evolution** | Extremely Easy (0 migrations) | Difficult (requires database migrations) |
| **Query Complexity** | Very Low (single table query) | High (requires joins or multiple queries) |
| **Write Integrity** | Application-Level / JSON Check Constraints | Native Database Engine Level |
| **Performance (Retrieval)**| Fast (single index seek) | Moderate to Slow (multiple joins/queries) |
| **Operational Simplicity** | Very High | Low |

---

## 3. Rationale: Why We Chose the Document Style

For spacecraft flight rules, **the Single Polymorphic Table (Document Style)** was chosen for three key architectural reasons:

### 1. The Polymorphism of Rules
Constraints are inherently polymorphic—they share the same metadata headers (`satellite_norad_id`, `context_name`, `parameter_name`) but vary in parameters. Querying them polymorphically using Table-per-Type results in messy code and query degradation. A single table with JSON serialization allows the database to remain simple while Python handles the polymorphic object generation.

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
      (constraint_type = 'InRange' AND parameters ? 'min_val' AND parameters ? 'max_val')
  );
  ```
* **Pydantic Validation**: When loading rules at startup, the parameters are unpacked and validated by Pydantic constraint classes. Any typo in the database config is caught and rejected immediately on application boot, preventing invalid rules from entering the validation engine.
