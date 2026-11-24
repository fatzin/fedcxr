"""Partição entre clientes e aquisição simulada."""
import numpy as np
import torch

from fedcxr import acquisition, partition


def test_dirichlet_covers_every_sample_and_alpha_controls_kl():
    rng = np.random.default_rng(0)
    labels = rng.integers(0, 3, 3000)
    idx = np.arange(3000)
    kls = {}
    for alpha in (100.0, 0.1):
        parts = partition.dirichlet(idx, labels, 10, alpha, np.random.default_rng(1), min_size=5)
        assert sorted(np.concatenate(parts).tolist()) == idx.tolist()
        kls[alpha] = partition.label_stats(parts, labels, 3)["kl_mean"]
    assert kls[100.0] < 0.01 < kls[0.1]


def test_iid_split_is_balanced():
    parts = partition.iid(np.arange(1000), 10, np.random.default_rng(0))
    assert sorted(len(p) for p in parts) == [100] * 10


def test_acquisition_is_identity_at_zero_severity():
    imgs = (torch.rand(5, 32, 32) * 255).to(torch.uint8)
    profile = acquisition.sample_profiles(1, 0.0, seed=0)[0]
    assert torch.equal(acquisition.apply_profile(imgs, profile, seed=0), imgs)


def test_harmonization_moves_histogram_towards_reference():
    imgs = (torch.rand(5, 32, 32) * 255).to(torch.uint8)
    shifted = acquisition.apply_profile(imgs, acquisition.sample_profiles(1, 1.0, seed=3)[0], seed=0)
    ref = acquisition.reference_cdf(imgs)
    out = acquisition.harmonize(shifted, ref)
    gap_before = (acquisition.reference_cdf(shifted) - ref).abs().max()
    gap_after = (acquisition.reference_cdf(out) - ref).abs().max()
    assert gap_after < gap_before
