from flask import Flask, render_template, request, redirect
from flask_httpauth import HTTPBasicAuth
from project.ac_plot import ac_plot
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from datetime import datetime
from project.maintenance_log import maintenance_log

server = Flask(__name__)
server.config.from_object("project.config.Config")
db = SQLAlchemy(server)


auth = HTTPBasicAuth()
server.secret_key = "supersecretkey"

users = {"user": "password"}


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), unique=True, nullable=False)
    active = db.Column(db.Boolean(), default=True, nullable=False)

    def __init__(self, email):
        self.email = email


@auth.verify_password
def verify_password(username, password):
    if username in users and users[username] == password:
        return username


ac_app = ac_plot(server)


app = DispatcherMiddleware(server, {"/ac_dash": ac_app.server})


@server.route("/")
def index():
    return render_template("index.html")


@server.route("/ac_dashing")
def render_ac():
    return redirect("/ac_dash")


# @server.route("/asd")
# def acer():
#     return ac_plot(server).index()


# @server.route("/testing")
# def ac_plots():
# return ac_plot.server()


# @app.route("/snowdepth")
# def snowdepth():
#     return render_template("snowdepth.html")


# @app.route("/maintenance_log")
# @auth.login_required
# def maintenance_log():
#     return render_template("maintenance_log.html")


@server.route("/snow_density_fen")
@auth.login_required
def snow_density_fen():
    return render_template("snow_density_fen.html")


@server.route("/snow_density_forest")
@auth.login_required
def snow_density_forest():
    return render_template("snow_density_forest.html")


@server.route("/snowdepth_forest")
@auth.login_required
def snowdepth_forest():
    return render_template("snowdepth_forest.html")


@server.route("/autochamber_state")
@auth.login_required
def autochamber_state():
    return render_template("autochamber_state.html")


@server.route("/snowdepth_fen")
@auth.login_required
def snowdepth_fen():
    return render_template("snowdepth_fen.html")


@server.route("/manual_measurement_forest")
@auth.login_required
def manual_measurement_forest():
    return render_template("manual_measurement_forest.html")


@server.route("/manual_measurement_fen")
@auth.login_required
def manual_measurement_fen():
    return render_template("manual_measurement_fen.html")


@server.route("/licor_inspect")
@auth.login_required
def licor_inspect():
    return render_template("licor_inspect.html")


@server.route("/water_table_level")
@auth.login_required
def water_table_level():
    return render_template("water_table_level.html")


# @app.route("/filter_page")
# def filter_page():
#     return render_template("filter.html", instruments=instruments)


@server.route("/licor_dl", methods=["POST"])
def run_licor_dl():
    from licor_dl import main

    licor_ids = ["01792"]  # Example list of IDs to process
    plots = []
    for licor_id in licor_ids:
        fig = main(licor_id)
        if fig is not None:
            plots.append(
                fig.to_html(full_html=False, include_plotlyjs="cdn")
            )  # Convert figure to HTML

    return render_template("result.html", plots=plots)
    # return redirect(url_for("licor_inspect"))


@server.route("/submit_water", methods=["POST"])
@auth.login_required
def submit_water():
    inputs = []

    name = request.form.get("measurerName")
    inputs.append(f"name,{name}")
    date = request.form.get("measurementDate")
    inputs.append(f"date,{date}")

    not_acceptable = ["", None]
    # inputs.append(f"{name},{date}")
    inputs.append("plot,water_in,water_out")
    for i in range(1, 73):
        input1 = request.form.get(f"waterIn{i}")
        input2 = request.form.get(f"waterOut{i}")
        if input1 not in not_acceptable or input2 not in not_acceptable:
            inputs.append(f"{i},{input1},{input2}")
            continue
    with open(f"{date}.csv", "w") as f:
        f.write("\n".join(inputs))
    return "<br>".join(inputs)


@server.route("/submit_ac", methods=["POST"])
@auth.login_required
def submit_ac():
    inputs = []

    name = request.form.get("measurerName")
    inputs.append(f"name,{name}")
    date = request.form.get("date")
    inputs.append(f"date,{date}")
    time = request.form.get("time")
    inputs.append(f"time,{time}")
    ac_loc = request.form.get("ac_loc")

    # not_acceptable = ["", None]
    dt = datetime.strptime(date + time, "%y%m%d%H%M")
    inputs.append("datetime,ac_loc")
    inputs.append(f"{dt},{ac_loc}")
    # with open(f"{date}.csv", "w") as f:
    #     f.write("\n".join(inputs))
    return "<br>".join(inputs)


@server.route("/submit_snow", methods=["POST"])
def submit_snow():
    inputs = []

    name = request.form.get("measurerName")
    inputs.append(f"name,{name}")
    date = request.form.get("measurementDate")
    inputs.append(f"date,{date}")
    manip_done = request.form.get("lumimanip")

    not_acceptable = ["", None]
    # inputs.append(f"{name},{date}")
    inputs.append("plot,snow1,snow2,snow3,palvi,manip_done")
    for i in range(1, 73):
        input1 = request.form.get(f"snow{i}-1")
        input2 = request.form.get(f"snow{i}-2")
        input3 = request.form.get(f"snow{i}-3")
        input4 = request.form.get(f"palvi{i}")
        if input4 == "":
            input4 = 100
        if (
            input1 not in not_acceptable
            or input2 not in not_acceptable
            or input3 not in not_acceptable
        ):
            inputs.append(f"{i},{input1},{input2},{input3},{input4},{manip_done}")
            continue
    with open(f"{date}.csv", "w") as f:
        f.write("\n".join(inputs))
    return "<br>".join(inputs)


@server.route("/submit_times", methods=["POST"])
def submit_times():
    inputs = []

    name = request.form.get("measurerName")
    inputs.append(f"name,{name}")
    date = request.form.get("measurementDate")
    inputs.append(f"date,{date}")
    licor_id = request.form.get("LicorId")
    inputs.append(f"licor_id,{licor_id}")

    not_acceptable = ["", None]

    inputs.append("Plot Number,Start Time,Notes,Chamber height")
    for i in range(1, 73):
        input1 = request.form.get(f"time{i}")
        input2 = request.form.get(f"snow{i}")
        try:
            input3 = request.form.get(f"note{i}").replace(",", " ")
        except Exception:
            pass
        if input1 not in not_acceptable and input2 not in not_acceptable:
            inputs.append(f"{i},{input1},{input3},{input2}")
        if input1 not in not_acceptable and input2 == "":
            input2 = 0
            inputs.append(f"{i},{input1},{input2}")
        # inputs.append(f"{i},{input1},{input2}")
        with open(f"{date}.csv", "w") as f:
            f.write("\n".join(inputs))
    return "<br>".join(inputs)


# create_dash_app(app)
# create_dash_app2(app)
# test_plot(app)
# ac_plot(app)
# maintenance_log(app)
# create_overview_app(app)
# create_overview_app_eeva(app)

if __name__ == "__main__":
    server.run(host="0.0.0.0", debug=True)
