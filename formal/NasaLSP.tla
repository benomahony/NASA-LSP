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
    published_diags,\* Function: URI -> Seq(Diagnostic)
                    \* Tracks what the server has most recently published to
                    \* the client.  Open docs have up-to-date diagnostics;
                    \* closed docs temporarily retain a <<>> (empty) entry
                    \* representing the clear-markers notification required
                    \* by the LSP protocol.
    pending_changes \* Set of URIs for which the client has queued a content
                    \* change that the server has not yet processed.  Only
                    \* URIs in this set may trigger DidChange.

vars == <<open_docs, published_diags, pending_changes>>

\* ---------------------------------------------------------------------------
\* Type invariant
\* ---------------------------------------------------------------------------

TypeInvariant ==
    /\ open_docs \in [DOMAIN open_docs -> CONTENT]
    /\ DOMAIN open_docs \subseteq URI
    /\ DOMAIN published_diags \subseteq URI
    /\ pending_changes \subseteq URI

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
  Non-empty diagnostics are never published for documents that are not open.
  Closed documents may retain a <<>> (empty) entry — this represents the
  LSP-required clear-markers notification sent on close.
*)
NoStaleDiagnostics ==
    \A uri \in DOMAIN published_diags :
        uri \in DOMAIN open_docs \/ published_diags[uri] = <<>>

(*
  INVARIANT 3 — Diagnostic Domain Complete
  Every open document has an entry in published_diags.
  (Closed documents may also appear with an empty entry pending cleanup.)
*)
DiagnosticDomainComplete ==
    DOMAIN open_docs \subseteq DOMAIN published_diags

\* ---------------------------------------------------------------------------
\* Initial state
\* ---------------------------------------------------------------------------

Init ==
    /\ open_docs = [x \in {} |-> ""]       \* No documents open at startup
    /\ published_diags = [x \in {} |-> <<>>]
    /\ pending_changes = {}

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
    \* Use (uri :> ...) @@ published_diags so the NEW value wins.
    \* TLC's @@ gives priority to the LEFT operand; a prior <<>> entry
    \* from DidClose would otherwise shadow the fresh Analyze result.
    /\ published_diags' = (uri :> Analyze(content)) @@ published_diags
    /\ UNCHANGED pending_changes

(*
  QueueChange — client sends a content-change notification.
  Records the URI as having a pending change; the actual content update
  is applied by DidChange.  Separating queuing from application allows
  the model to have idle states where no change is in flight.
*)
QueueChange(uri) ==
    /\ uri \in DOMAIN open_docs
    /\ uri \notin pending_changes
    /\ pending_changes' = pending_changes \cup {uri}
    /\ UNCHANGED <<open_docs, published_diags>>

(*
  DidChange — server processes a queued content change.
  Maps to the did_change handler in server.py (TEXT_DOCUMENT_DID_CHANGE).
  Precondition: document must be open AND have a pending change.
  Effect: update content, re-publish diagnostics for new content,
  clear the pending flag.
*)
DidChange(uri, new_content) ==
    /\ uri \in DOMAIN open_docs
    /\ uri \in pending_changes
    /\ new_content \in CONTENT
    /\ open_docs' = [open_docs EXCEPT ![uri] = new_content]
    /\ published_diags' = [published_diags EXCEPT ![uri] = Analyze(new_content)]
    /\ pending_changes' = pending_changes \ {uri}

(*
  DidClose — client closes a document.
  Not yet handled in server.py, but the LSP spec requires it.

  Effect (two parts, atomically):
    1. Publish an EMPTY diagnostic list for the URI.  This is the
       LSP-required notification that clears client-side error markers.
    2. Remove the URI from open_docs and from pending_changes.

  The empty entry remains in published_diags to make the "sent empty
  notification" step observable in the state trace.  NoStaleDiagnostics
  permits <<>> entries for closed documents.

  NOTE: The current implementation does NOT handle DidClose, so
  diagnostics persist on the client indefinitely — a known gap.
*)
DidClose(uri) ==
    /\ uri \in DOMAIN open_docs
    /\ open_docs' = [u \in DOMAIN open_docs \ {uri} |-> open_docs[u]]
    /\ published_diags' = [published_diags EXCEPT ![uri] = <<>>]
    /\ pending_changes' = pending_changes \ {uri}

\* ---------------------------------------------------------------------------
\* Next-state relation
\* ---------------------------------------------------------------------------

Next ==
    \/ \E uri \in URI, content \in CONTENT : DidOpen(uri, content)
    \/ \E uri \in DOMAIN open_docs : QueueChange(uri)
    \/ \E uri \in pending_changes, content \in CONTENT : DidChange(uri, content)
    \/ \E uri \in DOMAIN open_docs : DidClose(uri)

\* ---------------------------------------------------------------------------
\* Fairness
\* ---------------------------------------------------------------------------

(*
  Weak fairness on DidChange: once a change is queued for a URI, the
  server will eventually process it.  Because DidChange requires
  uri \in pending_changes, this condition is NOT continuously enabled
  for idle documents — preventing the model from being forced into
  infinite change loops and allowing idle states to be reachable.
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
  If a document is open and has a pending change, diagnostics will
  eventually be updated to reflect the new content.
*)
EventuallyConsistent ==
    \A uri \in URI :
        (uri \in pending_changes) ~>
        (uri \notin pending_changes /\
         (uri \in DOMAIN open_docs =>
          published_diags[uri] = Analyze(open_docs[uri])))

\* ---------------------------------------------------------------------------
\* Theorem
\* ---------------------------------------------------------------------------

THEOREM Spec => [](DiagnosticConsistency /\ NoStaleDiagnostics /\ DiagnosticDomainComplete)

\* ---------------------------------------------------------------------------
\* TLC model operator
\* Substituted for Analyze(_) via NasaLSP.cfg during model checking.
\* Not used in the spec proper.
\* ---------------------------------------------------------------------------

AnalyzeModel(c) ==
    IF c = "violating_code"
    THEN << [code |-> "NASA05", message |-> "too few asserts"] >>
    ELSE << >>

================================================================
