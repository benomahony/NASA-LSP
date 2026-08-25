# NASA Rule Coverage

| Rule | Coverage | Implementation |
|------|----------|----------------|
| **1. Simple Control Flow** | ✅ NASA LSP | NASA01-A (forbidden APIs), NASA01-B (no recursion) |
| **2. Bounded Loops** | ✅ NASA LSP | NASA02 (no `while True`) |
| **3. No Dynamic Allocation** | ❌ Not implemented | Could detect unbounded `list.append()` in loops |
| **4. Function Length ≤60 lines** | ✅ NASA LSP | NASA04 |
| **5. Assertion Density** | ✅ NASA LSP | NASA05 (≥2 asserts per function) |
| **6. Smallest Scope** | ⚠️ Partial | Python scoping + [Ruff](https://docs.astral.sh/ruff/) best practices |
| **7. Check Return Values** | ⚠️ Ruff | Use Ruff's `B018` rule |
| **8. Limited Preprocessor** | ⚠️ Partial | NASA01-A bans `__import__`; use Ruff for imports |
| **9. Pointer Restrictions** | - N/A | Not applicable to Python |
| **10. All Warnings Enabled** | ⚠️ Ruff + Mypy | Use Ruff's `ANN` + static type checker |

**Recommended setup:** NASA LSP + Ruff + Mypy for comprehensive coverage.

## Rule 1: Simple Control Flow

### NASA01-A: Forbidden Dynamic APIs

Flags calls to dynamic APIs that make code difficult to analyze:

- `eval`, `exec`, `compile`
- `globals`, `locals`
- `__import__`
- `setattr`, `getattr`

**Rationale:** Simpler control flow translates into stronger capabilities for analysis and often results in improved code clarity.

### NASA01-B: No Recursion

Identifies direct recursive function calls where a function calls itself.

**Rationale:** Banishing recursion results in having an acyclic function call graph, which code analyzers can exploit to prove limits on stack use and boundedness of executions.

## Rule 2: Bounded Loops

### NASA02: Unbounded Loops

Detects unbounded `while True` loops that violate the fixed upper bound requirement.

**Rationale:** The absence of recursion and the presence of loop bounds prevents runaway code. It must be trivially possible for a checking tool to prove statically that the loop cannot exceed a preset upper bound on the number of iterations.

## Rule 4: Function Length Limit

### NASA04: No Function Longer Than 60 Lines

Enforces the strict 60-line limit per function for verifiability and code clarity.

**Rationale:** Each function should be a logical unit in the code that is understandable and verifiable as a unit. It is much harder to understand a logical unit that spans multiple pages. Excessively long functions are often a sign of poorly structured code.

## Rule 5: Assertion Density

### NASA05: Assertion Count

Enforces minimum of 2 assert statements per function to detect impossible conditions and verify invariants.

**Rationale:** Statistics for industrial coding efforts indicate that unit tests often find at least one defect per 10 to 100 lines of written code. The odds of intercepting defects increase significantly with increasing assertion density.

### Assertion quality sub-rules

An assertion that only restates a type, echoes a just-assigned value, or bundles conditions together cannot fail on a real bug. These sub-rules flag such assertions and subtract them from the `NASA05` count, so weak asserts cannot pad a function to the minimum. They are enabled by default; narrow the set with `[tool.nasa-lsp].rules` if needed.

## Rule detection reference

One example per rule; each block is run through the analyzer by `tests/test_doc_examples.py`, which also fails if a rule has no example.

`NASA01-A` — call to a forbidden dynamic API:

```python
def f():
    eval("expr")
```

`NASA01-B` — a function that calls itself:

```python
def f():
    return f()
```

`NASA02` — an unbounded `while True` loop:

```python
def f():
    while True:
        pass
```

`NASA04` — a function whose body spans more than 60 lines (no example: the trigger is length alone).

`NASA05` — fewer than two meaningful assertions:

```python
def f():
    return 1
```

`NASA05-A` — an assertion with no message:

```python
def f(x):
    assert x > 0
```

`NASA05-M1` — an assertion restating a parameter's annotation:

```python
def f(x: int):
    assert isinstance(x, int), "x must be an int"
```

`NASA05-M2` — an assertion on a value that was just assigned a literal:

```python
def f():
    x = 5
    assert x is not None, "x must be set"
```

`NASA05-M3` — a `None` check made redundant by a following `isinstance`:

```python
def f(x):
    assert x is not None, "x must be set"
    assert isinstance(x, int), "x must be an int"
```

`NASA05-M4` — a truthiness assertion on a total string operation:

```python
def f(k):
    name = str(k)
    assert name, "name must be non-empty"
```

`NASA05-M5` — a post-condition already guaranteed by `len()`:

```python
def f(x):
    n = len(x)
    assert n >= 0, "length is non-negative"
```

`NASA05-M6` — a bare `isinstance()` type check:

```python
def f(x):
    assert isinstance(x, int), "x must be an int"
```

`NASA05-M7` — a compound assertion joined by `and`:

```python
def f(x):
    assert isinstance(x, int) and x > 0, "x must be a positive int"
```

## Original NASA Power of 10 Rules

The original rules were designed for C programming in safety-critical systems:

1. Restrict all code to very simple control flow constructs—do not use goto statements, setjmp or longjmp constructs, or direct or indirect recursion
2. Give all loops a fixed upper bound
3. Do not use dynamic memory allocation after initialization
4. No function should be longer than what can be printed on a single sheet of paper (≈60 lines)
5. The code's assertion density should average to minimally two assertions per function
6. Declare all data objects at the smallest possible level of scope
7. Each calling function must check the return value of nonvoid functions
8. The use of the preprocessor must be limited to inclusion of header files and simple macro definitions
9. The use of pointers must be restricted (no more than one level of dereferencing)
10. All code must be compiled with all compiler warnings enabled at the most pedantic setting
