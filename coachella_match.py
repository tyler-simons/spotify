import json
import pandas as pd
import os
import streamlit as st
from datetime import datetime, timedelta
import datetime as dt
import altair as alt
import numpy as np
import calplot as cp
import calendar
from streamlit_extras.badges import badge


st.set_page_config(layout="wide")
corner_radius = 4

days_of_week = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


# Get the week number of the first day for each month for the given year
def get_month_weeks(year):
    month_weeks = []
    for month in range(1, 13):
        if month == 12:
            first_day = dt.date(year, month, 15)
        else:
            first_day = dt.date(year, month, 3)
        first_day_week = first_day.isocalendar()[1]
        month_weeks.append(first_day_week)
    return month_weeks


# Filter for the minimum minutes played grouped by artist
st.title("🎡 Coachella 2023 Spotify Match 🎶")
st.markdown("Match your Spotify listening history with the Coachella 2023 lineup.")

# Write an about section with st.markdown
col1, col2 = st.columns(2)
col2.markdown(
    """
    ## About
     There are **so many** artists playing Coachella that it can be hard to keep track of all of them. This app takes your Spotify listening history and matches it with the Coachella 2023 lineup. It then shows you the total minutes you've listened to each match artist, who your top is, when they're playing and plots it all. We **do not** save your data and all the code is __open source__. The app is still in beta so please let me know if you have any feedback or suggestions! 
    """
)

col1.markdown(
    """
    ## How to use
    1. Download your Spotify listening history from [here](https://www.spotify.com/us/account/privacy/). Note that this takes about 5 days to process.
    2. Unzip the file and attach all of the files like `StreamingHistory#.json` or `endsong_#.json` into the app
    3. View your matches!
    """
)

col1, col2, col3, col4 = st.columns([5, 1, 3, 1])
with col2:
    badge("twitter", "TYLERSlMONS", "https://twitter.com/TYLERSlMONS")
with col4:
    badge("github", "tyler-simons/spotify", "https://github.com/tyler-simons/spotify")


# Extract the data from the csv as a list of items
festival = st.radio("Select a festival", ["Coachella", "Outside Lands"])
if festival == "Coachella":
    coachella_lineup = pd.read_csv("./coachella2023.csv")
else:
    coachella_lineup = pd.read_csv("./outsidelands2023.csv").columns
    coachella_lineup = pd.DataFrame(coachella_lineup)
    coachella_lineup.columns = ["Artist"]
    coachella_lineup["Day"] = "F"
    coachella_lineup = coachella_lineup.drop_duplicates()

    # Lowercase
    coachella_lineup["Artist"] = coachella_lineup["Artist"].str.lower().str.strip()

    # Conver to a dataframe
    coachella_lineup
st.write(coachella_lineup)


# Change the column names to be more readable
change_cols = {
    "master_metadata_track_name": "trackName",
    "master_metadata_album_artist_name": "artistName",
    "ts": "endTime",
    "ms_played": "msPlayed",
}

history = st.file_uploader(
    "Upload your Spotify listening history", type="json", accept_multiple_files=True
)


def validate_upload_files(file: pd.DataFrame):
    """
    Validate the files uploaded to make sure they are the correct format
    """

    StreamingHistoryColumns = ["endTime", "artistName", "trackName", "msPlayed"]
    endsongColumns = [
        "ts",
        "username",
        "platform",
        "ms_played",
        "conn_country",
        "ip_addr_decrypted",
        "user_agent_decrypted",
        "master_metadata_track_name",
        "master_metadata_album_artist_name",
        "master_metadata_album_album_name",
        "spotify_track_uri",
        "episode_name",
        "episode_show_name",
        "spotify_episode_uri",
        "reason_start",
        "reason_end",
        "shuffle",
        "skipped",
        "offline",
        "offline_timestamp",
        "incognito_mode",
    ]
    check1 = all([i in file.columns for i in StreamingHistoryColumns])
    check2 = all([i in file.columns for i in endsongColumns])
    if check1 or check2:
        return True
    else:
        return False


def get_all_data():
    """
    Get all the data from the uploaded files
    """
    if history:
        listening_history = []
        all_data = None
        for i in history:
            if "StreamingHistory" in i.name or "endsong_" in i.name:
                read_file = pd.read_json(path_or_buf=i)
                if validate_upload_files(read_file):
                    listening_history.append(read_file)

        if len(listening_history) > 0:
            all_data = pd.concat(listening_history).reset_index()
        return all_data
    else:
        st.info("Upload your Spotify listening history to see your matches")
        st.stop()


# Rename if the column name is in the dictionary
all_data = get_all_data()

# Check if the data was uploaded correctly
if all_data is None:
    st.error(
        "Please upload only files that match `StreamingHistory#.json` or `endsong_#.json` files"
    )
    st.stop()

all_data = all_data.rename(
    columns={i: change_cols[i] for i in change_cols if i in all_data.columns}
)

# Add features
all_data["endTime"] = pd.to_datetime(all_data["endTime"])
all_data["date"] = [i.date() for i in all_data["endTime"]]
all_data["minutesPlayed"] = all_data["msPlayed"] / 60000

# Merge the Coachella lineup with the listening history
all_data["artistName"] = all_data["artistName"].str.lower().str.strip()
# Check if the artist is in the lineup
all_data["inLineup"] = all_data["artistName"].isin(coachella_lineup["Artist"])
all_data["artistName"][all_data["inLineup"]]
all_data = all_data.merge(coachella_lineup, left_on="artistName", right_on="Artist", how="inner")

# Filter for the minimum minutes played grouped by artist
all_data = all_data.groupby("artistName").filter(lambda x: x["minutesPlayed"].sum() > 1)

# Get the top artist
grouped_artist_total = all_data.groupby(["artistName"])["minutesPlayed"].sum()
top_artist = grouped_artist_total.sort_values(ascending=False).index[0]

# Make a chart of the total minutes played by artist and put it in a streamlit column
top_artists_total_minutes = (
    all_data.groupby(["artistName"])["minutesPlayed"].sum().sort_values(ascending=False)
)
top_artists_total_minutes = top_artists_total_minutes.rename("Total Minutes").reset_index()
top_artists_order = top_artists_total_minutes["artistName"].to_list()

all_data = all_data.merge(top_artists_total_minutes.reset_index(), on="artistName", how="left")
all_data["rank"] = all_data["Total Minutes"].rank(ascending=False)

# Artist top minutes chart
col1, col2 = st.columns(2)
minutes_played_chart = (
    alt.Chart(top_artists_total_minutes.reset_index().head(40))
    .mark_bar(width=40, cornerRadius=corner_radius)
    .encode(
        y=alt.Y(
            "artistName",
            sort=top_artists_order,
            title="Artist",
            axis=alt.Axis(
                labels=False,
            ),
        ),
        x=alt.X(
            "Total Minutes:Q",
            title="Total Minutes",
            axis=alt.Axis(
                format="d",
            ),
            scale=alt.Scale(domain=(0, top_artists_total_minutes["Total Minutes"].max() * 1.2)),
        ),
        color=alt.Color(
            "artistName:N",
            title="Artist",
            sort=top_artists_order,
            scale=alt.Scale(scheme="viridis"),
            legend=None,
        ),
    )
    .properties(height=500)
)
# Add mark_text as the artists
minutes_played_chart = minutes_played_chart + minutes_played_chart.mark_text(
    align="left", baseline="middle", dx=3, fontSize=12
).encode(text=alt.Text("artistName:N", title="Artist"))

limit_40 = "(Top 40)" if len(all_data["artistName"].unique()) > 40 else ""

col1.markdown("---")
col1.subheader(f"My Top {festival} Artists {limit_40}")
col1.altair_chart(minutes_played_chart, use_container_width=True)

# Make a chart that shows the total artists by day where the artists are colors
# and the days are the x-axis and the y is the total sum of the artists
day_chart = (
    alt.Chart(all_data[["artistName", "Day", "rank"]].drop_duplicates().head(40))
    .mark_bar(cornerRadius=corner_radius)
    .encode(
        x=alt.X("Day", title="Day", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("count(artistName):Q", title="Total Artists"),
        color=alt.Color(
            "artistName:N",
            title="Artist",
            scale=alt.Scale(scheme="viridis"),
            sort=top_artists_order,
            legend=None,
        ),
        order=alt.Order("rank", sort="ascending"),
        tooltip=[alt.Tooltip("artistName:N", title="Artist")],
    )
    .properties(height=500)
)

# Add mark_text as the artists
day_chart = day_chart + (
    day_chart.mark_text(color="black", fill="white", fontSize=12, dy=12).encode(
        x=alt.X("Day", title="Day"),
        y=alt.Y("count(artistName):Q", title="Total Artists", stack="zero"),
        text=alt.Text("artistName", title="Artist"),
        order=alt.Order("rank", sort="ascending"),
    )
)

col2.markdown("---")
col2.subheader(f"Which day are they playing? {limit_40}")
col2.altair_chart(day_chart, use_container_width=True)


# Make three streamlit columns with st.metric for each of the following
col1, col2, col3, col4 = st.columns([4, 2, 3, 2])
col2.metric("Total Artists", all_data["artistName"].nunique())
col3.metric("Top Artist", top_artist)
col4.metric("Total Coachella Hours", int(all_data["minutesPlayed"].sum() / 60))
col1.metric(
    "Date Range", f"{all_data['endTime'].min().date()} - {all_data['endTime'].max().date()}"
)
