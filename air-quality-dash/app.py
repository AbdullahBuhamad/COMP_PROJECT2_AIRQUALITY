import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html
from dash.dependencies import Input, Output

# ---------- Data ----------
DATA_PATH = os.path.join("data", "processed", "aq_clean_template.csv")
df = pd.read_csv(DATA_PATH)

# Parse datetime
if not df.empty and "datetime_local" in df.columns:
    df["datetime_local"] = pd.to_datetime(df["datetime_local"], errors="coerce")

cities = sorted(df["city"].dropna().unique().tolist())
stations_by_city = (
    df[["city", "station"]]
    .drop_duplicates()
    .sort_values(["city", "station"])
)

# ---------- AQI utilities ----------
AQI_TABLE = {
    "pm25": [
        (0.0, 12.0,   0,  50),
        (12.1, 35.4, 51, 100),
        (35.5, 55.4,101, 150),
        (55.5,150.4,151, 200),
        (150.5,250.4,201, 300),
        (250.5,350.4,301, 400),
        (350.5,500.4,401, 500),
    ],
    "o3": [
        (0,   54,   0,  50),
        (55,  70,  51, 100),
        (71,  85, 101, 150),
        (86, 105, 151, 200),
        (106,200, 201, 300),
    ]
}
AQI_CATEGORY = [
    (0, 50, "Good"),
    (51, 100, "Moderate"),
    (101, 150, "Unhealthy for Sensitive Groups"),
    (151, 200, "Unhealthy"),
    (201, 300, "Very Unhealthy"),
    (301, 500, "Hazardous"),
]

def compute_aqi_for_value(pollutant: str, value: float):
    if value is None or pd.isna(value):
        return np.nan
    table = AQI_TABLE.get(pollutant, [])
    for BPlo, BPhi, Ilo, Ihi in table:
        if BPlo <= value <= BPhi:
            return (Ihi - Ilo) / (BPhi - BPlo) * (value - BPlo) + Ilo
    if table and value > table[-1][1]:
        return 500.0
    return np.nan

def aqi_category(aqi: float | None) -> str:
    if aqi is None or pd.isna(aqi):
        return "—"
    for lo, hi, name in AQI_CATEGORY:
        if lo <= aqi <= hi:
            return name
    return "—"

def empty_fig(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=320,
        margin=dict(l=40, r=20, t=60, b=40),
        xaxis=dict(showgrid=True),
        yaxis=dict(showgrid=True),
    )
    fig.add_annotation(
        text="(Your chart will appear here after you make selections.)",
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=12)
    )
    return fig

def add_aqi_bands(fig: go.Figure) -> go.Figure:
    """Faint horizontal bands for AQI categories (0–200)."""
    bands = [
        (0, 50, "Good"),
        (51, 100, "Moderate"),
        (101, 150, "USG"),
        (151, 200, "Unhealthy"),
    ]
    colors = {
        "Good": "rgba(0, 176, 80, 0.08)",
        "Moderate": "rgba(255, 192, 0, 0.10)",
        "USG": "rgba(255, 153, 0, 0.10)",
        "Unhealthy": "rgba(255, 0, 0, 0.08)",
    }
    for lo, hi, name in bands:
        fig.add_hrect(y0=lo, y1=hi, line_width=0, fillcolor=colors[name], layer="below")
    return fig

# Colors for the pie chart categories
PIE_COLORS = {
    "Good (0–50)": "#2ECC71",
    "Moderate (51–100)": "#F1C40F",
    "Unhealthy SG (101–150)": "#E67E22",
    "Unhealthy (151–200)": "#E74C3C",
    "Very Unhealthy (201–300)": "#8E44AD",
    "Hazardous (301–500)": "#7D3C98",
}

pollutant_options = [
    {"label": "PM2.5 (µg/m³)", "value": "pm25"},
    {"label": "O₃ (ppb)", "value": "o3"},
]

# ---------- App ----------
app = Dash(__name__, title="Air Quality & Health Guidance")

app.layout = html.Div(
    className="container",
    children=[
        html.H1("Air Quality & Health Guidance"),
        dcc.Markdown(
            id="howto-md",
            className="howto",
            children=(
                "**How to use:**\n"
                "1) Choose a city and (optionally) a station.\n"
                "2) Pick a date range and pollutants.\n"
                "3) Set aggregation and an AQI threshold to highlight exceedances.\n"
                "The panels below will update with trends, drivers, and guidance."
            ),
        ),

        # Controls
        html.Div(
            className="controls-grid",
            children=[
                html.Div([
                    html.Label("City"),
                    dcc.Dropdown(
                        id="city-dd",
                        options=[{"label": c, "value": c} for c in cities],
                        value=cities[0] if cities else None,
                        clearable=False,
                    ),
                ]),
                html.Div([
                    html.Label("Station"),
                    dcc.Dropdown(
                        id="station-dd",
                        placeholder="Select a station (optional)",
                        options=[],  # by callback
                        clearable=True,
                    ),
                ]),
                html.Div([
                    html.Label("Date range"),
                    dcc.DatePickerRange(id="dates"),
                ]),
                html.Div([
                    html.Label("Pollutants"),
                    dcc.Dropdown(
                        id="pollutants-dd",
                        options=pollutant_options,
                        value=["pm25", "o3"],
                        multi=True,
                        clearable=False,
                    ),
                ]),
                html.Div([
                    html.Label("Aggregation"),
                    dcc.RadioItems(
                        id="agg-radio",
                        options=[
                            {"label": "Hourly", "value": "H"},
                            {"label": "Daily", "value": "D"},
                            {"label": "Weekly", "value": "W"},
                        ],
                        value="D",
                        inline=True,
                    ),
                ]),
                html.Div([
                    html.Label("AQI threshold (highlight)"),
                    dcc.Slider(
                        id="aqi-thresh",
                        min=50, max=200, step=10, value=100,
                        marks={i: str(i) for i in range(50, 201, 25)},
                        tooltip={"placement": "bottom", "always_visible": False},
                    ),
                ], className="slider-cell"),
            ],
        ),

        # KPI tiles
        html.Div(
            className="kpi-grid",
            children=[
                html.Div(id="kpi-avg-aqi", className="kpi-card", children=["Avg AQI: —"]),
                html.Div(id="kpi-exceed-rate", className="kpi-card", children=["% ≥ threshold: —"]),
                html.Div(id="kpi-worst-day", className="kpi-card", children=["Worst period: —"]),
                html.Div(id="kpi-top-driver", className="kpi-card", children=["Top driver: —"]),
            ],
        ),

        # Charts
        html.Div(
            className="charts-grid",
            children=[
                dcc.Graph(id="fig-aqi-trend", figure=empty_fig("AQI trend")),
                dcc.Graph(id="fig-pollutant-bar", figure=empty_fig("Pollutant contribution")),
                dcc.Graph(id="fig-category-pie", figure=empty_fig("AQI category breakdown")),
            ],
        ),

        dcc.Markdown(id="insight-md", className="insight", children="_Select options to see insights here._"),
    ],
)

# ---------- Callbacks ----------

# Populate stations from city
@app.callback(
    Output("station-dd", "options"),
    Output("station-dd", "value"),
    Input("city-dd", "value"),
)
def update_stations(city):
    if not city:
        return [], None
    opts = (
        stations_by_city.query("city == @city")["station"]
        .dropna().unique().tolist()
    )
    return [{"label": s, "value": s} for s in opts], None

# Date picker bounds/defaults
@app.callback(
    Output("dates", "min_date_allowed"),
    Output("dates", "max_date_allowed"),
    Output("dates", "start_date"),
    Output("dates", "end_date"),
    Input("city-dd", "value"),
    Input("station-dd", "value"),
)
def update_dates(city, station):
    if df.empty or "datetime_local" not in df.columns:
        return None, None, None, None
    dff = df.copy()
    if city:
        dff = dff[dff["city"] == city]
    if station:
        dff = dff[dff["station"] == station]
    dff = dff.dropna(subset=["datetime_local"])
    if dff.empty:
        return None, None, None, None
    dmin = dff["datetime_local"].min().date()
    dmax = dff["datetime_local"].max().date()
    # start/end as ISO strings (important for Dash)
    return dmin, dmax, dmin.isoformat(), dmax.isoformat()

# MAIN: trend + bar + PIE + KPIs + narrative
@app.callback(
    Output("fig-aqi-trend", "figure"),
    Output("fig-pollutant-bar", "figure"),
    Output("fig-category-pie", "figure"),
    Output("kpi-avg-aqi", "children"),
    Output("kpi-exceed-rate", "children"),
    Output("kpi-worst-day", "children"),
    Output("kpi-top-driver", "children"),
    Output("insight-md", "children"),
    Input("city-dd", "value"),
    Input("station-dd", "value"),
    Input("dates", "start_date"),
    Input("dates", "end_date"),
    Input("pollutants-dd", "value"),
    Input("agg-radio", "value"),
    Input("aqi-thresh", "value"),
)
def update_all(city, station, start_date, end_date, pollutants, agg, thresh):
    dff = df.copy()

    # Guard: ignore invalid station for the selected city
    if city:
        valid_stations = (
            stations_by_city.query("city == @city")["station"]
            .dropna().unique().tolist()
        )
        if station and station not in valid_stations:
            station = None

    if city:
        dff = dff[dff["city"] == city]
    if station:
        dff = dff[dff["station"] == station]

    # Inclusive date range (whole end day)
    sd = pd.to_datetime(start_date).normalize() if start_date else None
    ed = pd.to_datetime(end_date).normalize() if end_date else None
    if sd is not None:
        dff = dff[dff["datetime_local"] >= sd]
    if ed is not None:
        dff = dff[dff["datetime_local"] < (ed + pd.Timedelta(days=1))]

    if pollutants:
        dff = dff[dff["pollutant"].isin(pollutants)]

    if dff.empty:
        empty = empty_fig("AQI trend")
        return (empty,
                empty_fig("Pollutant contribution"),
                empty_fig("AQI category breakdown"),
                ["Avg AQI: —"], ["% ≥ threshold: —"], ["Worst period: —"], ["Top driver: —"],
                "_No data in the selected filters._")

    # Concentrations pivot
    dff = dff.dropna(subset=["datetime_local", "value"]).sort_values("datetime_local")
    conc = dff.pivot_table(index="datetime_local", columns="pollutant", values="value", aggfunc="mean").sort_index()

    # Resample
    if agg in ("H", "D", "W"):
        conc = conc.resample(agg).mean()

    # AQIs
    aqi_cols = {}
    for p in (pollutants or []):
        if p in conc.columns:
            aqi_cols[p] = conc[p].apply(lambda v: compute_aqi_for_value(p, v))
    if not aqi_cols:
        empty = empty_fig("AQI trend")
        return (empty,
                empty_fig("Pollutant contribution"),
                empty_fig("AQI category breakdown"),
                ["Avg AQI: —"], ["% ≥ threshold: —"], ["Worst period: —"], ["Top driver: —"],
                "_No AQI could be computed for the selected pollutants._")

    aqi_df = pd.DataFrame(aqi_cols)
    aqi_df["aqi_max"] = aqi_df.max(axis=1)
    aqi_df["aqi_cat"] = aqi_df["aqi_max"].apply(aqi_category)

    # ---------- KPIs ----------
    avg_aqi = float(np.nanmean(aqi_df["aqi_max"])) if aqi_df["aqi_max"].notna().any() else np.nan
    exceed_rate = float((aqi_df["aqi_max"] >= (thresh or 100)).mean() * 100) if aqi_df["aqi_max"].notna().any() else np.nan
    if aqi_df["aqi_max"].notna().any():
        worst_idx = aqi_df["aqi_max"].idxmax()
        worst_time = pd.to_datetime(worst_idx)
        worst_value = aqi_df.loc[worst_idx, "aqi_max"]
        worst_txt = f"{worst_time.strftime('%Y-%m-%d %H:%M')} (AQI {worst_value:.0f})"
    else:
        worst_txt = "—"

    mean_by_pollutant = aqi_df.drop(columns=["aqi_max", "aqi_cat"]).mean(numeric_only=True)

    # ---------- Figure 1: AQI Trend ----------
    fig_trend = go.Figure()
    add_aqi_bands(fig_trend)  # background bands

    fig_trend.add_trace(
        go.Scatter(
            x=aqi_df.index,
            y=aqi_df["aqi_max"],
            mode="lines+markers",
            name="AQI (overall)",
            hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>AQI: %{y:.0f}<extra></extra>",
        )
    )

    if thresh is not None:
        fig_trend.add_hline(
            y=thresh, line_dash="dash",
            annotation_text=f"Threshold {thresh}", annotation_position="top left"
        )

    # Annotate worst period
    if aqi_df["aqi_max"].notna().any():
        fig_trend.add_annotation(
            x=worst_idx, y=float(worst_value),
            text="Worst", showarrow=True, arrowhead=2, yshift=8
        )

    title_bits = [f"AQI trend — {city}" if city else "AQI trend"]
    if station: title_bits.append(f"Station: {station}")
    if sd is not None and ed is not None:
        title_bits.append(f"{sd.date()} → {ed.date()}")
    fig_trend.update_layout(
        title=" | ".join(title_bits),
        template="plotly_white",
        height=380,
        margin=dict(l=40, r=20, t=60, b=40),
        xaxis_title="Time",
        yaxis_title="AQI (EPA scale)",
        xaxis=dict(showspikes=True, spikemode="across", spikesnap="cursor", spikedash="dot"),
        yaxis=dict(showspikes=True, spikemode="across"),
    )
    if aqi_df["aqi_max"].notna().any():
        ymax = max(200, float(np.nanmax(aqi_df["aqi_max"])) * 1.15)
        fig_trend.update_yaxes(range=[0, ymax])

    # ---------- Figure 2: Pollutant contribution (mean AQI by pollutant) ----------
    mean_by_pollutant_sorted = mean_by_pollutant.sort_values(ascending=True)  # for horizontal bars
    bx = [("PM2.5" if k == "pm25" else "O₃") for k in mean_by_pollutant_sorted.index]
    by = [float(v) for v in mean_by_pollutant_sorted.values]
    fig_bar = go.Figure(
        data=[go.Bar(
            x=by, y=bx, orientation="h",
            text=[f"{v:.0f}" for v in by], textposition="outside",
            hovertemplate="<b>%{y}</b><br>Mean AQI: %{x:.0f}<extra></extra>",
            name="Mean AQI",
        )]
    )
    fig_bar.update_layout(
        title="Pollutant contribution (mean AQI over selection)",
        template="plotly_white",
        height=360,
        margin=dict(l=80, r=20, t=60, b=40),
        xaxis_title="Mean AQI",
        yaxis_title="",
    )

    # ---------- Figure 3: PIE — % time in AQI categories ----------
    # Build distribution of categories for overall AQI
    pie_bins = [0, 50, 100, 150, 200, 300, 500]
    pie_labels = [
        "Good (0–50)", "Moderate (51–100)", "Unhealthy SG (101–150)",
        "Unhealthy (151–200)", "Very Unhealthy (201–300)", "Hazardous (301–500)"
    ]
    cat_series = pd.cut(aqi_df["aqi_max"], bins=pie_bins, labels=pie_labels, right=True, include_lowest=True)
    counts = cat_series.value_counts().reindex(pie_labels, fill_value=0)

    fig_pie = go.Figure(data=[go.Pie(
        labels=counts.index,
        values=counts.values,
        hole=0.45,
        sort=False,
        marker=dict(colors=[PIE_COLORS[l] for l in counts.index]),
        hovertemplate="<b>%{label}</b><br>%{percent}<extra></extra>",
    )])
    fig_pie.update_layout(
        title="AQI category breakdown (share of time)",
        height=360,
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", y=-0.1),
    )

    # ---------- Narrative & KPIs ----------
    avg_txt = f"{avg_aqi:.0f}" if not np.isnan(avg_aqi) else "—"
    ex_txt = f"{exceed_rate:.1f}%" if not np.isnan(exceed_rate) else "—"
    driver_key = mean_by_pollutant.idxmax() if not mean_by_pollutant.dropna().empty else "—"
    driver_label = "PM2.5" if driver_key == "pm25" else ("O₃" if driver_key == "o3" else driver_key)

    city_txt = city or "selected area"
    period_txt = f" from {sd.date()} to {ed.date()}" if (sd is not None and ed is not None) else ""
    insight = (
        f"**Summary for {city_txt}{period_txt}:**\n\n"
        f"- Average AQI: **{avg_txt}**; periods ≥ threshold: **{ex_txt}**.\n"
        f"- Worst period: **{worst_txt}**.\n"
        f"- Likely driver pollutant: **{driver_label}**.\n\n"
        f"**Health guidance:**\n"
        f"- **Good (0–50):** Enjoy outdoor activities.\n"
        f"- **Moderate (51–100):** Sensitive individuals consider shorter exertion.\n"
        f"- **USG (101–150):** Sensitive groups limit prolonged or heavy exertion.\n"
        f"- **Unhealthy (151–200):** Everyone reduce prolonged or heavy exertion; sensitive groups avoid.\n"
    )

    kpi_avg = [f"Avg AQI: {avg_txt}"]
    kpi_exc = [f"% ≥ threshold: {ex_txt}"]
    kpi_worst = [f"Worst period: {worst_txt}"]
    kpi_driver = [f"Top driver: {driver_label}"]

    return (fig_trend, fig_bar, fig_pie,
            kpi_avg, kpi_exc, kpi_worst, kpi_driver, insight)

# ---------- Main ----------
if __name__ == "__main__":
    app.run_server(debug=True, port=8052)
