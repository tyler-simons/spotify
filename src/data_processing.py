import pandas as pd
from datetime import timedelta
import calendar
import streamlit as st

def process_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply transformations and feature engineering to the raw spotify data.
    """
    if df.empty:
        return df
    
    # Ensure correct types
    df["endTime"] = pd.to_datetime(df["endTime"])
    
    # Removed legacy +16h offset to ensure accurate UTC-based timezone conversion later
    # df["endTime"] = df["endTime"] + timedelta(hours=16)
    
    df["date"] = df["endTime"].dt.date
    df["dow"] = df["endTime"].dt.weekday
    df["day_of_week_str"] = df["dow"].apply(lambda x: calendar.day_name[x])
    df["time"] = df["endTime"].dt.hour
    
    # isocalendar returns year, week, day
    iso_cal = df["endTime"].dt.isocalendar()
    df["week"] = iso_cal.week
    df["year"] = df["endTime"].dt.year.astype(int)
    
    df["minutesPlayed"] = df["msPlayed"] / 60000
    
    # Filter out short plays (< 10 seconds) roughly
    # Original code had: all_data = all_data[all_data["msPlayed"] > 10000]
    # STATUS: COMMENTED OUT to separate music stats from interaction stats
    # df = df[df["msPlayed"] > 10000].copy()
    
    # Sanitize string columns to avoid NoneType issues during sorting/grouping
    df["artistName"] = df["artistName"].fillna("Unknown Artist").astype(str)
    df["trackName"] = df["trackName"].fillna("Unknown Track").astype(str)
    
    # Platform simplification (e.g. "iOS 15.2" -> "iOS", "OS X 12.1" -> "Desktop")
    # Platform simplification
    def clean_platform(p):
        if not isinstance(p, str): return "Unknown"
        p = p.lower()
        if "ios" in p or "iphone" in p: return "Mobile (iOS)"
        if "android" in p: return "Mobile (Android)"
        if "os x" in p or "mac" in p: return "Desktop (Mac)"
        if "windows" in p or "win32" in p: return "Desktop (Windows)"
        if "google" in p or "chrome" in p or "web" in p: return "Web Player"
        if "desktop" in p: return "Desktop"
        return "Other"

    # Robust column search
    pl_col = None
    for c in ["platform", "Platform", "userAgent", "user_agent"]:
        if c in df.columns:
            pl_col = c
            break
            
    if pl_col:
        df["platform_clean"] = df[pl_col].apply(clean_platform)
    else:
        df["platform_clean"] = "Unknown"

    return df

def get_valid_music_df(df: pd.DataFrame) -> pd.DataFrame:
    """Returns dataframe filtered for actual music listening (exclude skips/podcasts)."""
    return df[
        (df["msPlayed"] > 30000) & # Only songs played > 30s
        (df["artistName"] != "Unknown Artist")
    ].copy()

def get_top_artists(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate top artists by total minutes played, including a monthly trend line.
    """
    # Use strict music filter
    df_music = get_valid_music_df(df)
    
    # Include every qualifying artist, even in small uploaded histories.
    df_filtered = df_music.copy()
    
    # 1. Get the aggregate totals first to identify Top N
    top_stats = (
        df_filtered.groupby("artistName")["minutesPlayed"]
        .sum(numeric_only=True)
        .sort_values(ascending=False)
    )
    
    # we'll return top 50 with trends (calculating trend for ALL might be slow, so let's limit if needed, 
    # but for now we'll do all significant ones)
    
    # 2. Calculate Trends
    # Create a month column for grouping
    df_filtered["month_idx"] = pd.to_datetime(df_filtered["date"]).dt.to_period("M")
    
    # Group by Artist + Month
    monthly_activity = (
        df_filtered.groupby(["artistName", "month_idx"])["minutesPlayed"]
        .sum()
        .reset_index()
    )
    
    # Pivot to verify we have all months for the selected period?
    # Actually, for a sparkline, 'relative' trend is often enough, but missing zeros can be misleading.
    # Let's ensure we cover the range present in the data.
    all_months = pd.period_range(df_filtered["month_idx"].min(), df_filtered["month_idx"].max(), freq='M')
    
    # Helper to get trend list
    def get_trend_list(group):
        # Reindex to full date range filling 0
        s = group.set_index("month_idx")["minutesPlayed"]
        s = s.reindex(all_months, fill_value=0)
        # Explicit conversion to python float to avoid int64 serialization error
        return [float(x) for x in s]

    trends = monthly_activity.groupby("artistName").apply(get_trend_list).rename("trend")
    
    # 3. Combine
    result = top_stats.to_frame().join(trends)
    result = result.reset_index()
    
    # Convert to hours for friendlier display
    result["Hours"] = result["minutesPlayed"] / 60
    
    return result

def get_top_songs(df: pd.DataFrame, n: int = 50) -> pd.DataFrame:
    """
    Get top N songs by play count with trend lines.
    """
    df_music = get_valid_music_df(df)
    
    # 1. Get Top N by Count
    top_songs_stats = (
        df_music.groupby(["artistName", "trackName"])["msPlayed"]
        .count()
        .sort_values(ascending=False)
        .head(n)
        .rename("Listens")
        .reset_index()
    )
    
    # 2. Calculate Trend for these Top N only (optimization)
    # Filter original data to only include these top songs
    # Create a composite key for easier filtering
    df_music["song_key"] = df_music["artistName"] + "|||" + df_music["trackName"]
    top_keys = set(top_songs_stats["artistName"] + "|||" + top_songs_stats["trackName"])
    
    subset = df_music[df_music["song_key"].isin(top_keys)].copy()
    
    subset["month_idx"] = pd.to_datetime(subset["date"]).dt.to_period("M")
    all_months = pd.period_range(subset["month_idx"].min(), subset["month_idx"].max(), freq='M')
    
    monthly_counts = (
        subset.groupby(["song_key", "month_idx"])["msPlayed"]
        .count()
        .reset_index()
        .rename(columns={"msPlayed": "count"})
    )
    
    def get_trend_list(group):
        s = group.set_index("month_idx")["count"]
        s = s.reindex(all_months, fill_value=0)
        # Explicit conversion to python float
        return [float(x) for x in s]
        
    trends = monthly_counts.groupby("song_key").apply(get_trend_list).rename("trend")
    
    # Match back
    top_songs_stats["song_key"] = top_songs_stats["artistName"] + "|||" + top_songs_stats["trackName"]
    result = top_songs_stats.merge(trends, left_on="song_key", right_index=True)
    
    return result.drop(columns=["song_key"])

def get_hourly_activity(df: pd.DataFrame, timezone: str = "UTC") -> pd.DataFrame:
    """
    Groups data by hour of day, adjusting for timezone.
    """
    df = df.copy()
    
    # Check for endTime column (standard history) or ts (extended)
    if "endTime" in df.columns:
        # Convert to datetime, assume UTC if naive (datasets vary, but usually UTC)
        dt_series = pd.to_datetime(df["endTime"], utc=True)
        # Convert to target timezone
        dt_series = dt_series.dt.tz_convert(timezone)
        
        df["local_hour"] = dt_series.dt.hour
    elif "date" in df.columns:
         # Fallback: Parsing 'date' + 'time' into a naive datetime is risky without offsets.
         # But if we must:
         # For now, just rely on raw 'time' if timezone conversion isn't possible
         df["local_hour"] = df["time"]
    else:
        df["local_hour"] = df["time"]

    # Aggregate
    hourly_counts = (
        df.groupby("local_hour")["msPlayed"]
        .count()
        .reset_index()
        .rename(columns={"msPlayed": "Count", "local_hour": "time"})
    )
    
    # Fill missing hours 0-23
    all_hours = pd.DataFrame({"time": range(24)})
    hourly_counts = pd.merge(all_hours, hourly_counts, on="time", how="left").fillna(0)
    
    # Create nice Format (e.g. "6:00" or "6 PM")
    def format_hour(h):
        return f"{int(h)}:00"
        
    hourly_counts["hour_label"] = hourly_counts["time"].apply(format_hour)
    
    return hourly_counts

def get_platform_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregates play count by platform."""
    # pandas 2.0+ value_counts().reset_index() returns [name, "count"]
    # We want to map the name (platform_clean) to "Platform" and "count" to "Plays"
    return df["platform_clean"].value_counts().reset_index().rename(
        columns={"platform_clean": "Platform", "count": "Plays"}
    )

def get_interaction_stats(df: pd.DataFrame) -> dict:
    """Calculates skip rates and context usage."""
    total = len(df)
    if total == 0: return {}
    
    # Check if 'skipped' column exists and has data
    skips = df["skipped"].sum() if "skipped" in df.columns else 0
    skip_rate = (skips / total) * 100
    
    # Reason Start
    if "reason_start" in df.columns:
        start_reasons = df["reason_start"].value_counts(normalize=True).mul(100).head(3).to_dict()
    else:
        start_reasons = {}
        
    return {
        "skip_rate": skip_rate,
        "shuffles": df["shuffle"].sum() if "shuffle" in df.columns else 0,
        "top_start_reasons": start_reasons
    }

def filter_by_artist(df: pd.DataFrame, artist_name: str) -> pd.DataFrame:
    """Return data filter by artist name, or all if 'All Artists'."""
    if artist_name == "All Artists":
        return df
    return df[df["artistName"] == artist_name]
