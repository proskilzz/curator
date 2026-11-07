# Curator

A local-AI media assistant for macOS.

Curator looks at what you already have (your Downloads folder, plus screenshots of your YouTube, Spotify, Apple Music or streaming apps), learns your taste and where you are in each show, and suggests what to watch or listen to next — three picks at a time, each with a reason. It tells you when the next episode of a show you follow comes out. Like, pass or mark things as seen, and the picks adjust over time.

When you ask for something, Curator fetches it from **sources you configure** (for example YouTube via yt-dlp, the Internet Archive, or your own media server).

## Principles

- **Local first.** The language model runs on your Mac. Your file list, screenshots and taste profile never leave it.
- **The model suggests, code acts.** The AI only ranks real titles from public metadata (TMDB, TVmaze) and explains its picks. Fetching is plain, rule-checked code: allowlisted sources and file types, size and daily caps, and confirmation before every download.
- **No sources bundled.** Curator ships with no torrent or indexer sites. What you connect, and whether it is legal where you live, is up to you.

## Status

Early build. Working so far: open the app, press **Scan Downloads**, and Curator lists the movies and TV episodes it found (offline). Everything starts ticked; untick what you don't want, then **Save to library** (a local SQLite database).

```
uv run curator
```

## Planned stack

Python core · SQLite · guessit · TMDB + TVmaze APIs · yt-dlp · local LLM (MLX / llama.cpp) · web UI in a Mac app window

## Credits

Metadata will come from [TMDB](https://www.themoviedb.org) and [TVmaze](https://www.tvmaze.com). This product uses the TMDB API but is not endorsed or certified by TMDB.
