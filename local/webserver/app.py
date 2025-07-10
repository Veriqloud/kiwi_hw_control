import os
import io
import requests
from flask import Flask, render_template, Response
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import mon_bob 

API_KEY = os.getenv("OPENWEATHER_API_KEY")  # set this env var
CITY = "Paris,FR"

app = Flask(__name__)

#def fetch_temperature():
#    url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric"
#    resp = requests.get(url)
#    data = resp.json()
#    return data["main"]["temp"]

def create_figure(temp_history):
    fig = Figure()
    ax = fig.subplots()
    ax.plot(range(len(temp_history)), temp_history, marker='o')
    #ax.set_title(f"Temperature in {CITY}")
    #ax.set_xticks(range(len(temp_history)))
    #ax.set_xticklabels([f"T-{i}" for i in reversed(range(len(temp_history)))])
    ax.set_ylabel("counts")
    #ax.ygrid(True)
    lower = int(min(temp_history)/1000)*1000
    upper = (int(max(temp_history)/1000)+1)*1000
    ax.set_ylim(lower, upper)
    return fig

# Store last 10 temps
temp_history = []

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/plot.png")
def plot_png():
    temp = mon_bob.get_counts()[0] # fetch_temperature()
    temp_history.append(temp)
    if len(temp_history) > 40:
        temp_history.pop(0)
    fig = create_figure(temp_history)
    buf = io.BytesIO()
    FigureCanvas(fig).print_png(buf)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")

if __name__ == "__main__":
    mon_bob.connect_to_bob()
    app.run(debug=True)

