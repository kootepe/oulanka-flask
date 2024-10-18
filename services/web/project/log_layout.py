from dash import dcc, html


def create_layout():
    timeinput = {"display": "inline-block", "margin": "0px"}
    # App layout with placeholders for dropdowns
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            dcc.Dropdown(
                                options=[],
                                id="col-dd",
                                style={"width": "500px"},
                            )
                        ],
                        id="projects",
                    ),
                    html.Div(
                        [
                            html.Label("Select instrument"),
                            dcc.Dropdown(
                                id="selected-instrument",
                                options=[],
                                style={"width": "500px"},
                            ),
                        ],
                        id="instrument-dropdown",
                    ),
                    html.Div(id="selected-value"),
                    html.Div(
                        [
                            dcc.Checklist({1: "Timerange"}, id="is-range"),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.P(
                                                        "Input date:",
                                                        style=timeinput,
                                                        id="start-date-label",
                                                    ),
                                                    dcc.Input(id="text-date"),
                                                ]
                                            ),
                                            html.Div(
                                                [
                                                    html.P(
                                                        "Input time:",
                                                        style=timeinput,
                                                        id="start-time-label",
                                                    ),
                                                    dcc.Input(id="text-time"),
                                                ]
                                            ),
                                        ],
                                        style={
                                            "margin-top": "10px",
                                            "margin-bottom": "10px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.P(
                                                        "End:",
                                                        style=timeinput,
                                                        id="end-date-label",
                                                    ),
                                                    dcc.Input(
                                                        id="text-date-end",
                                                    ),
                                                ],
                                            ),
                                            html.Div(
                                                [
                                                    html.P(
                                                        "End:",
                                                        style=timeinput,
                                                        id="end-time-label",
                                                    ),
                                                    dcc.Input(
                                                        id="text-time-end",
                                                    ),
                                                ],
                                            ),
                                        ],
                                        style={
                                            "display": "none",
                                            "margin-top": "10px",
                                            "margin-bottom": "10px",
                                        },
                                        id="range-div",
                                    ),
                                ],
                                style={"display": "flex", "gap": "20px"},
                            ),
                            html.Div([dcc.Input(value="EK", id="user-name")]),
                            html.Div(
                                dcc.Textarea(
                                    id="text-content",
                                    value="",
                                    style={
                                        "height": "100px",
                                        "width": "500px",
                                        "text-align": "left",
                                        "vertical-align": "top",
                                    },
                                    n_blur=0,
                                )
                            ),
                            html.Button(
                                "Submit",
                                id="submit-button",
                                style={"height": "25px"},
                                disabled=False,
                            ),
                        ],
                        id="text-input",
                    ),
                    html.Div(id="text-out"),
                    # stores text from the textbox so that it doesn't get wiped
                    # on updates
                    dcc.Store(id="textarea-content-store"),
                ],
                style={"width": "600px"},
            ),
            html.Div(
                "Old logs go here.",
                id="logs-display",
                style={"padding-left": "100px"},
            ),
        ],
        style={"display": "flex", "margin": "auto"},
    )
