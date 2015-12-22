from .pandas_vb_common import *
try:
    from pandas import date_range
except ImportError:
    def date_range(start=None, end=None, periods=None, freq=None):
        return DatetimeIndex(start, end, periods=periods, offset=freq)
from pandas.tools.plotting import andrews_curves


class plot_timeseries_period(object):
    goal_time = 0.2

    def setup(self):
        self.N = 2000
        self.M = 5
        self.df = DataFrame(np.random.randn(self.N, self.M), index=date_range('1/1/1975', periods=self.N))

    def time_plot_timeseries_period(self):
        self.df.plot()

class plot_andrews_curves(object):
    goal_time = 0.6

    def setup(self):
        self.N = 500
        self.M = 10
	data_dict = {x: np.random.randn(self.N) for x in range(self.M)}
	data_dict["Name"] = ["A"] * self.N
        self.df = DataFrame(data_dict)

    def time_plot_andrews_curves(self):
        andrews_curves(self.df, "Name")
