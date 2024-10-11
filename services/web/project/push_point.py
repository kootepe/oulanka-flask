#!/usr/bin/env python3
import influxdb_client as ifdb
from influxdb_client.client.write_api import SYNCHRONOUS
import logging
from urllib3.exceptions import NewConnectionError


def ifdb_push(point_data, ifdb_dict):
    """
    Push data to InfluxDB

    args:
    ---
    df -- pandas dataframe
        data to be pushed into influxdb

    returns:
    ---

    """
    url = ifdb_dict.get("url")
    bucket = ifdb_dict.get("bucket")
    measurement_name = ifdb_dict.get("measurement_name")
    timezone = ifdb_dict.get("timezone")

    with init_client(ifdb_dict) as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        # log_point = ifdb.Point.from_dict(point_data)
        try:
            write_api.write(
                bucket=bucket,
                record=point_data,
                debug=True,
            )
        except NewConnectionError:
            print(f"Couldn't connect to database at {url}")
            pass

        logging.info("Pushed data between log item to DB")


def init_client(ifdb_dict):
    url = ifdb_dict.get("url")
    token = ifdb_dict.get("token")
    org = ifdb_dict.get("organization")
    timeout = ifdb_dict.get("timeout")

    client = ifdb.InfluxDBClient(url=url, token=token, org=org, timeout=timeout)
    return client
