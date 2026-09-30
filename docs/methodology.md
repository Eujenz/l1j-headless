# Methodology: Behavioral Archaeology & Conformance Verification

## 1. Overview & Core Philosophy

L1J Headless employs **Behavioral Archaeology** to extract observable gameplay semantics from legacy server implementations without perpetuating technical debt, monolithic architectures, or runtime dependencies on legacy Java infrastructure.

```text
Legacy Reference (182c)
       │
       ▼ [Observation & Instrumentation]
Compatibility Contract (JSON / Markdown)
       │
       ▼ [Decoupled Implementation]
Native Headless Runtime (Python)
       │
       ▼ [Multi-Layer Comparison]
Differential Replay & Conformance Certification
```

### Core Principles
1. **Legacy implementation ≠ Compatibility contract**:
   The internal code structure, class hierarchies, and database schemas of legacy servers are historical artifacts. A compatibility contract specifies observable, verifiable input-output behavior, not legacy internal architecture.
2. **Modern design ≠ Legacy fact**:
   Modern architectural enhancements (e.g. server-side static collision validation, explicit event buses, decoupled spatial graphs) are intentional design decisions, not retrospective claims about what the legacy 2000s server did.
3. **Behavioral Coverage ≠ Full Game Coverage**:
   Certified scenario slices validate precise, isolated domains (such as 8-direction collision or combat math). Passing a slice certifies conformance for that slice's defined scope, not whole-game parity.

---

## 2. Provenance Taxonomy

Every behavioral assertion, constant, formula, and contract entry is tagged with an explicit provenance tier:

| Tier | Definition | Example |
| :--- | :--- | :--- |
| **`LEGACY_OBSERVED`** | Directly observed from instrumented legacy execution traces or source analysis. | Hit calculation formula in `Character.HitFigure` |
| **`DERIVED_CANONICAL`** | Synthesized from multiple legacy sources into a standardized, reusable structure. | 8-direction delta table, portal transition table from `dungeon.sql` |
| **`CONTROLLED_SUBSTITUTION`** | Intentional replacement of legacy infrastructure with deterministic modern primitives. | Seeded 48-bit LCG RNG replacing unseeded system random |
| **`MODERN_DESIGN`** | Architectural additions required for autonomous headless operation. | Server-side collision arbiter in player movement, domain event stream |
| **`INFERRED`** | Educated hypothesis where legacy source is ambiguous or missing; pending empirical verification. | Undocumented edge-case collision behaviors |
| **`UNKNOWN`** | Unverified or contested behavior explicitly flagged for investigation. | Timing jitter under network lag |

---

## 3. The Four-Stage Pipeline

### Stage 1: Legacy Observation & Instrumentation
Legacy Java servers (in reference repository `Eujenz/182c`) are instrumented with non-intrusive trace loggers. Given explicit scenario inputs, the legacy runtime emits bit-exact oracle traces (`oracle_trace_*.jsonl`).

### Stage 2: Canonical Contract Formulation
Observable inputs, environmental preconditions, state transformations, domain events, and binary outputs are frozen into a canonical specification and machine-readable contract (`scenario_XXX_contract.json`).

### Stage 3: Native Implementation
The native headless runtime implements the behavioral contract from first principles, strictly decoupled from Java, MySQL, client render loops, and socket networking. The native engine executes autonomously without reading oracle traces.

### Stage 4: Differential Replay & Verification
The differential verification harness executes the Native engine against the frozen contract and compares outputs against the legacy oracle across multiple conformance layers:
- **L1 World & Entity State**: Exact matching of coordinates, HP, inventory, and status.
- **L2 Domain Events**: Strict event ordering and semantic payload equivalence.
- **L3 Navigation & Wire Output**: Path trajectory, step counts, and binary packet layouts.
