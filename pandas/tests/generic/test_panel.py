# -*- coding: utf-8 -*-
# pylint: disable-msg=E1101,W0612

from warnings import catch_warnings

import pytest

from pandas import Panel, Panel4D
from pandas.util.testing import (assert_panel_equal,
                                 assert_panel4d_equal,
                                 assert_almost_equal)

import pandas.util.testing as tm
from .test_generic import Generic


class TestPanel(Generic):
    _typ = Panel
    _comparator = lambda self, x, y: assert_panel_equal(x, y, by_blocks=True)

    def test_to_xarray(self):

        tm._skip_if_no_xarray()
        from xarray import DataArray

        with catch_warnings(record=True):
            p = tm.makePanel()

            result = p.to_xarray()
            assert isinstance(result, DataArray)
            assert len(result.coords) == 3
            assert_almost_equal(list(result.coords.keys()),
                                ['items', 'major_axis', 'minor_axis'])
            assert len(result.dims) == 3

            # idempotency
            assert_panel_equal(result.to_pandas(), p)


class TestPanel4D(Generic):
    _typ = Panel4D
    _comparator = lambda self, x, y: assert_panel4d_equal(x, y, by_blocks=True)

    def test_sample(self):
        pytest.skip("sample on Panel4D")

    def test_to_xarray(self):

        tm._skip_if_no_xarray()
        from xarray import DataArray

        with catch_warnings(record=True):
            p = tm.makePanel4D()

            result = p.to_xarray()
            assert isinstance(result, DataArray)
            assert len(result.coords) == 4
            assert_almost_equal(list(result.coords.keys()),
                                ['labels', 'items', 'major_axis',
                                 'minor_axis'])
            assert len(result.dims) == 4

            # non-convertible
            pytest.raises(ValueError, lambda: result.to_pandas())


# run all the tests, but wrap each in a warning catcher
for t in ['test_rename', 'test_rename_axis', 'test_get_numeric_data',
          'test_get_default', 'test_nonzero',
          'test_downcast', 'test_constructor_compound_dtypes',
          'test_head_tail',
          'test_size_compat', 'test_split_compat',
          'test_unexpected_keyword',
          'test_stat_unexpected_keyword', 'test_api_compat',
          'test_stat_non_defaults_args',
          'test_truncate_out_of_bounds',
          'test_metadata_propagation', 'test_copy_and_deepcopy',
          'test_sample']:

    def f():
        def tester(self):
            with catch_warnings(record=True):
                return getattr(super(TestPanel, self), t)()
        return tester

    setattr(TestPanel, t, f())

    def f():
        def tester(self):
            with catch_warnings(record=True):
                return getattr(super(TestPanel4D, self), t)()
        return tester

    setattr(TestPanel4D, t, f())
