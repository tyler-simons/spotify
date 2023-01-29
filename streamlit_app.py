import json
import pandas as pd
import os
import streamlit as st
from datetime import datetime, timedelta
import altair as alt
import numpy as np
import calplot as cp

st.set_page_config(layout="wide")
corner_radius = 4

months = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


@st.experimental_memo()
def get_data():
    listening_history = []
    for i in range(0, 20):
        try:
            listening_history.append(pd.read_json(f"./2022/data/endsong_{i}.json"))
        except:
            pass
    all_data = pd.concat(listening_history).reset_index()
    return all_data


all_data = get_data()

# Extract the data from the csv as a list of items
coachella_lineup = pd.read_csv("./coachella2023.csv")


# Change the column names to be more readable
change_cols = {
    "master_metadata_track_name": "trackName",
    "master_metadata_album_artist_name": "artistName",
    "ts": "endTime",
    "ms_played": "msPlayed",
}
# Rename if the column name is in the dictionary
all_data = all_data.rename(columns={i: change_cols[i] for i in change_cols if i in all_data.columns})


# filer the artists that are in the coachella lineup
# join the coachella lineup with the listening history
all_data = all_data.merge(coachella_lineup, left_on="artistName", right_on="Artist", how="inner")

# Add features
all_data["endTime"] = pd.to_datetime(all_data["endTime"])
all_data["endTime"] = pd.Series([(i + timedelta(hours=16)) for i in all_data.endTime])
all_data["day"] = [i.date() for i in all_data["endTime"]]
all_data["dow"] = [i.weekday() for i in all_data["endTime"]]
all_data["time"] = [i.hour for i in all_data["endTime"]]
all_data["week"] = all_data["endTime"].dt.isocalendar().week
all_data["year"] = all_data["endTime"].dt.isocalendar().year
all_data["minutesPlayed"] = all_data["msPlayed"] / 60000

# Filter for the minimum minutes played grouped by artist
st.title("🎡 Coachella 2023 Spotify Match 🎶")
st.markdown("Match your Spotify listening history with the Coachella 2023 lineup.")

# Write an about section with st.markdown
col1, col2 = st.columns(2)
col2.markdown(
    """
    ## About
    I'm attending Coachella this year. After looking at the line-up, I was having trouble remembering exactly which artists I've spent time listening to. This app takes your Spotify listening history and matches it with the Coachella 2023 lineup. It then shows you the total minutes you've listened to each artist, the top artist, and a chart of the total artists by day. You can also filter the artists by the minimum minutes you've listened to them.
    """
)
col1.markdown(
    """
    ## How to use
    1. Download your Spotify listening history from [here](https://www.spotify.com/us/account/privacy/). Note that this takes about 5 days for the last year or 30 days for your entire listening history
    2. Unzip the file and put the `data` folder in the same directory as this app
    3. Run the app and see your matches!
    """
)


min_min = st.number_input("Select Minimum Minutes", 1, 60, 5)
# Grab a date range for the min and max date
min_date = all_data["endTime"].min().date()
max_date = all_data["endTime"].max().date()

date_range_choice = st.radio(
    "Select Date Range",
    ["Last 30 Days", "Last Year", "All Time"],
)

if date_range_choice == "Last 30 Days":
    date_range = [max_date - timedelta(days=30), max_date]
elif date_range_choice == "Last Year":
    date_range = [max_date - timedelta(days=365), max_date]
else:
    date_range = [min_date, max_date]

date_range = st.date_input(
    "Custom Date Range",
    date_range,
    min_value=min_date,
    max_value=max_date,
    help="Select a date range of your listening history",
)
all_data = all_data.groupby("artistName").filter(lambda x: x["minutesPlayed"].sum() > min_min)
all_data = all_data[(all_data["endTime"].dt.date >= date_range[0]) & (all_data["endTime"].dt.date <= date_range[1])]

grouped_artist_total = all_data.groupby(["artistName"])["minutesPlayed"].sum()
top_artist = grouped_artist_total.sort_values(ascending=False).index[0]

# Make a chart of the total minutes played by artist and put it in a streamlit column
top_artists_total_hours = grouped_artist_total.sort_values(ascending=False) / 60
top_artists_total_minutes = (grouped_artist_total.sort_values(ascending=False)).rename("Total Minutes")
top_artists_order = top_artists_total_minutes.index.to_list()

all_data = all_data.merge(top_artists_total_minutes.reset_index(), on="artistName", how="left")
all_data["rank"] = all_data["Total Minutes"].rank(ascending=False)


# Make three streamlit columns with st.metric for each of the following
col1, col2, col3 = st.columns(3)
col1.metric("Total Artists", all_data["artistName"].nunique())
col2.metric("Top Artist", top_artist)
col3.metric("Date Range", f"{all_data['endTime'].min().date()} - {all_data['endTime'].max().date()}")

col1, col2 = st.columns(2)

# Artist top minutes chart
minutes_played_chart = (
    alt.Chart(top_artists_total_minutes.reset_index())
    .mark_bar(width=40, cornerRadius=corner_radius)
    .encode(
        y=alt.Y("artistName", sort=top_artists_order, title="Artist"),
        x=alt.X("Total Minutes:Q", title="Total Minutes", axis=alt.Axis(format="d")),
        color=alt.Color(
            "artistName:N", title="Artist", sort=top_artists_order, scale=alt.Scale(scheme="viridis"), legend=None
        ),
    )
    .properties(height=500)
)
col1.altair_chart(minutes_played_chart, use_container_width=True)

# Make a chart that shows the total artists by day where the artists are colors
# and the days are the x-axis and the y is the total sum of the artists
day_chart = (
    alt.Chart(all_data[["artistName", "Day", "rank"]].drop_duplicates())
    .mark_bar(cornerRadius=corner_radius)
    .encode(
        y=alt.Y("Day", title="Day"),
        # X should be in order of top_artists_order
        x=alt.X("count(artistName):Q", title="Total Artists"),
        color=alt.Color(
            "artistName:N",
            title="Artist",
            scale=alt.Scale(scheme="viridis"),
            sort=top_artists_order,
        ),
        order=alt.Order("rank", sort="ascending"),
        tooltip=[alt.Tooltip("artistName:N", title="Artist")],
    )
    .properties(height=500)
)
col2.altair_chart(day_chart, use_container_width=True)


# calplot
# Make a heatmap of the total minutes played by day and make them select the artist

# Artist heatmap
heatmap_artist = st.selectbox("Select Artist", ["All"] + all_data["artistName"].unique().tolist())
if heatmap_artist == "All":
    heatmap_data = all_data
else:
    heatmap_data = all_data[all_data["artistName"] == heatmap_artist]

# set the heatmap data as categorical variables so we can fill in 0s for the missing dates
heatmap_data["week"] = pd.Categorical(values=heatmap_data["endTime"].dt.week, categories=list(range(0, 53)))
heatmap_data["dow"] = pd.Categorical(values=heatmap_data["endTime"].dt.dayofweek, categories=list(range(0, 7)))
heatmap_data = heatmap_data.groupby(["week", "dow", "year"]).sum()["minutesPlayed"].reset_index()

# Pandas cut at 0, between 0 and 1, and greater than 1
heatmap_data["min_bucket"] = pd.cut(
    heatmap_data["minutesPlayed"], bins=[-1, 1, 5, 15, 10000], labels=["0 min", "<5 min", "<15 min", ">15 min"]
)
import calendar

artist_heat = (
    alt.Chart(heatmap_data)
    .mark_rect(cornerRadius=corner_radius, width=20, height=15)
    .encode(
        # Set ticks at 0-52 and the labels as the months
        x=alt.X(
            "week:O",
            title="Week",
            axis=alt.Axis(values=["Jan"] * 53, tickCount=12, labelAngle=0, labelAlign="right", labels=True),
        ),
        y=alt.Y("dow:O", title="Day"),
        # Set the color to be grey for 0 and green for more than 0
        color=alt.Color(
            "min_bucket:O",
            title="min_bucket Played",
            scale=alt.Scale(
                range=[
                    "#e0e0e0",
                    "#cddc39",
                    "#8bc34a",
                    "#4caf50",
                ],
                domain=["0 min", "<5 min", "<15 min", ">15 min"],
            ),
        ),
    )
)

st.altair_chart(artist_heat, use_container_width=True)


# # Total songs
# st.write(f"Total songs: {all_data.shape[0]}")
# st.write(f"Total unique songs: {all_data[['artistName', 'trackName']].drop_duplicates().shape[0]}")

# # Total artists
# st.write(f"Total artists: {all_data['artistName'].nunique()}")


# # All data
# st.dataframe(all_data)

# # Top artists by minute
# grouped_artist_total = all_data.groupby(["artistName"])["minutesPlayed"].sum()
# top_artists_total_hours = grouped_artist_total.sort_values(ascending=False)[0:10] / 60
# top_artists_total_minutes = (grouped_artist_total.sort_values(ascending=False)[0:10]).rename("Total Minutes")

# st.write("Top ten artists by total minutes")
# st.table(top_artists_total_minutes)

# # Top songs
# st.write("Top Songs")
# st.write(all_data.groupby(["artistName", "trackName"]).count())

# # Just cut the data for the top 10 artists
# top_artists = top_artists_total_minutes.index.to_list()

# #
# top_artist_all_data = all_data[[i in top_artists for i in all_data.artistName]]
# top_artists_minutes_by_month = top_artist_all_data.groupby(["artistName", "month"], as_index=False).sum()
# minutes_played_chart = (
#     p9.ggplot(
#         data=top_artists_minutes_by_month,
#         mapping=p9.aes(x="month", y="minutesPlayed", fill="artistName"),
#     )
#     + p9.geom_col(color="black")
#     + p9.theme_classic()
#     + p9.scale_x_continuous(breaks=range(1, 13))
# )
# st.pyplot(p9.ggplot.draw(minutes_played_chart))

# # Replace the plotnine chart above with altair, make the x-axis the name of the month in order

# top_artists_minutes_by_month["month"] = top_artists_minutes_by_month["month"].replace(
#     {i: months[i - 1] for i in range(1, 13)}
# )

# minutes_played_chart = (
#     alt.Chart(top_artists_minutes_by_month)
#     .mark_bar(width=40)
#     .encode(
#         x=alt.X("month", sort=months),
#         y="minutesPlayed",
#         color="artistName",
#     )
# )

# st.altair_chart(minutes_played_chart, use_container_width=True)


# # Artist minutes by day
# artist_date_group = ["artistName", "day"]
# artist_date_sum_minutes = all_data.groupby(artist_date_group, as_index=False).sum()
# st.write(artist_date_sum_minutes.sort_values("minutesPlayed", ascending=False))

# # Repeated songs
# st.write("Most repeated")
# artist_date_group = ["artistName", "day", "trackName"]
# artist_date_song_sum = all_data.groupby(artist_date_group, as_index=False).count()
# st.write(artist_date_song_sum.sort_values("index", ascending=False))

# repeated_song_listens = artist_date_song_sum["index"]
# repeat_song_counts = repeated_song_listens.value_counts().reset_index(name="counts")
# repeat_song_counts.columns = ["counts", "songs"]
# st.write(repeat_song_counts)
# repeated_counts = (
#     p9.ggplot(
#         data=repeat_song_counts,
#         mapping=p9.aes(x="counts", y="songs"),
#     )
#     + p9.geom_col()
#     + p9.theme_bw()
# )
# st.pyplot(p9.ggplot.draw(repeated_counts))


# # Time of the day
# st.write("The Daily times listened by hour")
# artist_time = ["artistName", "time"]
# artist_date_song_sum = all_data.groupby(artist_time, as_index=False).count()
# st.write(artist_date_song_sum.sort_values("msPlayed", ascending=False).query('artistName == "The Daily"'))

# # Artist heatmap by month
# all_data.groupby(["artistName", "month"]).sum()

# # Time of day listens
# all_data["time"]
# repeated_counts = (
#     p9.ggplot(
#         data=repeat_song_counts,
#         mapping=p9.aes(x="counts", y="songs"),
#     )
#     + p9.geom_col()
#     + p9.theme_bw()
# )
# st.pyplot(p9.ggplot.draw(repeated_counts))


# time_counts = all_data.groupby(["time"], as_index=False).count()
# st.write(time_counts)
# time_counts = time_counts[["time", "index"]]
# time_counts.columns = ["hour", "numSongs"]
# st.write(time_counts)
# time_count_plot = (
#     p9.ggplot(data=time_counts, mapping=p9.aes(x="hour", y="numSongs"))
#     + p9.geom_col()
#     + p9.theme_bw()
#     + p9.scale_x_continuous(breaks=range(0, 24))
# )
# st.pyplot(p9.ggplot.draw(time_count_plot))
