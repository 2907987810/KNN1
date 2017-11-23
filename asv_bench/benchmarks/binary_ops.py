import numpy as np
from pandas import DataFrame, Series, date_range
try:
    import pandas.core.computation.expressions as expr
except ImportError:
    import pandas.computation.expressions as expr


class Ops(object):

    goal_time = 0.2

    params = [[True, False], ['default', 1]]
    param_names = ['use_numexpr', 'threads']

    def setup(self, use_numexpr, threads):
        np.random.seed(1234)
        self.df = DataFrame(np.random.randn(20000, 100))
        self.df2 = DataFrame(np.random.randn(20000, 100))

        if threads != 'default':
            expr.set_numexpr_threads(threads)
        if not use_numexpr:
            expr.set_use_numexpr(False)

    def time_frame_add(self, use_numexpr, threads):
        self.df + self.df2

    def time_frame_mult(self, use_numexpr, threads):
        self.df * self.df2

    def time_frame_multi_and(self, use_numexpr, threads):
        self.df[(self.df > 0) & (self.df2 > 0)]

    def time_frame_comparison(self, use_numexpr, threads):
        self.df > self.df2

    def teardown(self, use_numexpr, threads):
        expr.set_use_numexpr(True)
        expr.set_numexpr_threads()


class Ops2(object):

    goal_time = 0.2

    def setup(self):
        N = 10**3
        np.random.seed(1234)
        self.df = DataFrame(np.random.randn(N, N))
        self.df2 = DataFrame(np.random.randn(N, N))

        self.df_int = DataFrame(np.random.randint(np.iinfo(np.int16).min,
                                                  np.iinfo(np.int16).max,
                                                  size=(N, N)))
        self.df2_int = DataFrame(np.random.randint(np.iinfo(np.int16).min,
                                                   np.iinfo(np.int16).max,
                                                   size=(N, N)))

    # Division

    def time_frame_float_div(self):
        self.df // self.df2

    def time_frame_float_div_by_zero(self):
        self.df / 0

    def time_frame_float_floor_by_zero(self):
        self.df // 0

    def time_frame_int_div_by_zero(self):
        self.df_int / 0

    # Modulo

    def time_frame_int_mod(self):
        self.df_int % self.df2_int

    def time_frame_float_mod(self):
        self.df % self.df2


class Timeseries(object):

    goal_time = 0.2

    params = [None, 'US/Eastern']

    def setup(self, tz):
        self.N = 10**6
        self.halfway = ((self.N // 2) - 1)
        self.s = Series(date_range('20010101', periods=self.N, freq='T',
                                   tz=tz))
        self.ts = self.s[self.halfway]

        self.s2 = Series(date_range('20010101', periods=self.N, freq='s',
                                    tz=tz))

    def time_series_timestamp_compare(self, tz):
        self.s <= self.ts

    def time_timestamp_series_compare(self, tz):
        self.ts >= self.s

    def time_timestamp_ops_diff(self, tz):
        self.s2.diff()

    def time_timestamp_ops_diff_with_shift(self, tz):
        self.s - self.s.shift()
