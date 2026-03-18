# Formal Specifications — NASA-LSP

This directory contains TLA+ formal specifications for the NASA-LSP server.
They complement the test suite by providing machine-checkable proofs of
correctness properties that tests can only sample.

## Files

| File | Specifies |
|------|-----------|
| `NasaLSP.tla` | LSP server state machine (document lifecycle, diagnostic consistency) |
| `NasaLSP.cfg` | TLC model checker configuration for `NasaLSP.tla` |
| `NasaAnalyzer.tla` | Analyzer rule semantics (soundness, completeness, monotonicity) |
| `NasaAnalyzer.cfg` | TLC model checker configuration for `NasaAnalyzer.tla` |

---

## What Each Spec Covers

### NasaLSP.tla — Server State Machine

Models the lifecycle of open documents and the invariant that published
diagnostics always reflect current document content.

**Safety invariants checked:**

- **DiagnosticConsistency** — For every open document, the diagnostics sent
  to the client equal `Analyze(current_content)`. The client never sees
  stale results.
- **NoStaleDiagnostics** — Diagnostics are never published for documents the
  client hasn't opened.
- **DiagnosticDomainComplete** — Every open document has exactly one set of
  published diagnostics; no document is silently skipped.

**Liveness property:**

- **EventuallyConsistent** — If a document is open, diagnostics will
  eventually be published for it (progress guarantee).

**Known gap exposed by the spec:**
The current `server.py` has no `DidClose` handler. The spec models it as
an action; the implementation gap means diagnostics for closed documents
persist on the client indefinitely. This is a correctness bug the spec
makes precise.

---

### NasaAnalyzer.tla — Analyzer Rule Semantics

Provides reference definitions for each NASA rule as pure predicates,
independent of the Python AST implementation. These serve as an oracle
for differential testing.

**Rule predicates:**

| Predicate | Rule | Fires when |
|-----------|------|-----------|
| `Nasa01A_Fires(f)` | NASA01-A | `f.has_forbidden_call = TRUE` |
| `Nasa01B_Fires(f)` | NASA01-B | `f.is_recursive = TRUE` |
| `Nasa02_Fires(f)` | NASA02 | `f.has_while_true = TRUE` |
| `Nasa04_Fires(f)` | NASA04 | `f.line_count >= 60` |
| `Nasa05_Fires(f)` | NASA05 | `f.assert_count < 2` |

**Invariants checked:**

- **DiagnosticsMatchSpec** — Computed diagnostics equal `ExpectedDiagnostics`
  (the reference predicate set) after every content change.
- **NoDiagnosticsForUnknownFunctions** — No diagnostic references a function
  name that isn't in the current program.
- **DiagnosticCodesValid** — All emitted codes are in the known set
  `{NASA01-A, NASA01-B, NASA02, NASA04, NASA05}`.

**Theorems:**

- **Nasa05Monotone** — Adding assert statements cannot cause NASA05 to appear
  where it wasn't present. (Removing asserts cannot make a compliant function
  safe for this rule.)
- **Nasa04AntiMonotone** — Shortening a function cannot introduce a NASA04
  violation.

---

## Running the Model Checker

### Prerequisites

Download the TLA+ tools jar:
```
https://github.com/tlaplus/tlaplus/releases/latest
```

Or install via the [TLA+ VS Code extension](https://marketplace.visualstudio.com/items?itemName=alygin.vscode-tlaplus).

### Check NasaLSP.tla

```bash
cd formal/
java -jar tla2tools.jar -config NasaLSP.cfg NasaLSP.tla
```

Expected output: all invariants hold, liveness property satisfied, state
space exhausted.

### Check NasaAnalyzer.tla

```bash
cd formal/
java -jar tla2tools.jar -config NasaAnalyzer.cfg NasaAnalyzer.tla
```

### Using the TLA+ Toolbox GUI

1. Open the Toolbox and create a new spec pointing at `NasaLSP.tla`.
2. Create a model, load `NasaLSP.cfg`.
3. Run TLC. The small constant sets (2 URIs, 3 content values) ensure the
   state space is exhausted in seconds.

---

## Relationship to the Test Suite

| Layer | Tool | Guarantees |
|-------|------|-----------|
| Unit tests | pytest | Specific inputs produce expected outputs |
| Property tests | Hypothesis | Statistical coverage of random inputs |
| Mutation tests | mutmut | Test suite catches code mutations |
| **Formal spec** | **TLC** | **All reachable states satisfy invariants** |

The TLA+ specs do not replace tests — they operate at a different level.
Tests verify the implementation on concrete inputs; TLC verifies the
*design* (the state machine) exhaustively over all reachable states within
the model's finite bounds.

---

## Extending the Specs

**To add a new rule (e.g., NASA03 — no dynamic memory allocation):**

1. Add a field to the `Function` record in `NasaAnalyzer.tla`:
   ```tla
   has_dynamic_alloc : BOOLEAN
   ```
2. Define the predicate:
   ```tla
   Nasa03_Fires(f) == f.has_dynamic_alloc
   ```
3. Add `"NASA03"` to `DiagCode` and update `ExpectedDiagnostics`.
4. Add a monotonicity theorem if applicable.

**To model the DidClose fix in NasaLSP.tla:**
The `DidClose` action is already specified. Once `server.py` implements the
handler, verify the implementation matches the action's postcondition:
publish an empty diagnostic list to clear client-side indicators.
