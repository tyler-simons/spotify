import altair as alt
import pandas as pd
import streamlit as st
from .utils import get_month_weeks, build_date_from_pieces
import calendar
from datetime import datetime

CORNER_RADIUS = 4

def chart_top_artists(top_artists_df: pd.DataFrame) -> alt.Chart:
    """
    Bar chart of top artists by hours played.
    Expects dataframe with 'artistName' and 'Hours'.
    """
    # Take top 40 for the chart
    data = top_artists_df.head(40)
    top_artists_order = data["artistName"].tolist()

    chart = (
        alt.Chart(data)
        .mark_bar(width=40, cornerRadius=CORNER_RADIUS)
        .encode(
            y=alt.Y(
                "artistName",
                sort=top_artists_order,
                title="Artist",
                axis=alt.Axis(labels=False), # Hide axis labels for cleaner look if using tooltips/text
            ),
            x=alt.X(
                "Hours:Q",
                title="Hours Listened", # Changed title
                axis=alt.Axis(format="d"),
            ),
            color=alt.Color(
                "artistName:N",
                title="Artist",
                sort=top_artists_order,
                scale=alt.Scale(scheme="tealblues"), # Underwater scheme
                legend=None,
            ),
            tooltip=["artistName", "Hours"]
        )
        .properties(height=500)
    )
    
    # Removed text labels
    # text = chart.mark_text(
    #     align="left", baseline="middle", dx=3, fontSize=12
    # ).encode(text=alt.Text("artistName:N"))

    return chart # Removed + text

def chart_top_songs(df: pd.DataFrame) -> alt.Chart:
    """
    Bar chart for top songs.
    """
    # Calculate rank for sorting
    df["rank"] = df["Listens"].rank(ascending=False, method="first")
    sorted_df = df.sort_values("rank")
    
    songs_order = sorted_df["trackName"].tolist()
    
    chart = (
        alt.Chart(sorted_df)
        .mark_bar()
        .encode(
            x=alt.X("Listens:Q", title="Play Count"),
            y=alt.Y("trackName:N", title=None, axis=alt.Axis(limit=300), sort="-x"),
            color=alt.Color(
                "artistName:N", 
                title="Artist", 
                # Halocline Palette: Navy -> Teal -> Pink
                scale=alt.Scale(range=["#0E215C", "#00A68F", "#EB5E89", "#2C64B8", "#F7A35C"]),
                legend=None
            ),
            tooltip=[
                alt.Tooltip("trackName", title="Track"),
                alt.Tooltip("artistName", title="Artist"),
                alt.Tooltip("Listens", title="Plays")
            ]
        )
        .properties(height=max(400, len(df) * 20))
    )
    
    return chart

def chart_play_history(df: pd.DataFrame, title: str, date_range: tuple = None) -> alt.Chart:
    """
    Bar chart of minutes played over time (aggregated by month).
    Ensures that all months in the selected date_range are shown.
    """
    df = df.copy()
    
    # Determine the date range to cover
    if date_range and len(date_range) == 2:
        start_date = date_range[0]
        end_date = date_range[1]
    else:
        # Fallback if no valid range provided
        if df.empty:
             start_date = datetime.now().date().replace(month=1, day=1)
             end_date = datetime.now().date().replace(month=12, day=31)
        else:
             start_date = df["date"].min()
             end_date = df["date"].max()
             
    # Ensure start/end are datetime-compatible for pandas
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    
    # Generate complete sequence of months
    # We use 'MS' (month start) to align nicely
    full_months = pd.period_range(start=start_ts, end=end_ts, freq='M').to_timestamp()
    dates_df = pd.DataFrame({"month_start": full_months})

    # Prepare data for merge
    # Convert 'date' to datetime if not already
    df["date"] = pd.to_datetime(df["date"])
    df["month_start"] = df["date"].dt.to_period("M").dt.to_timestamp()
    agg_df = df.groupby("month_start")["minutesPlayed"].sum().reset_index()
    
    # Merge with full range to fill 0s
    merged_df = pd.merge(dates_df, agg_df, on="month_start", how="left").fillna(0)
    
    # Format for chart (Year-Month string looks cleaner on categorical/ordinal axis as requested)
    # Using %b %Y (e.g. "Jan 2025") for better readability
    merged_df["YearMonth"] = merged_df["month_start"].dt.strftime("%b %Y")
    
    chart = (
        alt.Chart(merged_df)
        .mark_bar(color="#147eb2", cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("yearmonth(month_start):T", title="Month", axis=alt.Axis(format="%b %Y", labelAngle=-45)),
            y=alt.Y("minutesPlayed:Q", title="Minutes played", scale=alt.Scale(zero=True), axis=alt.Axis(format=",.1~f", grid=True, tickCount=5)),
            tooltip=[
                alt.Tooltip("yearmonth(month_start):T", title="Month", format="%B %Y"),
                alt.Tooltip("minutesPlayed:Q", title="Minutes played", format=",.1f"),
            ],
        )
        .properties(height=360, title=title)
    )
    return chart

def chart_calendar_heatmap(df: pd.DataFrame, year: int, artist_name: str, quarter: int = None) -> alt.Chart:
    """Daily listening by calendar date; dates outside the observed span stay blank."""
    year_df = df[pd.to_datetime(df["date"]).dt.year == year].copy()
    daily = year_df.groupby("date", as_index=False)["minutesPlayed"].sum()
    daily["date"] = pd.to_datetime(daily["date"])
    dates = pd.DataFrame({"date": pd.date_range(daily["date"].min(), daily["date"].max())})
    daily = dates.merge(daily, on="date", how="left").fillna({"minutesPlayed": 0})
    jan1 = pd.Timestamp(year=year, month=1, day=1)
    daily["week_index"] = ((daily["date"].dt.dayofyear - 1 + jan1.weekday()) // 7).astype(int)
    daily["weekday"] = daily["date"].dt.day_name()
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    labels = ["0", "< 30", "30–<60", "60–<120", "120–<240", "240+"]
    daily["band"] = pd.cut(daily["minutesPlayed"], bins=[-0.01, 0, 30, 60, 120, 240, float("inf")], labels=labels, right=False, include_lowest=True)
    # An exact zero needs its own band when using left-closed intervals.
    daily["band"] = daily["band"].astype(object)
    daily.loc[daily["minutesPlayed"] == 0, "band"] = "0"
    starts = [pd.Timestamp(year=year, month=m, day=1) for m in range(1, 13)]
    month_weeks = [int((d.dayofyear - 1 + jan1.weekday()) // 7) for d in starts]
    expr = " ".join(f"datum.value == {week} ? '{calendar.month_abbr[i]}' :" for i, week in enumerate(month_weeks, 1)) + " ''"
    max_week = int((pd.Timestamp(year=year, month=12, day=31).dayofyear - 1 + jan1.weekday()) // 7)
    if quarter is not None:
        first_month = 1 + 3 * (quarter - 1)
        last_month = first_month + 2
        daily = daily[daily["date"].dt.month.between(first_month, last_month)]
        first_week = month_weeks[first_month - 1]
        last_date = pd.Timestamp(year=year, month=last_month, day=calendar.monthrange(year, last_month)[1])
        last_week = int((last_date.dayofyear - 1 + jan1.weekday()) // 7)
        domain = list(range(first_week, last_week + 1))
        ticks = month_weeks[first_month - 1:last_month]
    else:
        domain = list(range(max_week + 1))
        ticks = month_weeks
    return (alt.Chart(daily).mark_rect(cornerRadius=2, strokeWidth=1, stroke="#ffffff").encode(
        x=alt.X("week_index:O", title=None, scale=alt.Scale(domain=domain),
                axis=alt.Axis(values=ticks, labelExpr=expr, labelAngle=0, labelOverlap=False, ticks=False, domain=False)),
        y=alt.Y("weekday:O", title=None, sort=days, scale=alt.Scale(domain=days), axis=alt.Axis(labelOverlap=False, labelLimit=90, ticks=False, domain=False)),
        color=alt.Color("band:N", title="Minutes per day", sort=labels,
                        scale=alt.Scale(domain=labels, range=["#e3edf1", "#bfdde9", "#85c2dc", "#4e9fc4", "#1c73a4", "#104667"]),
                        legend=None),
        tooltip=[alt.Tooltip("date:T", title="Date", format="%b %d, %Y"),
                 alt.Tooltip("minutesPlayed:Q", title="Minutes played", format=",.1f")]
    ).properties(height=260))


def chart_hourly_activity(df: pd.DataFrame) -> alt.Chart:
    """Qualifying music plays by local hour, including zero-count hours."""
    return (alt.Chart(df).mark_bar(color="#147eb2", cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("time:O", title="Hour of day", axis=alt.Axis(labelAngle=0, labelOverlap=True)),
        y=alt.Y("Count:Q", title="Qualifying plays", scale=alt.Scale(zero=True), axis=alt.Axis(grid=True, tickCount=5, format=",d")),
        tooltip=[alt.Tooltip("hour_label:N", title="Hour"), alt.Tooltip("Count:Q", title="Plays", format=",.0f")]
    ).properties(height=300))

def chart_platform_usage(df: pd.DataFrame) -> alt.Chart:
    """Compare qualifying plays by the platform reported in the export."""
    data = df.copy()
    total = data["Plays"].sum()
    data["share"] = data["Plays"] / total if total else 0
    return (alt.Chart(data).mark_bar(color="#147eb2", cornerRadiusEnd=3, size=22).encode(
        y=alt.Y("Platform:N", sort="-x", title=None,
                axis=alt.Axis(labelLimit=180, labelOverlap=False)),
        x=alt.X("Plays:Q", title="Qualifying plays", scale=alt.Scale(zero=True),
                axis=alt.Axis(grid=True, tickCount=5, format=",d")),
        tooltip=[alt.Tooltip("Platform:N", title="Platform"),
                 alt.Tooltip("Plays:Q", title="Qualifying plays", format=",d"),
                 alt.Tooltip("share:Q", title="Share of qualifying plays", format=".1%")]
    ).properties(height=max(160, min(320, len(data) * 42))))
