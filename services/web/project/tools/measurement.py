import pandas as pd
from project.tools.influxdb_funcs import read_ifdb
from project.tools.gas_funcs import calculate_pearsons_r
from project.tools.filter import get_datetime_index


class MeasurementCycle:
    def __init__(self, id, start, close, open, end, data=None):
        self.id = id
        self.start = start
        self.close = close
        self.open = open
        self.end = end
        self.data = data
        self.lagtime_index = None
        self.lagtime_s = None
        self.is_valid = True
        self.localize_times()

    def find_max(self, gas):
        mask1 = self.data.index > self.open
        mask2 = self.data.index < (self.open + pd.Timedelta(minutes=2))
        data = self.data[mask1 & mask2]
        if not data.empty:
            self.lagtime_index = data[gas].idxmax()
            self.lagtime_s = (self.lagtime_index - self.open).total_seconds()
            print(self.lagtime_s)

    def del_lagtime(self):
        self.lagtime_index = None

    def localize_times(self):
        tz = "Europe/Helsinki"
        self.start = self.start.tz_localize(tz)
        self.close = self.close.tz_localize(tz)
        self.open = self.open.tz_localize(tz)
        self.end = self.end.tz_localize(tz)
        self.lag_end = self.open + pd.Timedelta(minutes=2)

    def get_data(self, ifdb_dict):
        if self.data is None:
            tz = "Europe/Helsinki"
            meas_dict = {"measurement": "AC LICOR", "fields": "CH4,CO2,DIAG"}
            self.data = read_ifdb(
                ifdb_dict, meas_dict, start_ts=self.start, stop_ts=self.end
            )
            if not self.data.empty:
                self.data.set_index("datetime", inplace=True)
                self.data.index = pd.to_datetime(self.data.index)
                self.data = self.data.tz_localize(tz)
            start, end = get_datetime_index(
                self.data, self, s_key="close", e_key="open"
            )
            data = self.data.iloc[start:end]
            if data["DIAG"].sum() == 0:
                self.is_valid = False

    def get_max(self, ifdb_dict):
        # tz = "Europe/Helsinki"
        # meas_dict = {"measurement": "AC LICOR", "fields": "CH4,CO2"}
        # end = self.open + pd.Timedelta(minutes=2)
        # data = read_ifdb(ifdb_dict, meas_dict, start_ts=self.open, stop_ts=end)
        self.get_data(ifdb_dict)
        start, end = get_datetime_index(self.data, self, s_key="open", e_key="lag_end")
        data = self.data.iloc[start:end]
        if data is None:
            self.lagtime_index = None
            self.lagtime_s = None
            self.r = None
            return
        if data.empty:
            return
        self.get_r()
        if self.r > 0.95:
            self.lagtime_index = data["CH4"].idxmax()
            self.lagtime_s = (self.lagtime_index - self.open).total_seconds()

    def push_lagtimes(self, ifdb_dict):
        pass

    def get_r(self):
        start, end = get_datetime_index(self.data, self, s_key="close", e_key="open")
        data = self.data.iloc[start:end]
        self.r = calculate_pearsons_r(data.index.view(int), data["CH4"])
