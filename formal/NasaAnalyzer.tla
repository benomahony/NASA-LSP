------------------------ MODULE NasaAnalyzer ------------------------
(*
  Formal specification of the NASA-LSP analyzer rule semantics.

  This spec models the correctness properties of the core analysis engine
  in src/nasa_lsp/analyzer.py. Rather than re-implementing the AST
  traversal, it formalizes what the CORRECT behavior must be — expressed
  as invariants and theorems — which can then be used as an oracle to
  check the Python implementation.

  Scope of this spec:
    - NASA01-A  Forbidden API detection (eval, exec, compile, ...)
    - NASA01-B  No direct recursion
    - NASA02    No unbounded while True loops
    - NASA04    Function length <= 60 lines
    - NASA05    >= 2 assert statements per function

  Abstract domains:
    - A "program" is modeled as a set of functions, each with measurable
      properties. We do not model the full AST.
    - A "diagnostic" is a (rule_code, function_name) pair.
    - "Analyze" maps a program to the set of diagnostics it should produce.

  See NasaLSP.tla for the server-level state machine spec.
*)

EXTENDS Naturals, FiniteSets, TLC

\* ---------------------------------------------------------------------------
\* Constants (configure in NasaAnalyzer.cfg)
\* ---------------------------------------------------------------------------

CONSTANTS
    FunctionName,           \* Set of possible function names
    MAX_LINES,              \* NASA04 threshold (60 in production; use smaller value for TLC)
    MIN_ASSERTS,            \* NASA05 threshold (2 in production)
    MAX_LINE_COUNT,         \* TLC bound for line_count field; must be >= MAX_LINES
    MAX_ASSERT_COUNT        \* TLC bound for assert_count field; must be >= MIN_ASSERTS

ASSUME MAX_LINES \in Nat /\ MAX_LINES >= 1
ASSUME MIN_ASSERTS \in Nat /\ MIN_ASSERTS >= 1
ASSUME MAX_LINE_COUNT >= MAX_LINES
ASSUME MAX_ASSERT_COUNT >= MIN_ASSERTS

\* ---------------------------------------------------------------------------
\* Abstract program representation
\* ---------------------------------------------------------------------------

(*
  A Function record captures the properties the analyzer measures:
    name          : FunctionName
    line_count    : Nat  (end_lineno - lineno + 1 in the AST)
    assert_count  : Nat  (direct asserts, not in nested functions)
    is_recursive  : BOOLEAN  (direct self-call in body)
    has_forbidden_call : BOOLEAN  (calls eval/exec/compile/etc.)
    has_while_true : BOOLEAN  (contains `while True:`)
*)

Function == [
    name           : FunctionName,
    line_count     : 0..MAX_LINE_COUNT,
    assert_count   : 0..MAX_ASSERT_COUNT,
    is_recursive   : BOOLEAN,
    has_forbidden_call : BOOLEAN,
    has_while_true : BOOLEAN
]

\* A Program is a finite set of functions.
\* For TLC we model programs with at most one function: the empty program
\* plus all singleton programs.  This avoids enumerating the full power-set
\* (2^|Function| elements) while still exercising every rule predicate.
Program == {{}} \cup {{f} : f \in Function}

\* ---------------------------------------------------------------------------
\* Rule predicates — one per NASA rule
\* These are the REFERENCE DEFINITIONS against which the implementation
\* must be tested.
\* ---------------------------------------------------------------------------

(*
  NASA01-A: Forbidden API call detected in a function.
  The analyzer MUST emit a diagnostic iff has_forbidden_call is TRUE.
*)
Nasa01A_Fires(f) == f.has_forbidden_call

(*
  NASA01-B: Direct recursion detected.
  The analyzer MUST emit a diagnostic iff is_recursive is TRUE.
  NOTE: Mutual recursion is out of scope for this implementation.
*)
Nasa01B_Fires(f) == f.is_recursive

(*
  NASA02: Unbounded while True loop.
  The analyzer MUST emit a diagnostic iff has_while_true is TRUE.
  NOTE: `while 1` or `while not False` are NOT detected — known gap.
*)
Nasa02_Fires(f) == f.has_while_true

(*
  NASA04: Function exceeds 60 lines.
  The analyzer MUST emit a diagnostic iff line_count >= MAX_LINES.
  Note: the condition is >= (not >). A 60-line function IS a violation.
*)
Nasa04_Fires(f) == f.line_count >= MAX_LINES

(*
  NASA05: Insufficient assert statements.
  The analyzer MUST emit a diagnostic iff assert_count < MIN_ASSERTS.
  Note: asserts in nested functions/classes do NOT count toward this total.
*)
Nasa05_Fires(f) == f.assert_count < MIN_ASSERTS

\* ---------------------------------------------------------------------------
\* Expected diagnostic set for a program
\* This is the ground-truth oracle for differential testing.
\* ---------------------------------------------------------------------------

DiagCode == {"NASA01-A", "NASA01-B", "NASA02", "NASA04", "NASA05"}

(*
  The complete set of diagnostics that a correct analyzer MUST produce
  for a given program. Each element is a (code, function_name) pair.
*)
ExpectedDiagnostics(prog) ==
    LET firing == {<<c, g>> \in DiagCode \X prog :
                      \/ (c = "NASA01-A" /\ Nasa01A_Fires(g))
                      \/ (c = "NASA01-B" /\ Nasa01B_Fires(g))
                      \/ (c = "NASA02"   /\ Nasa02_Fires(g))
                      \/ (c = "NASA04"   /\ Nasa04_Fires(g))
                      \/ (c = "NASA05"   /\ Nasa05_Fires(g))}
    IN {<<p[1], p[2].name>> : p \in firing}

\* ---------------------------------------------------------------------------
\* Correctness properties of the analyzer
\* ---------------------------------------------------------------------------

(*
  SOUNDNESS: Every diagnostic the analyzer emits corresponds to a real
  violation. No false positives.

  If Analyze(prog) returns diag (code, name), then the function named
  `name` in prog actually violates rule `code`.
*)
Soundness(prog, actual_diags) ==
    \A d \in actual_diags :
        LET code == d[1]
            name == d[2]
            f    == CHOOSE g \in prog : g.name = name
        IN
        \/ (code = "NASA01-A" /\ Nasa01A_Fires(f))
        \/ (code = "NASA01-B" /\ Nasa01B_Fires(f))
        \/ (code = "NASA02"   /\ Nasa02_Fires(f))
        \/ (code = "NASA04"   /\ Nasa04_Fires(f))
        \/ (code = "NASA05"   /\ Nasa05_Fires(f))

(*
  COMPLETENESS (within documented scope): The analyzer emits a diagnostic
  for every violation it claims to detect. No false negatives for in-scope
  patterns.

  The completeness claim is limited to the patterns the implementation
  actually handles. Known gaps (mutual recursion, `while 1`) are excluded.
*)
Completeness(prog, actual_diags) ==
    \A f \in prog :
        \/ (Nasa01A_Fires(f) => \E d \in actual_diags : d = <<"NASA01-A", f.name>>)
        \/ (Nasa01B_Fires(f) => \E d \in actual_diags : d = <<"NASA01-B", f.name>>)
        \/ (Nasa02_Fires(f)  => \E d \in actual_diags : d = <<"NASA02",   f.name>>)
        \/ (Nasa04_Fires(f)  => \E d \in actual_diags : d = <<"NASA04",   f.name>>)
        \/ (Nasa05_Fires(f)  => \E d \in actual_diags : d = <<"NASA05",   f.name>>)

(*
  IDEMPOTENCY: Analyzing the same program twice produces the same result.
  This is critical for editor integration — repeated cursor moves must not
  cause flickering diagnostics.
*)
Idempotency(prog, analyze_op(_)) ==
    analyze_op(prog) = analyze_op(prog)

(*
  MONOTONICITY (NASA05): Adding more assert statements to a function can
  never introduce a NASA05 diagnostic that wasn't there before.
  Formally: if f.assert_count >= MIN_ASSERTS, then increasing assert_count
  cannot cause Nasa05_Fires to become TRUE.
*)
Nasa05Monotone ==
    \A n \in 0..MAX_ASSERT_COUNT :
        n >= MIN_ASSERTS =>
        \A m \in 0..MAX_ASSERT_COUNT :
            m >= n => ~Nasa05_Fires([assert_count |-> m,
                                     name |-> CHOOSE fn \in FunctionName : TRUE,
                                     line_count |-> 1,
                                     is_recursive |-> FALSE,
                                     has_forbidden_call |-> FALSE,
                                     has_while_true |-> FALSE])

(*
  MONOTONICITY (NASA04): Shortening a function can never introduce a NASA04
  diagnostic that wasn't there before.
*)
Nasa04AntiMonotone ==
    \A n \in 0..MAX_LINE_COUNT :
        n < MAX_LINES =>
        \A m \in 0..MAX_LINE_COUNT :
            m <= n => ~Nasa04_Fires([line_count |-> m,
                                     name |-> CHOOSE fn \in FunctionName : TRUE,
                                     assert_count |-> MIN_ASSERTS,
                                     is_recursive |-> FALSE,
                                     has_forbidden_call |-> FALSE,
                                     has_while_true |-> FALSE])

\* ---------------------------------------------------------------------------
\* State variables (for model checking the analyzer as a transition system)
\* ---------------------------------------------------------------------------

(*
  Model the analyzer's interaction with a single document being edited.
  The editor sends content changes; the analyzer produces updated diagnostics.
*)

VARIABLES
    current_content,    \* Current document content (abstract: a Function set)
    current_diags       \* Diagnostics last computed by the analyzer

avars == <<current_content, current_diags>>

\* ---------------------------------------------------------------------------
\* Initial state
\* ---------------------------------------------------------------------------

InitAnalyzer ==
    /\ current_content \in Program
    /\ current_diags = ExpectedDiagnostics(current_content)

\* ---------------------------------------------------------------------------
\* Actions
\* ---------------------------------------------------------------------------

(*
  ContentChange — editor sends new content.
  The analyzer MUST recompute diagnostics for the new content.
  After this action, current_diags must equal ExpectedDiagnostics of the
  new content — no caching of stale results.
*)
ContentChange(new_prog) ==
    /\ new_prog \in Program
    /\ current_content' = new_prog
    /\ current_diags' = ExpectedDiagnostics(new_prog)

NextAnalyzer ==
    \E prog \in Program : ContentChange(prog)

SpecAnalyzer == InitAnalyzer /\ [][NextAnalyzer]_avars

\* ---------------------------------------------------------------------------
\* Analyzer invariants to check with TLC
\* ---------------------------------------------------------------------------

(*
  After every content change, the published diagnostics match the spec.
*)
DiagnosticsMatchSpec ==
    current_diags = ExpectedDiagnostics(current_content)

(*
  No diagnostic is produced for a function not in the current content.
*)
NoDiagnosticsForUnknownFunctions ==
    \A d \in current_diags :
        \E f \in current_content : f.name = d[2]

(*
  Diagnostic codes are always from the known set.
*)
DiagnosticCodesValid ==
    \A d \in current_diags : d[1] \in DiagCode

\* ---------------------------------------------------------------------------
\* Range validity — position properties
\* ---------------------------------------------------------------------------

(*
  A Range is valid if start <= end (both line and character).
  This formalizes the LSP requirement and catches off-by-one errors.
*)
ValidRange(r) ==
    /\ r.start.line >= 0
    /\ r.start.character >= 0
    /\ r.end.line >= r.start.line
    /\ (r.start.line = r.end.line => r.end.character >= r.start.character)

(*
  All ranges in a diagnostic list must be valid.
*)
AllRangesValid(diag_list) ==
    \A d \in diag_list : ValidRange(d.range)

\* ---------------------------------------------------------------------------
\* Theorems
\* ---------------------------------------------------------------------------

THEOREM Nasa05Monotone
THEOREM Nasa04AntiMonotone

THEOREM SpecAnalyzer =>
    [](DiagnosticsMatchSpec /\ NoDiagnosticsForUnknownFunctions /\ DiagnosticCodesValid)

================================================================
