import pandas as pd
from project.tools.influxdb_funcs import read_ifdb


class MeasurementCycle:
    def __init__(self, id, start, close, open, end, data=None):
        self.id = id
        self.start = start
        self.close = close
        self.open = open
        self.end = end
        self.data = data
        self.lagtime_index = None
        self.localize_times()

    def find_max(self, gas):
        mask1 = self.data.index > self.open
        mask2 = self.data.index < (self.open + pd.Timedelta(minutes=2))
        data = self.data[mask1 & mask2]
        if not data.empty:
            self.lagtime_index = data[gas].idxmax()
            self.lagtime_s = (self.lagtime_index - self.open).total_seconds()
            print(self.lagtime_s)

    def remove_lagtime(self):
        self.lagtime_index = None

    def localize_times(self):
        tz = "Europe/Helsinki"
        self.start = self.start.tz_localize(tz)
        self.close = self.close.tz_localize(tz)
        self.open = self.open.tz_localize(tz)
        self.end = self.end.tz_localize(tz)

    def get_data(self, ifdb_dict):
        meas_dict = {"measurement": "AC LICOR", "fields": "CH4,CO2"}
        self.data = read_ifdb(
            ifdb_dict, meas_dict, start_ts=self.start, stop_ts=self.end
        )

    def get_max(self, ifdb_dict):
        tz = "Europe/Helsinki"
        meas_dict = {"measurement": "AC LICOR", "fields": "CH4,CO2"}
        end = self.open + pd.Timedelta(minutes=2)
        data = read_ifdb(ifdb_dict, meas_dict, start_ts=self.open, stop_ts=end)
        if data is None:
            self.lagtime_index = None
            self.lagtime_s = None
            return
        if not data.empty:
            data.set_index("datetime", inplace=True)
            data.index = pd.to_datetime(data.index)
            data = data.tz_localize(tz)
            self.lagtime_index = data["CH4"].idxmax()
            self.lagtime_s = (self.lagtime_index - self.open).total_seconds()
