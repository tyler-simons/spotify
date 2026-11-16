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
    st.write("Explore the artists, tracks, and rhythms in your listening history.")
    st.caption("A data exploration by [Tyler Simons](https://tylersimons.com/) · Music by [halocline](https://open.spotify.com/artist/5ofIlDx8lax1NOi2stXaTn)")
    
    # --- Top Controls (Framed) ---
    with st.container(border=True):
        st.subheader("Build your report")
        
        c1, c2 = st.columns([1, 1])
        
        with c1:
            st.markdown("**Listening history**")
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
            st.markdown("**Time range**")
            
            # --- Data Loading ---
            if not uploaded_files:
                raw_df = load_data(data_dir="example_data_2")
            else:
                raw_df = load_data(uploaded_files=uploaded_files)

            if raw_df.empty:
                st.warning("Upload data to generate your report.")
                st.stop()
                
            required = {"endTime", "msPlayed", "artistName", "trackName"}
            if not required.issubset(raw_df.columns):
                st.error("These files do not look like Spotify streaming history. Upload the StreamingHistory JSON files from your Spotify data export.")
                st.stop()
            try:
                df = process_data(raw_df)
            except (ValueError, TypeError, KeyError):
                st.error("We could not read this listening history. Check the files and try again.")
                st.stop()

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
    st.caption(f"Showing {start_date:%b %d, %Y} – {end_date:%b %d, %Y} · UTC dates · Ranges end at the latest entry in the export.")

    # --- Section 1: Executive Summary ---
    
    # Calculate High Level Stats
    music_df = get_valid_music_df(df) # Filtered for music
    if music_df.empty:
        st.info("No music tracks were found in this date range. Try another range or upload a different history file.")
        st.stop()
    total_min = music_df["minutesPlayed"].sum()
    total_hours = total_min / 60
    
    unique_artists = music_df["artistName"].nunique()
    unique_tracks = music_df[["artistName", "trackName"]].drop_duplicates().shape[0]
    
    # Enhanced Metrics Display
    st.subheader("At a glance")
    st.caption("Music plays longer than 30 seconds. Listening time is summed across qualifying plays.")
    
    # Single row of 5 key metrics
    cols = st.columns(5)
    
    active_days = music_df['date'].nunique()
    avg_daily = total_hours / active_days if active_days else 0
    
    cols[0].metric("Listening time", f"{total_hours:,.1f} hrs" if total_hours >= 1 else f"{total_min:,.1f} min", help="Total time spent listening to music in the selected period.")
    cols[1].metric("Artists", f"{unique_artists:,}")
    cols[2].metric("Tracks", f"{unique_tracks:,}")
    cols[3].metric("Active days", f"{active_days:,}")
    cols[4].metric("Per active day", f"{avg_daily:.1f} hrs" if avg_daily >= 1 else f"{avg_daily * 60:.1f} min", help="Listening time divided by days with a qualifying music play.")

    st.divider()

    # --- Section 2: Listening Habits ---
    st.header("Listening habits")
    
    st.subheader("Listening over time")
    st.caption("Minutes of music per month · partial months reflect the selected date range.")
    st.altair_chart(chart_play_history(music_df, "", date_range=selected_dates), use_container_width=True)

    platform_stats = get_platform_stats(music_df)
    if (platform_stats["Platform"] != "Unknown").any():
        st.subheader("Listening by device")
        st.caption("Qualifying plays by reported platform. Other includes platforms the export does not identify clearly.")
        st.altair_chart(chart_platform_usage(platform_stats), use_container_width=True)

    # Hourly Activity
    st.subheader("Your daily rhythm")
    st.caption("Qualifying music plays by local hour. Spotify timestamps are treated as UTC.")
    
    with st.expander("Timezone Settings"):
        # Common timezones to choose from
        common_timezones = [
            "UTC", "US/Pacific", "US/Eastern", "US/Central", "US/Mountain",
            "Europe/London", "Europe/Paris", "Europe/Berlin", 
            "Asia/Tokyo", "Australia/Sydney"
        ]
        selected_tz = st.selectbox("Select Display Timezone", common_timezones, index=1) # Default to US/Pacific

    hourly_stats = get_hourly_activity(music_df, timezone=selected_tz)
    st.altair_chart(chart_hourly_activity(hourly_stats), use_container_width=True)

    st.divider()
    

    # --- Section 4: The Charts ---
    st.header("Your favorites")
    
    xc1, xc2 = st.columns(2)
    with xc1:
        st.subheader("Top artists")
        st.caption("Ranked by listening hours · the small trend shows monthly listening.")
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
        st.subheader("Top tracks")
        st.caption("Ranked by qualifying plays · the small trend shows monthly plays.")
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
    st.header("Artist deep dive")
    
    # Sort artists by popularity (Total Minutes) in the filtered timeframe
    if not music_df.empty:
        rank_df = music_df.groupby("artistName")["minutesPlayed"].sum().sort_values(ascending=False)
        valid_artists = rank_df.index.tolist()
    else:
        valid_artists = []
        
    selected_artist = st.selectbox("Choose an artist", ["All Artists"] + valid_artists)
    
    artist_subset = filter_by_artist(music_df, selected_artist)
    
    if not artist_subset.empty:
            st.altair_chart(
                chart_play_history(artist_subset, f"History: {selected_artist}", date_range=selected_dates), 
                use_container_width=True
            )
            st.subheader("Listening calendar")
            st.caption("Minutes of music per day · UTC dates · Blank cells fall outside the observed span.")
            available_years = sorted(artist_subset["year"].unique(), reverse=True)
            year_col, _ = st.columns([1, 3])
            with year_col:
                sel_year = st.selectbox("Year", available_years)
            st.markdown(
                '<div style="display:flex;flex-wrap:wrap;gap:0.4rem 1rem;align-items:center;font-size:0.85rem;color:#335970;margin:0.5rem 0 1rem">'
                '<strong>Minutes per day</strong>' + "".join(
                    f'<span><span aria-hidden="true" style="display:inline-block;width:0.75rem;height:0.75rem;background:{color};border:1px solid #9cb9c6;margin-right:0.3rem"></span>{label}</span>'
                    for label, color in [("0", "#e3edf1"), ("&lt;30", "#bfdde9"), ("30–&lt;60", "#85c2dc"), ("60–&lt;120", "#4e9fc4"), ("120–&lt;240", "#1c73a4"), ("240+", "#104667")]
                ) + "</div>", unsafe_allow_html=True
            )
            for first_quarter in (1, 3):
                quarter_columns = st.columns(2)
                for offset, col in enumerate(quarter_columns):
                    quarter = first_quarter + offset
                    with col:
                        st.markdown(f"**{['January – March', 'April – June', 'July – September', 'October – December'][quarter - 1]}**")
                        st.altair_chart(
                            chart_calendar_heatmap(artist_subset, sel_year, selected_artist, quarter),
                            use_container_width=True
                        )
            st.caption("Days within the observed span with no qualifying plays are shown as zero. Hover for the exact date and minutes.")

if __name__ == "__main__":
    main()


