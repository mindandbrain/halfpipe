# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
"""

import math
import logging
from pprint import pformat

from mpmath import mpf, workdps, sqrt, erfinv, gamma, hyper, pi, power, betainc

logger = logging.getLogger("halfpipe")


def adaptive_precision(func):
    """
    ensure that the wrapped is run with sufficient precision
    """

    def wrapper(*args):
        if any(math.isnan(a) for a in args):
            return math.nan  # skip computation

        if math.isinf(args[0]):  # first argument is always the statistic
            return args[0]

        dps = 2 ** 4

        zprev = None

        while dps <= 2 ** 16:  # avoid infinite loop
            with workdps(dps):
                z = math.inf

                try:
                    z = float(func(*args))
                except ValueError:
                    pass
                except ZeroDivisionError:
                    return math.nan

                if zprev is not None:
                    if math.isfinite(z):
                        if math.isclose(z, zprev):
                            return float(z)

                dps *= 2

                zprev = z

        if not math.isnan(z):
            logger.warning(f"Convergence failure for adaptive_precision with args {pformat(args)}")
        return float(z)

    return wrapper


@adaptive_precision
def t2z_convert(t, nu):
    t = mpf(t)
    nu = mpf(nu)

    z = sqrt(mpf("2")) * erfinv(  # inverse normal cdf
        mpf("2") * t
        * gamma((mpf("1") / mpf("2")) * nu + mpf("1") / mpf("2"))
        * hyper(
            (mpf("1") / mpf("2"), (mpf("1") / mpf("2")) * nu + mpf("1") / mpf("2")),
            (mpf("3") / mpf("2"),),
            -power(t, mpf("2")) / nu,
        )
        / (sqrt(pi) * sqrt(nu) * gamma((mpf("1") / mpf("2")) * nu))
    )

    return z


@adaptive_precision
def f2z_convert(x, d1, d2):
    x = mpf(x)
    d1 = mpf(d1)
    d2 = mpf(d2)

    if x < mpf("0") or d1 < mpf("0") or d2 < mpf("0"):
        return mpf("0")

    z = sqrt(mpf("2")) * erfinv(  # inverse normal cdf
        -mpf("1") + mpf("2")
        * betainc(  # F distribution cdf
            d1 / mpf("2"),
            d2 / mpf("2"),
            x2=d1 * x / (d1 * x + d2),
            regularized=True
        )
    )

    return z
