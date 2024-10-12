from dash import dcc, html


def create_layout():
    graph_style = {"height": "300px", "width": "900px"}
    return html.Div(
        [
            html.Button("Previous", id="prev-button", n_clicks=0),
            html.Button("Next", id="next-button", n_clicks=0),
            html.Div(id="chamber-buttons"),
            html.Div(id="measurement-info", style={"padding": "20px 0"}),
            dcc.Checklist({1: "Skip invalid"}, id="skip-invalid"),
            html.Div(
                [
                    html.Button("Find lagtime", id="find-max", n_clicks=0),
                    html.Button("Delete lagtime", id="del-lagtime", n_clicks=0),
                    html.Button("Push all", id="push-all", n_clicks=0),
                    html.Button("Push current lagtime", id="push-lag", n_clicks=0),
                ]
            ),
            html.Div(
                [
                    html.Div(
                        [
                            dcc.Graph(id="ch4-graph", style=graph_style),
                            dcc.Graph(id="co2-graph", style=graph_style),
                        ],
                    ),
                    html.Div(
                        [
                            dcc.Graph(id="lag-graph", style=graph_style),
                            dcc.Graph(id="flux-graph", style=graph_style),
                        ],
                    ),
                ],
                style={"display": "flex"},
            ),
            html.Div(id="output"),
            dcc.Store(id="stored-index", data=0),
            dcc.Store(id="stored-chamber", data="All"),
            dcc.Store(id="relayout-data", data=None),
        ]
    )
