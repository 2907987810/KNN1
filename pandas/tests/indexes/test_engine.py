# -*- coding: utf-8 -*-

import numpy as np
import pytest

import pandas as pd
from pandas._libs.index import (Int64Engine, UInt64Engine,
                                Float64Engine, ObjectEngine)


class TestNumericEngine(object):

    @pytest.mark.parametrize('data', [[0, 1, 2]])
    def test_engine_type(self, data, num_engine):
        index = pd.Index(data, dtype=num_engine._dtype)
        if issubclass(index.dtype.type, np.signedinteger):
            assert isinstance(index._engine, Int64Engine)
        elif issubclass(index.dtype.type, np.unsignedinteger):
            assert isinstance(index._engine, UInt64Engine)
        elif issubclass(index.dtype.type, np.floating):
            assert isinstance(index._engine, Float64Engine)
        else:
            raise TypeError("unexpected dtype {}".format(index.dtype))

    @pytest.mark.parametrize('data', [[0, 1, 2]])
    def test_is_monotonic_ordered(self, data, num_engine):
        codes = np.array(data, dtype=num_engine._dtype)
        e = num_engine(lambda: codes, len(codes))
        assert e.is_monotonic_increasing
        assert not e.is_monotonic_decreasing

        # reverse sort order
        codes = np.array(list(reversed(data)), dtype=num_engine._dtype)
        e = num_engine(lambda: codes, len(codes))
        assert not e.is_monotonic_increasing
        assert e.is_monotonic_decreasing

    @pytest.mark.parametrize('data', [[1, 0, 2]])
    def test_is_not_monotonic_ordered(self, data, num_engine):
        codes = np.array(data, dtype=num_engine._dtype)
        e = num_engine(lambda: codes, len(codes))
        assert not e.is_monotonic_increasing
        assert not e.is_monotonic_decreasing

    @pytest.mark.parametrize('values, expected', [
        ([1, 2, 3], True),
        ([1, 1, 2], False),
    ])
    def test_is_unique(self, values, expected, num_engine):

        codes = np.array(values, dtype=num_engine._dtype)
        e = num_engine(lambda: codes, len(codes))
        assert e.is_unique is expected


class TestObjectEngine(object):

    def setup_class(cls):
        cls.Engine = ObjectEngine
        cls.dtype = object

    @pytest.mark.parametrize('data', [['a', 'b', 'c']])
    def test_engine_type(self, data):
        index = pd.Index(data)
        assert isinstance(index._engine, self.Engine)

    @pytest.mark.parametrize('data', [['a', 'b', 'c']])
    def test_is_monotonic_ordered(self, data):
        codes = np.array(data, dtype=self.dtype)
        e = self.Engine(lambda: codes, len(codes))
        assert e.is_monotonic_increasing
        assert not e.is_monotonic_decreasing

        # reverse sort order
        codes = np.array(list(reversed(data)), dtype=self.dtype)
        e = self.Engine(lambda: codes, len(codes))
        assert not e.is_monotonic_increasing
        assert e.is_monotonic_decreasing

    @pytest.mark.parametrize('data', [['a', 'c', 'b']])
    def test_is_not_monotonic_ordered(self, data):
        codes = np.array(data, dtype=self.dtype)
        e = self.Engine(lambda: codes, len(codes))
        assert not e.is_monotonic_increasing
        assert not e.is_monotonic_decreasing

    @pytest.mark.parametrize('values, expected', [
        (['a', 'b', 'c'], True),
        (['a', 'a', 'b'], False),
    ])
    def test_is_unique(self, values, expected):
        codes = np.array(values, dtype=self.dtype)
        e = self.Engine(lambda: codes, len(codes))
        assert e.is_unique is expected
