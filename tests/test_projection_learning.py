"""Acquire intermediate features beyond fixed coordinate partitions."""

import random
from dataclasses import dataclass
from typing import Any

import pytest

from nca.abi import Contract, Manifest
from nca.discovery import discover
from nca.projection_learning import ProjectionEncoder, propose_projections


@dataclass
class Measurement:
    manifest = Manifest("measurement", "1", Contract(("input",), "vector"), effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return value


class Baseline:
    manifest = Manifest("baseline", "1", Contract(("input",), "output"), effects=frozenset())

    def invoke(self, value: Any) -> bool:
        return True


def test_acquire_oblique_type_and_select_on_fresh_rows() -> None:
    rng = random.Random(70)
    rows = [((rng.uniform(-1, 1), rng.uniform(-1, 1)),) for _ in range(1000)]
    labels = [row[0][0] + row[0][1] >= 0 for row in rows]
    sizes = []

    def propose(train: Any, targets: Any) -> Any:
        sizes.append(len(train))
        return propose_projections(Baseline(), Measurement(), train, targets, limit=1,
                                   projection_cost=1, encoding_cost=1, decoder_cost=1)

    result = discover(Baseline(), propose, rows, labels, lambda a, b: a == b)
    assert sizes == [500]
    assert result.chosen is not None
    assert sum(result.trials[0].outcomes) >= 475
    proposal = propose(rows[:500], labels[:500])[0]
    assert len(proposal.constructors) == 2
    projection, partition = proposal.constructors
    assert projection.type() != partition.type()
    assert proposal.expert.feature.measurement.manifest.contract.output == projection.type()


def test_coincident_centroids_and_invalid_observations() -> None:
    rows = [((-1.0, -1.0),), ((1.0, 1.0),), ((-1.0, 1.0),), ((1.0, -1.0),)]
    options = dict(limit=1, projection_cost=1, encoding_cost=1, decoder_cost=1)
    assert propose_projections(Baseline(), Measurement(), rows, [True, True, False, False],
                               **options) == []
    for bad in [[((0.0,),), ((0.0, 1.0),)], [((float("nan"),),), ((1.0,),)]]:
        with pytest.raises(ValueError):
            propose_projections(Baseline(), Measurement(), bad, [True, False], **options)
    projection = ProjectionEncoder(Measurement(), (1.0, 2.0), 1)
    with pytest.raises(ValueError, match="dimension"):
        projection.invoke((1.0,))


def test_pair_search_budget() -> None:
    rows = [((float(i),),) for i in range(6)]
    labels = [i // 2 for i in range(6)]
    assert len(propose_projections(Baseline(), Measurement(), rows, labels, limit=2,
                                  projection_cost=0, encoding_cost=0, decoder_cost=0)) == 2
