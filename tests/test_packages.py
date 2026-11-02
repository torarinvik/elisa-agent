"""Content-addressed experts and composites planned in their own scope (§28)."""

from importlib import metadata
from pathlib import Path
from typing import Any

import pytest
import torch

from nca.abi import NOTHING, Calls, Contract, Manifest, Message, seq_type
from nca.cache import ResultCache, value_digest
from nca.evidence import (benchmark, error_bound, evaluation, exact, rates, route_bound,
                          route_risk, answer_within, refine_within)
from nca.optimize import cheapest_within, plan_pareto
from nca.ladder import CALIBRATION, Calibrated, Rung, attested, calibration
from nca.objects import Attestation, Composite, Names, Primitive, Store, canonical, digest
from nca.packages import GROUP, Export, discover, install
from nca.planner import Apply, plan_stable
from nca.runtime import RiskLedger, execute
from nca.workspace import Workspace

TEXT = "text.v1"
WORD = "word.v1"
INT = "int.v1"
ENTRY = f"{__name__}:make"


class Expert:
    def __init__(self, name: str, inputs: list[str], output: str, effects: list[str] | None,
                 cost: float = 1.0) -> None:
        self.name = name
        self.manifest = Manifest(name, "1.0.0", Contract(tuple(inputs), output), cost,
                                 effects=None if effects is None else frozenset(effects))

    def invoke(self, *values: Any) -> Any:
        return BEHAVIOR[self.name](*values)


BEHAVIOR = {
    "split": lambda text: text.split(),
    "length": len,
    "sum": sum,
    "count-letters": lambda word: sum(c.isalpha() for c in word),
    "over": lambda _: (0.01, 0.99),
}


def make(name: str, inputs: list[str], output: str, effects: list[str] | None = (),
         cost: float = 1.0) -> Expert:
    return Expert(name, inputs, output, effects if effects is None else list(effects), cost)


def primitive(name: str, inputs: list[str], output: str, cost: float = 1.0,
              effects: list[str] | None = ()) -> Primitive:
    arguments = {"name": name, "inputs": inputs, "output": output, "cost": cost,
                 "effects": None if effects is None else list(effects)}
    return Primitive(make(**arguments).manifest, ENTRY, arguments)


def counting_package(store: Store, exports: bool = True) -> str:
    """Splits text into words, reads each word with a required slot and sums."""
    members = (store.put(primitive("split", [TEXT], seq_type(WORD))),
               store.put(primitive("sum", [seq_type(INT)], INT)))
    return store.put(Composite("counting", "1.0.0", members, requires=(((WORD,), INT),),
                               exports=(Contract((TEXT,), INT),) if exports else None,
                               effects=frozenset()))


def test_references_are_digests_of_canonical_contents() -> None:
    assert canonical({"b": [1, (2,)], "a": "é"}) == '{"a":"é","b":[1,[2]]}'.encode()
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    with pytest.raises(ValueError):
        canonical(float("nan"))
    one, other = primitive("sum", [seq_type(INT)], INT), primitive("sum", [seq_type(INT)], INT)
    assert one.ref == other.ref and one.ref.startswith("sha256:") and len(one.ref) == 71
    assert primitive("sum", [seq_type(INT)], INT, cost=2.0).ref != one.ref


def test_store_admits_only_well_formed_dags_and_round_trips(tmp_path: Path) -> None:
    store = Store()
    with pytest.raises(KeyError):
        store.put(Composite("orphan", "1", ("sha256:" + "0" * 64,)))
    impure = store.put(primitive("split", [TEXT], seq_type(WORD), effects=["io"]))
    with pytest.raises(ValueError):
        store.put(Composite("pure", "1", (impure,), effects=frozenset()))
    package = counting_package(store)
    note = store.put(Attestation(package, "audit", {"error": 0.01}, "tests"))
    with pytest.raises(KeyError):
        store.put(Attestation("sha256:" + "1" * 64, "audit", {}))
    store.save(tmp_path)
    reopened = Store.open(tmp_path)
    assert len(reopened) == len(store)
    assert reopened.get(package) == store.get(package)
    assert [a.claim for a in reopened.attestations(package, "audit")] == [{"error": 0.01}]
    assert reopened.get(note).ref == note
    (tmp_path / f"{package.removeprefix('sha256:')}.json").write_text("{}")
    with pytest.raises(ValueError):
        Store.open(tmp_path)


def test_names_point_at_references() -> None:
    names = Names()
    assert names.bind("counting", "sha256:a") is None
    assert names.bind("counting", "sha256:b") == "sha256:a"
    assert names.resolve("counting") == "sha256:b"


def test_flatten_keeps_member_order_and_shares_members() -> None:
    store = Store()
    split = store.put(primitive("split", [TEXT], seq_type(WORD)))
    length = store.put(primitive("length", [seq_type(WORD)], INT))
    inner = store.put(Composite("inner", "1", (split, length)))
    outer = store.put(Composite("outer", "1", (length, inner, split)))
    assert store.flatten(outer) == [length, split]
    assert list(store.walk(outer)) == [length, split, inner, outer]


def test_transparent_composites_install_their_members_once() -> None:
    store = Store()
    split = store.put(primitive("split", [TEXT], seq_type(WORD)))
    length = store.put(primitive("length", [seq_type(WORD)], INT))
    both = store.put(Composite("both", "1", (split, length, split)))
    modules = install(store, both)
    assert [m.manifest.module_id for m in modules] == ["split", "length"]
    assert [m.identity for m in modules] == [split, length]
    route = plan_stable(modules, (TEXT,), INT)
    assert execute(route, {TEXT: Message(TEXT, "a bc d", "input")}, Workspace(), 10).payload == 3


def test_exports_are_higher_order_experts_whose_requirements_the_planner_fills() -> None:
    store = Store()
    package = counting_package(store)
    reader = store.put(primitive("count-letters", [WORD], INT))
    world = store.put(Composite("world", "1", (reader, package)))
    modules = install(store, world)
    export = modules[-1]
    assert isinstance(export, Export)
    assert export.manifest.contract == Contract((TEXT,), INT, (((WORD,), INT),))
    # The requirement is read once per word: affine calls, declared exactly.
    assert export.manifest.calls == (Calls(0.0, 1.0),)
    assert export.manifest.effects == frozenset()
    route = plan_stable(modules, (TEXT,), INT)
    assert isinstance(route, Apply) and route.module is export
    result = execute(route, {TEXT: Message(TEXT, "ab, c!", "input")}, Workspace(), 10)
    assert result.payload == 3


def test_exports_hide_members_and_their_types() -> None:
    store = Store()
    sealed = install(store, counting_package(store))
    assert [m.manifest.contract.output for m in sealed] == [INT]
    assert plan_stable(sealed, (TEXT,), seq_type(WORD)) is None
    transparent = install(store, counting_package(store, exports=False))
    assert plan_stable(transparent, (TEXT,), seq_type(WORD)) is not None


def test_unimplementable_exports_are_rejected() -> None:
    store = Store()
    split = store.put(primitive("split", [TEXT], seq_type(WORD)))
    package = store.put(Composite("broken", "1", (split,), exports=(Contract((TEXT,), INT),)))
    with pytest.raises(ValueError, match="cannot implement"):
        install(store, package)


def test_composites_nest() -> None:
    store = Store()
    package = counting_package(store)
    reader = store.put(primitive("count-letters", [WORD], INT))
    # A sealed composite that satisfies the inner requirement itself.
    sealed = store.put(Composite("sealed", "1", (reader, package),
                                 exports=(Contract((TEXT,), INT),), effects=frozenset()))
    (export,) = install(store, sealed)
    assert export.manifest.contract.slots == ()
    route = plan_stable([export], (TEXT,), INT)
    assert execute(route, {TEXT: Message(TEXT, "abc de", "input")}, Workspace(), 10).payload == 5


class FirstOnly(Expert):
    """Reads only its first input."""

    def demand(self, index: int, demand: Any) -> Any:
        return demand if index == 0 else NOTHING


def first_only() -> FirstOnly:
    return FirstOnly("first", [TEXT, INT], WORD, [])


def test_installed_primitives_keep_their_implementations_demand() -> None:
    BEHAVIOR["first"] = lambda text, _: text
    store = Store()
    first = store.put(Primitive(first_only().manifest, f"{__name__}:first_only"))
    length = store.put(primitive("length", [TEXT], INT))
    modules = install(store, store.put(Composite("both", "1", (first, length))))
    route = plan_stable(modules, (TEXT,), WORD)
    assert isinstance(route, Apply) and route.module.manifest.module_id == "first"
    workspace = Workspace()
    assert execute(route, [Message(TEXT, "ab", "input")], workspace, 10).payload == "ab"
    assert not any(m.producer.startswith("length") for m in workspace.messages())


def test_declared_manifest_must_match_the_loaded_one() -> None:
    wrong = Primitive(make("sum", [seq_type(INT)], INT).manifest, ENTRY,
                      {"name": "sum", "inputs": [seq_type(INT)], "output": INT, "cost": 5.0})
    with pytest.raises(ValueError, match="not the declared"):
        wrong.load()


def test_sealed_exports_are_cached_as_one_pure_expert() -> None:
    store = Store()
    reader = store.put(primitive("count-letters", [WORD], INT))
    sealed = store.put(Composite("sealed", "1", (reader, counting_package(store)),
                                 exports=(Contract((TEXT,), INT),), effects=frozenset()))
    (export,) = install(store, sealed)
    route = plan_stable([export], (TEXT,), INT)
    cache = ResultCache()
    for _ in range(2):
        assert execute(route, [Message(TEXT, "abc de", "input")], Workspace(), 10,
                       cache=cache).payload == 5
    assert cache.stats.hits == 1 and len(cache) == 1


def test_calibration_is_an_attestation_beside_the_expert() -> None:
    store = Store()
    ref = store.put(Primitive(make("over", ["x"], "dist").manifest, ENTRY,
                              {"name": "over", "inputs": ["x"], "output": "dist"}))
    (expert,) = install(store, ref)
    rung = Rung(expert)
    rung.calibrate([0] * 10, torch.tensor([1] * 7 + [0] * 3))
    claim = calibration(rung, ref, decisions=[(0, 1), ((0,), (1,))], issuer="tests")
    note = store.put(claim)
    (stored,) = store.attestations(ref, CALIBRATION)
    assert stored.ref == note
    read = attested(expert, stored)
    assert read.temperatures == rung.temperatures and len(read.temperatures) == 3
    assert read.held_out is None
    other = store.put(primitive("sum", [seq_type(INT)], INT))
    (wrong,) = install(store, other)
    with pytest.raises(ValueError, match="another expert"):
        attested(wrong, stored)


def contribute_counting(store: Store) -> str:
    return counting_package(store)


def contribute_reader(store: Store) -> str:
    return store.put(primitive("count-letters", [WORD], INT))


def contribute_nothing(store: Store) -> str:
    return primitive("length", [TEXT], INT).ref


def contribute_failure(store: Store) -> str:
    raise RuntimeError("broken")


def contributions(monkeypatch: pytest.MonkeyPatch, **entries: str) -> None:
    found = [metadata.EntryPoint(name.replace("_", "."), f"{__name__}:{value}", GROUP)
             for name, value in entries.items()]
    monkeypatch.setattr(metadata, "entry_points",
                        lambda group: [e for e in found if e.group == group])


def test_discovered_packages_install_in_name_order(monkeypatch: pytest.MonkeyPatch) -> None:
    contributions(monkeypatch, z_counting="contribute_counting", a_reader="contribute_reader")
    store = Store()
    names = discover(store)
    assert [name for name, _ in names.items()] == ["a.reader", "z.counting"]
    world = store.put(Composite("world", "1", tuple(ref for _, ref in names.items())))
    route = plan_stable(install(store, world), (TEXT,), INT)
    assert execute(route, [Message(TEXT, "ab, c!", "input")], Workspace(), 10).payload == 3


@pytest.mark.parametrize(("entries", "error"), [
    ({"one": "contribute_reader", "one_": "contribute_counting"}, "contributed twice"),
    ({"broken": "contribute_failure"}, "failed"),
    ({"absent": "contribute_nothing"}, "not in the store"),
])
def test_discovery_refuses_ambiguous_or_broken_contributions(
        monkeypatch: pytest.MonkeyPatch, entries: dict[str, str], error: str) -> None:
    found = [metadata.EntryPoint(name.rstrip("_"), f"{__name__}:{value}", GROUP)
             for name, value in entries.items()]
    monkeypatch.setattr(metadata, "entry_points", lambda group: found)
    with pytest.raises((ValueError, RuntimeError), match=error):
        discover(Store())


def test_discovery_keeps_existing_names(monkeypatch: pytest.MonkeyPatch) -> None:
    contributions(monkeypatch, reader="contribute_reader")
    names = Names()
    names.bind("reader", "sha256:" + "2" * 64)
    with pytest.raises(ValueError, match="already bound"):
        discover(Store(), names)
    assert names.resolve("reader") == "sha256:" + "2" * 64


def test_installed_distributions_contribute_their_domain_packages() -> None:
    store = Store()
    names = dict(discover(store).items())
    assert {"nca.arithmetic", "nca.formulas"} <= set(names)
    for ref in names.values():
        obj = store.get(ref)
        assert isinstance(obj, Composite) and obj.exports and obj.effects == frozenset()


def test_route_risk_charges_invocations_through_maps_and_packages() -> None:
    store = Store()
    reader = store.put(primitive("count-letters", [WORD], INT))
    split = store.put(primitive("split", [TEXT], seq_type(WORD)))
    total = store.put(primitive("sum", [seq_type(INT)], INT))
    rates = {"split": 0.0, "sum": 0.0, "count-letters": 0.01}

    def rate(module: Any) -> float | None:
        return rates.get(module.manifest.module_id)

    flat = plan_stable(install(store, store.put(Composite("flat", "1", (split, reader, total)))),
                       (TEXT,), INT)
    assert route_risk(flat, rate, length=5) == pytest.approx(0.05)
    world = install(store, store.put(Composite("world", "1", (reader, counting_package(store)))))
    packaged = plan_stable(world, (TEXT,), INT)
    assert isinstance(packaged.module, Export)
    assert route_risk(packaged, rate, length=5) == pytest.approx(0.05)
    del rates["sum"]
    assert route_risk(packaged, rate, length=5) is None


def test_error_bounds_come_from_trusted_evaluations() -> None:
    store = Store()
    (reader,) = install(store, store.put(primitive("count-letters", [WORD], INT)))
    bench = benchmark(list(range(100)))
    store.put(evaluation(reader.identity, bench, [i >= 3 for i in range(100)], "lab"))
    bound = error_bound(store, reader.identity, bench, {"lab"}, 0.05)
    assert 0.03 < bound < 0.1
    assert error_bound(store, reader.identity, bench, {"other"}, 0.05) is None


def test_planning_by_risk_picks_the_cheapest_route_within_a_target() -> None:
    BEHAVIOR["careful-count"] = BEHAVIOR["count-letters"]
    store = Store()
    cheap = store.put(primitive("count-letters", [WORD], INT, cost=1.0))
    careful = store.put(primitive("careful-count", [WORD], INT, cost=10.0))
    modules = install(store, store.put(Composite("world", "1", (cheap, careful,
                                                                counting_package(store)))))
    package = modules[-1]
    inner = {m.manifest.module_id: m.identity for m in package.library if hasattr(m, "identity")}
    bounds = {modules[0].identity: 0.05, modules[1].identity: 0.001,
              inner["split"]: 0.0, inner["sum"]: 0.0}
    frontier = plan_pareto(modules, (TEXT,), INT, 5, rates(bounds, length=5))
    assert [(o.cost, o.error) for o in frontier] == [
        pytest.approx((7.0, 0.25)), pytest.approx((52.0, 0.005))]
    chosen = cheapest_within(frontier, 0.01)
    assert chosen.plan.slots[0].module is modules[1]
    del bounds[modules[1].identity]
    assert [o.error for o in plan_pareto(modules, (TEXT,), INT, 5, rates(bounds, 5))] == [
        pytest.approx(0.25)]


def test_route_bounds_spend_confidence_by_invocations_and_skip_exact_experts() -> None:
    store = Store()
    reader = store.put(primitive("count-letters", [WORD], INT))
    world = install(store, store.put(Composite("world", "1", (reader, counting_package(store)))))
    route = plan_stable(world, (TEXT,), INT)
    inner = {m.manifest.module_id: m.identity for m in route.module.library
             if hasattr(m, "identity")}
    bench = benchmark(list(range(1000)))
    for identity, failures in ((world[0].identity, 10), (inner["split"], 0), (inner["sum"], 0)):
        store.put(evaluation(identity, bench, [i >= failures for i in range(1000)], "lab"))
    benches = dict.fromkeys((world[0].identity, inner["split"], inner["sum"]), bench)
    audited = route_bound(route, store, benches, {"lab"}, 0.05, length=5)
    store.put(exact(inner["split"], "splits on spaces by construction", "lab"))
    store.put(exact(inner["sum"], "integer addition", "lab"))
    tighter = route_bound(route, store, benches, {"lab"}, 0.05, length=5)
    reader_alone = 5 * error_bound(store, world[0].identity, bench, {"lab"}, 0.05)
    assert tighter == pytest.approx(reader_alone) and tighter < audited
    del benches[world[0].identity]
    assert route_bound(route, store, benches, {"lab"}, 0.05, length=5) is None


class Reporting(Expert):
    """Counts letters and reports a risk that grows with the word's length."""

    def risk(self, output: int, *inputs: Any) -> float:
        return 0.01 * output


def reporting() -> Reporting:
    return Reporting("count-letters", [WORD], INT, [])


def test_the_ledger_charges_reported_risks_through_packages() -> None:
    store = Store()
    reader = store.put(Primitive(reporting().manifest, f"{__name__}:reporting"))
    world = install(store, store.put(Composite("world", "1", (reader, counting_package(store)))))
    route = plan_stable(world, (TEXT,), INT)
    inner = route.module.library
    exact_ids = {m.manifest.module_id for m in inner} - {"count-letters"}

    def exact_module(module: Any) -> bool:
        return module.manifest.module_id in exact_ids

    text = [Message(TEXT, "ab cde f", "input")]
    answer, ledger = answer_within(route, text, 0.1, exact_module)
    assert answer == 6 and ledger.charge == pytest.approx(0.06) and ledger.certified
    assert answer_within(route, text, 0.05, exact_module)[0] is None
    abstained, unaccounted = answer_within(route, text, 1.0)
    assert abstained is None and set(unaccounted.uncertified) == {"split", "sum"}
    # A cached export is not served while a ledger is kept: its route must charge.
    cache = ResultCache()
    execute(route, text, Workspace(), 10, cache=cache)
    kept = RiskLedger(exact_module)
    execute(route, text, Workspace(), 10, cache=cache, ledger=kept)
    assert kept.charge == pytest.approx(0.06)


def test_calibrated_experts_report_their_calibrated_risk() -> None:
    store = Store()
    (expert,) = install(store, store.put(Primitive(make("over", ["x"], "dist").manifest, ENTRY,
                                                   {"name": "over", "inputs": ["x"],
                                                    "output": "dist"})))
    rung = Rung(expert)
    rung.calibrate([0] * 10, torch.tensor([1] * 7 + [0] * 3))
    calibrated = Calibrated(rung)
    reading = calibrated.invoke(0)
    assert reading[1] == pytest.approx(0.7, abs=0.02)
    assert calibrated.risk(reading) == pytest.approx(1 - reading[1])


class Rung1(Expert):
    """A word reader that reports a fixed risk."""

    def __init__(self, name: str, reported: float) -> None:
        super().__init__(name, [WORD], INT, [])
        self.reported = reported

    def invoke(self, word: str) -> int:
        return len(word)

    def risk(self, output: int, *inputs: Any) -> float:
        return self.reported


def test_refinement_climbs_the_riskiest_invocation_on_any_route() -> None:
    from nca.modules.refinement import Escalating

    reader = Escalating([Rung1("cheap", 0.04), Rung1("dear", 0.001)], "reader")
    modules = [Expert("split", [TEXT], seq_type(WORD), []), reader,
               Expert("sum", [seq_type(INT)], INT, [])]
    route = plan_stable(modules, (TEXT,), INT)

    def exact_module(module: Any) -> bool:
        return module.manifest.module_id in {"split", "sum"}

    text = [Message(TEXT, "ab cd ab ef", "input")]
    answer, ledger, executions = refine_within(route, text, 0.1, exact_module)
    # Three distinct words: 0.16 > 0.1; climbing "ab" (read twice) gives 0.082.
    assert answer == 8 and executions == 2
    assert ledger.charge == pytest.approx(0.002 + 0.08)
    # Levels persist: "ab" is already at the top, so two climbs remain, and
    # with every word at the top (0.004) the target is out of reach.
    answer, ledger, executions = refine_within(route, text, 0.003, exact_module)
    assert answer is None and executions == 3


def test_batched_refinement_climbs_shared_inputs_once_per_round() -> None:
    from nca.evidence import refine_batch
    from nca.modules.refinement import Escalating

    reader = Escalating([Rung1("cheap", 0.04), Rung1("dear", 0.001)], "reader")
    modules = [Expert("split", [TEXT], seq_type(WORD), []), reader,
               Expert("sum", [seq_type(INT)], INT, [])]
    route = plan_stable(modules, (TEXT,), INT)

    def exact_module(module: Any) -> bool:
        return module.manifest.module_id in {"split", "sum"}

    rows = [("ab cd ab ef",), ("ab gh",), ("x",)]
    answers, ledgers, rounds = refine_batch(route, (TEXT,), rows, 0.05, exact_module)
    # Round 1: rows 0 (0.16) and 1 (0.08) both climb "ab", once; row 2 (0.04)
    # is answered. Round 2: row 1 (0.041) is answered, row 0 (0.082) climbs
    # "cd". Round 3: row 0 (0.043) is answered.
    assert answers == [8, 4, 1] and rounds == 3
    assert [ledger.charge for ledger in ledgers] == pytest.approx([0.043, 0.041, 0.04])
    assert reader.levels == {value_digest(["ab"]): 1, value_digest(["cd"]): 1}
