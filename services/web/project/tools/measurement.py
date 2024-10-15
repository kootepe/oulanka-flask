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
        self.og_close_offset = 240
        self.og_open_offset = 720
        self.close_offset = 240
        self.open_offset = 720
        # self.og_start = start.tz_localize("Europe/Helsinki").tz_convert("UTC")
        self.start = start.tz_localize("Europe/Helsinki").tz_convert("UTC")
        self.og_open = self.start + pd.Timedelta(seconds=self.open_offset)
        self.og_close = self.start + pd.Timedelta(seconds=self.close_offset)
        self.end = end.tz_localize("Europe/Helsinki").tz_convert("UTC")
        self.lag_end = self.open + pd.Timedelta(seconds=120)
        self.data = data
        self.calc_data = None
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

    @property
    def lagtime_index(self):
        return self.get_lag_idx()

    def close_t(self):
        return (
            self.start
            + pd.Timedelta(seconds=self.og_close_offset)
            + pd.Timedelta(seconds=self.lagtime_s)
        )

    def open_t(self):
        return self.start + pd.Timedelta(seconds=self.open_offset)

    def get_lag_idx(self):
        return self.og_open + pd.Timedelta(seconds=self.lagtime_s)

    def del_lagtime(self):
        self.lagtime_s = 0
        self.open_offset = self.og_open_offset

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
            if (
                self.data["CH4"].is_monotonic_decreasing
                or self.data["CH4"].is_monotonic_increasing
            ):
                self.is_valid = False
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
        self.lagtime_s = 0
        self.open_offset = self.og_open_offset
        lagtime_idx = data["CH4"].idxmax()
        lagtime_idx = self.find_negative_lagtime(data, lagtime_idx)
        # if (lagtime_idx - open).total_seconds() == 119:
        if (lagtime_idx - self.open).total_seconds() >= 100:
            logger.debug("Max lagtime")
            lagtime_idx = self.find_negative_lagtime(data, lagtime_idx, 10)

        self.lagtime_s = (lagtime_idx - self.og_open).total_seconds()
        logger.debug(f"lag seconds: {self.lagtime_s}")

    def find_negative_lagtime(self, data, lagtime_idx, back=0):
        i = 0
        open = self.og_open
        lag_end = self.lag_end
        back = pd.Timedelta(seconds=back)
        lag = (lagtime_idx - open).total_seconds()
        while (lag == 0 and i < 12) or (lag > 130 and i < 10):
            i += 1
            ten_s = pd.Timedelta(seconds=10) + back
            start = open - ten_s
            end = lag_end - ten_s
            logger.debug(f"Find between {start} {end} ")
            data = self.get_lag_df(start, end).copy()
            lagtime_idx = data["CH4"].idxmax()
            open = open - ten_s
            lag_end = lag_end - ten_s

        return lagtime_idx

    def push_lagtimes(self, ifdb_dict):
        pass

    def get_r(self):
        self.r = calculate_pearsons_r(
            self.calc_data.index.view(int), self.calc_data["CH4"]
        )
