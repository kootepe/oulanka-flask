from project.tools.influxdb_funcs import init_client
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd


def create_plot(measurement, gas, color_key="blue"):
    color_dict = {"blue": "rgb(14,168,213,0)", "green": "rgba(27,187,11,1)"}

    if measurement.adjusted_close is not None:
        close = measurement.adjusted_close
    else:
        close = measurement.close

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
        x=[measurement.open, measurement.open],
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
            line=dict(color="red", dash="dash"),
            name="lagtime",
        )
        if measurement.lagtime_index
        else None
    )

    layout = go.Layout(
        yaxis_title="Value",
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
            l=20,
            r=20,
            t=40,
            b=20,
        ),
        xaxis=dict(type="date"),
    )
    fig = go.Figure(
        data=[trace_data, open_line, close_line, lag_line]
        if lag_line
        else [trace_data, open_line, close_line],
        layout=layout,
    )

    return fig


def mk_lag_graph(measurements, current_measurement, ifdb_dict):
    with init_client(ifdb_dict) as client:
        [m.get_max(ifdb_dict, client) for m in measurements]
    # Extract data from each measurement and store in a list of tuples
    data = [(m.open, m.lagtime_s, m.id) for m in measurements]
    data2 = [(m.open, m.lagtime_s, m.id) for m in current_measurement]

    # Create a pandas DataFrame from the list
    df = pd.DataFrame(data, columns=["open", "lagtime", "id"]).set_index("open")
    df["idx"] = range(len(df))
    df2 = pd.DataFrame(data2, columns=["open", "lagtime", "id"]).set_index("open")

    # Generate a scatter plot with Plotly Graph Objects
    color_map = create_color_mapping(df, "id")
    colors = [color_map[val] for val in df["id"]]

    trace_data = go.Scatter(
        x=df.index,
        y=df["lagtime"],
        mode="markers",
        name="Lag time",
        marker=dict(
            color=colors,
            symbol="x-thin",
            size=5,
            line=dict(color=colors, width=2),
        ),
        customdata=df,
    )
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
        hoverinfo="none",
        showlegend=False,
    )
    layout = go.Layout(
        xaxis_title="Open Time",
        yaxis_title="Lag Time (s)",
        template="plotly_white",
        hovermode="closest",
        # width=1000,
        # height=300,
        title={
            "text": "Scatter Plot of Lag Time vs. Open Time",
            # "x": 0.33,  # Horizontal position of the title (0 - left, 0.5 - center, 1 - right)
            # "y": 0.82,  # Vertical position of the title, with 1 being the top
            # "xanchor": "center",  # Anchoring the title horizontally
            # "yanchor": "top",  # Anchoring the title vertically
        },
        margin=dict(
            l=20,
            r=20,
            t=40,
            b=20,
        ),
        xaxis=dict(type="date", showspikes=True),
        yaxis=dict(showspikes=True),
    )
    fig = go.Figure(
        data=[trace_data, highlighter],
        layout=layout,
    )

    return fig


def create_color_mapping(df, column_name):
    # Get unique values from the column
    unique_values = df[column_name].unique()

    # Generate a color map based on the number of unique values
    color_map = (
        px.colors.qualitative.Plotly
    )  # You can choose another color palette if you prefer
    colors = {val: color_map[i % len(color_map)] for i, val in enumerate(unique_values)}

    return colors
