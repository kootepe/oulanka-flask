#!/usr/bin/env python3

import influxdb_client as ifdb
from influxdb_client.client.write_api import SYNCHRONOUS
import logging
import pandas as pd
import numpy as np
from urllib3.exceptions import NewConnectionError
from project.tools.time_funcs import (
    convert_timestamp_format,
)

logger = logging.getLogger("defaultLogger")


def init_client(ifdb_dict):
    url = ifdb_dict.get("url")
    token = ifdb_dict.get("token")
    org = ifdb_dict.get("organization")
    timeout = ifdb_dict.get("timeout")

    client = ifdb.InfluxDBClient(url=url, token=token, org=org, timeout=timeout)
    return client


def mk_field_q(field_list):
    q = f'\t|> filter(fn: (r) => r["_field"] == "{field_list[0]}"'
    for f in field_list[1:]:
        q += f' or r["_field"] == "{f}"'
    q += ")\n"
    return q


def mk_bucket_q(bucket):
    return f'from(bucket: "{bucket}")\n'


def mk_range_q(start, stop):
    return f"\t|> range(start: {start}, stop: {stop})\n"


def mk_meas_q(measurement):
    return f'\t|> filter(fn: (r) => r["_measurement"] == "{measurement}")\n'


def mk_query(bucket, start, stop, measurement, fields, array_filter=None):
    if array_filter:
        # arr = array_filter["arr"]
        arr = str(array_filter["arr"]).replace("'", '"')
        tag = array_filter["tag"]

        query = (
            f"arr = {arr}\n"
            f"{mk_bucket_q(bucket)}"
            f"{mk_range_q(start, stop)}"
            f"{mk_meas_q(measurement)}"
            f"{mk_field_q(fields)}"
            f'\t|> filter(fn: (r) => contains(value: r["{tag}"], set: arr))\n'
            '\t|> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
        )
        pass
    else:
        query = (
            f"{mk_bucket_q(bucket)}"
            f"{mk_range_q(start, stop)}"
            f"{mk_meas_q(measurement)}"
            f"{mk_field_q(fields)}"
            '\t|> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
        )

    return query


def mk_oldest_ts_q(bucket, measurement, fields):
    query = (
        f"{mk_bucket_q(bucket)}"
        f"{mk_range_q(0, 'now()')}"
        f"{mk_meas_q(measurement)}"
        f"{mk_field_q(fields)}"
        '\t|> first(column: "_time")\n'
        '\t|> yield(name: "first")'
    )
    return query


def mk_newest_ts_q(bucket, measurement, fields):
    query = (
        f"{mk_bucket_q(bucket)}"
        f"{mk_range_q(0, 'now()')}"
        f"{mk_meas_q(measurement)}"
        f"{mk_field_q(fields)}"
        '|> last(column: "_time")\n'
        '|> yield(name: "last")'
    )
    return query


def mk_ifdb_ts(ts):
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def read_ifdb(ifdb_dict, meas_dict, start_ts=None, stop_ts=None, arr=None):
    bucket = ifdb_dict.get("bucket")
    measurement = meas_dict.get("measurement")
    fields = list(meas_dict.get("fields").split(","))
    logger.debug(f"Query from bucket:       {bucket}.")
    logger.debug(f"Query from Measurement:  {measurement}.")
    logger.debug(f"Query from:              {start_ts} to {stop_ts}.")

    if start_ts is not None:
        start = mk_ifdb_ts(start_ts)
    else:
        start = 0

    if stop_ts is not None:
        stop = mk_ifdb_ts(stop_ts)
    else:
        stop = "now()"

    with init_client(ifdb_dict) as client:
        q_api = client.query_api()
        query = mk_query(bucket, start, stop, measurement, fields, arr)
        # logger.debug(query)
        try:
            df = q_api.query_data_frame(query)[["_time"] + fields]
        except Exception:
            logger.info(f"No data with query:\n {query}")
            return None

        df = df.rename(columns={"_time": "datetime"})
        # logger.debug(df)
        if "DIAG" in df.columns:
            logger.debug(f"diagsum: {df['DIAG'].sum()}")
        return df


def just_read(ifdb_dict, meas_dict, client, start_ts=None, stop_ts=None, arr=None):
    logger.debug(f"Running query from {start_ts} to {stop_ts}")

    bucket = ifdb_dict.get("bucket")
    measurement = meas_dict.get("measurement")
    fields = list(meas_dict.get("fields").split(","))

    if start_ts is not None:
        start = mk_ifdb_ts(start_ts)
    else:
        start = 0

    if stop_ts is not None:
        stop = mk_ifdb_ts(stop_ts)
    else:
        stop = "now()"

    q_api = client.query_api()
    query = mk_query(bucket, start, stop, measurement, fields, arr)
    logger.debug(query)
    try:
        df = q_api.query_data_frame(query)[["_time"] + fields]
    except Exception as e:
        logger.debug(e)
        logger.info(f"No data with query:\n {query}")
        return None

    df = df.rename(columns={"_time": "datetime"})
    return df


def ifdb_push(df, client, ifdb_dict, tag_columns):
    """
    Push data to InfluxDB

    args:
    ---
    df -- pandas dataframe
        data to be pushed into influxdb

    returns:
    ---

    """
    logger.debug("Attempting push.")
    bucket = ifdb_dict.get("bucket")
    measurement_name = ifdb_dict.get("measurement")

    write_api = client.write_api(write_options=SYNCHRONOUS)
    dc = ifdb_dict
    print(f"Writing {dc.get('measurement')} to {dc.get('url')} {dc.get('bucket')}")
    print("data:")
    print(df.head())
    print(df.tail())
    print(df.tz_convert("Europe/Helsinki"))
    try:
        write_api.write(
            bucket=bucket,
            record=df,
            data_frame_measurement_name=measurement_name,
            # NOTE: figure out a good way of handling tag cols
            data_frame_tag_columns=tag_columns,
            debug=True,
        )
    except Exception as e:
        print(e)
        print("No pushing")
