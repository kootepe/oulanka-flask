from project.tools.influxdb_funcs import init_client, just_read, read_ifdb
from plotly.graph_objs import Figure
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import logging

logger = logging.getLogger("defaultLogger")


def mk_gas_plot(measurement, gas, color_key="blue"):
    logger.debug(f"Running for {gas}.")
    color_dict = {"blue": "rgb(14,168,213,0)", "green": "rgba(27,187,11,1)"}

    close = measurement.close
    open = measurement.open

    trace_data = go.Scatter(
        x=measurement.data.index,
        y=measurement.data[gas],
        mode="markers",
        name="Data",
        marker=dict(
            color="rgba(65,224,22,0)",
            symbol="x-thin",
            size=5,
            line=dict(color=color_dict.get(color_key), width=1),
        ),
    )
    close_line = go.Scatter(
        x=[close, close],
        y=[measurement.data[gas].min(), measurement.data[gas].max()],
        mode="lines",
        line=dict(color="red", dash="dash"),
        name="Close",
    )
    open_line = go.Scatter(
        x=[open, open],
        y=[measurement.data[gas].min(), measurement.data[gas].max()],
        mode="lines",
        line=dict(color="green", dash="dash"),
        name="Open",
    )

    lag_line = (
        go.Scatter(
            x=[measurement.lagtime_index, measurement.lagtime_index],
            y=[measurement.data[gas].min(), measurement.data[gas].max()],
            mode="lines",
            line=dict(color="black", dash="dash"),
            name="lagtime",
        )
        if measurement.lagtime_index
        else None
    )

    layout = go.Layout(
        # width=1000,
        # height=300,
        title={
            "text": f"Chamber {measurement.id} {gas} Measurement {close}",
            # "x": 0.33,  # Horizontal position of the title (0 - left, 0.5 - center, 1 - right)
            # "y": 0.82,  # Vertical position of the title, with 1 being the top
            # "xanchor": "center",  # Anchoring the title horizontally
            # "yanchor": "top",  # Anchoring the title vertically
        },
        margin=dict(
            l=10,
            r=10,
            t=25,
            b=10,
        ),
        xaxis=dict(type="date"),
    )

    fig = go.Figure(
        data=[trace_data, open_line, close_line, lag_line]
        if lag_line
        else [trace_data, open_line, close_line],
        layout=layout,
    )
    if measurement.is_valid is False or measurement.manual_valid is False:
        fig.update_layout(
            {
                "plot_bgcolor": "rgba(255, 223, 223, 1)",
            },
            # template=draft_template,
            annotations=[
                dict(
                    name="draft watermark",
                    text="INVALID",
                    textangle=0,
                    opacity=0.4,
                    font=dict(color="black", size=50),
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                )
            ],
        )

    return fig


def mk_lag_plot(measurements, current_measurement, ifdb_dict, selected_chambers, index):
    logger.debug("Creating lag graph.")
    current_measurement = measurements[index]
    data2 = [
        (
            current_measurement.close,
            current_measurement.lagtime_s,
            current_measurement.id,
        )
    ]

    tz = "Europe/Helsinki"
    start_ts = measurements[0].close - pd.Timedelta(minutes=3)
    end_ts = measurements[-1].close + pd.Timedelta(minutes=3)
    meas_dict = {"measurement": "flux_point", "fields": "id,lagtime"}
    arr_str = [str(id) for id in selected_chambers]
    tag = "chamber"
    q_arr = {"tag": tag, "arr": arr_str}

    logger.debug("Querying.")
    df = read_ifdb(ifdb_dict, meas_dict, start_ts=start_ts, stop_ts=end_ts, arr=q_arr)
    if df is None:
        return go.Figure()
    df.set_index("datetime", inplace=True)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    df["idx"] = range(len(df))
    df2 = pd.DataFrame(data2, columns=["close", "lagtime", "id"]).set_index("close")

    color_map = create_color_mapping(df, "id")

    # Create a list of traces, one for each unique `id`
    traces = []
    for unique_id, color in color_map.items():
        filtered_df = df[df["id"] == unique_id]
        traces.append(
            go.Scatter(
                x=filtered_df.index,
                y=filtered_df["lagtime"],
                mode="markers",
                name=f"{unique_id}",
                marker=dict(
                    color=color,
                    symbol="x-thin",
                    size=5,
                    line=dict(color=color, width=1.5),
                ),
                customdata=filtered_df,
                hoverinfo="all",
            )
        )

    # Add the highlighter trace
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

    # Layout configuration
    layout = go.Layout(
        hovermode="closest",
        hoverdistance=20,
        title={"text": "Lag time"},
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(
            type="date",
            showspikes=True,
            spikethickness=1,
            spikedash="solid",
        ),
        yaxis=dict(showspikes=True, spikethickness=1, spikedash="solid"),
        legend=dict(
            font=dict(size=10),
            orientation="h",
            tracegroupgap=3,
            itemclick=False,
            itemdoubleclick=False,
        ),
    )

    # Add all traces (separate traces for each id) and the highlighter trace to the figure
    fig = go.Figure(data=traces + [highlighter], layout=layout)
    fig.add_hline(y=0, line_dash="dash", line_color="blue", line_width=1)

    return fig


fixed_color_mapping = {}
color_list = px.colors.qualitative.Plotly + px.colors.qualitative.D3


def create_color_mapping(df, column_name):
    # Get unique values from the column, sorted to ensure consistent ordering
    unique_values = sorted(df[column_name].unique())

    # Update the fixed color mapping if any new values appear
    for i, val in enumerate(unique_values):
        if val not in fixed_color_mapping:
            fixed_color_mapping[val] = color_list[
                len(fixed_color_mapping) % len(color_list)
            ]

    # Return the fixed color mapping for the current unique values
    return {val: fixed_color_mapping[val] for val in unique_values}
