"""
Tests for 2D compatibility.
"""
import numpy as np
import pytest

from .base import BaseExtensionTests


class Dim2CompatTests(BaseExtensionTests):
    def test_take_2d(self, data):
        arr2d = data.reshape(-1, 1)

        result = arr2d.take([0, 0, -1], axis=0)

        expected = data.take([0, 0, -1]).reshape(-1, 1)
        self.assert_extension_array_equal(result, expected)

    def test_repr_2d(self, data):
        # this could fail in a corner case where an element contained the name
        res = repr(data.reshape(1, -1))
        assert res.count(f"<{type(data).__name__}") == 1

        res = repr(data.reshape(-1, 1))
        assert res.count(f"<{type(data).__name__}") == 1

    def test_reshape(self, data):
        arr2d = data.reshape(-1, 1)
        assert arr2d.shape == (data.size, 1)
        assert len(arr2d) == len(data)

        arr2d = data.reshape((-1, 1))
        assert arr2d.shape == (data.size, 1)
        assert len(arr2d) == len(data)

        with pytest.raises(ValueError):
            data.reshape((data.size, 2))
        with pytest.raises(ValueError):
            data.reshape(data.size, 2)

    def test_getitem_2d(self, data):
        arr2d = data.reshape(1, -1)

        result = arr2d[0]
        self.assert_extension_array_equal(result, data)

        with pytest.raises(IndexError):
            arr2d[1]

        with pytest.raises(IndexError):
            arr2d[-2]

        result = arr2d[:]
        self.assert_extension_array_equal(result, arr2d)

        result = arr2d[:, :]
        self.assert_extension_array_equal(result, arr2d)

        result = arr2d[:, 0]
        expected = data[[0]]
        self.assert_extension_array_equal(result, expected)

        # dimension-expanding getitem on 1D
        result = data[:, np.newaxis]
        self.assert_extension_array_equal(result, arr2d.T)

    def test_iter_2d(self, data):
        arr2d = data.reshape(1, -1)

        objs = list(iter(arr2d))
        assert len(objs) == arr2d.shape[0]

        for obj in objs:
            assert isinstance(obj, type(data))
            assert obj.dtype == data.dtype
            assert obj.ndim == 1
            assert len(obj) == arr2d.shape[1]

    def test_concat_2d(self, data):
        left = data.reshape(-1, 1)
        right = left.copy()

        # axis=0
        result = left._concat_same_type([left, right], axis=0)
        expected = data._concat_same_type([data, data]).reshape(-1, 1)
        self.assert_extension_array_equal(result, expected)

        # axis=1
        result = left._concat_same_type([left, right], axis=1)
        expected = data.repeat(2).reshape(-1, 2)
        self.assert_extension_array_equal(result, expected)

        # axis > 1 -> invalid
        with pytest.raises(ValueError):
            left._concat_same_type([left, right], axis=2)

    @pytest.mark.parametrize("method", ["mean", "median", "var", "std", "sum", "prod"])
    def test_reductions_2d_axis_none(self, data, method):
        if not hasattr(data, method):
            pytest.skip("test is not applicable for this type/dtype")

        arr2d = data.reshape(1, -1)

        err_expected = None
        err_result = None
        try:
            expected = getattr(data, method)()
        except Exception as err:
            # if the 1D reduction is invalid, the 2D reduction should be as well
            err_expected = err
            try:
                result = getattr(arr2d, method)(axis=None)
            except Exception as err2:
                err_result = err2

        else:
            result = getattr(arr2d, method)(axis=None)

        if err_result is not None or err_expected is not None:
            assert type(err_result) == type(err_expected)
            return

        assert result == expected  # TODO: or matching NA
