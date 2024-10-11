import pandas as pd
import plotly.graph_objects as go
import pyarrow.feather as feather
import dill
from dash import Dash, dcc, html, Input, Output, State, callback_context


def create_dash_app2(flask_app):
    # Load data from Feather files
    # df_timestamps = pd.read_feather("timestamps_progress.feather")
    df_timestamps = pd.read_feather("timestamps.feather")
    df_data = pd.read_feather("fen_all_old_all.feather")
    path = "/home/eerokos/code/python/for_torben/fluxObject/measurements.pkl"
    with open(path, "rb") as f:
        classes = dill.load(f)
    #
    [print(c.date) for c in classes]

    if "validated" not in df_timestamps.columns:
        df_timestamps["validated"] = None
    if "validity" not in df_timestamps.columns:
        df_timestamps["validity"] = None

    # Filter the data for required columns
    df_data = df_data[["CH4"]]

    df_timestamps["start"] = pd.to_datetime(df_timestamps["start_time"]) - pd.Timedelta(
        minutes=3
    )
    df_timestamps["end"] = pd.to_datetime(df_timestamps["end_time"]) + pd.Timedelta(
        minutes=3
    )
    # app = Dash(__name__)
    app = Dash(__name__, server=flask_app, url_base_pathname="/chamber_validation2/")

    app.layout = html.Div(
        [
            dcc.Graph(id="data-plot"),
            html.Button("Mark as Valid", id="mark-valid-button", n_clicks=0),
            html.Button("Mark as Invalid", id="mark-invalid-button", n_clicks=0),
            html.Button("Previous", id="previous-button", n_clicks=0),
            html.Button("Next", id="next-button", n_clicks=0),
            dcc.Input(
                id="jump-to-input",
                type="number",
                min=0,
                placeholder="Jump to index",
                debounce=True,
            ),
            html.Button("Jump", id="jump-button", n_clicks=0),
            dcc.Checklist(
                id="skip-validated",
                options=[
                    {"label": "Skip Validated", "value": "skip", "disabled": True}
                ],
                value=[],
            ),
            html.Button("Save Progress", id="save-button", n_clicks=0),
            dcc.Store(id="current-index", data=0),
            dcc.Store(id="df-timestamps", data=df_timestamps.to_dict("records")),
        ]
    )

    @app.callback(
        Output("data-plot", "figure"),
        Output("current-index", "data"),
        Input("mark-valid-button", "n_clicks"),
        Input("mark-invalid-button", "n_clicks"),
        Input("next-button", "n_clicks"),
        Input("previous-button", "n_clicks"),
        Input("jump-button", "n_clicks"),
        Input("skip-validated", "value"),
        State("jump-to-input", "value"),
        State("current-index", "data"),
        State("df-timestamps", "data"),
    )
    def update_plot(
        mark_valid_clicks,
        mark_invalid_clicks,
        next_clicks,
        previous_clicks,
        jump_clicks,
        skip_validated,
        jump_index,
        current_index,
        timestamps_data,
    ):
        df_timestamps_updated = pd.DataFrame(timestamps_data)

        # Ensure the 'validated' column contains boolean values
        with pd.option_context("future.no_silent_downcasting", True):
            df_timestamps_updated["validated"] = (
                df_timestamps_updated["validated"].fillna(False).astype(bool)
            )

        if "skip" in skip_validated:
            valid_rows = df_timestamps_updated[~df_timestamps_updated["validated"]]
        else:
            valid_rows = df_timestamps_updated

        if not valid_rows.empty:
            # Determine action based on button clicks
            ctx = callback_context
            if not ctx.triggered:
                action = None
            else:
                action = ctx.triggered[0]["prop_id"].split(".")[0]

            if action == "mark-valid-button" and mark_valid_clicks > 0:
                df_timestamps_updated.at[current_index, "validated"] = True
                df_timestamps_updated.at[current_index, "validity"] = 1
                current_index += 1
            elif action == "mark-invalid-button" and mark_invalid_clicks > 0:
                df_timestamps_updated.at[current_index, "validated"] = True
                df_timestamps_updated.at[current_index, "validity"] = 0
                current_index += 1
            elif action == "next-button" and next_clicks > 0:
                current_index += 1
            elif action == "previous-button" and previous_clicks > 0:
                current_index -= 1
            elif action == "jump-button" and jump_clicks > 0 and jump_index is not None:
                current_index = jump_index

            # Ensure the index is within the valid range
            if "skip" in skip_validated:
                valid_indices = valid_rows.index.tolist()
                current_index = min(max(0, current_index), len(valid_indices) - 1)
                if valid_indices:
                    current_index = valid_indices[current_index]
            else:
                current_index = min(
                    max(0, current_index), len(df_timestamps_updated) - 1
                )

            # Update the plot with the current index data
            if current_index < len(df_timestamps_updated):
                print(current_index)
                row = df_timestamps_updated.iloc[current_index]
                start_time = row["start_time"]
                end_time = row["end_time"]
                close_time = row["close_time"]
                open_time = row["open_time"]
                start = row["start"]
                end = row["end"]
                print(start)
                print(end)
                filtered_data = df_data[
                    (df_data.index >= start) & (df_data.index <= end)
                ]

                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=filtered_data.index,
                        y=filtered_data["CH4"],
                        mode="markers",
                        name="Value",
                        connectgaps=True,
                        marker=dict(
                            color="rgba(17,157,255,0)",
                            size=8,
                            line=dict(color="rgb(17,157,255)", width=2),
                        ),
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

                if row["validated"] == 1:
                    validated_text = f'<br><span style="color:green">Validated: {row["validated"]}</span>'
                else:
                    validated_text = f'<br><span style="color:red">Validated: {row["validated"]}</span>'
                if row["validity"] == 1:
                    validity_text = f'<br><span style="color:green">Validity: {row["validity"]}</span>'
                else:
                    validity_text = f'<br><span style="color:red">Validity: {row["validity"]}</span>'
                r_text = f'<br><span style="color:red">Validity: {row["CH4_pearsons_r"]}</span>'
                fig.update_layout(
                    title=f"Data from {start_time} to {end_time} {current_index}/{len(timestamps_data)} {validity_text} {validated_text} {r_text}",
                    width=1200,
                    height=500,
                    xaxis_title="Timestamp",
                    yaxis_title="Value",
                )
            else:
                fig = go.Figure()

        return fig, current_index

    @app.callback(
        Output("df-timestamps", "data"),
        Input("mark-valid-button", "n_clicks"),
        Input("mark-invalid-button", "n_clicks"),
        State("current-index", "data"),
        State("df-timestamps", "data"),
    )
    def validate_data(
        mark_valid_clicks, mark_invalid_clicks, current_index, timestamps_data
    ):
        df_timestamps_updated = pd.DataFrame(timestamps_data)
        if mark_valid_clicks > 0 and mark_valid_clicks >= mark_invalid_clicks:
            df_timestamps_updated.at[current_index, "validated"] = True
            df_timestamps_updated.at[current_index, "validity"] = 1
        elif mark_invalid_clicks > 0 and mark_invalid_clicks >= mark_valid_clicks:
            df_timestamps_updated.at[current_index, "validated"] = True
            df_timestamps_updated.at[current_index, "validity"] = 0

        return df_timestamps_updated.to_dict("records")

    @app.callback(
        Output("save-button", "children"),
        Input("save-button", "n_clicks"),
        State("df-timestamps", "data"),
    )
    def save_progress(n_clicks, timestamps_data):
        if n_clicks > 0:
            df_timestamps_updated = pd.DataFrame(timestamps_data)
            feather.write_feather(df_timestamps_updated, "timestamps_progress.feather")
            return "Progress Saved"
        return "Save Progress"
