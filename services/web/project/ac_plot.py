import dash
from dash import Dash, dcc, html, Input, Output, State, ctx
import pandas as pd
import json
from datetime import datetime, timedelta

from project.ac_layout import create_layout
from project.tools.create_graph import create_plot, mk_lag_graph
from project.tools.measurement import MeasurementCycle
from project.tools.logger import init_logger


def ac_plot(flask_app):
    logger = init_logger()
    with open("project/config.json", "r") as f:
        config = json.load(f)
        ifdb_dict = config["ifdb_dict"]

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
        buttons : [html.Button, ...]
            list of html.Button labeled with chamber IDs



        """
        buttons = [
            html.Button(
                "All",
                id={"type": "dynamic-button", "index": "All"},
                n_clicks=0,
                style={"width": "50px", "height": "25px"},
            )
        ]
        buttons += [
            html.Button(
                chamber,
                id={"type": "dynamic-button", "index": chamber},
                n_clicks=0,
                style={"width": "50px", "height": "25px"},
            )
            for chamber in cycle_dict.keys()
        ]
        return buttons

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
        [Input({"type": "dynamic-button", "index": dash.dependencies.ALL}, "n_clicks")],
        State("stored-index", "data"),
        State("stored-chamber", "data"),
    )
    def update_graph(
        prev_clicks, next_clicks, find_max, del_lagtime, cham_n_clicks, index, chamber
    ):
        tz = "Europe/Helsinki"
        chamber_measurements = (
            all_measurements if chamber == "All" else cycle_dict[chamber]
        )
        if not ctx.triggered:
            # Handle the case when no button is triggered
            index = 0  # Reset index or any default value you'd like to set
            chamber = "All"  # Set a default chamber or any default value
            chamber_measurements = all_measurements  # Default to all measurements
            triggered_id = None
        # Safeguard to check for triggered input
        else:
            # Directly access ctx.triggered_id as a dictionary
            triggered_id = ctx.triggered_id
            if triggered_id == "prev-button":
                index = (index - 1) % len(chamber_measurements)
            elif triggered_id == "next-button":
                index = (index + 1) % len(chamber_measurements)
            elif triggered_id == "find-max" or triggered_id == "del-lagtime":
                pass  # Additional logic for find-max button can be placed here
            elif triggered_id.get("type") == "dynamic-button":
                chamber = triggered_id["index"]
                chamber_measurements = (
                    all_measurements if chamber == "All" else cycle_dict[chamber]
                )
                index = 0

        # Retrieve the current measurement based on the updated index
        measurement = chamber_measurements[index]

        # Ensure measurement data is loaded
        if measurement.data is None:
            measurement.get_data(ifdb_dict)
            # measurement.data.set_index("datetime", inplace=True)
            # measurement.data.index = pd.to_datetime(measurement.data.index)
            # measurement.data = measurement.data.tz_localize(tz)

        if triggered_id == "find-max":
            measurement.find_max("CH4")
        if triggered_id == "del-lagtime":
            measurement.del_lagtime()

        if not measurement.no_data_in_db:
            fig_ch4 = create_plot(measurement, "CH4", "Methane")
            fig_co2 = create_plot(
                measurement, "CO2", "Carbon Dioxide", color_key="green"
            )
        lag_graph = mk_lag_graph(chamber_measurements, [measurement], ifdb_dict)
        # lag_graph = None
        measurement_info = f"Measurement {index + 1}/{len(chamber_measurements)} - Date: {measurement.start.date()}"

        return fig_ch4, fig_co2, lag_graph, measurement_info, index, chamber

    return app
