"""Requests are proposed from typed evidence independently of a fixed output vocabulary."""
from types import SimpleNamespace

import pytest

from nca.abi import Contract, Manifest, Message, Request
from nca.kernel import Kernel
from nca.memory import WorkingMemory
from nca.thinking import Opinion, Thought, think, through
from nca.workspace import Workspace


def test_live_template_index_binds_values_and_respects_type_variable_agreement() -> None:
    kernel = Kernel([])
    index = kernel.templates
    contract = Contract(("box[?x]", "?x"), "reading[?x]")
    providers = [SimpleNamespace(manifest=Manifest(name, "1", contract)) for name in ("first", "second")]
    evidence = [Message(t, v, "observed") for t, v in (("box[a]", 1), ("a", 2), ("a", 3), ("b", 4))]
    assert list(index.requests(evidence)) == []
    kernel.install(providers)
    assert list(index.requests(evidence)) == [
        Request("reading[a]", (("box[a]", 1), ("a", value))) for value in (2, 3)]


def test_concept_asks_for_a_new_result_then_uses_its_content() -> None:
    kernel = Kernel([])
    templates = kernel.templates

    class Reader:
        cost = 1.

        def think(self, memory: WorkingMemory) -> Opinion:
            requests = templates.requests([memory.back("input", 0)])
            for request in requests:
                if request.type_id in memory.scratch:
                    return Opinion([1.], [memory.scratch.read(request.type_id)])
                return Opinion([1.], [request])
            return Opinion([1.], ["default"])

    reader = Reader()
    def choose(value: int) -> Thought:
        memory = WorkingMemory({"input": 1})
        memory.write("input", Message("source", value, "observed"))
        return think([reader], memory, budget=4., ask=through(kernel, Workspace(), budget=2))

    assert choose(4).out == "default"
    kernel.install([SimpleNamespace(manifest=Manifest("late", "1", Contract(("source",), "fresh")),
                                    invoke=lambda value: value)])
    for value in (4, 7):
        result = choose(value)
        assert result.out == value and result.asks == 1


def test_request_can_select_a_late_provider_and_bind_repeated_types_in_order() -> None:
    contract = Contract(("x", "x"), "y")
    old = SimpleNamespace(manifest=Manifest("old", "1", contract), invoke=lambda a, b: 0)
    new = SimpleNamespace(manifest=Manifest("new", "1", contract), invoke=lambda a, b: (a, b))
    kernel = Kernel([old])
    ask = through(kernel, Workspace(), budget=4)
    args = (("x", 5), ("x", 3))
    request = Request("y", args, provider=new.manifest.ref)
    assert ask(request).value is None
    kernel.install([new])
    assert ask(request).value == (5, 3)
    assert ask(Request("y", args)).value == 0
    assert kernel.resolve(request, ("new",)) is None
    assert ask(Request("z", args, provider=new.manifest.ref)).value is None
    assert ask(Request("y", (("z", 5), ("x", 3)), provider=new.manifest.ref)).value is None


def test_binding_budget_bounds_unsuccessful_search_and_preserves_first_solution() -> None:
    expert = SimpleNamespace(manifest=Manifest("late", "1", Contract(("a", "a"), "b")))
    templates = Kernel([expert]).templates
    values = [Message("a", i, "observed") for i in (0, 1)]
    assert list(templates.candidates(values, work=2)) == []
    prefix = [candidate.request for candidate in templates.candidates(values, work=4)]
    assert prefix == list(templates.requests(values))[:2]


def test_install_preserves_exclusions_and_borrowed_library_snapshot() -> None:
    from nca.index import ProducerIndex

    original = SimpleNamespace(manifest=Manifest("original", "1", Contract(("x",), "y")))
    late = SimpleNamespace(manifest=Manifest("late", "1", Contract(("x",), "z")))
    borrowed = ProducerIndex([original])
    kernel = Kernel([original], index=borrowed)
    request = Request("z", (("x", 1),))
    assert kernel.resolve(request, ()) is None
    assert kernel.resolve(request, ("original",)) is None
    kernel.install([late])
    assert kernel.resolve(request, ("original",)).module is late
    assert kernel.resolve(request, ()).module is late
    assert kernel.resolve(request, ("late",)) is None
    assert borrowed.size == 1


def test_interpretation_uses_the_answer_even_if_a_constant_was_installed_first() -> None:
    constant = SimpleNamespace(manifest=Manifest("early", "1", Contract((), "action")), invoke=lambda: 0)
    kernel = Kernel([constant], acquire=lambda contract: pytest.fail("proposal triggered acquisition"))
    required = Request("action", (("unfamiliar", 8),), required=frozenset({0}))
    assert kernel.plan(required) is None and kernel.requests == 0
    kernel.install([SimpleNamespace(manifest=Manifest("late", "1", Contract(("unfamiliar",), "action")),
                                    invoke=lambda value: value)])
    ask = through(kernel, Workspace(), budget=3)
    assert ask(required).value == 8
    assert ask(Request("action", required.inputs)).value == 0


def test_bound_request_cannot_load_weights_after_budget_refusal() -> None:
    from nca.loader import ExpertStore, LazyExpert

    store = ExpertStore(budget=32)
    expert = LazyExpert(Manifest("priced", "1", Contract(("x",), "y"), cost=5.),
                        lambda: SimpleNamespace(invoke=lambda x: x), 32, store)
    kernel = Kernel([expert])
    request = Request("y", (("x", 7),), provider=expert.manifest.ref)
    assert through(kernel, Workspace(), budget=4, cost_budget=4.)(request).value is None
    assert store.stats.loads == 0
    assert through(kernel, Workspace(), budget=4, cost_budget=5.)(request).value == 7
    assert store.stats.loads == 1
