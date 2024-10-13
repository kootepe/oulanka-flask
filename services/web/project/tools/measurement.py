import pandas as pd
from collections import namedtuple
from project.tools.influxdb_funcs import just_read, read_ifdb
from project.tools.gas_funcs import calculate_pearsons_r
from project.tools.filter import get_datetime_index
import logging

logger = logging.getLogger("defaultLogger")


class MeasurementCycle:
    def __init__(self, id, start, close, open, end, data=None):
        self.id = id
        self.close_offset = 240
        self.open_offset = 720
        self.og_close = close
        self.og_start = start
        self.start = start.tz_localize("Europe/Helsinki").tz_convert("UTC")
        self.end = end.tz_localize("Europe/Helsinki").tz_convert("UTC")
        self.lag_end = self.open + pd.Timedelta(seconds=120)
        self.data = data
        self.calc_data = None
        self.lagtime_index = None
        self.lagtime_s = 0
        self.is_valid = True
        self.no_data_in_db = False
        self.has_errors = False
        self.adjusted_time = False
        self.manual_valid = None

    @property
    def close(self):
        return self.close_t()

    @property
    def open(self):
        return self.open_t()

    def close_t(self):
        return (
            self.start
            + pd.Timedelta(seconds=self.close_offset)
            + pd.Timedelta(seconds=self.lagtime_s)
        )

    def open_t(self):
        return self.start + pd.Timedelta(seconds=self.open_offset)

    def del_lagtime(self):
        self.lagtime_index = None

    def just_get_data(self, ifdb_dict, client):
        if self.data is None:
            # tz = "Europe/Helsinki"
            meas_dict = {"measurement": "AC LICOR", "fields": "CH4,CO2,DIAG"}
            self.data = just_read(
                ifdb_dict, meas_dict, client, start_ts=self.start, stop_ts=self.end
            )
            if self.data is None:
                self.is_valid = False
                self.no_data_in_db = True
                return
            if self.data.empty:
                self.is_valid = False
                return
            self.data.set_index("datetime", inplace=True)
            self.data.index = pd.to_datetime(self.data.index)
            start, end = get_datetime_index(
                self.data, self, s_key="close", e_key="open"
            )
            self.calc_data = self.data.iloc[start:end].copy()
            if self.calc_data["DIAG"].sum() != 0:
                self.has_errors = True
            self.get_max()

    def get_data(self, ifdb_dict):
        if self.data is None:
            meas_dict = {"measurement": "AC LICOR", "fields": "CH4,CO2,DIAG"}
            self.data = read_ifdb(
                ifdb_dict, meas_dict, start_ts=self.start, stop_ts=self.end
            )
            if self.data is None:
                self.is_valid = False
                self.no_data_in_db = True
                return
            if self.data.empty:
                self.is_valid = False
                return
            self.data.set_index("datetime", inplace=True)
            self.data.index = pd.to_datetime(self.data.index)
            start, end = get_datetime_index(
                self.data, self, s_key="close", e_key="open"
            )
            self.calc_data = self.data.iloc[start:end]
            if self.calc_data["DIAG"].sum() != 0:
                self.is_valid = False
            self.get_max()

    def get_max(self, ifdb_dict=None):
        data = None
        if self.data is None:
            self.get_data(ifdb_dict)
        if self.data is not None and not self.data.empty:
            start, end = get_datetime_index(
                self.data, self, s_key="open", e_key="lag_end"
            )
            data = self.data.iloc[start:end].copy()
        if data is None:
            self.is_valid = False
            # self.lagtime_index = None
            # self.lagtime_s = None
            # self.r = None
            return
        if data.empty:
            self.is_valid = False
            return
        self.get_r()
        if self.r < 0.6:
            self.is_valid = False
        self.get_lagtime(data)

    def get_lag_df(self, start, end):
        frame = namedtuple("filter", ["open", "lag_end"])
        filter = frame(start, end)

        start, end = get_datetime_index(
            self.data, filter, s_key="open", e_key="lag_end"
        )
        data = self.data.iloc[start:end].copy()
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
            data = self.get_lag_df(open - ten_s, self.lag_end).copy()
            lagtime_idx = data["CH4"].idxmax()
            open = open - ten_s
        return lagtime_idx

    def push_lagtimes(self, ifdb_dict):
        pass

    def get_r(self):
        self.r = calculate_pearsons_r(
            self.calc_data.index.view(int), self.calc_data["CH4"]
        )
