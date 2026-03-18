------------------------ MODULE NasaLSP ------------------------
(*
  Formal specification of the NASA-LSP Language Server Protocol server.

  This spec models the state machine of the LSP server as implemented in
  src/nasa_lsp/server.py. It captures:

    1. Document lifecycle: open → change* → close
    2. Diagnostic consistency: published diagnostics always reflect the
       current document content (no stale diagnostics)
    3. No diagnostics for unopened documents
    4. Idempotency: running checks on unchanged content produces the same
       diagnostics

  The abstract function Analyze(content) stands in for the real Python
  analyzer. The spec does NOT enumerate specific rule violations; see
  NasaAnalyzer.tla for rule-level properties.

  Model check with TLC using NasaLSP.cfg.
*)

EXTENDS Sequences, FiniteSets, TLC

CONSTANTS
    URI,        \* The set of all possible document URIs (model: {"uri1","uri2"})
    CONTENT,    \* The set of all possible document content strings
    Analyze(_)  \* Abstract analysis function: CONTENT -> Seq(Diagnostic)
                \* In the model, supply a simple operator returning a fixed set.

\* ---------------------------------------------------------------------------
\* State variables
\* ---------------------------------------------------------------------------

VARIABLES
    open_docs,      \* Function: URI -> CONTENT  (only open documents)
    published_diags \* Function: URI -> Seq(Diagnostic)
                    \* Tracks what the server has published to the client.
                    \* Only populated for open documents.

vars == <<open_docs, published_diags>>

\* ---------------------------------------------------------------------------
\* Type invariant
\* ---------------------------------------------------------------------------

TypeInvariant ==
    /\ open_docs \in [DOMAIN open_docs -> CONTENT]
    /\ DOMAIN open_docs \subseteq URI
    /\ published_diags \in [DOMAIN published_diags -> Seq(Diagnostic)]
    /\ DOMAIN published_diags \subseteq URI

\* ---------------------------------------------------------------------------
\* Safety invariants
\* ---------------------------------------------------------------------------

(*
  INVARIANT 1 — Diagnostic Consistency
  For every open document, the published diagnostics exactly match what
  Analyze would produce for the current content. This is the core
  correctness property: the client always sees up-to-date diagnostics.
*)
DiagnosticConsistency ==
    \A uri \in DOMAIN open_docs :
        /\ uri \in DOMAIN published_diags
        /\ published_diags[uri] = Analyze(open_docs[uri])

(*
  INVARIANT 2 — No Stale Diagnostics
  Diagnostics are never published for documents that are not open.
  Prevents the server from reporting errors on files the client hasn't
  opened (which would be confusing and incorrect).
*)
NoStaleDiagnostics ==
    DOMAIN published_diags \subseteq DOMAIN open_docs

(*
  INVARIANT 3 — Diagnostic Domain Matches Open Docs
  Every open document has exactly one set of published diagnostics.
  The domain of diagnostics equals the domain of open documents.
*)
DiagnosticDomainComplete ==
    DOMAIN published_diags = DOMAIN open_docs

\* ---------------------------------------------------------------------------
\* Initial state
\* ---------------------------------------------------------------------------

Init ==
    /\ open_docs = [x \in {} |-> ""]       \* No documents open at startup
    /\ published_diags = [x \in {} |-> <<>>]

\* ---------------------------------------------------------------------------
\* Actions
\* ---------------------------------------------------------------------------

(*
  DidOpen — client opens a document.
  Maps to the did_open handler in server.py (TEXT_DOCUMENT_DID_OPEN).
  Precondition: document is not already open.
  Effect: add to open_docs, immediately publish diagnostics.
*)
DidOpen(uri, content) ==
    /\ uri \notin DOMAIN open_docs
    /\ uri \in URI
    /\ content \in CONTENT
    /\ open_docs' = open_docs @@ (uri :> content)
    /\ published_diags' = published_diags @@ (uri :> Analyze(content))

(*
  DidChange — client sends an incremental or full content change.
  Maps to the did_change handler in server.py (TEXT_DOCUMENT_DID_CHANGE).
  Precondition: document must already be open.
  Effect: update content, re-publish diagnostics for new content.

  This is the key step that ensures diagnostics track content changes.
*)
DidChange(uri, new_content) ==
    /\ uri \in DOMAIN open_docs
    /\ new_content \in CONTENT
    /\ open_docs' = [open_docs EXCEPT ![uri] = new_content]
    /\ published_diags' = [published_diags EXCEPT ![uri] = Analyze(new_content)]

(*
  DidClose — client closes a document.
  Not yet handled in server.py, but the LSP spec requires it.
  Effect: remove from open_docs and clear diagnostics.

  NOTE: The current implementation does NOT handle DidClose. This means
  diagnostics for closed documents persist indefinitely — a known gap.
  When DidClose is implemented, it should publish an empty diagnostic
  list to clear client-side indicators.
*)
DidClose(uri) ==
    /\ uri \in DOMAIN open_docs
    /\ open_docs' = [u \in DOMAIN open_docs \ {uri} |-> open_docs[u]]
    /\ published_diags' = [u \in DOMAIN published_diags \ {uri} |-> published_diags[u]]

\* ---------------------------------------------------------------------------
\* Next-state relation
\* ---------------------------------------------------------------------------

Next ==
    \/ \E uri \in URI, content \in CONTENT : DidOpen(uri, content)
    \/ \E uri \in DOMAIN open_docs, content \in CONTENT : DidChange(uri, content)
    \/ \E uri \in DOMAIN open_docs : DidClose(uri)

\* ---------------------------------------------------------------------------
\* Fairness
\* ---------------------------------------------------------------------------

(*
  Weak fairness on DidChange ensures that if a document is open and new
  content is available, the server will eventually re-analyze it.
  This is a liveness property (progress), complementing the safety
  invariants above.
*)
Fairness ==
    \A uri \in URI :
        WF_vars(\E content \in CONTENT : DidChange(uri, content))

\* ---------------------------------------------------------------------------
\* Specification
\* ---------------------------------------------------------------------------

Spec == Init /\ [][Next]_vars /\ Fairness

\* ---------------------------------------------------------------------------
\* Liveness property
\* ---------------------------------------------------------------------------

(*
  LIVENESS — Eventual Diagnostic Publication
  If a document is open and its content has changed, diagnostics will
  eventually be updated to reflect the new content.

  This captures the real-time feedback guarantee expected from an LSP server.
*)
EventuallyConsistent ==
    \A uri \in URI :
        (uri \in DOMAIN open_docs) ~>
        (uri \in DOMAIN published_diags /\
         published_diags[uri] = Analyze(open_docs[uri]))

\* ---------------------------------------------------------------------------
\* Theorem
\* ---------------------------------------------------------------------------

THEOREM Spec => [](DiagnosticConsistency /\ NoStaleDiagnostics /\ DiagnosticDomainComplete)

================================================================
