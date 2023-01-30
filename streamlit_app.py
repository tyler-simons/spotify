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
days_of_week = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

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
     There are so many artists playing Coachella it can be hard to keep track of all of them. This app takes your Spotify listening history and matches it with the Coachella 2023 lineup. It then shows you the total minutes you've listened to each match artist, who your top artist is, and plots it all. The bottom section allows you filter by artist to get a bit more detail on your listening history. The app is still in beta so please let me know if you have any feedback or suggestions! 
    """
)
with col2:
    badge("twitter", "TYLERSlMONS", "https://twitter.com/TYLERSlMONS")
col1.markdown(
    """
    ## How to use
    1. Download your Spotify listening history from [here](https://www.spotify.com/us/account/privacy/). Note that this takes about 5 days for the last year or 30 days for your entire listening history
    2. Unzip the file and attach all of the files like `StreamingHistory#.json`
    3. Run the app and see your matches!
    """
)

# Extract the data from the csv as a list of items
coachella_lineup = pd.read_csv("./coachella2023.csv")

# Change the column names to be more readable
change_cols = {
    "master_metadata_track_name": "trackName",
    "master_metadata_album_artist_name": "artistName",
    "ts": "endTime",
    "ms_played": "msPlayed",
}


history = st.file_uploader("Upload your Spotify listening history", type="json", accept_multiple_files=True)


@st.experimental_memo
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
all_data = all_data.rename(columns={i: change_cols[i] for i in change_cols if i in all_data.columns})

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

full_data_copy = all_data
all_data = all_data.merge(coachella_lineup, left_on="artistName", right_on="Artist", how="inner")

all_data = all_data.groupby("artistName").filter(lambda x: x["minutesPlayed"].sum() > 1)

grouped_artist_total = all_data.groupby(["artistName"])["minutesPlayed"].sum()
top_artist = grouped_artist_total.sort_values(ascending=False).index[0]

# Make a chart of the total minutes played by artist and put it in a streamlit column
top_artists_total_hours = grouped_artist_total.sort_values(ascending=False) / 60
top_artists_total_minutes = (grouped_artist_total.sort_values(ascending=False)).rename("Total Minutes")
top_artists_order = top_artists_total_minutes.index.to_list()

all_data = all_data.merge(top_artists_total_minutes.reset_index(), on="artistName", how="left")
all_data["rank"] = all_data["Total Minutes"].rank(ascending=False)

# Artist top minutes chart
col1, col2 = st.columns(2)
minutes_played_chart = (
    alt.Chart(top_artists_total_minutes.reset_index())
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
            scale=alt.Scale(domain=(0, top_artists_total_minutes.max() * 1.2)),
        ),
        color=alt.Color(
            "artistName:N", title="Artist", sort=top_artists_order, scale=alt.Scale(scheme="viridis"), legend=None
        ),
    )
    .properties(height=500)
)
# Add mark_text as the artists
minutes_played_chart = minutes_played_chart + minutes_played_chart.mark_text(
    align="left", baseline="middle", dx=3, fontSize=12
).encode(text=alt.Text("artistName:N", title="Artist"))

col1.markdown("---")
col1.subheader("Top Coachella Artists")
col1.altair_chart(minutes_played_chart, use_container_width=True)

# Make a chart that shows the total artists by day where the artists are colors
# and the days are the x-axis and the y is the total sum of the artists
day_chart = (
    alt.Chart(all_data[["artistName", "Day", "rank"]].drop_duplicates())
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
    day_chart.mark_text(color="black", fill="white", fontSize=12, dy=20).encode(
        x=alt.X("Day", title="Day"),
        y=alt.Y("count(artistName):Q", title="Total Artists", stack="zero"),
        text=alt.Text("artistName", title="Artist"),
        order=alt.Order("rank", sort="ascending"),
    )
)

col2.markdown("---")
col2.subheader("Which day are they playing?")
col2.altair_chart(day_chart, use_container_width=True)


# Make three streamlit columns with st.metric for each of the following
col1, col2, col3, col4 = st.columns([4, 2, 3, 2])
col2.metric("Total Artists", all_data["artistName"].nunique())
col3.metric("Top Artist", top_artist)
col4.metric("Total Coachella Minutes", int(all_data["minutesPlayed"].sum()))
col1.metric("Date Range", f"{all_data['endTime'].min().date()} - {all_data['endTime'].max().date()}")


# Make a heatmap of the total minutes played by day and make them select the artist
st.markdown("---")
st.title("Artist Explorer")

# Artist heatmap
col1, col2, col3 = st.columns([1, 3, 3])
include_all = col1.radio(
    "Include All Listening Data?",
    ["Yes", "No"],
    horizontal=True,
    index=1,
    help="If you select 'Yes', the heatmap will include all listening data. If you select 'No', the heatmap will only include listening data for the artists at Coachella",
)
if include_all == "Yes":
    all_data = full_data_copy
else:
    all_data = all_data

top_artist_order = all_data.groupby("artistName")["minutesPlayed"].sum().sort_values(ascending=False).index.to_list()
heatmap_artist = col2.selectbox("Select Artist", ["All"] + top_artist_order)
sorted_years_reversed = sorted(all_data["year"].unique(), reverse=True)
year_select = col3.selectbox("Select Year", sorted_years_reversed)

if heatmap_artist == "All":
    heatmap_data = all_data
else:
    heatmap_data = all_data[all_data["artistName"] == heatmap_artist]


# Get the most listened year for the selected artist
most_listened_year = heatmap_data.groupby("year")["minutesPlayed"].sum().sort_values(ascending=False).index[0]
heatmap_data = heatmap_data[heatmap_data["year"] == year_select]

# Get number of listened hours in the selected year
total_listened_hours = heatmap_data["minutesPlayed"].sum() / 60


# If there is no data for the selected artist and year, show a message
if heatmap_data.empty:
    st.info(f"No listening data for {heatmap_artist} in {year_select}")
    st.stop()


# set the heatmap data as categorical variables so we can fill in 0s for the missing dates
simple_heatmap_data = heatmap_data[
    ["artistName", "trackName", "endTime", "minutesPlayed", "date", "year", "week", "dow", "day_of_week_str"]
]
simple_heatmap_data["week"] = pd.Categorical(
    values=simple_heatmap_data["endTime"].dt.week, categories=list(range(0, 53))
)
simple_heatmap_data["day_of_week_str"] = pd.Categorical(
    values=simple_heatmap_data["day_of_week_str"],
    categories=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    ordered=True,
)
heatmap_agg = simple_heatmap_data.groupby(["week", "day_of_week_str", "year"]).sum()["minutesPlayed"].reset_index()

# Pandas cut at 0, between 0 and 1, and greater than 1
bucket_labels = ["0 min", "1-5 min", "5-15 min", ">15 min"]
heatmap_agg["min_bucket"] = pd.cut(heatmap_agg["minutesPlayed"], bins=[-1, 1, 5, 15, 10000], labels=bucket_labels)

month_weeks = get_month_weeks(2022)

# reformat the above to be
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


# Add the month to heatmap data
artist_heat = (
    alt.Chart(heatmap_agg)
    .mark_rect(cornerRadius=corner_radius, width=15, height=15)
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
        y=alt.Y("day_of_week_str:O", title="Day", sort=days_of_week),
        # Set the color to be grey for 0 and green for more than 0
        color=alt.Color(
            "min_bucket:O",
            title="Minutes Played",
            scale=alt.Scale(
                # Use grey, light blue, blue, dark blue for the colors
                range=[
                    "#e0e0e0",
                    "#90caf9",
                    "#2196f3",
                    "#0d47a1",
                ],
                domain=bucket_labels,
            ),
        ),
        tooltip=[
            alt.Tooltip("date:T", title="Date", format="%Y-%m-%d"),
            alt.Tooltip("minutesPlayed:Q", title="Minutes Played", format=".0f"),
        ],
    )
)

# Create a second chart of just the months on the x axis to be added to the first chart
st.altair_chart(artist_heat, use_container_width=True)

artist_data_display = simple_heatmap_data[["artistName", "trackName", "minutesPlayed", "date"]].rename(
    columns={"artistName": "Artist", "trackName": "Track"}
)

# Aggregate to get total minutes and times played by artist and track
artist_data_display = (
    artist_data_display.groupby(["Artist", "Track"])
    .agg({"minutesPlayed": "sum", "date": "count"})
    .rename(columns={"date": "Times Played", "minutesPlayed": "Total Minutes"})
)


# Filter to minutes >= 1
artist_data_display = artist_data_display[artist_data_display["Total Minutes"] >= 1]

# Format minutes to 1 decimal place
artist_data_display["Total Minutes"] = artist_data_display["Total Minutes"].apply(lambda x: f"{x:.1f}")
artist_data_display = artist_data_display.reset_index()

# If artist is selected, drop the artist column
if heatmap_artist != "All":
    artist_data_display = artist_data_display.drop(columns=["Artist"])

col1, col2 = st.columns(2)
col1.subheader("Track Count")
col1.dataframe(artist_data_display.sort_values(["Times Played", "Total Minutes"], ascending=False))

col2.subheader("Stats")

# get the index + 1 for the selected artist from top_artist_order
rank = top_artist_order.index(heatmap_artist) + 1
col2.metric(f"Rank for {heatmap_artist}", f"#{rank}")
col2.metric(f"Total Hours Listened in {year_select}", f"{total_listened_hours:.1f}")
col2.metric(f"Most Listened Year for {heatmap_artist}", most_listened_year)

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
