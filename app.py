"""Road accident data explorer for India."""
import os
from pathlib import Path
import pandas as pd
from flask import Flask, Response, abort, jsonify, redirect, render_template, request
from io import BytesIO
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
TREND_PATH = BASE_DIR / "data" / "india_annual_trends_2015_2024.csv"
STATE_TREND_PATH = BASE_DIR / "data" / "state_accidents_2015_2024.csv"
STATE_CASUALTY_PATH = BASE_DIR / "data" / "state_casualties_2017_2023.csv"
STATE_RATE_PATH = BASE_DIR / "data" / "state_per_capita_rates.csv"
SOURCE_URL = "https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2042509"
MORTH_2023_URL = "https://morth.gov.in/backend/documents/uploaded/Road-Accident-in-India-2023-Publications.pdf"
MORTH_2024_TOTALS_URL = "https://sansad.in/getFile/loksabhaquestions/annex/187/AU4505_smjOzM.pdf?source=pqals"
STATE_HISTORY_URL = "https://dataful.in/datasets/19606/"
STATE_TREND_SOURCE_URL = "https://prsindia.org/budgets/parliament/demand-for-grants-2026-27-analysis-road-transport-and-highways"
STATE_TREND_OFFICIAL_URL = "https://sansad.in/getFile/loksabhaquestions/annex/187/AU3388_xs92Gd.pdf?source=pqals"
MORTH_2019_URL = "https://morth.gov.in/sites/default/files/RA_Uploading.pdf"
MORTH_2021_URL = "https://www.morth.gov.in/sites/default/files/RA_2021_Compressed.pdf"
MORTH_2023_URL = "https://morth.gov.in/backend/documents/uploaded/Road-Accident-in-India-2023-Publications.pdf"
CASUALTY_2017_2021_URL = "https://sansad.in/getFile/loksabhaquestions/annex/1711/AU57.pdf?source=pqals"
KERALA_URL = "https://keralapolice.gov.in/crime/road-accidents"
NCRB_URL = "https://data.gov.in/ministrydepartment/National%20Crime%20Records%20Bureau%20%28NCRB%29"
app = Flask(__name__)
NAV = [("Dashboard", "/"), ("Latest data", "/latest"), ("Search", "/search"),
       ("Reports", "/reports"), ("Safety", "/safety"), ("Resources", "/resources"), ("About", "/about")]


def active_data_source(requested=None):
    """Production is always MySQL; CSV is only an explicit local option."""
    if os.getenv("APP_ENV", "").lower() == "production":
        return "mysql"
    if requested is not None and requested not in {"csv", "mysql"}:
        abort(400, description="data_source must be either 'mysql' or 'csv'.")
    source = requested or os.getenv("DATA_SOURCE", "csv")
    if source not in {"csv", "mysql"}:
        app.logger.error("DATA_SOURCE must be either 'mysql' or 'csv'.")
        abort(503, description="The configured data source is invalid.")
    return source


def load_csv_data():
    wide = pd.read_csv(STATE_TREND_PATH)
    frame = wide.melt(id_vars=["location", "location_type"], var_name="year", value_name="accidents_reported")
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
    frame["accidents_reported"] = pd.to_numeric(frame["accidents_reported"], errors="coerce")
    frame = frame.dropna(subset=["accidents_reported"])
    frame["casualty_source"] = ""
    frame["casualty_source_url"] = ""
    frame.loc[frame["year"].between(2017, 2019), "casualty_source"] = "Lok Sabha Unstarred Question 57 (2023)"
    frame.loc[frame["year"].between(2017, 2019), "casualty_source_url"] = CASUALTY_2017_2021_URL
    frame.loc[frame["year"].between(2020, 2023), "casualty_source"] = "MoRTH Road Accidents in India 2023"
    frame.loc[frame["year"].between(2020, 2023), "casualty_source_url"] = MORTH_2023_URL
    casualty = pd.read_csv(STATE_CASUALTY_PATH)
    long_casualty = casualty.melt(id_vars=["location"], var_name="metric_year", value_name="value").dropna(subset=["value"])
    parts = long_casualty["metric_year"].str.extract(r"(?P<year>\d{4})_(?P<metric>killed|injured)")
    long_casualty["year"] = pd.to_numeric(parts["year"], errors="coerce").astype("Int64")
    long_casualty["metric"] = parts["metric"]
    casualty = long_casualty.pivot_table(index=["location", "year"], columns="metric", values="value", aggfunc="first").reset_index()
    casualty = casualty.rename(columns={"killed": "persons_killed", "injured": "persons_injured"})
    frame = frame.merge(casualty, on=["location", "year"], how="left")
    for column in ("persons_killed", "persons_injured"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Float64")
    if STATE_RATE_PATH.exists():
        frame = frame.merge(pd.read_csv(STATE_RATE_PATH), on=["location", "year"], how="left")
    return frame


def load_mysql_data():
    required = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        app.logger.error("MySQL configuration is missing: %s", ", ".join(missing))
        abort(503, description="The MySQL database is not configured. Set the required DB_* environment variables.")
    try:
        port = int(os.getenv("DB_PORT", "3306"))
    except ValueError:
        app.logger.error("DB_PORT must be a valid integer.")
        abort(503, description="The MySQL database configuration is invalid.")

    try:
        import mysql.connector
    except ImportError:
        app.logger.exception("mysql-connector-python is not installed.")
        abort(503, description="The MySQL database driver is not installed.")

    connection_options = {
        "host": os.environ["DB_HOST"],
        "port": port,
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "database": os.environ["DB_NAME"],
        "connection_timeout": 5,
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
    }
    if os.getenv("DB_SSL_CA"):
        connection_options["ssl_ca"] = os.environ["DB_SSL_CA"]
    try:
        connection = mysql.connector.connect(**connection_options)
    except mysql.connector.Error:
        app.logger.exception("Could not connect to the configured MySQL database.")
        abort(503, description="The MySQL database is unavailable. Check the host, credentials, network access, and schema.")

    query = """SELECT l.location_name AS location, l.location_type,
        s.statistic_year AS year, s.accidents_reported, s.persons_killed,
        s.persons_injured FROM accident_statistics s JOIN locations l
        ON l.location_id=s.location_id WHERE l.location_type IN ('COUNTRY','STATE','UT')
        AND s.road_type_id=1 ORDER BY l.location_type,l.location_name,s.statistic_year"""
    try:
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
    except mysql.connector.Error:
        app.logger.exception("Could not read accident statistics from MySQL.")
        abort(503, description="The MySQL database query failed. Confirm that road_accident_database.sql was imported.")
    finally:
        connection.close()

    if not rows:
        app.logger.error("The configured MySQL database contains no accident statistics.")
        abort(503, description="The MySQL database contains no accident statistics. Import road_accident_database.sql.")
    frame = pd.DataFrame(rows, columns=columns)
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
    for column in ("accidents_reported", "persons_killed", "persons_injured"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Float64")
    frame["casualty_source"] = ""
    frame["casualty_source_url"] = ""
    state_rows = frame["location_type"].isin(("STATE", "UT"))
    older_casualties = state_rows & frame["year"].between(2017, 2019)
    newer_casualties = state_rows & frame["year"].between(2020, 2023)
    frame.loc[older_casualties, "casualty_source"] = "Lok Sabha Unstarred Question 57 (2023)"
    frame.loc[older_casualties, "casualty_source_url"] = CASUALTY_2017_2021_URL
    frame.loc[newer_casualties, "casualty_source"] = "MoRTH Road Accidents in India 2023"
    frame.loc[newer_casualties, "casualty_source_url"] = MORTH_2023_URL
    return frame


def load_data(source_choice=None):
    """Load data from MySQL in production and honor local source selection in development."""
    source = active_data_source(source_choice)
    if source == "mysql":
        return load_mysql_data(), "Configured MySQL database", None
    return load_csv_data(), "State/UT accident totals (2015?2024) with official casualty detail (2017?2023)", None

def selected_view(default_scope="india"):
    scope = request.args.get("scope", default_scope)
    if scope not in {"india", "state"}:
        scope = "india"
    source_choice = active_data_source(request.args.get("data_source"))
    if scope == "india":
        if source_choice == "mysql":
            frame, source_label, warning = load_data(source_choice)
            frame = frame[frame["location_type"] == "COUNTRY"]
        else:
            frame = pd.read_csv(TREND_PATH)
            source_label = "MoRTH data cited in Lok Sabha Unstarred Question 4505 (19 March 2026)"
            warning = None
    else:
        frame, source_label, warning = load_data(source_choice)
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
    years = sorted(frame["year"].dropna().astype(int).unique().tolist(), reverse=True)
    requested_year = request.args.get("year", "")
    if requested_year:
        try:
            year_value = int(requested_year)
            if year_value not in years:
                requested_year = ""
            else:
                frame = frame[frame["year"] == year_value]
        except ValueError:
            requested_year = ""
    if not requested_year and years:
        requested_year = str(years[0])
        frame = frame[frame["year"] == years[0]]
    state = request.args.get("state", "All States and UTs").strip()
    if scope == "state" and state and state != "All States and UTs":
        frame = frame[frame["location"].str.casefold() == state.casefold()]
    q = request.args.get("q", "").strip()
    if q and scope == "state":
        frame = frame[frame["location"].str.contains(q, case=False, na=False)]
    return frame, source_label, warning, years, requested_year, q, scope, state, source_choice


def add_rates(frame):
    out = frame.copy()
    if not out.empty and "accidents_reported" in out and "persons_killed" in out:
        out["fatalities_per_100"] = None
        valid = out["persons_killed"].notna() & out["accidents_reported"].notna() & out["accidents_reported"].ne(0)
        if valid.any():
            killed = pd.to_numeric(out.loc[valid, "persons_killed"], errors="coerce").astype(float)
            accidents = pd.to_numeric(out.loc[valid, "accidents_reported"], errors="coerce").astype(float)
            out.loc[valid, "fatalities_per_100"] = (killed / accidents * 100).round(1)
    for field in ("persons_killed_per_lakh", "persons_injured_per_lakh"):
        if field in out:
            out[field] = pd.to_numeric(out[field], errors="coerce").round(1)
    return out


def base_context(active):
    return {"nav": NAV, "active": active}


def location_choices():
    frame, _, _ = load_data()
    frame = frame[frame["location_type"].isin(("STATE", "UT"))]
    return sorted(frame["location"].dropna().unique().tolist())


@app.get("/")
def dashboard():
    frame, source, warning, years, year, q, scope, state, data_source = selected_view()
    if scope == "india":
        totals = {"accidents": int(frame["accidents_reported"].fillna(0).sum()),
                  "killed": int(frame["persons_killed"].fillna(0).sum()),
                  "injured": int(frame["persons_injured"].fillna(0).sum()), "locations": 36}
        if data_source == "mysql":
            trend_frame, _, _ = load_data(data_source)
            trend_frame = trend_frame[trend_frame["location_type"] == "COUNTRY"]
        else:
            trend_frame = pd.read_csv(TREND_PATH)
        trend = trend_frame.sort_values("year").to_dict("records")
        top_accidents, top_killed, rows = [], [], []
    else:
        has_casualty_data = bool(not frame.empty and frame["persons_killed"].notna().any())
        totals = {"accidents": int(frame["accidents_reported"].fillna(0).sum()) if not frame.empty else 0,
                  "killed": int(frame["persons_killed"].fillna(0).sum()) if has_casualty_data else None,
                  "injured": int(frame["persons_injured"].fillna(0).sum()) if has_casualty_data else None,
                  "locations": int(frame["location"].nunique()) if not frame.empty else 0}
        comparison = add_rates(load_data(data_source)[0])
        comparison = comparison[comparison["location_type"].isin(("STATE", "UT"))]
        comparison["year"] = pd.to_numeric(comparison["year"], errors="coerce").astype("Int64")
        comparison = comparison[comparison["year"] == int(year)] if year else comparison
        top_accidents = comparison.nlargest(8, "accidents_reported").to_dict("records") if not comparison.empty else []
        top_killed = comparison.dropna(subset=["persons_killed"]).nlargest(8, "persons_killed").to_dict("records") if not comparison.empty else []
        rows = add_rates(frame).sort_values("accidents_reported", ascending=False).to_dict("records")
        trend = []
    has_casualty_data = bool(not frame.empty and frame["persons_killed"].notna().any()) if scope == "state" else True
    return render_template("dashboard.html", **base_context("Dashboard"), totals=totals,
        years=years, year=year, q=q, source=source, warning=warning, scope=scope,
        state=state, data_source=data_source, states=location_choices(), trend=trend,
        top_accidents=top_accidents, top_killed=top_killed, rows=rows,
        has_casualty_data=has_casualty_data)


@app.get("/health")
def health():
    if active_data_source() == "mysql":
        load_mysql_data()
    return jsonify({"status": "ok"})


@app.get("/latest")
def latest():
    frame, state_source, _ = load_data()
    frame = frame[frame["location_type"].isin(("STATE", "UT"))]
    years = sorted(frame["year"].dropna().astype(int).unique().tolist(), reverse=True)
    state = request.args.get("state", "Andhra Pradesh")
    if state not in set(frame["location"].dropna()):
        state = "Andhra Pradesh"
    try:
        year = int(request.args.get("year", years[0]))
    except (TypeError, ValueError):
        year = years[0]
    if year not in years:
        year = years[0]
    if year <= 2019:
        selected_state_source_url = MORTH_2019_URL
    elif year <= 2021:
        selected_state_source_url = MORTH_2021_URL
    else:
        selected_state_source_url = STATE_TREND_SOURCE_URL
    state_frame = frame[(frame["location"] == state) & (frame["year"] == year)]
    state_record = state_frame.iloc[0].to_dict() if not state_frame.empty else None
    return render_template("latest.html", **base_context("Latest data"),
        morth_url=MORTH_2023_URL, totals_url=MORTH_2024_TOTALS_URL,
        kerala_url=KERALA_URL, ncrb_url=NCRB_URL, states=location_choices(),
        years=years, year=year, state=state, state_record=state_record,
        state_source=state_source, state_source_url=selected_state_source_url,
        official_state_source_url=STATE_TREND_OFFICIAL_URL if year >= 2020 else None)


@app.get("/search")
def search():
    frame, source, warning, years, year, q, scope, state, data_source = selected_view("state")
    display = add_rates(frame).sort_values("accidents_reported", ascending=False)
    return render_template("search.html", **base_context("Search"), rows=display.to_dict("records"),
        years=years, year=year, q=q, source=source, warning=warning, states=location_choices(), state=state,
        has_casualty_data=bool(not display.empty and display["persons_killed"].notna().any()))


@app.get("/reports")
def reports():
    if "scope" not in request.args:
        return redirect("/reports?scope=state")
    frame, source, warning, years, year, q, scope, state, _ = selected_view()
    return render_template("reports.html", **base_context("Reports"), years=years, year=year,
        q=q, source=source, warning=warning, count=len(frame), scope=scope,
        states=location_choices(), state=state)


@app.get("/reports/download.csv")
def download_csv():
    frame, source, warning, _, year, q, scope, state, _ = selected_view()
    frame = add_rates(frame)
    frame.insert(0, "source", source)
    frame.insert(1, "selected_year", year)
    frame.insert(2, "coverage_note", "Blank casualty values mean no comparable official State/UT figure was found for this year. Population rates are not included in this bundled dataset.")
    frame.insert(3, "selected_state", state)
    frame.insert(4, "search_filter", q)
    return Response(frame.to_csv(index=False), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=road_accidents_{year or 'all_years'}.csv"})


@app.get("/reports/download.pdf")
def download_pdf():
    """Create a filter-aware, paginated, branded summary PDF."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
            TableStyle, PageBreak, KeepTogether)
        from reportlab.graphics.shapes import Drawing, String, Rect
    except ImportError:
        return "PDF export needs ReportLab. Install it with: python -m pip install -r requirements.txt", 503

    frame, source, warning, _, year, q, scope, state, _ = selected_view()
    frame = add_rates(frame).sort_values("accidents_reported", ascending=False)
    selected_total = int(frame["accidents_reported"].fillna(0).sum()) if not frame.empty else 0
    known_killed = frame["persons_killed"].dropna()
    known_injured = frame["persons_injured"].dropna()
    dark = colors.HexColor("#3A0F34")
    gold = colors.HexColor("#EAAA00")
    ink = colors.HexColor("#241923")
    muted = colors.HexColor("#756C74")
    paper = colors.HexColor("#F4F2F0")
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=15*mm,
        leftMargin=15*mm, topMargin=18*mm, bottomMargin=16*mm,
        title=f"Roadwise road safety report · {year}", author="Roadwise")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Hero", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=26, textColor=dark, alignment=TA_LEFT, spaceAfter=2))
    styles.add(ParagraphStyle(name="Sub", parent=styles["BodyText"], fontSize=9,
        leading=13, textColor=muted, spaceAfter=7))
    styles.add(ParagraphStyle(name="SectionRoadwise", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=dark, spaceBefore=9, spaceAfter=6))
    styles.add(ParagraphStyle(name="SmallRoadwise", parent=styles["BodyText"],
        fontSize=7.5, leading=10, textColor=muted))
    story = [Paragraph("ROADWISE &nbsp; / &nbsp; INDIA ROAD SAFETY", styles["Heading3"]),
        Paragraph("State &amp; UT accident report", styles["Hero"]),
        Paragraph(f"Reporting year: <b>{year}</b> &nbsp; · &nbsp; Area: <b>{state}</b>" + (f" &nbsp; · &nbsp; Search: <b>{q}</b>" if q else ""), styles["Sub"])]
    if warning:
        story.append(Paragraph(warning, styles["SmallRoadwise"]))
    kpi_data = [["REPORTED ACCIDENTS", "PEOPLE KILLED", "PEOPLE INJURED", "LOCATIONS"],
        [f"{selected_total:,}", f"{int(known_killed.sum()):,}" if len(known_killed) else "Not available",
         f"{int(known_injured.sum()):,}" if len(known_injured) else "Not available",
         str(frame.location.nunique() if "location" in frame else 0)]]
    kpis = Table(kpi_data, colWidths=[64*mm]*4, rowHeights=[8*mm, 13*mm])
    kpis.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),paper),("TEXTCOLOR",(0,0),(-1,0),muted),
        ("TEXTCOLOR",(0,1),(-1,1),dark),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),7),
        ("FONTSIZE",(0,1),(-1,1),15),("LEFTPADDING",(0,0),(-1,-1),9),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LINEBELOW",(0,0),(-1,0),1,gold)]))
    story.extend([kpis, Spacer(1, 5*mm), Paragraph("Location details", styles["SectionRoadwise"])])
    columns = ["Location", "Type", "Accidents", "Killed", "Injured", "Deaths / 100 accidents", "Casualty source"]
    table_data = [columns]
    for _, row in frame.iterrows():
        val = lambda key: "—" if pd.isna(row.get(key)) else f"{float(row[key]):,.1f}" if "per_lakh" in key or key == "fatalities_per_100" else f"{int(row[key]):,}"
        table_data.append([str(row.get("location", "India")), str(row.get("location_type", "")),
            val("accidents_reported"), val("persons_killed"), val("persons_injured"), val("fatalities_per_100"),
            str(row.get("casualty_source") or "—")])
    widths = [47*mm, 15*mm, 26*mm, 23*mm, 23*mm, 34*mm, 48*mm]
    detail = Table(table_data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    detail.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),dark),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),
        ("LEADING",(0,0),(-1,-1),9),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,paper]),
        ("TEXTCOLOR",(0,1),(-1,-1),ink),("GRID",(0,0),(-1,-1),.25,colors.HexColor("#DDD6DD")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),5),
        ("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story.append(detail)
    story.extend([Spacer(1, 3*mm), Paragraph("How to read this report", styles["SectionRoadwise"]),
        Paragraph("Figures are reported police statistics, not live alerts or exact crash locations. Blank values indicate missing comparable State/UT casualty data, not zero. Deaths per 100 accidents are calculated from the selected reported figures; they are severity ratios, not population rates. State boundaries and reporting revisions can affect comparisons.", styles["SmallRoadwise"]),
        Paragraph(f"Source: {source}. State/UT accident counts cover 2015–2024. State/UT killed/injured detail is bundled for 2017–2023; 2015–2016 and 2024 casualty detail is not available in the bundled file. Population-normalized rates are not yet included because a comparable official population denominator has not been imported. Sources: MoRTH Road Accidents in India 2023 and Lok Sabha Unstarred Question 57 (2023).", styles["SmallRoadwise"])])
    def page(canvas, document):
        canvas.saveState()
        w, h = landscape(A4)
        canvas.setFillColor(dark); canvas.rect(0, h-5*mm, w, 5*mm, fill=1, stroke=0)
        canvas.setFont("Helvetica", 7); canvas.setFillColor(muted)
        canvas.drawString(15*mm, 8*mm, "ROADWISE · Government-reported data with context")
        canvas.drawRightString(w-15*mm, 8*mm, f"Page {document.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return Response(buffer.getvalue(), mimetype="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=roadwise_report_{year or 'selected'}.pdf"})


@app.get("/safety")
def safety():
    return render_template("safety.html", **base_context("Safety"))


@app.get("/resources")
def resources():
    return render_template("resources.html", **base_context("Resources"), source_url=SOURCE_URL,
        morth_url=MORTH_2023_URL, totals_url=MORTH_2024_TOTALS_URL,
        kerala_url=KERALA_URL, ncrb_url=NCRB_URL, state_history_url=STATE_HISTORY_URL,
        state_trend_url=STATE_TREND_SOURCE_URL, state_trend_official_url=STATE_TREND_OFFICIAL_URL,
        morth_2019_url=MORTH_2019_URL, morth_2021_url=MORTH_2021_URL,
        casualty_2017_2021_url=CASUALTY_2017_2021_URL)


@app.get("/about")
def about():
    return render_template("about.html", **base_context("About"))


@app.get("/api/summary")
def api_summary():
    frame, source, warning, _, year, _, scope, state, _ = selected_view()
    return jsonify({"year": year, "scope": scope, "state": state, "source": source, "warning": warning,
        "locations": int(frame["location"].nunique()) if "location" in frame and not frame.empty else 0,
        "accidents": int(frame["accidents_reported"].fillna(0).sum()) if not frame.empty else 0,
        "persons_killed": int(frame["persons_killed"].fillna(0).sum()) if not frame.empty else 0,
        "persons_injured": int(frame["persons_injured"].fillna(0).sum()) if not frame.empty else 0})


if __name__ == "__main__":
    app.run(debug=os.getenv("APP_ENV", "").lower() != "production")
