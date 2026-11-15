from itertools import product
from math import isclose, log2

import pytest

from nca.granularity import balanced, gathered, saved, searched


def test_an_expert_pays_once_it_holds_more_than_its_address_and_is_used_twice() -> None:
    assert saved(8, 2, 3) == 2
    assert saved(6, 2, 3) == 0
    assert saved(100, 1, 3) == -3
    assert all(saved(2 * address + 1, uses, address) > 0 for uses in range(2, 40) for address in range(12))
    with pytest.raises(ValueError):
        saved(1, 0, 1)


def test_the_balanced_size_is_the_root_of_content_times_address() -> None:
    size, route = balanced(600, 6)
    assert isclose(size, 60) and isclose(route, 10)
    assert isclose(size, 6 * route)
    for content, address in product((24, 60, 600), (3, 6)):
        size, _ = balanced(content, address)
        assert all(max(content / steps, address * steps) >= size - 1e-9 for steps in range(1, 200))


def test_the_trials_are_fewest_near_the_balance() -> None:
    assert isclose(searched(24, 3, 3), log2(3 * 2 ** 8 + 2 ** 9))
    assert min((1, 2, 3, 4, 6, 8), key=lambda steps: searched(24, 3, steps)) == 3
    assert min(range(1, 60), key=lambda steps: searched(600, 6, steps)) == 10
    assert isclose(searched(10000, 6, 1), 10000)


def test_parts_with_the_same_users_are_one_expert_and_small_or_lone_parts_stay_with_their_users() -> None:
    users = {"a": {1, 2}, "b": {1, 2}, "c": {2}, "d": {1, 2, 3}, "e": {2, 3}}
    library = gathered(users, {"a": 5.0, "b": 4.0, "c": 50.0, "d": 6.0, "e": 1.5})
    assert set(library.experts) == {(frozenset("ab"), frozenset({1, 2})), (frozenset("d"), frozenset({1, 2, 3}))}
    assert library.private == frozenset("ce")
    assert library.address == 1
    assert library.cost == 73 and library.apart == 89


def test_nothing_is_gathered_where_nothing_is_shared() -> None:
    library = gathered({"a": {1}, "b": {2}, "c": set()}, {"a": 9.0, "b": 9.0, "c": 9.0})
    assert library.experts == () and library.private == frozenset("ab")
    assert library.cost == library.apart == 18
