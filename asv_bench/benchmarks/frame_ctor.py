import numpy as np
import pandas.util.testing as tm
from pandas import DataFrame, Series, MultiIndex, Timestamp, date_range
try:
    from pandas.tseries.offsets import Nano, Hour
except ImportError:
    # For compatability with older versions(?)
    from pandas.core.datetools import *


class FromDicts(object):

    goal_time = 0.2

    def setup(self):
        np.random.seed(1234)
        N, K = 5000, 50
        index = tm.makeStringIndex(N)
        columns = tm.makeStringIndex(K)
        frame = DataFrame(np.random.randn(N, K), index=index, columns=columns)
        self.data = frame.to_dict()
        self.some_dict = list(self.data.values())[0]
        self.dict_list = frame.to_dict(orient='records')
        self.data2 = {i: {j: float(j) for j in range(100)}
                      for i in range(2000)}

    def time_list_of_dict(self):
        DataFrame(self.dict_list)

    def time_nested_dict(self):
        DataFrame(self.data)

    def time_dict(self):
        Series(self.some_dict)

    def time_nested_dict_int64(self):
        # nested dict, integer indexes, regression described in #621
        DataFrame(self.data2)


class FromSeries(object):

    goal_time = 0.2

    def setup(self):
        mi = MultiIndex.from_product([range(100), range(100)])
        self.s = Series(np.random.randn(10000), index=mi)

    def time_mi_series(self):
        DataFrame(self.s)


class FromDictwithTimestamp(object):

    goal_time = 0.2
    params = [Nano(1), Hour(1)]
    param_names = ['offset']

    def setup(self, offset):
        N = 10**3
        np.random.seed(1234)
        idx = date_range(Timestamp('1/1/1900'), freq=offset, periods=N)
        df = DataFrame(np.random.randn(N, 10), index=idx)
        self.d = df.to_dict()

    def time_dict_with_timestamp_offsets(self, offset):
        DataFrame(self.d)
