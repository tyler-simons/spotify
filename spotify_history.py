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


st.set_page_config(layout="centered")
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


def build_date_from_pieces(row):
    dt = datetime.strptime(f"{row['year']}-{row['week']}-{row['day_of_week_str']}", "%Y-%W-%A")
    return dt.date()


# Filter for the minimum minutes played grouped by artist
st.title("🎁 Spotify Data Deepdive 🎶")
st.markdown("Deep dive into your listening habits")

# Write an about section with st.markdown
col1, col2 = st.columns(2)
col2.markdown(
    """
    ## About
    This app helps you dig into your\
     listening history to help you learn about yourself. It shows you your \
    top songs and artists and visualizes your listening history. We **do not** \
    save your data and all the code is __open source__. The app is still in beta \
    . I hope you enjoy it!
    """
)
with col2:
    badge("twitter", "TYLERSlMONS", "https://twitter.com/TYLERSlMONS")
col1.markdown(
    """
    ## How to use
    1. Download your Spotify listening history from [here](https://www.spotify.com/us/account/privacy/). Note that this takes about 5 days for the last year or 30 days for your entire listening history
    2. Unzip the file and attach all of the files like `StreamingHistory#.json` or `endsong_#.json` into the app
    3. Run the app and visualize your music history!
    """
)

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


# @st.experimental_memo
def get_all_data():
    if history:
        listening_history = []
        for i in history:
            listening_history.append(pd.read_json(path_or_buf=i))
        all_data = pd.concat(listening_history).reset_index()
        return all_data
    else:
        st.info("Upload your Spotify listening history to see your matches")
        st.stop()


# Rename if the column name is in the dictionary
all_data = get_all_data()
all_data = all_data.rename(
    columns={i: change_cols[i] for i in change_cols if i in all_data.columns}
)


# Add features
all_data["endTime"] = pd.to_datetime(all_data["endTime"])
all_data["endTime"] = pd.Series([(i + timedelta(hours=16)) for i in all_data.endTime])
all_data["date"] = [i.date() for i in all_data["endTime"]]
all_data["dow"] = [i.weekday() for i in all_data["endTime"]]
all_data["day_of_week_str"] = all_data["dow"].apply(lambda x: calendar.day_name[x])
all_data["time"] = [i.hour for i in all_data["endTime"]]
all_data["week"] = all_data["endTime"].dt.isocalendar().week
all_data["year"] = all_data["endTime"].dt.isocalendar().year
all_data["minutesPlayed"] = all_data["msPlayed"] / 60000

all_data = all_data[all_data["msPlayed"] > 10000]
all_data_full_songs = all_data

full_data_copy = all_data


# Filter for the minimum minutes played grouped by artist
all_data = all_data.groupby("artistName").filter(lambda x: x["minutesPlayed"].sum() > 5)

# Get the top artist
grouped_artist_total = all_data.groupby(["artistName"])["minutesPlayed"].sum()
top_artist = grouped_artist_total.sort_values(ascending=False).index[0]

# Make a chart of the total minutes played by artist and put it in a streamlit column
top_artists_total_hours = (
    all_data.groupby(["artistName"])["minutesPlayed"].sum().sort_values(ascending=False) / 60
)
top_artists_total_hours = top_artists_total_hours.rename("Hours", inplace=True)

# Get the order of the artists
all_data = all_data.merge(top_artists_total_hours.reset_index(), on="artistName", how="left")
all_data["rank"] = all_data["Hours"].rank(ascending=False)
top_artists_order = all_data.sort_values("rank")["artistName"].unique().tolist()

# Get the min and max year
min_year, max_year = all_data["year"].min(), all_data["year"].max()


# Make three streamlit columns with st.metric for each of the following
col1, col2, col3, col4 = st.columns([4, 2, 3, 2])
col1.metric("Timespan", f"{min_year} - {max_year}")
col2.metric("Lifetime Artists", all_data["artistName"].nunique())
col3.metric(
    "Lifetime Tracks", all_data.groupby(["artistName", "trackName"]).size().reset_index().shape[0]
)
col4.metric("Lifetime Hours", int(all_data["minutesPlayed"].sum() / 60))


# Artist top hours chart
minutes_played_chart = (
    alt.Chart(top_artists_total_hours.reset_index().head(40))
    .mark_bar(width=40, cornerRadius=corner_radius)
    .encode(
        y=alt.Y(
            "artistName",
            sort=top_artists_order[0:40],
            title="Artist",
            axis=alt.Axis(
                labels=False,
            ),
        ),
        x=alt.X(
            "Hours:Q",
            title="Total Hours",
            axis=alt.Axis(
                format="d",
            ),
            scale=alt.Scale(domain=(0, top_artists_total_hours.max() * 1.2)),
        ),
        color=alt.Color(
            "artistName:N",
            title="Artist",
            sort=top_artists_order[0:40],
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

st.markdown("---")
st.subheader("Top Lifetime Artists")
st.altair_chart(minutes_played_chart, use_container_width=True)
with st.expander("Top Artists Raw Data"):
    st.write(top_artists_total_hours)

# Make a chart that shows the top songs by number of listens where listens are more than
# 20 seconds

# Filter for all songs where the msPlayed is greater than 10 seconds

TOP_SONG_N = 40

top_songs = (
    all_data_full_songs.groupby(["artistName", "trackName"])["msPlayed"]
    .count()
    .sort_values(ascending=False)
)
top_songs = top_songs.rename("Listens")
top_songs = top_songs.reset_index()
top_songs["rank"] = top_songs["Listens"].rank(ascending=False)
top_songs_order = top_songs.sort_values("rank")["trackName"].unique().tolist()[0:TOP_SONG_N]

day_chart = (
    alt.Chart(top_songs.head(TOP_SONG_N))
    .mark_bar(cornerRadius=corner_radius)
    .encode(
        x=alt.X(
            "Listens",
            title="# Plays",
            axis=alt.Axis(labelAngle=0),
            scale=alt.Scale(domain=(0, top_songs["Listens"].max() * 1.2)),
        ),
        y=alt.Y("trackName", title="Track", axis=alt.Axis(labels=False), sort=top_songs_order),
        color=alt.Color(
            "artistName:N",
            title="Artist",
            scale=alt.Scale(scheme="viridis"),
            sort=top_artists_order,
            legend=None,
        ),
        order=alt.Order("rank", sort="ascending"),
        tooltip=[
            alt.Tooltip("trackName:N", title="Track"),
            alt.Tooltip("artistName:N", title="Artist"),
            alt.Tooltip("Listens:Q", title="# Plays"),
        ],
    )
    .properties(height=500)
)

# Add mark_text as the artists
day_chart = day_chart + (
    day_chart.mark_text(align="left", baseline="middle", dx=3, fontSize=12).encode(
        x=alt.X("Listens", title="# Plays"),
        y=alt.Y("trackName", title="Track", stack="zero", sort=top_songs_order),
        text=alt.Text("trackName", title="Track"),
        order=alt.Order("rank", sort="ascending"),
    )
)

st.markdown("---")
st.subheader("Top 40 Lifetime Songs")
st.altair_chart(day_chart, use_container_width=True)
with st.expander("Top Song Raw Data"):
    st.write(top_songs)


# Make a heatmap of the total minutes played by day and make them select the artist
st.markdown("---")

# Artist heatmap
col2, col3 = st.columns(2)

top_artist_order = (
    all_data.groupby("artistName")["minutesPlayed"]
    .sum()
    .sort_values(ascending=False)
    .index.to_list()
)

# Select artist
heatmap_artist = st.selectbox("Select Artist", ["All"] + top_artist_order)
st.title(f"Lifetime Analysis for {heatmap_artist}")
st.write("Dig a bit deeper into your favorite artists")


if heatmap_artist == "All":
    heatmap_data = all_data
else:
    heatmap_data = all_data[all_data["artistName"] == heatmap_artist]

# Give the main stats for the artist
# Total lifetime minutes, total unique tracks, top year for artist

# Total lifetime minutes for the artist
total_lifetime_hours = heatmap_data["minutesPlayed"].sum() / 60

# Total unique tracks for the artist
total_unique_tracks = heatmap_data["trackName"].nunique()

# Top song all time for the aritst
top_song = (
    heatmap_data.groupby("trackName")["minutesPlayed"].sum().sort_values(ascending=False).index[0]
)

most_listened_year = (
    heatmap_data.groupby("year")["minutesPlayed"].sum().sort_values(ascending=False).index[0]
)

# Artist bar chart over time
if heatmap_artist == "All":
    all_artist_raw = all_data
else:
    all_artist_raw = all_data.query(f"artistName == '{heatmap_artist}'")
all_artist = all_artist_raw.copy()
all_artist["year_month"] = pd.to_datetime(all_artist["date"]).dt.strftime("%Y-%m")
all_artist = all_artist.groupby(["year_month"], as_index=False).sum()

bar_chart = (
    alt.Chart(all_artist)
    .mark_bar()
    .encode(
        x=alt.X("year_month:T", title="Date", axis=alt.Axis(labelAngle=0), timeUnit="yearmonth"),
        y=alt.Y("minutesPlayed:Q", title="Minutes Played", axis=alt.Axis(format=".0f")),
        tooltip=[
            alt.Tooltip("year_month:T", title="Date", format="%b-%Y", timeUnit="yearmonth"),
            alt.Tooltip("minutesPlayed:Q", title="Minutes Played", format=".0f"),
        ],
    )
    .properties(
        width=800,
        height=400,
        title=f"Minutes Played by Month for {heatmap_artist}",
    )
)


# Two columns for the stats
col0, col1, col2, col3 = st.columns(4)
# Round total_lifetime_hours to 2 decimal places
if heatmap_artist == "All":
    col0.metric(f"Lifetime Rank", "-")
else:
    col0.metric(f"Lifetime Rank", f"{top_artist_order.index(heatmap_artist) + 1}")

col1.metric("Total Lifetime Hours", f"{total_lifetime_hours:.2f}")
col2.metric("Total Unique Tracks", total_unique_tracks)
col3.metric("Most Listened Year", most_listened_year)

st.altair_chart(bar_chart, use_container_width=True)

# Get the dataframe for the top songs which contains
# how many minutes were played for each song and the play count for each song
top_songs = (
    all_artist_raw.groupby(["trackName", "artistName"], as_index=False)
    .agg({"minutesPlayed": "sum", "date": "count"})
    .rename(
        columns={
            "date": "Listens",
            "minutesPlayed": "Total Minutes",
            "artistName": "Artist",
            "trackName": "Track",
        }
    )
    .sort_values(by="Listens", ascending=False)
    .drop("Artist", axis=1)
    .set_index("Track")
    # Format the minutes played
    .style.format({"Total Minutes": "{:.1f}"})
)

st.subheader(f"Lifetime Top Songs by {heatmap_artist}")
st.dataframe(top_songs, use_container_width=True)


# Dataframe of top tracks
st.markdown("---")
sorted_years_reversed = sorted(all_artist_raw["year"].unique(), reverse=True)
# Get the index of the top year
top_year_index = sorted_years_reversed.index(most_listened_year)


year_select = st.selectbox(
    f"Select year for deeper analysis", sorted_years_reversed, top_year_index
)
heatmap_data = all_artist_raw[all_artist_raw["year"] == year_select]

st.title(f"{heatmap_artist} in {year_select}")

# Refine even further with the year for the artist
# Year select
# Heatmap chart for the year
# Summary stats for the artist x year
# Dataframe of the top tracks for the year with the artist


# Get number of listened hours in the selected year
total_listened_hours = heatmap_data["minutesPlayed"].sum() / 60


def build_heatmap(heatmap_data):

    # set the heatmap data as categorical variables so we can fill in 0s for the missing dates
    simple_heatmap_data = heatmap_data[
        [
            "artistName",
            "trackName",
            "endTime",
            "minutesPlayed",
            "date",
            "year",
            "week",
            "dow",
            "day_of_week_str",
        ]
    ]
    simple_heatmap_data["week"] = pd.Categorical(
        values=simple_heatmap_data["endTime"].dt.week, categories=list(range(0, 53))
    )
    simple_heatmap_data["day_of_week_str"] = pd.Categorical(
        values=simple_heatmap_data["day_of_week_str"],
        categories=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        ordered=True,
    )
    heatmap_agg = (
        simple_heatmap_data.groupby(["week", "day_of_week_str", "year"])
        .sum()["minutesPlayed"]
        .reset_index()
    )

    # Pandas cut at 0, between 0 and 1, and greater than 1
    bucket_labels = ["0 min", "1-5 min", "5-15 min", "15-60 min", "60+ min"]
    heatmap_agg["min_bucket"] = pd.cut(
        heatmap_agg["minutesPlayed"], bins=[-1, 1, 5, 15, 60, 60 * 60 * 24], labels=bucket_labels
    )

    month_weeks = get_month_weeks(2022)

    # reformat the above to be used in the altair transform_calculate
    format_label_expr = "||".join(
        [
            f"datum.value === {month_week} ?  '{month}': ''"
            for month, month_week in zip(calendar.month_abbr[1:], month_weeks)
        ]
    )

    # Extract the date, year, day_of_week from simple_heatmap_data and left join to the heatmap_agg
    heatmap_agg = (
        heatmap_agg.merge(
            simple_heatmap_data[["date", "week", "year", "day_of_week_str"]].drop_duplicates(),
            left_on=["week", "day_of_week_str", "year"],
            right_on=["week", "day_of_week_str", "year"],
            how="left",
        )
        .drop_duplicates()
        .sort_values(["date", "day_of_week_str"])
    )

    # Split the dataframe based on if the date is None
    missing_dates = heatmap_agg[heatmap_agg["date"].isnull()]
    not_missing_dates = heatmap_agg[heatmap_agg["date"].notnull()]

    # Replace the missing dates
    missing_dates["date"] = missing_dates.apply(build_date_from_pieces, axis=1)

    # Concat the two dataframes back together
    heatmap_agg = pd.concat([missing_dates, not_missing_dates])

    # Add the month to heatmap data
    artist_heat = (
        alt.Chart(heatmap_agg)
        .mark_rect(cornerRadius=2, width=9, height=10)
        .encode(
            # Set ticks at 0-52 and the labels as the months
            x=alt.X(
                "week:O",
                title="Week",
                axis=alt.Axis(
                    # If the
                    labelExpr=format_label_expr,
                    # set angle to 0 so the labels are horizontal
                    labelAngle=0,
                ),
            ),
            y=alt.Y(
                "day_of_week_str:O",
                title="Day",
                sort=days_of_week,
                # remove axis title
                axis=alt.Axis(title=None),
            ),
            # Set the color to be grey for 0 and green for more than 0
            color=alt.Color(
                "min_bucket:O",
                title="Minutes Played",
                scale=alt.Scale(
                    # Use grey, light blue, medium blue, medium dark blue, dark blue for the colors
                    range=["#e0e0e0", "#90caf9", "#64b5f6", "#42a5f5", "#1e88e5"],
                    domain=bucket_labels,
                ),
                legend=alt.Legend(
                    # Set the legend to be on the top
                    orient="bottom",
                ),
            ),
            tooltip=[
                alt.Tooltip("date:T", title="Date", format="%Y-%m-%d"),
                alt.Tooltip("minutesPlayed:Q", title="Minutes Played", format=".0f"),
            ],
        )
        .properties(
            # Set the width and height of the chart
            width=800,
            height=340,
            # Set the title of the chart
            title=f"Minutes Played by Day for {heatmap_artist} in {year_select}",
        )
    )
    return artist_heat


st.subheader("Stats")

col1, col2, col3 = st.columns(3)

# Rank for the year
yearly_rank = (
    all_data[all_data["year"] == year_select]
    .groupby(["artistName"])
    .sum()
    .sort_values("minutesPlayed", ascending=False)
    .reset_index()
)
yearly_rank["rank"] = yearly_rank["minutesPlayed"].rank(ascending=False)

yearly_rank = yearly_rank[yearly_rank["artistName"] == heatmap_artist]

if heatmap_artist == "All":
    col1.metric(f"Artist Rank in {year_select}", "-")
else:
    col1.metric(f"Artist Rank in {year_select}", f"{yearly_rank['rank'].values[0]:.0f}")

# Total hours played for the year
col2.metric(f"Hours Played in {year_select}", f"{total_listened_hours:.0f}")

# Total unique tracks
col3.metric(
    f"Unique Tracks Played in {year_select}", f"{len(heatmap_data['trackName'].unique()):.0f}"
)

# Create a second chart of just the months on the x axis to be added to the first chart
artist_heat = build_heatmap(heatmap_data)
st.altair_chart(artist_heat, use_container_width=True)

st.subheader(f"Track Leaderboard for {year_select}")

# Dataframe with tracknames, total minutes, and total plays
track_leaderboard = (
    heatmap_data.groupby(["trackName"])
    .agg({"minutesPlayed": "sum", "endTime": "count"})
    .reset_index()
    .rename(columns={"endTime": "Listens", "minutesPlayed": "Total Minutes", "trackName": "Track"})
    .sort_values("Total Minutes", ascending=False)
    .set_index("Track")
    .sort_values("Listens", ascending=False)
    # Format minutes
    .style.format({"Total Minutes": "{:.1f}"})
)
st.dataframe(track_leaderboard, use_container_width=True)
