import dash
from dash import Dash, dcc, html, Input, Output, State, ctx
import pandas as pd
import json
from datetime import datetime, timedelta
from plotly.graph_objs import Figure
from pprint import pprint

from project.ac_layout import create_layout
from project.tools.logger import init_logger
from project.tools.measurement import MeasurementCycle
from project.tools.influxdb_funcs import init_client, ifdb_push
from project.tools.create_graph import create_plot, mk_lag_graph, mk_lag_graph_old


def ac_plot(flask_app):
    logger = init_logger()
    with open("project/config.json", "r") as f:
        config = json.load(f)
        ifdb_read_dict = config["ifdb_read_dict"]
        ifdb_push_dict = config["ifdb_push_dict"]

    with open("project/cycle.json", "r") as f:
        cycles = json.load(f)["CYCLE"]

    def generate_month():
        today = datetime.today()
        return [(today - timedelta(days=i)).date() for i in range(60)][::-1]

    # Generate measurement cycle
    all_measurements = []
    month = generate_month()
    for day in month:
        for cycle in cycles:
            if pd.Timestamp(f"{day} {cycle.get('START')}") > datetime.now():
                continue
            s, c, o, e = (
                pd.Timestamp(f"{day} {cycle.get(time)}")
                for time in ["START", "CLOSE", "OPEN", "END"]
            )
            all_measurements.append(MeasurementCycle(cycle["CHAMBER"], s, c, o, e))

    # Organize measurements by chamber ID
    cycle_dict = {}
    for mes in all_measurements:
        cycle_dict.setdefault(mes.id, []).append(mes)

    # Initialize Dash app
    app = Dash(__name__, server=flask_app, url_base_pathname="/dashing/")
    app.layout = create_layout(all_measurements[0])

    @app.callback(
        Output("chamber-buttons", "children"),
        Input("output", "children"),
    )
    def generate_buttons(_):
        """
        Generate a button for each chamber.

        Parameters
        ----------
        _ :


        Returns
        -------
        buttons : list of dcc.Checklist or html.Button for multi-selection


        """
        # Use Checklist for multi-select functionality
        options = [
            {"label": chamber, "value": chamber} for chamber in cycle_dict.keys()
        ]
        return dcc.Checklist(
            id="chamber-select",
            options=options,
            value=[],  # Default no selections
            inline=True,
        )

    @app.callback(
        Output("ch4-graph", "figure"),
        Output("co2-graph", "figure"),
        Output("lag-graph", "figure"),
        Output("measurement-info", "children"),
        Output("stored-index", "data"),
        Output("stored-chamber", "data"),
        Output("ch4-slide", "value"),
        State("lag-graph", "relayoutData"),
        State("lag-graph", "figure"),
        Input("prev-button", "n_clicks"),
        Input("next-button", "n_clicks"),
        Input("find-max", "n_clicks"),
        Input("del-lagtime", "n_clicks"),
        Input("push-all", "n_clicks"),
        Input("push-lag", "n_clicks"),
        Input("chamber-select", "value"),
        State("stored-index", "data"),
        State("stored-chamber", "data"),
        [Input("lag-graph", "clickData")],
        Input("ch4-slide", "value"),
        Input("co2-slide", "value"),
        Input("mark-invalid", "n_clicks"),
        Input("mark-valid", "n_clicks"),
    )
    def update_graph(
        lag_state,
        lag_graph_data,
        prev_clicks,
        next_clicks,
        find_max,
        del_lagtime,
        push_all,
        push_one,
        selected_chambers,
        index,
        chamber,
        get_point,
        ch4_slider_values,
        co2_slider_values,
        mark_invalid,
        mark_valid,
    ):
        logger.debug("Running.")
        if not selected_chambers:
            selected_chambers = cycle_dict.keys()
        measurements = sorted(
            [
                measurement
                for chamber in selected_chambers
                for measurement in cycle_dict.get(chamber, [])
            ],
            key=lambda x: x.open,
        )
        pt = None
        if not measurements:
            return (
                Figure(),
                Figure(),
                Figure(),
                "No data available",
                0,
                selected_chambers,
            )

        if not ctx.triggered:
            # Handle the case when no button is triggered
            triggered_id = None
        # Safeguard to check for triggered input
        else:
            triggered_id = ctx.triggered_id if ctx.triggered else None
            if triggered_id == "lag-graph":
                pt = get_point.get("points")[0]
                index = pt.get("customdata")[2]
                y_value = pt["y"]

            elif triggered_id == "chamber-select":
                index = 0

            elif triggered_id == "prev-button":
                index = decrement_index(index, measurements)

            elif triggered_id == "next-button":
                index = increment_index(index, measurements)

        # current measurement is the current index
        measurement = measurements[index]

        slider_vals = update_slider(ch4_slider_values, measurement, triggered_id)

        # Ensure measurement data is loaded
        if measurement.data is None and measurement.is_valid is True:
            measurement.get_data(ifdb_read_dict)

        if triggered_id == "find-max":
            measurement.get_max()
        if triggered_id == "del-lagtime":
            measurement.del_lagtime()
        if triggered_id == "push-all":
            push_all_data(ifdb_read_dict, ifdb_push_dict, measurements)
        if triggered_id == "push-lag":
            push_one_lag(ifdb_push_dict, measurement)
        if triggered_id == "mark-invalid":
            measurement.manual_valid = False
        if triggered_id == "mark-valid":
            measurement.manual_valid = True

        fig_ch4 = Figure()
        fig_co2 = Figure()
        if measurement.data is not None:
            fig_ch4 = create_plot(measurement, "CH4")
            fig_co2 = create_plot(measurement, "CO2", color_key="green")

        lag_graph = mk_lag_graph(
            measurements, measurement, ifdb_push_dict, selected_chambers, index
        )
        # # lag_graph = mk_lag_graph_old(measurements, [measurement], ifdb_read_dict)
        if lag_graph_zoom(lag_state):
            lag_graph.update_layout(lag_graph_zoom(lag_state))

        if triggered_id == "lag-graph" and get_point:
            lag_graph.data[1].update(x=[pt["x"]], y=[y_value])

        logger.debug(f"lag_state:\n{lag_state}")

        min_val = measurement.start.value
        max_val = measurement.end.value
        value = [measurement.open.value, measurement.close.value]
        marks = {
            int(measurement.data.index[i].value): measurement.data.index[i].strftime("")
            for i in range(0, len(measurement.data.index), 1)
        }

        if measurement.is_valid is True:
            valid_str = "Valid: True"
        else:
            valid_str = "Valid: False"
        measurement_info = f"Measurement {index + 1}/{len(measurements)} - Date: {measurement.start.date()} {valid_str}"

        return (
            fig_ch4,
            fig_co2,
            lag_graph,
            measurement_info,
            index,
            chamber,
            slider_vals,
        )

    def update_slider(ch4_slider_values, measurement, triggered_id):
        logger.debug("Running.")
        close, open = ch4_slider_values
        if triggered_id != "ch4-slide":
            close, open = measurement.close_offset, measurement.open_offset
        if triggered_id == "ch4-slide":
            measurement.close_offset = close
            measurement.open_offset = open

        return [close, open]

    def lag_graph_zoom(lag_state_dict):
        lag_graph_layout = {"xaxis": {"range": None}, "yaxis": {"range": None}}
        if lag_state_dict is None:
            lag_graph_layout = None
            pass
        elif "autosize" in lag_state_dict.keys():
            lag_graph_layout = None
            pass
        else:
            if "xaxis.range[0]" in lag_state_dict:
                lag_graph_layout["xaxis"]["range"] = [
                    lag_state_dict["xaxis.range[0]"],
                    lag_state_dict["xaxis.range[1]"],
                ]
            if "yaxis.range[0]" in lag_state_dict:
                lag_graph_layout["yaxis"]["range"] = [
                    lag_state_dict["yaxis.range[0]"],
                    lag_state_dict["yaxis.range[1]"],
                ]
        return lag_graph_layout

    def push_all_data(read_dict, push_dict, measurements):
        tag_cols = ["chamber"]
        with init_client(ifdb_read_dict) as client:
            [m.just_get_data(read_dict, client) for m in measurements]
        data = [(m.close, m.lagtime_s, int(m.id), int(m.id)) for m in measurements]
        df = pd.DataFrame(
            data, columns=["close", "lagtime", "id", "chamber"]
        ).set_index("close")
        print(df["lagtime"].isnull().sum())

        with init_client(push_dict) as client:
            ifdb_push(df, client, push_dict, tag_cols)

    def push_one_lag(ifdb_dict, measurement):
        tag_cols = ["id"]
        data = [
            (
                measurement.og_close,
                measurement.lagtime_s,
                int(measurement.id),
                int(measurement.id),
            )
        ]
        df = pd.DataFrame(
            data, columns=["close", "lagtime", "id", "chamber"]
        ).set_index("close")

        with init_client(ifdb_dict) as client:
            ifdb_push(df, client, ifdb_dict, tag_cols)

    def decrement_index(index, measurements):
        return (index - 1) % len(measurements)

    def increment_index(index, measurements):
        return (index + 1) % len(measurements)

    return app
