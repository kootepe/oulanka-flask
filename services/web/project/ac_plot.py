import dash
from dash import Dash, dcc, html, Input, Output, State, ctx, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import pandas as pd
import json
from datetime import datetime, timedelta
from pprint import pprint
from dash.dependencies import Input, Output

from project.tools.influxdb_funcs import read_ifdb
from project.tools.filter import get_datetime_index

current_index = 0
current_chamber = None
current_button = "All"


class MeasurementCycle:
    def __init__(self, id, start, close, open, end, data=None):
        self.id = id
        self.start = start
        self.close = close
        self.open = open
        self.end = end
        self.data = data
        self.lagtime = None

    def find_max(self, gas):
        # mask = (self.data.index > self.open) & (
        #     self.data.index < (self.open + pd.Timedelta(minutes=2))
        # )
        print("asd")
        mask1 = self.data.index > self.open
        mask2 = self.data.index < (self.open + pd.Timedelta(minutes=2))
        data = self.data[mask1 & mask2]
        max = data[gas].idxmax()
        self.lagtime = max


def ac_plot(flask_app):
    # path = "/home/eerokos/code/python/for_torben/fluxObject/measurements.pkl"
    # with open(path, "rb") as f:
    #     measurements = dill.load(f)

    # measurements = [m for m in measurements if m.is_valid == 1]
    with open("project/config.json", "r") as f:
        config = json.load(f)
        ifdb_dict = config["ifdb_dict"]

    # ifdb_dict = {
    #     "url": "https://ota.oulu.fi:8086",
    #     # "token": "WhrsztYUFS71VjeVtIfbBDRqsTXNi0GWXM9sdYVcceDIQK1MrudEjav1TwGpHKCSWWiFaQeNl_76Sm8qX3AnJA::",
    #     # "token": "b2nqPhs0O5GotZAowvCEPsUkJecVeOH7t5UlT7arQ48kCEgq_NLvholxuZZfMUKZ2ilNwKQybisRHyR7tNliJQ==",
    #     "token": "Q5oMI2-_cN2K6WObtaV-9CGecZDKr-uT9ZGiJeQagC_MuMBbg7GqJldZiy6gUN3Tfr6DupP5gLNzFXVsH-wXmA==",
    #     "organization": "Oulangan TA",
    #     "bucket": "Testi",
    # }
    meas_dict = {"measurement": "AC LICOR", "fields": "CH4,CO2"}

    with open("project/cycle.json", "r") as f:
        cycles = json.load(f)
        cycles = cycles["CYCLE"]

    def generate_week():
        today = datetime.today()
        week = [(today - timedelta(days=i)).date() for i in range(7)][::-1]
        print(week)
        return week

    all_measurements = []
    tz = "UTC"
    tz = "Europe/Helsinki"
    now_utc = pd.Timestamp.now(tz="UTC")
    now = pd.Timestamp.now()

    week = generate_week()
    for day in week:
        for cycle in cycles:
            if pd.Timestamp(f"{day} {cycle.get('START')}") > now:
                continue
            s = pd.Timestamp(f"{day} {cycle.get('START')}")
            c = pd.Timestamp(f"{day} {cycle.get('CLOSE')}")
            o = pd.Timestamp(f"{day} {cycle.get('OPEN')}")
            e = pd.Timestamp(f"{day} {cycle.get('END')}")
            # s = pd.Timestamp(f"{day} {cycle.get('START')}").tz_localize(tz)
            # c = pd.Timestamp(f"{day} {cycle.get('CLOSE')}").tz_localize(tz)
            # o = pd.Timestamp(f"{day} {cycle.get('OPEN')}").tz_localize(tz)
            # e = pd.Timestamp(f"{day} {cycle.get('END')}").tz_localize(tz)
            id = cycle.get("CHAMBER")
            cycle = MeasurementCycle(id, s, c, o, e)
            all_measurements.append(cycle)

    cycle_dict = {}
    for measurement in all_measurements:
        id = measurement.id
        if id not in cycle_dict.keys():
            cycle_dict.update({id: [measurement]})
        else:
            cycle_dict[id] += [measurement]

    # Initialize Dash
    app = Dash(__name__, server=flask_app, url_base_pathname="/dashing/")

    # Layout of the Dash app
    app.layout = html.Div(
        [
            dcc.Store(id="stored-chamber"),
            html.Div(id="chamber-buttons"),
            html.Div(id="measurement-info", style={"padding": "20px 0"}),
            html.Button("Previous", id="prev-button", n_clicks=0),
            html.Button("Next", id="next-button", n_clicks=0),
            html.Button("Find lagtime", id="find-max", n_clicks=0),
            dcc.Graph(id="ch4-graph"),
            dcc.Graph(id="co2-graph"),
            html.Div(id="output"),  # To display which button was clicked
        ]
    )

    @app.callback(
        Output("chamber-buttons", "children"),
        # Dummy input to ensure the callback is called at startup
        Input("output", "children"),
    )
    def generate_buttons(_):
        styles = {"width": "50px", "height": "25px"}
        buttons = [
            html.Button(
                "All",
                id={"type": "dynamic-button", "index": "All"},
                n_clicks=0,
                style=styles,
            )
        ]
        for key in cycle_dict.keys():
            buttons.append(
                html.Button(
                    key,
                    id={"type": "dynamic-button", "index": key},
                    n_clicks=0,
                    style=styles,
                )
            )
        return buttons

    @app.callback(
        Output("ch4-graph", "figure"),
        Output("co2-graph", "figure"),
        Output("measurement-info", "children"),
        Input("prev-button", "n_clicks"),
        Input("next-button", "n_clicks"),
        Input("find-max", "n_clicks"),
        [Input({"type": "dynamic-button", "index": dash.dependencies.ALL}, "n_clicks")],
    )
    def update_graph(prev_clicks, next_clicks, find_max, cham_n_clicks):
        global current_index
        global current_chamber
        global current_button

        if current_button is None or current_button == "All":
            measurements = all_measurements
        else:
            measurements = cycle_dict[current_button]

        if not ctx.triggered:
            measurements = all_measurements
            current_button = "All"
            current_index = 0
        if ctx.triggered:
            button_id_str = ctx.triggered[0]["prop_id"].split(".")[0]
            if ctx.triggered_id == "prev-button":
                current_index = (current_index - 1) % len(measurements)
            elif ctx.triggered_id == "next-button":
                current_index = (current_index + 1) % len(measurements)
            elif ctx.triggered_id == "find-max":
                # current_index = (current_index + 1) % len(measurements)
                pass
            elif button_id_str != "chamber-id.value" and button_id_str != "chamber-id":
                button_id = json.loads(button_id_str)  # Safely parse JSON string
                key = button_id["index"]  # Extract key from the button id
                if key == "All":
                    measurements = all_measurements
                    current_button = key
                    current_index = 0
                    pass
                else:
                    measurements = cycle_dict[key]
                    current_button = key
                    current_index = 0

        measurement = measurements[current_index]
        tz = "Europe/Helsinki"
        # measurement.start = measurement.start.tz_convert("Europe/Helsinki")
        # measurement.end = measurement.end.tz_convert("Europe/Helsinki")
        s = measurement.start
        e = measurement.end

        measurement.data = read_ifdb(ifdb_dict, meas_dict, start_ts=s, stop_ts=e)
        # measurement.data.index.tz_localize(tz)
        measurement.data.set_index("datetime", inplace=True)

        measurement.data.index.tz_convert(tz)
        # measurement.open = measurement.open.tz_convert("Europe/Helsinki")
        # measurement.close = measurement.close.tz_convert("Europe/Helsinki")
        if measurement.open.tzinfo is None:
            measurement.open = measurement.open.tz_localize(tz)
            measurement.close = measurement.close.tz_localize(tz)
        if ctx.triggered_id == "find-max":
            # measurement.find_max("CH4")
            mask1 = measurement.data.index > measurement.open
            # mask2 = measurement.data.index < (
            #     measurement.open + pd.Timedelta(minutes=2)
            # )
            # print(mask1)
            # print(mask2)
            data = measurement.data[mask1]
            # print(data.index)
            # print(data)
            max = data["CH4"].idxmax()
            measurement.lagtime = max
        if measurement.lagtime is None:
            fig_ch4 = create_plot_methane(measurement)
            fig_co2 = create_plot_co2(measurement)
        else:
            fig_ch4 = create_plot_methane(measurement, lagtime=measurement.lagtime)
            fig_co2 = create_plot_co2(measurement)

        # Information about the current measurement
        measurement_info = f"Measurement {current_index + 1}/{len(measurements)} - Date: {measurement.start.date()}"

        return fig_ch4, fig_co2, measurement_info

    def create_table(df):
        data_table = dash_table.DataTable(
            columns=[{"name": i, "id": i} for i in df.columns],
            data=df.to_dict("records"),
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": "rgb(230, 230, 230)",
                "fontWeight": "bold",
            },
            style_cell={"textAlign": "left"},
            page_size=10,
        )
        return data_table

    def create_plot_methane(measurement, lagtime=None):
        # Plot the time series data
        trace_data = go.Scatter(
            x=measurement.data.index,
            y=measurement.data["CH4"],
            mode="markers",
            name="Data",
            marker=dict(
                color="rgba(65,224,22,0)",
                symbol="x-thin",
                size=5,
                line=dict(color="rgb(14,168,213)", width=1),
            ),
        )

        # Add draggable vertical lines for 'open' and 'close'
        open_line = go.Scatter(
            x=[measurement.open, measurement.open],
            y=[measurement.data["CH4"].min(), measurement.data["CH4"].max()],
            mode="lines",
            line=dict(color="green", dash="dash"),
            name="Open",
        )

        close_line = go.Scatter(
            x=[measurement.close, measurement.close],
            y=[measurement.data["CH4"].min(), measurement.data["CH4"].max()],
            mode="lines",
            line=dict(color="red", dash="dash"),
            name="Close",
        )
        if lagtime is not None:
            lag_line = go.Scatter(
                x=[measurement.lagtime, measurement.lagtime],
                y=[measurement.data["CH4"].min(), measurement.data["CH4"].max()],
                mode="lines",
                line=dict(color="red", dash="dash"),
                name="lagtime",
            )
        else:
            lag_line = None

        layout = go.Layout(
            title=f"Chamber {measurement.id} Measurement at {measurement.close}",
            xaxis_title="Time",
            yaxis_title="Value",
            xaxis=dict(type="date"),
            shapes=[
                # Vertical lines at 'open' and 'close'
                dict(
                    type="line",
                    x0=measurement.open,
                    x1=measurement.open,
                    y0=measurement.data["CH4"].min(),
                    y1=measurement.data["CH4"].max(),
                    line=dict(color="green", dash="dash"),
                ),
                dict(
                    type="line",
                    x0=measurement.close,
                    x1=measurement.close,
                    y0=measurement.data["CH4"].min(),
                    y1=measurement.data["CH4"].max(),
                    line=dict(color="red", dash="dash"),
                ),
            ],
        )
        if lagtime is None:
            fig = go.Figure(data=[trace_data, close_line, open_line], layout=layout)
        else:
            fig = go.Figure(
                data=[trace_data, close_line, open_line, lag_line], layout=layout
            )

        return fig

    def create_plot_co2(measurement):
        # Plot the time series data
        trace_data = go.Scatter(
            x=measurement.data.index,
            y=measurement.data["CO2"],
            mode="markers",
            name="Data",
            marker=dict(
                color="rgba(65,224,22,0)",
                symbol="x-thin",
                size=5,
                line=dict(color="rgb(14,168,213)", width=1),
            ),
        )

        # Add draggable vertical lines for 'open' and 'close'
        open_line = go.Scatter(
            x=[measurement.open, measurement.open],
            y=[measurement.data["CO2"].min(), measurement.data["CO2"].max()],
            mode="lines",
            line=dict(color="green", dash="dash"),
            name="Open",
        )

        close_line = go.Scatter(
            x=[measurement.close, measurement.close],
            y=[measurement.data["CO2"].min(), measurement.data["CO2"].max()],
            mode="lines",
            line=dict(color="red", dash="dash"),
            name="Close",
        )

        layout = go.Layout(
            title=f"Chamber {measurement.id} Measurement at {measurement.close}",
            xaxis_title="Time",
            yaxis_title="Value",
            xaxis=dict(type="date"),
            shapes=[
                # Vertical lines at 'open' and 'close'
                dict(
                    type="line",
                    x0=measurement.open,
                    x1=measurement.open,
                    y0=measurement.data["CO2"].min(),
                    y1=measurement.data["CO2"].max(),
                    line=dict(color="green", dash="dash"),
                ),
                dict(
                    type="line",
                    x0=measurement.close,
                    x1=measurement.close,
                    y0=measurement.data["CO2"].min(),
                    y1=measurement.data["CO2"].max(),
                    line=dict(color="red", dash="dash"),
                ),
            ],
        )
        fig = go.Figure(data=[trace_data, close_line, open_line], layout=layout)
        return fig
