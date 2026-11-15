import altair as alt
import pandas as pd
import streamlit as st
from .utils import get_month_weeks, build_date_from_pieces
import calendar

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
            y=alt.Y("minutesPlayed:Q", title="Minutes played", scale=alt.Scale(zero=True), axis=alt.Axis(format=",.0f", grid=True, tickCount=5)),
            tooltip=[
                alt.Tooltip("yearmonth(month_start):T", title="Month", format="%B %Y"),
                alt.Tooltip("minutesPlayed:Q", title="Minutes played", format=",.0f"),
            ],
        )
        .properties(height=360, title=title)
    )
    return chart

def chart_calendar_heatmap(df: pd.DataFrame, year: int, artist_name: str) -> alt.Chart:
    """
    Calendar heatmap for a specific year.
    """
    # Ensure all days are covered or handle standard heatmap logic
    # ... (omitted prep code same as before) ...
    
    # We need to ensure types for grouping
    df_year = df[df["year"] == year].copy()
    
    # Simplify for heatmap
    keep_cols = ["date", "minutesPlayed", "day_of_week_str", "week", "year"]
    # Ensure these cols exist
    for c in keep_cols:
        if c not in df_year.columns:
            # Should have been processed in data_processing
            pass

    # Aggregating
    heatmap_agg = (
        df_year.groupby(["week", "day_of_week_str"])["minutesPlayed"]
        .sum().reset_index()
    )
    
    # Bucketing
    bucket_labels = ["0 min", "1-5 min", "5-15 min", "15-60 min", "60+ min"]
    heatmap_agg["min_bucket"] = pd.cut(
        heatmap_agg["minutesPlayed"], bins=[-1, 1, 5, 15, 60, 100000], labels=bucket_labels
    )
    
    # We need a way to label months on the x-axis (weeks)
    # This requires the helper function from utils
    month_weeks = get_month_weeks(year)
    
    # Format label expression for Altair
    format_label_expr = "||".join(
        [
            f"datum.value === {month_week} ?  '{month}': ''"
            for month, month_week in zip(calendar.month_abbr[1:], month_weeks)
        ]
    )
    
    # Sort days
    days_order = [
         "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
    ]
    
    chart = (
        alt.Chart(heatmap_agg)
        .mark_rect(cornerRadius=2)
        .encode(
            x=alt.X(
                "week:O",
                title="Week",
                # Force domain to show all weeks 1-53 to keep chart width consistent
                scale=alt.Scale(domain=list(range(1, 54))),
                axis=alt.Axis(labelExpr=format_label_expr, labelAngle=0)
            ),
            y=alt.Y(
                "day_of_week_str:O",
                title=None,
                sort=days_order
            ),
            color=alt.Color(
                "min_bucket:O",
                title="Minutes Played",
                scale=alt.Scale(
                     # Halocline Heatmap: White -> Light Cyan -> Teal -> Navy
                     range=["#F2F8FA", "#CDE8E6", "#00A68F", "#2C64B8", "#0E215C"],
                     domain=bucket_labels
                ),
                legend=alt.Legend(orient="bottom")
            ),
            tooltip=[
                alt.Tooltip("week", title="Week"),
                alt.Tooltip("day_of_week_str", title="Day"),
                alt.Tooltip("minutesPlayed", title="Minutes", format=",.0f")
            ]
        )
        .properties(title=f"Listening History for {artist_name} in {year}")
        .configure_scale(bandPaddingInner=0.2)
    )
    
    return chart

def chart_hourly_activity(df: pd.DataFrame) -> alt.Chart:
    """
    Bar chart of listening count by hour of day.
    """
    # Ensure correct sorting of hours 0-23
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("hour_label:N", title="Hour of Day", sort=alt.EncodingSortField(field="time", order="ascending"), axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Count:Q", title="Songs Played"),
            color=alt.Color(
                "Count:Q", 
                # Single hue gradient: Teal -> Navy
                scale=alt.Scale(range=["#00A68F", "#0E215C"]), 
                legend=None
            ),
            tooltip=["hour_label", "Count"]
        )
        .properties(title="When do you listen?", height=300)
    )
    return chart

def chart_platform_usage(df: pd.DataFrame) -> alt.Chart:
    """
    Donut chart of platform usage.
    """
    base = alt.Chart(df).encode(
        theta=alt.Theta("Plays", stack=True)
    )

    pie = base.mark_arc(outerRadius=120, innerRadius=80).encode(
        color=alt.Color(
            "Platform", 
            # Halocline categorical palette
            scale=alt.Scale(range=["#00A68F", "#EB5E89", "#0E215C", "#F7A35C", "#2C64B8"]),
            legend=alt.Legend(title="Platform")
        ),
        order=alt.Order("Plays", sort="descending"),
        tooltip=["Platform", "Plays"]
    )

    chart = (
        pie
        .properties(title="Devices")
    )
    return chart

