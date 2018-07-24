# coding: utf-8

""" Test cases for GroupBy.plot """


from pandas import Series, DataFrame
import pandas.util.testing as tm
import pandas.util._test_decorators as td

import numpy as np

from pandas.tests.plotting.common import TestPlotBase

from itertools import count
import pandas as pd


def test_no_double_plot_for_first_group():
    class extGroupByPlot(pd.core.groupby.groupby.GroupByPlot):
        def __init__(self, groupby):
            super().__init__(groupby)

        def __getattr__(self, name):
            def attr(*args, **kwargs):
                counter_obj = count()

                def f(self):
                    getattr(self.plot, name)(*args, **kwargs)
                    next(counter_obj) # I have no idea why this is needed
                    return next(counter_obj)

                f.__name__ = name
                return self._groupby.apply(f)

            return attr

    df = pd.DataFrame([[1, 2], [3, 4], [5, 6], [7, 8]], columns=['x', 'y'])
    df['cat'] = [1, 1, 1, 1]
    g = df.groupby('cat')
    extra_plotting_methods = ['line', 'bar', 'barh',
                              'box', 'kde', 'density',
                              'area', 'pie', 'scatter',
                              'hexbin']

    for plotting_method in extra_plotting_methods:
        eG = extGroupByPlot(g)
        result = eG.__getattr__(plotting_method)(x='x', y='y')
        assert result.iloc[0] == 1


@td.skip_if_no_mpl
class TestDataFrameGroupByPlots(TestPlotBase):

    def test_series_groupby_plotting_nominally_works(self):
        n = 10
        weight = Series(np.random.normal(166, 20, size=n))
        height = Series(np.random.normal(60, 10, size=n))
        with tm.RNGContext(42):
            gender = np.random.choice(['male', 'female'], size=n)

        weight.groupby(gender).plot()
        tm.close()
        height.groupby(gender).hist()
        tm.close()
        # Regression test for GH8733
        height.groupby(gender).plot(alpha=0.5)
        tm.close()

    def test_plotting_with_float_index_works(self):
        # GH 7025
        df = DataFrame({'def': [1, 1, 1, 2, 2, 2, 3, 3, 3],
                        'val': np.random.randn(9)},
                       index=[1.0, 2.0, 3.0, 1.0, 2.0, 3.0, 1.0, 2.0, 3.0])

        df.groupby('def')['val'].plot()
        tm.close()
        df.groupby('def')['val'].apply(lambda x: x.plot())
        tm.close()

    def test_hist_single_row(self):
        # GH10214
        bins = np.arange(80, 100 + 2, 1)
        df = DataFrame({"Name": ["AAA", "BBB"],
                        "ByCol": [1, 2],
                        "Mark": [85, 89]})
        df["Mark"].hist(by=df["ByCol"], bins=bins)
        df = DataFrame({"Name": ["AAA"], "ByCol": [1], "Mark": [85]})
        df["Mark"].hist(by=df["ByCol"], bins=bins)

    def test_plot_submethod_works(self):
        df = DataFrame({'x': [1, 2, 3, 4, 5],
                        'y': [1, 2, 3, 2, 1],
                        'z': list('ababa')})
        df.groupby('z').plot.scatter('x', 'y')
        tm.close()
        df.groupby('z')['x'].plot.line()
        tm.close()

    def test_plot_kwargs(self):

        df = DataFrame({'x': [1, 2, 3, 4, 5],
                        'y': [1, 2, 3, 2, 1],
                        'z': list('ababa')})

        res = df.groupby('z').plot(kind='scatter', x='x', y='y')
        # check that a scatter plot is effectively plotted: the axes should
        # contain a PathCollection from the scatter plot (GH11805)
        assert len(res['a'].collections) == 1

        res = df.groupby('z').plot.scatter(x='x', y='y')
        assert len(res['a'].collections) == 1
