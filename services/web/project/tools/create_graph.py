import plotly.graph_objs as go


def create_plot(measurement, gas, title, color_key="blue"):
    color_dict = {"blue": "rgb(14,168,213,0)", "green": "rgba(27,187,11,1)"}
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
    open_line = go.Scatter(
        x=[measurement.open, measurement.open],
        y=[measurement.data[gas].min(), measurement.data[gas].max()],
        mode="lines",
        line=dict(color="green", dash="dash"),
        name="Open",
    )
    close_line = go.Scatter(
        x=[measurement.close, measurement.close],
        y=[measurement.data[gas].min(), measurement.data[gas].max()],
        mode="lines",
        line=dict(color="red", dash="dash"),
        name="Close",
    )
    lag_line = (
        go.Scatter(
            x=[measurement.lagtime, measurement.lagtime],
            y=[measurement.data[gas].min(), measurement.data[gas].max()],
            mode="lines",
            line=dict(color="red", dash="dash"),
            name="lagtime",
        )
        if measurement.lagtime
        else None
    )

    layout = go.Layout(
        title=f"Chamber {measurement.id} {title} Measurement {measurement.close}",
        xaxis_title="Time",
        yaxis_title="Value",
        width=1000,
        height=400,
        xaxis=dict(type="date"),
    )
    fig = go.Figure(
        data=[trace_data, open_line, close_line, lag_line]
        if lag_line
        else [trace_data, open_line, close_line],
        layout=layout,
    )

    return fig
