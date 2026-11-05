from itertools import product

import pytest

from nca.learning.version_space import VersionSpace
from nca.planner.dynamics import plan_actions
from nca.runtime import BudgetExceeded, UnresolvedRequest


def test_realizable_versions_generalize_or_refuse_and_plans_agree() -> None:
    states, actions = ("p", "q"), ("a", "b")
    inputs = tuple(product(states, actions))
    tables = [dict(zip(inputs, outputs, strict=True)) for outputs in product(states, repeat=4)]
    for truth in tables:
        for observed in inputs:
            family = [lambda pair, table=table: table[pair] for table in tables]
            model = VersionSpace(family, [(observed, truth[observed])], max_candidates=16)
            assert len(model.hypotheses) == 8
            for pair in inputs:
                try:
                    answer = model.predict(pair)
                except UnresolvedRequest:
                    continue
                assert answer == truth[pair]
            for initial, goal in product(states, repeat=2):
                plan = plan_actions(initial, lambda value: value == goal, actions,
                    lambda state, action: model.predict((state, action)), key=lambda value: value,
                    max_calls=4, max_states=2)
                if plan is not None:
                    actual = initial
                    for action in plan:
                        actual = truth[actual, action]
                    assert actual == goal


def test_missing_truth_can_be_unanimously_wrong_and_is_not_certification() -> None:
    model = VersionSpace([lambda value: "p"], [("observed", "p")], max_candidates=1)
    assert model.predict("unobserved") == "p"  # A true answer of q is not ruled out.
    with pytest.raises(ValueError):
        VersionSpace([lambda value: "p"] * 2, [("observed", "p")], max_candidates=1)
    def expensive(value: str) -> str:
        raise BudgetExceeded("unknown fit outcome")
    with pytest.raises(BudgetExceeded):
        VersionSpace([expensive], [("observed", "p")], max_candidates=1)


def test_adaptive_disagreement_cannot_reveal_an_unvisited_transition() -> None:
    states, actions = (0, 1), (0, 1)
    inputs = tuple(product(states, actions))
    tables = [dict(zip(inputs, outputs, strict=True)) for outputs in product(states, repeat=4)]
    family = [lambda pair, table=table: table[pair] for table in tables]

    def interact(world: dict[tuple[int, int], int]) -> list[tuple[tuple[int, int], int]]:
        observations = [((0, 0), world[0, 0])]
        current = 0
        for _ in range(3):
            model = VersionSpace(family, observations, max_candidates=len(family))
            choices = tuple((current, action) for action in actions)
            chosen = model.choose_disagreement(choices, max_inputs=len(choices))
            pair = choices[0 if chosen is None else chosen]
            current = world[pair]
            observations.append((pair, current))
        return observations

    for world in tables:
        observed = interact(world)
        visited = {pair for pair, _ in observed}
        for pair in set(inputs) - visited:
            alternate = dict(world)
            alternate[pair] = 1 - alternate[pair]
            assert interact(alternate) == observed
            assert alternate[pair] != world[pair]


def test_refinement_preserves_prior_agreement_and_resolves_disagreement() -> None:
    candidates = [lambda x: x, lambda x: "p"]
    prior = VersionSpace(candidates, [("p", "p")], max_candidates=2)
    with pytest.raises(UnresolvedRequest):
        prior.predict("q")
    refined = prior.refine([("q", "q")])
    assert prior.predict("p") == refined.predict("p") == "p"
    assert refined.predict("q") == "q"
    assert len(prior.hypotheses) == 2 and len(refined.hypotheses) == 1
    with pytest.raises(ValueError):
        refined.refine([("p", "other")])
    assert refined.predict("q") == "q"


def test_disagreement_choice_minimizes_worst_survivors_without_mutation() -> None:
    family = [lambda x, table=table: table[x] for table in
              ((0, 0, 0), (0, 0, 1), (0, 1, 0), (0, 1, 1))]
    model = VersionSpace(family, [(0, 0)], max_candidates=4)
    assert model.choose_disagreement((0, 1, 2), max_inputs=3) == 1
    assert len(model.hypotheses) == 4
    assert len(model.refine([(1, 1)]).hypotheses) == 2
    with pytest.raises(ValueError):
        model.choose_disagreement((0, 1), max_inputs=1)


def test_truthful_disagreement_strictly_shrinks_each_finite_version() -> None:
    tables = tuple(product((0, 1), repeat=3))
    for membership in product((False, True), repeat=len(tables)):
        selected = tuple(table for table, included in zip(tables, membership, strict=True) if included)
        if not selected:
            continue
        family = [lambda index, table=table: table[index] for table in selected]
        for truth in selected:
            model = VersionSpace(family, [(0, truth[0])], max_candidates=len(family))
            for index in (1, 2):
                choice = model.choose_disagreement((index,), max_inputs=1)
                refined = model.refine([(index, truth[index])])
                if choice is None:
                    assert refined.hypothesis_count == model.hypothesis_count
                else:
                    assert refined.hypothesis_count < model.hypothesis_count
                assert any(all(predict(i) == truth[i] for i in range(3))
                           for predict in refined.hypotheses)


def test_refinement_preserves_complete_search_reach_for_all_two_state_worlds() -> None:
    states, actions = ('p', 'q'), ('a', 'b')
    inputs = tuple(product(states, actions))
    tables = [dict(zip(inputs, outputs, strict=True)) for outputs in product(states, repeat=len(inputs))]
    for truth in tables:
        family = [lambda pair, table=table: table[pair] for table in tables]
        for first, second in product(inputs, repeat=2):
            original = VersionSpace(family, [(first, truth[first])], max_candidates=len(family))
            refined = original.refine([(second, truth[second])])
            for initial, goal in product(states, repeat=2):
                def plan(model: VersionSpace) -> tuple[str, ...] | None:
                    return plan_actions(initial, lambda state: state == goal, actions,
                        lambda state, action: model.predict((state, action)), key=lambda state: state,
                        max_calls=4, max_states=2)
                before, after = plan(original), plan(refined)
                if before is not None:
                    assert after is not None
                    actual = initial
                    for action in after:
                        actual = truth[actual, action]
                    assert actual == goal


def test_factorized_output_counts_match_enumerated_version_space() -> None:
    from math import prod

    states = tuple(product(('p', 'q'), repeat=2))
    rules = tuple(product(range(2), repeat=2))
    family = [lambda state, rule=rule: tuple(state[index] for index in rule) for rule in rules]
    for sample, truth in product(states, family):
        output = truth(sample)
        model = VersionSpace(family, [(sample, output)], max_candidates=len(family))
        allowed = tuple(tuple(index for index in range(2) if sample[index] == target) for target in output)
        assert len(model.hypotheses) == prod(map(len, allowed))
        worst = []
        for state in states:
            outcome_counts = []
            for target in states:
                enumerated = sum(candidate(state) == target for candidate in model.hypotheses)
                factorized = prod(sum(state[index] == target[j] for index in fields)
                                  for j, fields in enumerate(allowed))
                assert enumerated == factorized
                outcome_counts.append(enumerated)
            worst.append(max(outcome_counts))
        minimum = min(worst)
        expected = worst.index(minimum) if minimum < len(model.hypotheses) else None
        assert model.choose_disagreement(states, max_inputs=len(states)) == expected


def test_marginalizing_a_coupled_family_can_create_false_refusal() -> None:
    from collections.abc import Callable

    def rule(first: int, second: int) -> Callable[[tuple[str, ...]], tuple[str, str]]:
        return lambda state: (state[first], state[second])

    training = (('p', 'p', 'p', 'q'), ('p', 'p'))
    coupled = VersionSpace((rule(0, 2), rule(1, 3)), (training,), max_candidates=2)
    expanded = VersionSpace(tuple(rule(a, b) for a in (0, 1) for b in (2, 3)),
                            (training,), max_candidates=4)
    later = ('p', 'q', 'p', 'p')
    assert len(coupled.hypotheses) == 1 and coupled.predict(later) == ('p', 'p')
    assert len(expanded.hypotheses) == 2
    with pytest.raises(UnresolvedRequest):
        expanded.predict(later)


def test_noninjective_assembly_merges_joint_output_partitions() -> None:
    rules = tuple(product(range(2), repeat=2))
    state = ('p', 'q')
    # An order-erasing assembler maps two distinct coordinate outputs to one value.
    family = [lambda value, rule=rule: frozenset(value[index] for index in rule) for rule in rules]
    observed = ('p', 'p')
    model = VersionSpace(family, [(observed, frozenset({'p'}))], max_candidates=len(family))
    outcomes = [predict(state) for predict in model.hypotheses]
    actual_maximum = max(outcomes.count(value) for value in outcomes)
    componentwise_maximum = 1 * 1
    assert actual_maximum == 2 > componentwise_maximum
