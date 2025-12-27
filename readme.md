# Spotify Streaming History Merger & Ranker

A Python GUI application that consolidates your raw Spotify streaming history files into a single, ranked, and "playlist-ready" CSV. 

It goes beyond simple counting by normalizing track names (merging "Remastered" with original versions), filtering duplicates, and applying a smart sorting algorithm to prevent artist clustering in the final list.

## 🚀 Features

* **ZIP File Support:** Reads directly from the `my_spotify_data.zip` file provided by Spotify (no need to extract manually).
* **Smart Normalization:** Merges play counts for variations of the same track (e.g., "Song Name" vs. "Song Name - Remastered 2011" or "Song Name (Live)").
* **Smart Spacing Algorithm:** Reorders the final list to ensure the same artist or album does not appear continuously. It enforces a **6-track buffer** between songs by the same artist, moving tracks to their "alternative peak years" if necessary to maintain variety.
* **Clean Filtering:**
    * Removes tracks marked as "skipped" (listened to for < 30 seconds).
    * Removes tracks played in "Incognito Mode."
    * Filters out specific sleep/ambient noise (Hardcoded filter for Max Richter's *Sleep*).
* **Data Export:**
    * **CSV:** Exports a detailed dataset including play counts, peak years, total milliseconds played, and timestamps.
    * **Clipboard:** One-click copy of all Spotify URIs, ready to paste into a playlist generator or the Spotify desktop app.

## 📋 Prerequisites

This application relies entirely on the **Python Standard Library**. You do not need to install any external packages (like pandas or numpy).

* **Python 3.6+**
* **Tkinter** (usually included with standard Python installations).

## 🛠️ Installation & Usage

1.  **Download your Data:** Request your "Extended Streaming History" from your Spotify Account Privacy settings. Wait for the email and download the ZIP file.
2.  **Clone the Repo:**
    ```bash
    git clone [https://github.com/yourusername/spotify-history-merger.git](https://github.com/yourusername/spotify-history-merger.git)
    cd spotify-history-merger
    ```
3.  **Run the App:**
    ```bash
    python main.py
    ```
    *(Replace `main.py` with whatever you named the script)*
4.  **Using the GUI:**
    * **Step 1:** Click **Select ZIP File** and choose the file you downloaded from Spotify.
    * **Step 2:** Click **Save CSV As...** to choose where to save the results.
    * **Settings:** * *Max tracks:* Limit the output to your top N songs.
        * *Ignore duplicates:* Keeps the logic strict (recommended).
    * **Step 3:** Click **Process History**. The app will parse, clean, merge, and rank your data.
    * **Step 4:** Once finished, use **Copy URIs to Clipboard** to grab the track IDs, or open the CSV file in Excel/Google Sheets.

## 📊 The Logic Explained

### 1. Merging & Normalization
Spotify often logs the same song under different names (e.g., standard vs. Deluxe Edition). This app uses Regex to strip brackets, ` - Remastered`, and ` - Live` suffixes to calculate the **true** listen count for a song, regardless of which version you clicked.

### 2. The Ranking & Spacing Algorithm
The app doesn't just sort by "Most Played." It attempts to build an enjoyable listening history:
1.  It determines the **Peak Year** for every track (the year you listened to it most).
2.  It places tracks into the final list based on their Peak Year.
3.  **Conflict Resolution:** If placing a track would put it too close (within 6 spots) to another track by the same Artist or from the same Album, the algorithm looks for the **Next Best Year** (the year you listened to it second most) and tries to slot it there instead.

## 📂 Output CSV Structure

The generated CSV contains the following columns:

| Column | Description |
| :--- | :--- |
| `peak_year` | The year this song was listened to the most. |
| `peak_year_count` | How many times it was played in that specific year. |
| `listen_count` | Total plays across all years (merged). |
| `master_metadata_track_name` | The "cleanest" version of the track name found. |
| `master_metadata_album_artist_name` | Artist Name. |
| `master_metadata_album_album_name` | Album Name. |
| `total_ms_played` | Total time listened in milliseconds. |
| `first_listen_ts` | Timestamp of the very first stream. |
| `last_listen_ts` | Timestamp of the most recent stream. |
| `spotify_track_uri` | The unique Spotify ID for the track. |

## ⚠️ Disclaimer

This tool is not affiliated with Spotify. It processes your personal data locally on your machine; no data is uploaded to any server.

## 📄 License

MIT License. Free to use and modify.
