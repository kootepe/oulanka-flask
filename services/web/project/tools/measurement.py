import pandas as pd
from collections import namedtuple
from project.tools.influxdb_funcs import just_read, read_ifdb
from project.tools.gas_funcs import calculate_pearsons_r
from project.tools.filter import get_datetime_index


class MeasurementCycle:
    def __init__(self, id, start, close, open, end, data=None):
        self.id = id
        self.start = start
        self.close = close
        self.adjusted_close = None
        self.open = open
        self.end = end
        self.data = data
        self.lagtime_index = None
        self.lagtime_s = None
        self.is_valid = True
        self.localize_times()

    def find_max(self, gas):
        mask1 = self.data.index > self.open
        mask2 = self.data.index < (self.open + pd.Timedelta(seconds=90))
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
        self.lag_end = self.open + pd.Timedelta(seconds=120)

    def just_get_data(self, ifdb_dict, client):
        if self.is_valid is False:
            return
        if self.data is None:
            tz = "Europe/Helsinki"
            meas_dict = {"measurement": "AC LICOR", "fields": "CH4,CO2,DIAG"}
            self.data = just_read(
                ifdb_dict, meas_dict, client, start_ts=self.start, stop_ts=self.end
            )
            if self.data is None:
                self.is_valid = False
                return
            if self.data.empty:
                self.is_valid = False
                return
            if self.data is not None:
                if not self.data.empty:
                    self.data.set_index("datetime", inplace=True)
                    self.data.index = pd.to_datetime(self.data.index)
                    self.data = self.data.tz_localize(tz)
                start, end = get_datetime_index(
                    self.data, self, s_key="close", e_key="open"
                )
                self.calc_data = self.data.iloc[start:end]
                if self.calc_data["DIAG"].sum() != 0:
                    self.is_valid = False

    def get_data(self, ifdb_dict):
        if self.is_valid is False:
            return
        if self.data is None:
            tz = "Europe/Helsinki"
            meas_dict = {"measurement": "AC LICOR", "fields": "CH4,CO2,DIAG"}
            self.data = read_ifdb(
                ifdb_dict, meas_dict, start_ts=self.start, stop_ts=self.end
            )
            if self.data is None:
                self.is_valid = False
            if self.data is not None:
                if not self.data.empty:
                    self.data.set_index("datetime", inplace=True)
                    self.data.index = pd.to_datetime(self.data.index)
                    self.data = self.data.tz_localize(tz)
                start, end = get_datetime_index(
                    self.data, self, s_key="close", e_key="open"
                )
                self.calc_data = self.data.iloc[start:end]
                if self.calc_data["DIAG"].sum() != 0:
                    self.is_valid = False

    def get_max(self, ifdb_dict, client):
        data = None
        self.just_get_data(ifdb_dict, client)
        if self.data is not None:
            start, end = get_datetime_index(
                self.data, self, s_key="open", e_key="lag_end"
            )
            data = self.data.iloc[start:end]
        if data is None:
            self.lagtime_index = None
            self.lagtime_s = None
            self.r = None
            return
        if data.empty:
            return
        if self.is_valid is False:
            return
        self.get_r()
        if self.r < 0.6:
            self.is_valid = False
        # if self.r > 0.95:
        self.get_lagtime(data)

    def get_lag_df(self, start, end):
        frame = namedtuple("filter", ["open", "lag_end"])
        filter = frame(start, end)

        start, end = get_datetime_index(
            self.data, filter, s_key="open", e_key="lag_end"
        )
        data = self.data.iloc[start:end]
        return data

    def get_lagtime(self, data):
        lagtime_idx = data["CH4"].idxmax()
        lagtime_idx = self.find_negative_lagtime(data, lagtime_idx)
        self.lagtime_index = lagtime_idx
        self.lagtime_s = (self.lagtime_index - self.open).total_seconds()
        if self.adjusted_close is None:
            self.adjusted_close = self.close + pd.Timedelta(seconds=self.lagtime_s)

    def find_negative_lagtime(self, data, lagtime_idx):
        i = 0
        open = self.open
        while (lagtime_idx - open).total_seconds() == 0 and i < 5:
            i += 1
            ten_s = pd.Timedelta(seconds=10)
            data = self.get_lag_df(open - ten_s, self.lag_end)
            lagtime_idx = data["CH4"].idxmax()
            open = open - ten_s
        return lagtime_idx

    def push_lagtimes(self, ifdb_dict):
        pass

    def get_r(self):
        self.r = calculate_pearsons_r(
            self.calc_data.index.view(int), self.calc_data["CH4"]
        )
