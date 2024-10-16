import json
import pytz
import time
import uuid
from project.log_layout import create_layout
from project.push_point import ifdb_push
from datetime import datetime as dt
from dash import Dash, dcc, ctx, html, Input, Output, State
import temp_users

selected = []
is_range = []
text_date_end = None
text_time_end = None
users = temp_users.users


def maintenance_log(flask_app, url):
    app = Dash(__name__, server=flask_app, url_base_pathname=url)
    # app = Dash(__name__, server=flask_app, routes_pathname_prefix=url)
    tz = pytz.timezone("Europe/Helsinki")

    # Load projects data from JSON file
    with open("project/projects.json", "r") as f:
        projects_json = json.load(f)
        projects = projects_json["PROJECTS"]

    with open("project/maintenance_log_config.json", "r") as f:
        config = json.load(f)
        ifdb_dict = config["CONFIG"]["INFLUXDB"]

    # NOTE: import layout from file
    app.layout = create_layout()

    # Populate project dropdown
    @app.callback(
        Output("projects", "children"),
        Input("projects", "id"),  # Trigger this callback on load
    )
    def populate_first_dropdown(_):
        return create_dropdown(projects, "col-dd")

    # populate instrument dropdown based on chosen project
    @app.callback(Output("instrument-dropdown", "children"), Input("col-dd", "value"))
    def mk_instrument_dd(selected_value):
        # Only create the second dropdown if a value is selected
        if selected_value:
            instruments = projects[selected_value]["ELEMENTS"]
            return create_instrument_dropdown(
                instruments, "selected-instrument", multi=True
            )

        # Return an empty dropdown if no project is selected
        return html.Div(
            [
                html.Label("Select instrument"),
                dcc.Dropdown(
                    id="selected-instrument",
                    options=[],
                    style={"width": "500px"},
                ),
            ],
        )

    @app.callback(
        Output("text-date", "value"),
        Output("text-time", "value"),
        Input("selected-instrument", "value"),
        State("textarea-content-store", "data"),
    )
    def mk_input(selected, stored_text):
        now = dt.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")
        return date, time

    @app.callback(
        Output("text-out", "children"),
        Input("submit-button", "n_clicks"),
        State("col-dd", "value"),
        State("selected-instrument", "value"),
        State("user-name", "value"),
        State("text-content", "value"),
        State("text-date", "value"),
        State("text-time", "value"),
        State("text-date-end", "value"),
        State("text-time-end", "value"),
    )
    def submit_maintenance(
        submit_clicks,
        selected_project,
        selected_instr,
        username,
        txt_input,
        txt_dt,
        txt_time,
        txt_dt_end,
        txt_time_end,
    ):
        if submit_clicks:
            if not selected_project:
                return "Select project."
            if len(txt_input.strip()) == 0:
                return "Please enter log message."
            if txt_dt_end and txt_time_end:
                s_dt = dt.strptime(f"{txt_dt}{txt_time}", "%Y-%m-%d%H:%M:%S")
                e_dt = dt.strptime(f"{txt_dt_end}{txt_time_end}", "%Y-%m-%d%H:%M:%S")
                if s_dt > e_dt:
                    return "Start can't be older than end."
                s_dt = tz.localize(s_dt)
                # for grafana
                pt = mk_log_point(
                    txt_input,
                    username,
                    selected_project,
                    selected_instr,
                    s_dt=s_dt,
                    e_dt=e_dt,
                )
                ifdb_push(pt, ifdb_dict)
                return str(pt)

            else:
                s_dt = dt.strptime(f"{txt_dt}{txt_time}", "%Y-%m-%d%H:%M:%S")
                s_dt = tz.localize(s_dt)
                pt = mk_log_point(
                    txt_input, username, selected_project, selected_instr, s_dt
                )
                ifdb_push(pt, ifdb_dict)
                return str(pt)

    def mk_log_point(
        text_content,
        username,
        selected_project,
        selected_instruments,
        s_dt=None,
        e_dt=None,
    ):
        grafana_edt = None
        if e_dt is None:
            s_str = dt.strftime(s_dt, "%Y-%m-%d %H:%M:%S")
            maintenance_msg = f"{s_str} {username} {selected_project} {','.join(selected_instruments)}: {text_content}"
        if e_dt is not None:
            s_str = dt.strftime(s_dt, "%Y-%m-%d %H:%M:%S")
            e_str = dt.strftime(e_dt, "%Y-%m-%d %H:%M:%S")
            grafana_edt = int(time.mktime(tz.localize(e_dt).timetuple())) * 1000
            maintenance_msg = f"{s_str}-{e_str} {username} {selected_project} {','.join(selected_instruments)}: {text_content}"
        uuid = mk_uuid()

        point_data = [
            {
                "measurement": "log_message",
                "fields": {
                    "text": text_content,
                    "title": selected_project,
                    "project": selected_project,
                    "instruments": ",".join(selected_instruments),
                    "endTime": grafana_edt,
                    "uuid": uuid,
                },
                "tags": {"uuid": uuid, "user": username, "project": selected_project},
                "time": s_dt,
                "timezone": "Europe/Helsinki",
            },
            {
                "measurement": "maintenance_log_message",
                "fields": {
                    "text": maintenance_msg,
                    "title": selected_project,
                    "project": selected_project,
                    "instruments": ", ".join(selected_instruments),
                    "endTime": grafana_edt,
                    "uuid": uuid,
                },
                "tags": {"uuid": uuid},
                "time": s_dt,
                "timezone": "Europe/Helsinki",
            },
        ]
        if e_dt is None:
            for point in point_data:
                del point["fields"]["endTime"]
        return point_data

    def create_dropdown(dictionary, id, multi=False):
        dropdown = dcc.Dropdown(
            options=[{"label": key, "value": key} for key in dictionary],
            value=None,
            id=id,
            multi=multi,
        )
        col_dd = html.Div(
            [html.Label("Select Project", htmlFor=id), dropdown],
            style={"width": "500px"},
        )
        return col_dd

    def create_instrument_dropdown(dictionary, id, multi=False):
        dropdown = dcc.Dropdown(
            options=[{"label": key, "value": key} for key in dictionary],
            value=[],
            id=id,
            multi=multi,
        )
        col_dd = html.Div(
            [html.Label("Select instrument", htmlFor=id), dropdown],
            style={"width": "500px"},
        )
        return col_dd

    def mk_uuid():
        return str(uuid.uuid4())[:10]

    @app.callback(
        Output("range-div", "style"),
        Output("text-date-end", "value"),
        Output("text-time-end", "value"),
        Input("is-range", "value"),
    )
    def mk_range_div(is_range):
        if is_range is None:
            is_range = []
        now = dt.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")
        if len(is_range) > 0:
            return {"margin-top": "10px", "margin-bottom": "10px"}, date, time

        else:
            return {"display": "none"}, "", ""

    return app
