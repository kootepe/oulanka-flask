import dash
from dash import Dash, dcc, html, Input, Output, State, ctx
import pandas as pd
import json
from datetime import datetime, timedelta
from plotly.graph_objs import Figure

from project.ac_layout import create_layout
from project.tools.create_graph import create_plot, mk_lag_graph
from project.tools.measurement import MeasurementCycle
from project.tools.logger import init_logger


def ac_plot(flask_app):
    logger = init_logger()
    with open("project/config.json", "r") as f:
        config = json.load(f)
        ifdb_read_dict = config["ifdb_read_dict"]
        ifdb_push_dict = config["ifdb_push_dict"]

    with open("project/cycle.json", "r") as f:
        cycles = json.load(f)["CYCLE"]

    def generate_year():
        today = datetime.today()
        return [(today - timedelta(days=i)).date() for i in range(365)][::-1]

    def generate_month():
        today = datetime.today()
        return [(today - timedelta(days=i)).date() for i in range(60)][::-1]

    def generate_week():
        today = datetime.today()
        return [(today - timedelta(days=i)).date() for i in range(7)][::-1]

    def generate_day():
        today = datetime.today()
        return [(today - timedelta(days=i)).date() for i in range(1)][::-1]

    # Generate measurement cycle
    all_measurements = []
    hours = generate_day()
    week = generate_week()
    month = generate_month()
    year = generate_year()
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
    for measurement in all_measurements:
        cycle_dict.setdefault(measurement.id, []).append(measurement)

    # Initialize Dash app
    app = Dash(__name__, server=flask_app, url_base_pathname="/dashing/")
    app.layout = create_layout()

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
        Input("prev-button", "n_clicks"),
        Input("next-button", "n_clicks"),
        Input("find-max", "n_clicks"),
        Input("del-lagtime", "n_clicks"),
        Input("chamber-select", "value"),
        State("stored-index", "data"),
        State("stored-chamber", "data"),
        [Input("lag-graph", "clickData")],
        Input("skip-invalid", "value"),
    )
    def update_graph(
        prev_clicks,
        next_clicks,
        find_max,
        del_lagtime,
        selected_chambers,
        index,
        chamber,
        lag_graph,
        skip_invalid,
    ):
        if not selected_chambers:
            selected_chambers = cycle_dict.keys()
        chamber_measurements = sorted(
            [
                measurement
                for chamber in selected_chambers
                for measurement in cycle_dict.get(chamber, [])
            ],
            key=lambda x: x.open,
        )
        if not chamber_measurements:
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
            index = 0  # Reset index or any default value you'd like to set
            triggered_id = None
        # Safeguard to check for triggered input
        else:
            # Directly access ctx.triggered_id as a dictionary
            triggered_id = ctx.triggered_id
            if triggered_id == "lag-graph":
                pt = lag_graph.get("points")[0]
                index = pt.get("customdata")[2]
            elif triggered_id == "chamber-select":
                index = 0
            elif triggered_id == "prev-button":
                index = decrement_index(index, chamber_measurements)
            elif triggered_id == "next-button":
                index = increment_index(index, chamber_measurements)
            elif (
                triggered_id == "find-max"
                or triggered_id == "del-lagtime"
                or triggered_id == "skip-invalid"
            ):
                pass  # Additional logic for find-max button can be placed here

        # Retrieve the current measurement based on the updated index
        measurement = chamber_measurements[index]

        if skip_invalid and triggered_id == "chamber-select":
            while measurement.is_valid is False:
                index = increment_index(index, chamber_measurements)
                measurement = chamber_measurements[index]

        if skip_invalid and triggered_id == "next-button":
            while measurement.is_valid is False:
                index = increment_index(index, chamber_measurements)
                measurement = chamber_measurements[index]

        if skip_invalid and triggered_id == "prev-button":
            while measurement.is_valid is False:
                index = decrement_index(index, chamber_measurements)
                measurement = chamber_measurements[index]
        measurement = chamber_measurements[index]

        # Ensure measurement data is loaded
        if measurement.data is None and measurement.is_valid is True:
            measurement.get_data(ifdb_read_dict)

        if triggered_id == "find-max":
            measurement.find_max("CH4")
        if triggered_id == "del-lagtime":
            measurement.del_lagtime()

        fig_ch4 = Figure()
        fig_co2 = Figure()
        if measurement.is_valid is True:
            fig_ch4 = create_plot(measurement, "CH4")
            fig_co2 = create_plot(measurement, "CO2", color_key="green")

        lag_graph = mk_lag_graph(chamber_measurements, [measurement], ifdb_read_dict)
        measurement_info = f"Measurement {index + 1}/{len(chamber_measurements)} - Date: {measurement.start.date()}"

        return fig_ch4, fig_co2, lag_graph, measurement_info, index, chamber

    def decrement_index(index, measurements):
        return (index - 1) % len(measurements)

    def increment_index(index, measurements):
        return (index + 1) % len(measurements)

    return app
