from fractions import Fraction

import pytest
from shapely.affinity import scale

from experiments.external_committed_fixtures import certify, fixtures


@pytest.mark.parametrize("name,domain,blocks", list(fixtures()), ids=[r[0] for r in fixtures()])
def test_complete_certified_fixture(name, domain, blocks):
    polygons, result = certify(domain, blocks)
    if name == "L_room":
        assert {frozenset(p) for p in polygons} == {
            frozenset(((0, 0), (6, 0), (6, 2), (0, 2))),
            frozenset(((0, 0), (2, 0), (2, 6), (0, 6))),
        }
        assert Fraction(result["coverage"]["area_by_count"]["2"]) == 4


@pytest.mark.parametrize("name,domain,blocks",
                         [r for r in fixtures() if r[0] in {"L_room", "three_blocks", "concave_external"}],
                         ids=["L room", "three blocks", "concave external"])
def test_reflection_exchanges_handedness(name, domain, blocks):
    def reflect(shape):
        return scale(shape, xfact=-1, origin=(0, 0))

    original, _ = certify(domain, blocks)
    reflected, _ = certify(reflect(domain), {k: reflect(v) for k, v in blocks.items()})
    for hand in (-1, 1):
        assert {frozenset((-x, y) for x, y in p) for p, paths in original.items()
                if any(path["sign"] == hand for path in paths)} == {
                    frozenset(p) for p, paths in reflected.items()
                    if any(path["sign"] == -hand for path in paths)}
