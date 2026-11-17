# Neural Computer Agent

An experimental system that learns to reason by growing a library of small
experts instead of training one large model. The whole system can become very
large, but only the few parts needed for the task at hand are loaded into
memory and trained, so it runs on an ordinary computer.

## The goal

Most large models are a single network: to use or train any of it, all of it
must be in memory. This project asks whether a system can instead

- learn many different tasks with as little hand-written, task-specific code
  as possible,
- reuse what it learned on one task to learn the next with fewer examples,
- keep growing without forgetting what it already knows, and
- stay small in memory however much it has learned.

## The idea

![Experts are proposed by a key index over a growing trunk, confirm or reject, and only those that run are trained](docs/expert-routing.webp)

One step of the intended design:

1. **Describe.** A small shared *trunk* turns the input into a description.
   It is the only learned part that is always in memory.
2. **Propose.** A *key index* matches that description against a key stored
   for each expert and proposes a few candidates.
3. **Confirm.** Each candidate reports how well it fits, from its own record.
   A rejection widens the search.
4. **Run and train.** Only the confirmed experts run and learn. Their state
   is stored beside them on disk.

The trunk has versions. It grows by adding new parts beside the old ones, so
experts built on an earlier version keep working.

A *kernel* holds this together. Experts never call each other; they declare
what they take and give, and the kernel plans a route through them, loads
them when needed and evicts them when not. The kernel names no task: every
task-specific part lives in a separate package and is installed like any
other expert.

## Status

The diagram is the target, not a description of what is finished.

- **Built:** the kernel with typed contracts, planning, lazy loading and
  eviction; admission of new experts only on fresh evidence; a trunk kept as
  a library of blocks that are added and never changed, so that every stored
  expert gives what it gave, with a key index over them; a large body of
  mathematical results with machine-checked proofs.
- **Under test:** a small learner taught only by reward from the screen,
  choosing between experts by their own record, and how few judgements a
  new task needs.
- **Not built yet:** regrouping experts by use, and a search that reaches a
  first reward where random presses do not.

Measurements, including negative results, are in the dated research diary.

## Where to look

| Path | Contents |
|---|---|
| [`src/nca/`](src/nca) | The kernel and its generic runtimes |
| [`THEORY.md`](THEORY.md) | Index of the mathematical chapters in [`theory/`](theory) |
| [`lean/`](lean) | Lean proofs of the theory |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | How theory, proofs and code correspond |
| [`diary/`](diary) | Predictions, experiments and measurements by date |
| [`docs/Neural-Computer-Agent.md`](docs/Neural-Computer-Agent.md) | The original design specification |
| [`AGENTS.md`](AGENTS.md) | Rules for contributors |

## Getting started

    uv sync
    uv run pytest

The proofs build with `cd lean && lake exe cache get && lake build`. Expert
packages are separate repositories that register themselves through the
`nca.packages` entry-point group; the core does not depend on any of them.
