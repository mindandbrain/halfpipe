# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
"""

import pytest

import numpy as np
from scipy import stats

from ..miscmaths import t2z_convert, f2z_convert


def t2z_convert_numpy(t, dof):
    p = stats.t.cdf(t, dof)
    z = stats.norm.ppf(p)

    return z


def f2z_convert_numpy(f, dof1, dof2):
    p = stats.f.cdf(f, dof1, dof2)
    z = stats.norm.ppf(p)

    return z


@pytest.mark.parametrize("t", np.linspace(-7, 7, num=5))
@pytest.mark.parametrize("dof", [2, 10, 30])
def test_t2z_convert_numpy(t, dof):
    assert np.isclose(t2z_convert(t, dof), t2z_convert_numpy(t, dof))


@pytest.mark.parametrize("t", np.logspace(1, 4, num=5))
@pytest.mark.parametrize("dof", [2, 10, 30])
def test_t2z_convert_large(t, dof):
    assert np.isfinite(t2z_convert(t, dof))


@pytest.mark.parametrize("f", np.linspace(1e-3, 7, num=5))
@pytest.mark.parametrize("d1,d2", [
    (1, 1), (2, 1), (5, 2), (10, 1), (10, 100)
])
def test_f2z_convert_numpy(f, d1, d2):
    assert np.isclose(f2z_convert(f, d1, d2), f2z_convert_numpy(f, d1, d2))


@pytest.mark.parametrize("f", np.logspace(2, 4, num=5))
@pytest.mark.parametrize("d1,d2", [
    (10, 20), (10, 100)
])
def test_f2z_convert_large(f, d1, d2):
    assert np.isfinite(f2z_convert(f, d1, d2))


@pytest.mark.timeout(1)
def test_nonfinite():
    assert t2z_convert(np.inf, 1) == np.inf
    assert t2z_convert(-np.inf, 1) == -np.inf
    assert np.isnan(t2z_convert(np.nan, 1))

    assert f2z_convert(np.inf, 1, 1) == np.inf
    assert f2z_convert(-np.inf, 1, 1) == -np.inf
    assert np.isnan(f2z_convert(np.nan, 1, 1))
