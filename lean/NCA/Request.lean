import Mathlib.Data.Finset.Card
import NCA.Loading

/-!
# Kernel-mediated sub-goal requests

An expert never calls another expert. It asks the kernel for a value of a type
from given inputs; the kernel plans the request over the installed library
*excluding every expert in the current request chain* and executes the plan.
Resolution is well-typed, never routes back into the chain, and request chains
terminate: each requester is fresh, so a chain is no longer than the library.
-/

namespace NCA

variable {Ty : Type} [DecidableEq Ty] [SeqTypes Ty]

/-- Resolve a request for `t` from `avail`, excluding the experts in `chain`. -/
def resolve (lib chain : List (Contract Ty)) (avail : List Ty) (n : Nat) (t : Ty) :
    Option (Plan Ty) :=
  planStable (lib.filter fun c => decide (c ∉ chain)) avail n t

/-- **Typed resolution.** A resolved request is a well-typed plan producing the
requested type from the request's inputs. -/
theorem resolve_sound {lib chain : List (Contract Ty)} {avail : List Ty} {n : Nat} {t : Ty}
    {p : Plan Ty} (h : resolve lib chain avail n t = some p) : WellTyped lib avail p t :=
  WellTyped.mono (fun _ hc => (List.mem_filter.mp hc).1) (planStable_sound h)

/-- **No loops back.** A resolved request never invokes an expert in the chain. -/
theorem resolve_avoids {lib chain : List (Contract Ty)} {avail : List Ty} {n : Nat} {t : Ty}
    {p : Plan Ty} (h : resolve lib chain avail n t = some p) :
    ∀ c ∈ p.contracts, c ∉ chain := by
  intro c hc
  have := (planStable_sound h).contracts_subset c hc
  simpa using (List.mem_filter.mp this).2

/-- A chain of nested requests: each new requester is an expert of the plan
that resolved the previous request (with the chain so far excluded). -/
inductive RequestChain (lib : List (Contract Ty)) : List (Contract Ty) → Prop
  | nil : RequestChain lib []
  | cons {chain : List (Contract Ty)} {avail : List Ty} {n : Nat} {t : Ty} {p : Plan Ty}
      {c : Contract Ty} :
      RequestChain lib chain → resolve lib chain avail n t = some p → c ∈ p.contracts →
      RequestChain lib (c :: chain)

theorem RequestChain.nodup_subset {lib chain : List (Contract Ty)} (h : RequestChain lib chain) :
    chain.Nodup ∧ ∀ c ∈ chain, c ∈ lib := by
  induction h with
  | nil => simp
  | @cons chain avail n t p c _ hres hc ih =>
    refine ⟨List.nodup_cons.mpr ⟨resolve_avoids hres c hc, ih.1⟩, ?_⟩
    intro d hd
    rcases List.mem_cons.mp hd with rfl | hd
    · exact resolve_sound hres |>.contracts_subset d hc
    · exact ih.2 d hd

/-- **Termination.** Every chain of nested requests is at most as long as the
number of distinct installed experts, whatever the budget. -/
theorem RequestChain.length_le {lib chain : List (Contract Ty)} (h : RequestChain lib chain) :
    chain.length ≤ lib.toFinset.card := by
  obtain ⟨hnodup, hsub⟩ := h.nodup_subset
  rw [← List.toFinset_card_of_nodup hnodup]
  exact Finset.card_le_card fun c hc => List.mem_toFinset.mpr (hsub c (List.mem_toFinset.mp hc))

end NCA
