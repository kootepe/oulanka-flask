import pandas as pd
import plotly.graph_objects as go
import pyarrow.feather as feather
import dill
from dash import Dash, dcc, html, Input, Output, State, callback_context


def create_overview_app(flask_app):
    # Load data from Feather files
    df_timestamps = pd.read_feather("timestamps.feather")
    df_data = pd.read_feather("fen_all_old_all.feather")
    if "validated" not in df_timestamps.columns:
        df_timestamps["validated"] = None
    if "validity" not in df_timestamps.columns:
        df_timestamps["validity"] = None
    m1 = df_timestamps["start_time"] > "2021-11-01"
    m2 = df_timestamps["start_time"] < "2021-12-01"
    # df_timestamps = df_timestamps[m1 & m2]
    # Ensure the DataFrame has the required columns
    # mask = df_timestamps["CH4_flux"] < 0
    # df_timestamps = df_timestamps[mask]

    df_timestamps["start"] = pd.to_datetime(df_timestamps["start_time"]) - pd.Timedelta(
        2, "min"
    )
    df_timestamps["end"] = pd.to_datetime(df_timestamps["end_time"]) + pd.Timedelta(
        2, "min"
    )

    # Initialize Dash app with the Flask server
    app = Dash(__name__, server=flask_app, url_base_pathname="/overview/")

    # Calculate number of rows needed
    num_graphs = len(df_timestamps)
    num_columns = 5
    graphs_per_page = 50

    # Create the layout with buttons and graph container
    app.layout = html.Div(
        [
            html.H1("Overview of All Measurements"),
            html.Button("Previous 50", id="prev-50-button", n_clicks=0),
            html.Button("Next 50", id="next-50-button", n_clicks=0),
            html.Div(
                id="graph-container",
                children=[
                    html.Div(
                        [
                            dcc.Graph(id=f"graph-{row * num_columns + col}")
                            for col in range(num_columns)
                        ],
                        style={"display": "flex"},
                    )
                    for row in range(graphs_per_page // num_columns)
                ],
            ),
        ]
    )

    @app.callback(
        [Output(f"graph-{i}", "figure") for i in range(graphs_per_page)],
        [Input("prev-50-button", "n_clicks"), Input("next-50-button", "n_clicks")],
        [
            State("prev-50-button", "n_clicks_timestamp"),
            State("next-50-button", "n_clicks_timestamp"),
        ],
    )
    def update_overview_graphs(prev_clicks, next_clicks, prev_ts, next_ts):
        page = (next_clicks - prev_clicks) if (prev_clicks + next_clicks) > 0 else 0
        start_index = page * graphs_per_page
        end_index = start_index + graphs_per_page
        figs = []

        for i in range(start_index, min(end_index, num_graphs)):
            fig = go.Figure()
            print(df_timestamps)
            print(df_data)
            row = df_timestamps.iloc[i]
            start_time = row["start_time"]
            end_time = row["end_time"]
            close_time = row["close_time"]
            open_time = row["open_time"]
            start = row["start"] + pd.Timedelta(seconds=5)
            end = row["end"] - pd.Timedelta(seconds=5)
            filtered_data = df_data[(df_data.index >= start) & (df_data.index <= end)]

            fig.add_trace(
                go.Scatter(
                    x=filtered_data.index,
                    y=filtered_data["CH4"],
                    mode="lines",
                    name="Value",
                    connectgaps=False,
                )
            )
            fig.add_shape(
                type="rect",
                x0=start_time,
                x1=end_time,
                y0=min(filtered_data["CH4"]),
                y1=max(filtered_data["CH4"]),
                fillcolor="grey",
                opacity=0.3,
                line_width=0,
            )
            fig.add_shape(
                type="rect",
                x0=close_time,
                x1=open_time,
                y0=min(filtered_data["CH4"]),
                y1=max(filtered_data["CH4"]),
                fillcolor="green",
                opacity=0.3,
                line_width=0,
            )
            r_str = f"<br>r: {round(row['CH4_pearsons_r'], 3)}"
            f_str = f"<br>ch4_flux: {round(row['CH4_flux'], 3)}"
            is_valid = row["is_valid"]
            plot_str = f"Plot: {row['chamber']}"
            st_str = (pd.to_datetime(start_time)).strftime("%Y-%m-%d %H:%M")
            et_str = (pd.to_datetime(end_time)).strftime("%Y-%m-%d %H:%M")
            # st_str = pd.to_datetime(start_time, format="%y-%m-%d %H:%M")
            # et_str = pd.to_datetime(end_time, format="%y-%m-%d %H:%M")
            time_str = f"{st_str} to {et_str}"
            validated_text = (
                f'<br><span style="color:green">Validated: {row["validated"]}</span>'
            )
            if is_valid == 1:
                title = f'<span style="color:green">{plot_str} {r_str}{f_str}</span>'
            else:
                title = f'<span style="color:red">{plot_str} {r_str}{f_str}</span>'

            fig.update_layout(
                # title=f"Data from {start_time} to {end_time} {f_str}{r_str}",
                # title=f"{plot_str} {r_str}{f_str}",
                title=title,
                width=500,
                height=300,
                xaxis_title="Timestamp",
                yaxis_title="Value",
            )
            figs.append(fig)

        # Fill remaining figures with empty plots
        for _ in range(graphs_per_page - len(figs)):
            figs.append(go.Figure())

        return figs


def create_overview_app_eeva(flask_app):
    # Load data from Feather files
    df_timestamps = pd.read_feather("timestamps.feather")
    # df_data = pd.read_feather("forest_all_all_data.feather")
    df_data = pd.read_feather("fen_all_old_all.feather")

    # if "datetime" not in df_timestamps.columns:
    # df_timestamps["datetime"] = df_timestamps["start"]
    # print(df_timestamps["start"])
    # mask = df_timestamps["CH4_flux"] < 0
    # mask2 = df_timestamps["is_valid"] == 1
    # mask3 = df_timestamps["CH4_pearsons_r"] > 0.95
    # mask4 = df_timestamps["CH4_pearsons_r"] < 0.99
    # df_timestamps = df_timestamps[mask & mask2 & mask3]
    # df_timestamps = df_timestamps[mask & mask2]
    # df_timestamps = df_timestamps[mask3 & mask4]
    # df_timestamps = df_timestamps[m1]
    # print(len(df_timestamps))
    m = df_timestamps["is_valid"] == 1
    df_timestamps = df_timestamps[m]
    df_timestamps["CH4_pearsons_r_sq"] = df_timestamps["CH4_pearsons_r"] ** 2
    m1 = df_timestamps["CH4_pearsons_r"] < 0.975
    df_timestamps = df_timestamps[m1]
    m1 = df_timestamps.index > "2021-10-19"
    m2 = df_timestamps.index < "2022-10-31"
    df_timestamps = df_timestamps[m1 & m2]
    measurement_count = len(df_timestamps)
    # print(len(df_timestamps))
    # df_timestamps.sort_values("CH4_flux", ascending=False)
    # print(len(df_timestamps))

    df_timestamps["start"] = pd.to_datetime(df_timestamps["start_time"]) - pd.Timedelta(
        2, "min"
    )
    df_timestamps["end"] = pd.to_datetime(df_timestamps["end_time"]) + pd.Timedelta(
        2, "min"
    )

    # Initialize Dash app with the Flask server
    app = Dash(__name__, server=flask_app, url_base_pathname="/overview_eeva/")

    # Calculate number of rows needed
    num_graphs = len(df_timestamps)
    num_columns = 5
    graphs_per_page = 50

    # Create the layout with buttons and graph container
    app.layout = html.Div(
        [
            html.H1("Overview of Eevas measurements"),
            html.Button("Previous 50", id="prev-50-button", n_clicks=0),
            html.Button("Next 50", id="next-50-button", n_clicks=0),
            html.Div(
                id="graph-container",
                children=[
                    html.Div(
                        [
                            dcc.Graph(id=f"graph-{row * num_columns + col}")
                            for col in range(num_columns)
                        ],
                        style={"display": "flex"},
                    )
                    for row in range(graphs_per_page // num_columns)
                ],
            ),
        ]
    )

    @app.callback(
        [Output(f"graph-{i}", "figure") for i in range(graphs_per_page)],
        [Input("prev-50-button", "n_clicks"), Input("next-50-button", "n_clicks")],
        [
            State("prev-50-button", "n_clicks_timestamp"),
            State("next-50-button", "n_clicks_timestamp"),
        ],
    )
    def update_overview_graphs(prev_clicks, next_clicks, prev_ts, next_ts):
        page = (next_clicks - prev_clicks) if (prev_clicks + next_clicks) > 0 else 0
        start_index = page * graphs_per_page
        end_index = start_index + graphs_per_page
        page_total = int(round((measurement_count / graphs_per_page), 0))
        figs = []

        for i in range(start_index, min(end_index, num_graphs)):
            fig = go.Figure()
            row = df_timestamps.iloc[i]
            start_time = row["start_time"]
            end_time = row["end_time"]
            close_time = row["close_time"]
            open_time = row["open_time"]
            start = row["start"]
            end = row["end"]
            filtered_data = df_data[(df_data.index >= start) & (df_data.index <= end)]

            fig.add_trace(
                go.Scatter(
                    x=filtered_data.index,
                    y=filtered_data["CH4"],
                    mode="lines",
                    name="Value",
                )
            )
            fig.add_shape(
                type="rect",
                x0=start_time,
                x1=end_time,
                y0=min(filtered_data["CH4"]),
                y1=max(filtered_data["CH4"]),
                fillcolor="grey",
                opacity=0.3,
                line_width=0,
            )
            plot_str = f"Plot: {row['chamber']}"
            r_str = f"<br>r: {round(row['CH4_pearsons_r'], 3)}"
            f_str = f"<br>ch4_flux: {round(row['CH4_flux'], 3)}"
            page_str = f" Page: {page}/{page_total}"
            if row["is_valid"] == 0:
                fillcolor = "red"
                c_str = f"<br>invalid because: {row['checks']}"
                title = f"{plot_str}{page_str}{c_str}"
            else:
                fillcolor = "green"
                c_str = None
                title = f"{plot_str}{page_str}{r_str}{f_str}"

            fig.add_shape(
                type="rect",
                x0=close_time,
                x1=open_time,
                y0=min(filtered_data["CH4"]),
                y1=max(filtered_data["CH4"]),
                fillcolor=fillcolor,
                opacity=0.3,
                line_width=0,
            )
            # r_str = f"<br>r: {round(row['ch4_pearsons_r'], 3)}"
            # f_str = f"<br>ch4_flux: {round(row['ch4_flux'], 3)}"
            # r_str = f"<br>r: {round(row['CH4_pearsons_r'], 3)}"
            # f_str = f"<br>ch4_flux: {round(row['CH4_flux'], 3)}"
            # plot_str = f"Plot: {row['chamber']}"
            # st_str = (pd.to_datetime(start_time)).strftime("%Y-%m-%d %H:%M")
            # et_str = (pd.to_datetime(end_time)).strftime("%Y-%m-%d %H:%M")
            # st_str = pd.to_datetime(start_time, format="%y-%m-%d %H:%M")
            # et_str = pd.to_datetime(end_time, format="%y-%m-%d %H:%M")
            # time_str = f"{st_str} to {et_str}"
            fig.update_layout(
                # title=f"Data from {start_time} to {end_time} {f_str}{r_str}",
                title=title,
                width=500,
                height=300,
                xaxis_title="Timestamp",
                yaxis_title="Value",
            )
            figs.append(fig)

        # Fill remaining figures with empty plots
        for _ in range(graphs_per_page - len(figs)):
            figs.append(go.Figure())

        return figs
