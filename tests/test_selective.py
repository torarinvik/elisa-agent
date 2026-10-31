import numpy as np
import pytest

torch = pytest.importorskip("torch")

from torch import nn

from nca.selective import Reader, Rung, segment, solve


def constant_reader(probabilities: list[float]) -> Reader:
    """A reader whose output distribution ignores the glyph."""
    network = nn.Sequential(nn.Flatten(), nn.Linear(28 * 28, len(probabilities)))
    with torch.no_grad():
        network[1].weight.zero_()
        network[1].bias.copy_(torch.tensor(probabilities).log())
    return Reader(network, slice(None))


def ladders() -> tuple[list[Rung], list[Rung]]:
    unsure = constant_reader([0.4, 0.6] + [0.0001] * 8)
    sure = constant_reader([0.0001, 0.999] + [0.0001] * 8)
    operator = constant_reader([0.998, 0.001, 0.001])
    return [Rung(unsure), Rung(sure)], [Rung(operator)]


def test_refines_until_bound_meets_target() -> None:
    digits, operators = ladders()
    glyphs = [torch.zeros(28, 28)] * 3
    outcome = solve(glyphs, digits, operators, delta=0.05)
    assert outcome.tokens == ("1", "+", "1")
    assert not outcome.abstained and outcome.bound <= 0.05
    assert outcome.cost == pytest.approx(2 * digits[0].cost + 2 * digits[1].cost
                                         + operators[0].cost)


def test_abstains_when_no_rung_remains() -> None:
    digits, operators = ladders()
    outcome = solve([torch.zeros(28, 28)] * 3, digits[:1], operators, delta=0.05)
    assert outcome.abstained and outcome.bound > 0.05
    assert solve([torch.zeros(28, 28)] * 2, digits, operators, delta=1.0).abstained


def test_repair_merges_the_narrowest_gap() -> None:
    image = np.zeros((28, 80))
    for start, end in ((2, 10), (20, 24), (29, 33), (50, 58)):
        image[5:20, start:end] = 1.0
    assert len(segment(image, repair=False)) == 4
    repaired = segment(image, repair=True)
    assert len(repaired) == 3
    assert np.isclose(repaired[1].sum().item(), 15 * 8, rtol=1e-2)


def test_practice_queue_and_fine_tuning() -> None:
    from nca.practice import practice, queue

    torch.manual_seed(0)
    risks = torch.tensor([0.05, 0.6, 0.2, 0.9])
    assert queue(risks, 0.2).tolist() == [1, 2, 3]

    network = nn.Sequential(nn.Flatten(), nn.Linear(28 * 28, 10))
    glyphs, labels = torch.rand(16, 28, 28), torch.full((16,), 3)
    student = practice(network, glyphs, labels, (glyphs[:8], labels[:8]), epochs=3, seed=0)
    assert student is not network and not student.training
    with torch.no_grad():
        assert (student(glyphs[:, None]).argmax(dim=1) == 3).float().mean() > \
            (network(glyphs[:, None]).argmax(dim=1) == 3).float().mean()
