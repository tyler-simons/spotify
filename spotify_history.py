import streamlit as st
from datetime import timedelta
from src.data_loader import load_data
from src.data_processing import (
    process_data, 
    get_top_artists, 
    get_top_songs, 
    filter_by_artist, 
    get_hourly_activity, 
    get_platform_stats,
    get_interaction_stats,
    get_valid_music_df
)
from src.visualizations import (
    chart_top_artists, 
    chart_top_songs, 
    chart_play_history, 
    chart_calendar_heatmap,
    chart_hourly_activity,
    chart_platform_usage
)

# Config
st.set_page_config(layout="wide", page_title="Listening Report", page_icon=":material/water_drop:")


def main():
    st.caption("TYLER SIMONS  /  DATA EXPLORATIONS")
    st.title("Spotify Dive Report")
    st.markdown("Upload your streaming history to visualize your trends, discover top artists, and analyze your listening habits. *Created by [halocline](https://open.spotify.com/artist/5ofIlDx8lax1NOi2stXaTn).*")
    
    # --- Top Controls (Framed) ---
    with st.container(border=True):
        st.subheader(":material/settings: Report Settings")
        
        c1, c2 = st.columns([1, 1])
        
        with c1:
            st.markdown("**1. Upload Data**")
            uploaded_files = st.file_uploader(
                "Select your `StreamingHistory` JSON files", 
                type="json", 
                accept_multiple_files=True,
                label_visibility="collapsed"
            )
            
        with st.expander(":material/info: How to get extended history", expanded=False):
            st.markdown("""
            1. Go to **[Spotify Privacy](https://www.spotify.com/us/account/privacy/)**, scroll to **Download your data**.
            2. Check **"Extended streaming history"**.
            3. Wait for email (up to 30 days).
            4. Upload the `.json` files here.
            """)
            
        with c2:
            st.markdown("**2. Filter Dates**")
            
            # --- Data Loading ---
            if not uploaded_files:
                raw_df = load_data(data_dir="example_data_2")
            else:
                raw_df = load_data(uploaded_files=uploaded_files)

            if raw_df.empty:
                st.warning("Upload data to generate your report.")
                st.stop()
                
            # Process Data
            df = process_data(raw_df)

            min_date = df["date"].min()
            max_date = df["date"].max()
            
            # Date Range Selector (Radio Buttons Only)
            range_option = st.radio(
                "Filter Date Range",
                ["All Time", "Past Year", "Past 2 Years"],
                index=1, # Default to Past Year
                horizontal=True,
                label_visibility="collapsed"
            )
            
            if range_option == "All Time":
                start_date = min_date
            elif range_option == "Past Year":
                start_date = max(min_date, max_date - timedelta(days=365))
            elif range_option == "Past 2 Years":
                start_date = max(min_date, max_date - timedelta(days=730))
            
            end_date = max_date
            selected_dates = (start_date, end_date)

    # Validate (just in case)
    if not selected_dates:
        st.stop()
        
    start_date, end_date = selected_dates

    # Apply Filter
    mask = (df["date"] >= start_date) & (df["date"] <= end_date)
    df = df[mask]
    
    if df.empty:
        st.warning(f"No data found for period {start_date} to {end_date}.")
        st.stop()
        
    st.divider()

    if not uploaded_files:
        st.caption("Example listening history · Upload your own files to explore your data.")
    st.caption(f"Showing {start_date:%b %d, %Y} – {end_date:%b %d, %Y}")

    # --- Section 1: Executive Summary ---
    
    # Calculate High Level Stats
    music_df = get_valid_music_df(df) # Filtered for music
    if music_df.empty:
        st.info("No music tracks were found in this date range. Try another range or upload a different history file.")
        st.stop()
    total_min = music_df["minutesPlayed"].sum()
    total_hours = total_min / 60
    
    unique_artists = music_df["artistName"].nunique()
    unique_tracks = music_df["trackName"].nunique()
    
    # Enhanced Metrics Display
    st.subheader(":material/analytics: At a Glance")
    
    # Single row of 5 key metrics
    cols = st.columns(5)
    
    avg_daily = total_hours / df['date'].nunique() if df['date'].nunique() > 0 else 0
    
    cols[0].metric("Listening time", f"{total_hours:,.1f} hrs", help="Total time spent listening to music in the selected period.")
    cols[1].metric("Unique Artists", f"{unique_artists:,}")
    cols[2].metric("Unique Tracks", f"{unique_tracks:,}")
    cols[3].metric("Active Days", f"{df['date'].nunique()}")
    cols[4].metric("Avg Daily Listen", f"{avg_daily:.1f} hrs")

    st.divider()

    # --- Section 2: Listening Habits ---
    st.header(":material/calendar_month: Listening Habits")
    
    # Calculate stats first to determine layout
    platform_stats = get_platform_stats(df)
    has_known_devices = platform_stats[platform_stats["Platform"] != "Unknown"].shape[0] > 0
    
    if has_known_devices:
        col_habits_1, col_habits_2 = st.columns([2, 1])
        
        with col_habits_1:
            st.subheader("Activity Over Time")
            history_chart = chart_play_history(music_df, "", date_range=selected_dates)
            st.altair_chart(history_chart, use_container_width=True)
            
        with col_habits_2:
            st.subheader("Devices")
            st.altair_chart(chart_platform_usage(platform_stats), use_container_width=True)
            
    else:
        # Full width if no device data
        st.subheader("Activity Over Time")
        history_chart = chart_play_history(music_df, "", date_range=selected_dates)
        st.altair_chart(history_chart, use_container_width=True)
            
    # Hourly Activity
    st.subheader("Your Daily Rhythm")
    
    with st.expander("Timezone Settings"):
        # Common timezones to choose from
        common_timezones = [
            "UTC", "US/Pacific", "US/Eastern", "US/Central", "US/Mountain",
            "Europe/London", "Europe/Paris", "Europe/Berlin", 
            "Asia/Tokyo", "Australia/Sydney"
        ]
        selected_tz = st.selectbox("Select Display Timezone", common_timezones, index=1) # Default to US/Pacific

    hourly_stats = get_hourly_activity(df, timezone=selected_tz)
    st.altair_chart(chart_hourly_activity(hourly_stats), use_container_width=True)

    st.divider()
    
    # --- Section 3: Interactions & Flow ---
    stats = get_interaction_stats(df)
    

    st.divider()

    # --- Section 4: The Charts ---
    st.header(":material/trophy: The Favorites")
    
    xc1, xc2 = st.columns(2)
    with xc1:
        st.subheader("Top Artists (Music)")
        top_artists = get_top_artists(df)
        
        st.dataframe(
            top_artists.head(50),
            column_order=["artistName", "trend", "Hours"], 
            hide_index=True,
            use_container_width=True,
            column_config={
                "artistName": st.column_config.TextColumn("Artist"),
                "trend": st.column_config.LineChartColumn(
                    "Monthly Trend",
                    y_min=0,
                ),
                "Hours": st.column_config.ProgressColumn(
                    "Hours", 
                    format="%.1f", 
                    min_value=0, 
                    max_value=float(top_artists["Hours"].max())
                ),
                "minutesPlayed": None 
            },
            height=500
        )
        
    with xc2:
        st.subheader("Top Tracks")
        top_songs = get_top_songs(df)
        
        st.dataframe(
            top_songs,
            column_order=["trackName", "artistName", "trend", "Listens"],
            hide_index=True,
            use_container_width=True,
            column_config={
                "trackName": st.column_config.TextColumn("Track"),
                "artistName": st.column_config.TextColumn("Artist"),
                "trend": st.column_config.LineChartColumn(
                    "Monthly Trend",
                    y_min=0
                ),
                "Listens": st.column_config.ProgressColumn(
                    "Plays", 
                    format="%d", 
                    min_value=0, 
                    max_value=int(top_songs["Listens"].max())
                )
            },
            height=500
        )
        
    # --- Section 5: Deep Dive ---
    st.divider()
    st.header(":material/search: Artist Deep Dive")
    
    # Sort artists by popularity (Total Minutes) in the filtered timeframe
    if not music_df.empty:
        rank_df = music_df.groupby("artistName")["minutesPlayed"].sum().sort_values(ascending=False)
        valid_artists = rank_df.index.tolist()
    else:
        valid_artists = []
        
    selected_artist = st.selectbox("Select Artist", ["All Artists"] + valid_artists)
    
    artist_subset = filter_by_artist(music_df, selected_artist)
    
    if not artist_subset.empty:
            st.altair_chart(
                chart_play_history(artist_subset, f"History: {selected_artist}", date_range=selected_dates), 
                use_container_width=True
            )
            # Heatmap
            available_years = sorted(artist_subset["year"].unique(), reverse=True)
            sel_year = st.selectbox("Year", available_years)
            st.altair_chart(
                chart_calendar_heatmap(artist_subset, sel_year, selected_artist),
                use_container_width=True
            )

if __name__ == "__main__":
    main()


