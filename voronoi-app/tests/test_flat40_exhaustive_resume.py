from experiments.external_committed_fixtures import certify, fixtures
from experiments.flat40_exhaustive_resume import exact_caches


def test_exact_caches_preserve_exhaustive_fixture_geometry_and_provenance():
    for name, domain, blocks in fixtures():
        if name not in {"L_room", "three_blocks", "four_blocks", "concave_external"}:
            continue
        reference = certify(domain, blocks)
        with exact_caches():
            assert certify(domain, blocks) == reference
