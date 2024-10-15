import dash
from dash import Dash, dcc, html, Input, Output, State, ctx
import pandas as pd
import json
from datetime import datetime, timedelta
from plotly.graph_objs import Figure
from pprint import pprint
import logging
import plotly.graph_objs as go

from project.ac_layout import create_layout
from project.tools.logger import init_logger
from project.tools.measurement import MeasurementCycle
from project.tools.influxdb_funcs import init_client, ifdb_push
from project.tools.create_graph import mk_gas_plot, mk_lag_plot

lag_graph_dir = False

logger = logging.getLogger("defaultLogger")


def ac_plot(flask_app):
    logger = init_logger()
    ifdb_read_dict, ifdb_push_dict = load_config()
    cycles = load_cycles()

    # Generate measurement cycle
    month = generate_month()
    all_measurements = generate_measurements(month, cycles)
    cycle_dict = organize_measurements_by_chamber(all_measurements)

    # Initialize Dash app
    app = Dash(__name__, server=flask_app, url_base_pathname="/dashing/")
    app.layout = create_layout(all_measurements[0])

    @app.callback(Output("chamber-buttons", "children"), Input("output", "children"))
    def generate_buttons(_):
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
        Output("ch4-plot", "figure"),
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
        Input("find-lag", "n_clicks"),
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
        Input("reset-cycle", "n_clicks"),
        Input("reset-index", "n_clicks"),
        Input("max-r", "n_clicks"),
    )
    def update_graph(*args):
        triggered_id, index, measurements, measurement, selected_chambers = (
            handle_triggers(args, cycle_dict, logger)
        )

        if not measurements:
            return no_data_response(selected_chambers)

        slider_vals = update_slider(args[12], measurement, triggered_id)
        load_measurement_data(measurement, ifdb_read_dict)

        execute_actions(
            triggered_id, measurement, measurements, ifdb_read_dict, ifdb_push_dict
        )

        fig_ch4, fig_co2 = create_ch4_co2_plots(measurement)
        lag_graph = create_lag_graph(
            measurements,
            measurement,
            ifdb_push_dict,
            selected_chambers,
            index,
            triggered_id,
        )
        lag_graph = apply_lag_graph_zoom(lag_graph, args[0])

        measurement_info = generate_measurement_info(measurement, index, measurements)

        return (
            fig_ch4,
            fig_co2,
            lag_graph,
            measurement_info,
            index,
            selected_chambers,
            slider_vals,
        )

    return app


def load_config():
    with open("project/config.json", "r") as f:
        config = json.load(f)
    return config["ifdb_read_dict"], config["ifdb_push_dict"]


def load_cycles():
    with open("project/cycle.json", "r") as f:
        return json.load(f)["CYCLE"]


def generate_month():
    today = datetime.today()
    return [(today - timedelta(days=i)).date() for i in range(70)][::-1]


def generate_measurements(month, cycles):
    all_measurements = []
    for day in month:
        for cycle in cycles:
            if pd.Timestamp(f"{day} {cycle.get('START')}") > datetime.now():
                continue
            s, c, o, e = (
                pd.Timestamp(f"{day} {cycle.get(time)}")
                for time in ["START", "CLOSE", "OPEN", "END"]
            )
            all_measurements.append(MeasurementCycle(cycle["CHAMBER"], s, c, o, e))
    return all_measurements


def organize_measurements_by_chamber(all_measurements):
    cycle_dict = {}
    for mes in all_measurements:
        cycle_dict.setdefault(mes.id, []).append(mes)
    return cycle_dict


def handle_triggers(args, cycle_dict, logger):
    logger.debug("Running.")
    (
        lag_state,
        _,
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
        reset_cycle,
        reset_index,
        max_r,
    ) = args
    triggered_id = ctx.triggered_id if ctx.triggered else None
    selected_chambers = selected_chambers or list(cycle_dict.keys())

    measurements = sorted(
        [
            measurement
            for chamber in selected_chambers
            for measurement in cycle_dict.get(chamber, [])
        ],
        key=lambda x: x.open,
    )

    if triggered_id == "prev-button":
        index = decrement_index(index, measurements)
    elif triggered_id == "next-button":
        index = increment_index(index, measurements)
    elif triggered_id == "lag-graph" and get_point:
        logger.debug(get_point)
        index = get_point.get("points")[0].get("customdata")[2]
    elif triggered_id == "reset-index":
        index = 0
    elif triggered_id == "chamber-select":
        index = 0

    measurement = measurements[index] if measurements else None
    return triggered_id, index, measurements, measurement, selected_chambers


def no_data_response(selected_chambers):
    return Figure(), Figure(), Figure(), "No data available", 0, selected_chambers


def update_slider(ch4_slider_values, measurement, triggered_id):
    close, open = ch4_slider_values
    if triggered_id == "reset-cycle":
        measurement.close_offset = measurement.og_close_offset
        measurement.open_offset = measurement.og_open_offset
    if triggered_id != "ch4-slide":
        close, open = measurement.close_offset, measurement.open_offset
    if triggered_id == "ch4-slide":
        measurement.close_offset = close
        measurement.open_offset = open
    if triggered_id == "del-lagtime":
        close = measurement.og_close_offset
    return [close, open]


def load_measurement_data(measurement, ifdb_read_dict):
    if measurement.data is None and measurement.is_valid:
        measurement.get_data(ifdb_read_dict)


def execute_actions(
    triggered_id, measurement, measurements, ifdb_read_dict, ifdb_push_dict
):
    if triggered_id == "find-lag":
        measurement.get_max()
    if triggered_id == "del-lagtime":
        measurement.del_lagtime()
    if triggered_id == "max-r":
        measurement.get_max_r()
    if triggered_id == "push-all":
        push_all_data(ifdb_read_dict, ifdb_push_dict, measurements)
    if triggered_id == "push-lag":
        push_one_lag(ifdb_push_dict, measurement)
    if triggered_id == "mark-invalid":
        measurement.manual_valid = False
    if triggered_id == "mark-valid":
        measurement.manual_valid = True
    if triggered_id == "reset-cycle":
        measurement.lagtimes_s = 0


def create_ch4_co2_plots(measurement):
    fig_ch4, fig_co2 = Figure(), Figure()
    if measurement.data is not None:
        fig_ch4 = mk_gas_plot(measurement, "CH4")
        fig_co2 = mk_gas_plot(measurement, "CO2", color_key="green")
    return fig_ch4, fig_co2


def create_lag_graph(
    measurements, measurementos, ifdb_push_dict, selected_chambers, index, triggered_id
):
    global lag_graph_dir
    print(triggered_id)
    if lag_graph_dir is False or triggered_id == "chamber-select":
        lag_graph = mk_lag_plot(
            measurements, measurementos, ifdb_push_dict, selected_chambers, index
        )
    elif lag_graph_dir is not False:
        logger.debug("Recreating highlight")
        highlighter = apply_lag_highlighter(measurementos)
        updated_fig_data = lag_graph_dir["data"]
        # logger.debug(updated_fig_data[0])
        traces = list(updated_fig_data[:-1])
        highlighter = [highlighter]
        return go.Figure(traces + highlighter, lag_graph_dir.layout)
    lag_graph_dir = lag_graph
    return lag_graph


def apply_lag_highlighter(current_measurement):
    logger.debug("Creating highlighter")
    data2 = [
        (
            current_measurement.close,
            current_measurement.lagtime_s,
            current_measurement.id,
        )
    ]
    df2 = pd.DataFrame(data2, columns=["close", "lagtime", "id"]).set_index("close")
    logger.debug(df2)
    highlighter = go.Scatter(
        x=df2.index,
        y=df2["lagtime"],
        mode="markers",
        marker=dict(
            symbol="circle",
            size=15,
            color="rgba(255,0,0,0)",
            line=dict(color="rgba(255,0,0,1)", width=2),
        ),
        name="Current",
        hoverinfo="none",
        showlegend=True,
    )
    return highlighter


def apply_lag_graph_zoom(lag_graph, lag_state_dict):
    lag_graph_layout = lag_graph_zoom(lag_state_dict)
    if lag_graph_layout:
        lag_graph.update_layout(lag_graph_layout)
    return lag_graph


def lag_graph_zoom(lag_state_dict):
    layout = {"xaxis": {"range": None}, "yaxis": {"range": None}}
    if lag_state_dict and "xaxis.range[0]" in lag_state_dict:
        layout["xaxis"]["range"] = [
            lag_state_dict["xaxis.range[0]"],
            lag_state_dict["xaxis.range[1]"],
        ]
    if lag_state_dict and "yaxis.range[0]" in lag_state_dict:
        layout["yaxis"]["range"] = [
            lag_state_dict["yaxis.range[0]"],
            lag_state_dict["yaxis.range[1]"],
        ]
    return layout


def push_all_data(read_dict, push_dict, measurements):
    tag_cols = ["chamber"]
    with init_client(read_dict) as client:
        for m in measurements:
            m.just_get_data(read_dict, client)
    data = [(m.close, m.lagtime_s, int(m.id), int(m.id)) for m in measurements]
    df = pd.DataFrame(data, columns=["close", "lagtime", "id", "chamber"]).set_index(
        "close"
    )
    with init_client(push_dict) as client:
        ifdb_push(df, client, push_dict, tag_cols)


def push_one_lag(ifdb_dict, measurement):
    tag_cols = ["chamber"]
    data = [
        (
            measurement.og_close,
            measurement.lagtime_s,
            int(measurement.id),
            int(measurement.id),
        )
    ]
    df = pd.DataFrame(data, columns=["close", "lagtime", "id", "chamber"]).set_index(
        "close"
    )
    logger.debug(data)
    with init_client(ifdb_dict) as client:
        ifdb_push(df, client, ifdb_dict, tag_cols)


def decrement_index(index, measurements):
    return (index - 1) % len(measurements)


def increment_index(index, measurements):
    return (index + 1) % len(measurements)


def generate_measurement_info(measurement, index, measurements):
    valid_str = "Valid: True" if measurement.is_valid else "Valid: False"
    return f"Measurement {index + 1}/{len(measurements)} - Date: {measurement.start.date()} {valid_str}"
