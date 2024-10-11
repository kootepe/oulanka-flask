import dash
from dash import Dash, dcc, html, Input, Output, State, ctx
import pandas as pd
import json
from datetime import datetime, timedelta

from project.tools.influxdb_funcs import read_ifdb
from project.tools.create_graph import create_plot
from project.tools.measurement import MeasurementCycle


def ac_plot(flask_app):
    with open("project/config.json", "r") as f:
        config = json.load(f)
        ifdb_dict = config["ifdb_dict"]

    meas_dict = {"measurement": "AC LICOR", "fields": "CH4,CO2"}

    with open("project/cycle.json", "r") as f:
        cycles = json.load(f)["CYCLE"]

    def generate_week():
        today = datetime.today()
        return [(today - timedelta(days=i)).date() for i in range(7)][::-1]

    # Preprocess measurements and cycle data
    all_measurements = []
    week = generate_week()
    for day in week:
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

    app.layout = html.Div(
        [
            dcc.Store(id="stored-index", data=0),
            dcc.Store(id="stored-chamber", data="All"),
            html.Div(id="chamber-buttons"),
            html.Div(id="measurement-info", style={"padding": "20px 0"}),
            html.Button("Previous", id="prev-button", n_clicks=0),
            html.Button("Next", id="next-button", n_clicks=0),
            html.Div(
                [
                    html.Button("Find lagtime", id="find-max", n_clicks=0),
                    html.Button("Delete lagtime", id="del-lagtime", n_clicks=0),
                ]
            ),
            dcc.Graph(id="ch4-graph"),
            dcc.Graph(id="co2-graph"),
            html.Div(id="output"),
        ]
    )

    @app.callback(
        Output("chamber-buttons", "children"),
        Input("output", "children"),
    )
    def generate_buttons(_):
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
        measurement.data = read_ifdb(
            ifdb_dict, meas_dict, start_ts=measurement.start, stop_ts=measurement.end
        )
        measurement.data.set_index("datetime", inplace=True)
        measurement.data.index = pd.to_datetime(measurement.data.index)
        measurement.data = measurement.data.tz_localize(tz)

        if triggered_id == "find-max":
            measurement.find_max("CH4")
        if triggered_id == "del-lagtime":
            measurement.remove_lagtime()

        fig_ch4 = create_plot(measurement, "CH4", "Methane")
        fig_co2 = create_plot(measurement, "CO2", "Carbon Dioxide", color_key="green")
        measurement_info = f"Measurement {index + 1}/{len(chamber_measurements)} - Date: {measurement.start.date()}"

        return fig_ch4, fig_co2, measurement_info, index, chamber

    return app
