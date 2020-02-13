"""
Ops for masked arrays.
"""
from typing import Optional, Union

import numpy as np

from pandas._libs import lib, missing as libmissing
from pandas.compat.numpy import _np_version_under1p17


def kleene_or(
    left: Union[bool, np.ndarray],
    right: Union[bool, np.ndarray],
    left_mask: Optional[np.ndarray],
    right_mask: Optional[np.ndarray],
):
    """
    Boolean ``or`` using Kleene logic.

    Values are NA where we have ``NA | NA`` or ``NA | False``.
    ``NA | True`` is considered True.

    Parameters
    ----------
    left, right : ndarray, NA, or bool
        The values of the array.
    left_mask, right_mask : ndarray, optional
        The masks. Only one of these may be None, which implies that
        the associated `left` or `right` value is a scalar.

    Returns
    -------
    result, mask: ndarray[bool]
        The result of the logical or, and the new mask.
    """
    # To reduce the number of cases, we ensure that `left` & `left_mask`
    # always come from an array, not a scalar. This is safe, since because
    # A | B == B | A
    if left_mask is None:
        return kleene_or(right, left, right_mask, left_mask)

    assert isinstance(left, np.ndarray)

    raise_for_nan(right, method="or")

    if right is libmissing.NA:
        result = left.copy()
    else:
        result = left | right

    if right_mask is not None:
        # output is unknown where (False & NA), (NA & False), (NA & NA)
        left_false = ~(left | left_mask)
        right_false = ~(right | right_mask)
        mask = (
            (left_false & right_mask)
            | (right_false & left_mask)
            | (left_mask & right_mask)
        )
    else:
        if right is True:
            mask = np.zeros_like(left_mask)
        elif right is libmissing.NA:
            mask = (~left & ~left_mask) | left_mask
        else:
            # False
            mask = left_mask.copy()

    return result, mask


def kleene_xor(
    left: Union[bool, np.ndarray],
    right: Union[bool, np.ndarray],
    left_mask: Optional[np.ndarray],
    right_mask: Optional[np.ndarray],
):
    """
    Boolean ``xor`` using Kleene logic.

    This is the same as ``or``, with the following adjustments

    * True, True -> False
    * True, NA   -> NA

    Parameters
    ----------
    left, right : ndarray, NA, or bool
        The values of the array.
    left_mask, right_mask : ndarray, optional
        The masks. Only one of these may be None, which implies that
        the associated `left` or `right` value is a scalar.

    Returns
    -------
    result, mask: ndarray[bool]
        The result of the logical xor, and the new mask.
    """
    if left_mask is None:
        return kleene_xor(right, left, right_mask, left_mask)

    raise_for_nan(right, method="xor")
    if right is libmissing.NA:
        result = np.zeros_like(left)
    else:
        result = left ^ right

    if right_mask is None:
        if right is libmissing.NA:
            mask = np.ones_like(left_mask)
        else:
            mask = left_mask.copy()
    else:
        mask = left_mask | right_mask

    return result, mask


def kleene_and(
    left: Union[bool, libmissing.NAType, np.ndarray],
    right: Union[bool, libmissing.NAType, np.ndarray],
    left_mask: Optional[np.ndarray],
    right_mask: Optional[np.ndarray],
):
    """
    Boolean ``and`` using Kleene logic.

    Values are ``NA`` for ``NA & NA`` or ``True & NA``.

    Parameters
    ----------
    left, right : ndarray, NA, or bool
        The values of the array.
    left_mask, right_mask : ndarray, optional
        The masks. Only one of these may be None, which implies that
        the associated `left` or `right` value is a scalar.

    Returns
    -------
    result, mask: ndarray[bool]
        The result of the logical xor, and the new mask.
    """
    # To reduce the number of cases, we ensure that `left` & `left_mask`
    # always come from an array, not a scalar. This is safe, since because
    # A | B == B | A
    if left_mask is None:
        return kleene_and(right, left, right_mask, left_mask)

    assert isinstance(left, np.ndarray)
    raise_for_nan(right, method="and")

    if right is libmissing.NA:
        result = np.zeros_like(left)
    else:
        result = left & right

    if right_mask is None:
        # Scalar `right`
        if right is libmissing.NA:
            mask = (left & ~left_mask) | left_mask

        else:
            mask = left_mask.copy()
            if right is False:
                # unmask everything
                mask[:] = False
    else:
        # unmask where either left or right is False
        left_false = ~(left | left_mask)
        right_false = ~(right | right_mask)
        mask = (left_mask & ~right_false) | (right_mask & ~left_false)

    return result, mask


def raise_for_nan(value, method):
    if lib.is_float(value) and np.isnan(value):
        raise ValueError(f"Cannot perform logical '{method}' with floating NaN")


def sum(
    values: np.ndarray, mask: np.ndarray, skipna: bool, min_count: int = 0,
):
    """
    Sum for 1D masked array.

    Parameters
    ----------
    values : np.ndarray
        Numpy array with the values (can be of any dtype that support the
        operation).
    mask : np.ndarray
        Boolean numpy array (False for missing)
    skipna : bool, default True
        Whether to skip NA.
    min_count : int, default 0
        The required number of valid values to perform the operation. If fewer than
        ``min_count`` non-NA values are present the result will be NA.
    """
    if not skipna:
        if mask.any():
            return libmissing.NA
        else:
            if _below_min_count(values, None, min_count):
                return libmissing.NA
            return np.sum(values)
    else:
        if _below_min_count(values, mask, min_count):
            return libmissing.NA

        if _np_version_under1p17:
            return np.sum(values[~mask])
        else:
            return np.sum(values, where=~mask)


def _below_min_count(values, mask, min_count):
    """
    Check for the `min_count` keyword. Returns True if below `min_count` (when
    pd.NA should be returned from the reduction).
    """
    if min_count > 0:
        if mask is None:
            # no missing values, only check size
            non_nulls = values.size
        else:
            non_nulls = mask.size - mask.sum()
        if non_nulls < min_count:
            return True
    return False
