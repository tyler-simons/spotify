# Spotify Dive Report

Explore listening history through an interactive report of artists, tracks, listening patterns, and activity over time.

**[Open the live report](https://spotify-history.streamlit.app/)** · [Tyler Simons](https://tylersimons.com/)

The report starts with example data. Upload your own Spotify streaming history JSON files to explore your listening instead. The app also includes an artist deep dive and timezone controls.

## Run locally

Use Python 3.10 or newer and [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run streamlit run spotify_history.py
```

## Festival match

[Coachella Match](https://coachella-match.streamlit.app/) compares listening history with the 2023 Coachella and Outside Lands lineups. Run it locally with `uv run streamlit run coachella_match.py`.

Built with Python, Streamlit, pandas, and Altair.

## License

[MIT](https://choosealicense.com/licenses/mit/)
