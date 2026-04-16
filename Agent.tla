------------------------------ MODULE Agent ------------------------------
EXTENDS Naturals

CONSTANT MaxSteps

VARIABLES state, steps

Init ==
  /\ state = "reasoning"
  /\ steps = 0

Reason ==
  /\ state = "reasoning"
  /\ steps < MaxSteps
  /\ state' \in {"acting", "returning"}
  /\ steps' = steps + 1

Act ==
  /\ state = "acting"
  /\ state' = "reasoning"
  /\ UNCHANGED steps

Return ==
  /\ state = "returning"
  /\ state' = "done"
  /\ UNCHANGED steps

Next == Reason \/ Act \/ Return

Spec == Init /\ [][Next]_<<state, steps>>

Terminates == <>(state = "done")
Bounded == [](steps <= MaxSteps)
==========================================================================
