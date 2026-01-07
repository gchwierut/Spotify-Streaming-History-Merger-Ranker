import json
import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import zipfile
import threading
import datetime
import re
import unicodedata
from functools import cmp_to_key

class HistoryMergerApp:
    def __init__(self, root):
        self.root = root
        root.title("Spotify Streaming History Merger/Ranker")
        root.geometry("650x900")

        self.zip_path = None
        self.output_path = None
        self.is_running = False
        self.stop_event = threading.Event()
        self.final_uris = []

        # --- UI Setup ---
        main_frame = tk.Frame(root, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        frame_top = tk.Frame(main_frame)
        frame_top.pack(fill=tk.X, pady=5)
        tk.Button(frame_top, text="1. Select ZIP File", command=self.select_zip, width=20).pack(side=tk.LEFT, padx=5)
        self.label_zip = tk.Label(frame_top, text="No file selected", anchor="w", fg="gray")
        self.label_zip.pack(side=tk.LEFT, fill=tk.X, expand=True)

        frame_mid = tk.Frame(main_frame)
        frame_mid.pack(fill=tk.X, pady=5)
        tk.Button(frame_mid, text="2. Save CSV As...", command=self.select_output, width=20).pack(side=tk.LEFT, padx=5)
        self.label_out = tk.Label(frame_mid, text="No file selected", anchor="w", fg="gray")
        self.label_out.pack(side=tk.LEFT, fill=tk.X, expand=True)

        frame_algo = tk.LabelFrame(main_frame, text="Wrapped Settings", padx=10, pady=10)
        frame_algo.pack(fill=tk.X, pady=15)

        tk.Label(frame_algo, text="Target Year:").pack(anchor="w")
        self.entry_year = tk.Entry(frame_algo, width=8)
        self.entry_year.insert(0, "2025")
        self.entry_year.pack(pady=2)

        tk.Label(frame_algo, text="Recency Weight:").pack(anchor="w")
        self.val_recency = tk.DoubleVar(value=0.25)
        tk.Scale(frame_algo, from_=0.0, to=1.0, resolution=0.05, orient=tk.HORIZONTAL, variable=self.val_recency).pack(fill=tk.X)

        tk.Label(frame_algo, text="Time Weight:").pack(anchor="w")
        self.val_time = tk.DoubleVar(value=0.005)
        tk.Scale(frame_algo, from_=0.0, to=0.02, resolution=0.001, orient=tk.HORIZONTAL, variable=self.val_time).pack(fill=tk.X)

        tk.Label(frame_algo, text="Min Duration (ms):").pack(anchor="w")
        self.entry_ms = tk.Entry(frame_algo, width=8)
        self.entry_ms.insert(0, "30000")
        self.entry_ms.pack(pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=15)
        self.status_label = tk.Label(main_frame, text="Ready", fg="blue")
        self.status_label.pack(anchor="w")

        self.run_button = tk.Button(main_frame, text="GENERATE SEQUENCE", command=self.run_process,
                                    bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), state=tk.DISABLED)
        self.run_button.pack(fill=tk.X, pady=5)

        self.copy_button = tk.Button(main_frame, text="Copy URIs to Clipboard", command=self.copy_to_clipboard,
                                     bg="#dddddd", fg="black", state=tk.DISABLED)
        self.copy_button.pack(fill=tk.X, pady=5)

    def select_zip(self):
        path = filedialog.askopenfilename(filetypes=[("ZIP files", "*.zip")])
        if path:
            self.zip_path = path
            self.label_zip.config(text=path, fg="black")
            if self.output_path:
                self.run_button.config(state=tk.NORMAL)

    def select_output(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if path:
            self.output_path = path
            self.label_out.config(text=path, fg="black")
            if self.zip_path:
                self.run_button.config(state=tk.NORMAL)

    def run_process(self):
        if self.is_running:
            return
        self.is_running, self.final_uris = True, []
        threading.Thread(target=self.process_files, daemon=True).start()

    def copy_to_clipboard(self):
        if not self.final_uris:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(self.final_uris))
        messagebox.showinfo("Copied", f"Copied {len(self.final_uris)} URIs!")

    def normalize_string(self, s):
        if not s: return ""
        s = unicodedata.normalize('NFKD', s).lower()
        parts = re.split(r'[-(\[]', s, maxsplit=1)
        s = parts[0]
        s = re.sub(r'[^\w\s]', '', s)
        return re.sub(r'\s+', ' ', s).strip()

    def process_files(self):
        try:
            min_ms = int(self.entry_ms.get())
            raw_plays = []

            # --- PASS 1: READ ---
            with zipfile.ZipFile(self.zip_path, 'r') as z:
                files = sorted([n for n in z.namelist() if n.endswith('.json')])
                total_files = len(files) or 1
                for i, filename in enumerate(files):
                    self.update_progress((i / total_files) * 30, f"Reading {filename}...")
                    with z.open(filename) as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            data = data.get('items', [])
                        for item in data:
                            if item.get('incognito_mode'): continue

                            uri = item.get('spotify_track_uri') or item.get('uri')
                            ms = item.get('ms_played') if item.get('ms_played') is not None else item.get('msPlayed', 0)
                            if not uri or ms < min_ms: continue

                            ts_str = item.get('ts') or item.get('endTime')
                            dt = None
                            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M"):
                                try:
                                    dt = datetime.datetime.strptime(ts_str, fmt).replace(tzinfo=datetime.timezone.utc)
                                    break
                                except Exception: continue
                            if not dt: continue

                            name = item.get('master_metadata_track_name') or item.get('trackName')
                            artist = item.get('master_metadata_album_artist_name') or item.get('artistName')
                            album = item.get('master_metadata_album_album_name') or item.get('albumName')

                            if not name or not artist: continue
                            if album and "sleep" in album.lower() and "max richter" in artist.lower(): continue

                            raw_plays.append({
                                "dt": dt,
                                "uri": uri,
                                "name": name,
                                "artist": artist,
                                "album": album,
                                "ms": ms,
                                "shuffle": item.get('shuffle', False)
                            })

            # --- PASS 2: SESSIONS & INDEXING ---
            self.update_progress(40, "Building Sessions & Indexing...")
            raw_plays.sort(key=lambda x: x["dt"])

            track_map = {}
            SESSION_TIMEOUT_SEC = 1200 # 20 mins

            current_session_id = 0
            current_session_index = 0
            last_ts_val = 0

            session_history = {}

            for play in raw_plays:
                ts_val = play["dt"].timestamp()

                if (ts_val - last_ts_val) > SESSION_TIMEOUT_SEC:
                    current_session_id += 1
                    current_session_index = 0

                key = f"{self.normalize_string(play['name'])}|{self.normalize_string(play['artist'])}"
                if key not in track_map:
                    track_map[key] = {
                        "main_uri": play["uri"],
                        "name": play["name"],
                        "artist": play["artist"],
                        "album": play["album"],
                        "year_stats": {},
                        "uri_counts": {},
                        "total_plays": 0,
                        "raw_key": key
                    }

                m = track_map[key]
                m["total_plays"] += 1
                m["uri_counts"][play["uri"]] = m["uri_counts"].get(play["uri"], 0) + 1

                if m["uri_counts"][play["uri"]] >= m["uri_counts"].get(m["main_uri"], 0):
                    m["main_uri"] = play["uri"]
                    m["name"] = play["name"]
                    m["artist"] = play["artist"]
                    m["album"] = play["album"]

                y = play["dt"].year
                if y not in m["year_stats"]:
                    m["year_stats"][y] = {
                        "plays": 0, "ms": 0, "last_ts": 0.0
                    }

                ys = m["year_stats"][y]
                ys["plays"] += 1
                ys["ms"] += play["ms"]
                if ts_val > ys["last_ts"]:
                    ys["last_ts"] = ts_val

                # --- SESSION RECORDING (Only Non-Shuffle) ---
                if not play["shuffle"]:
                    if key not in session_history:
                        session_history[key] = {}
                    if current_session_id not in session_history[key]:
                        session_history[key][current_session_id] = current_session_index

                current_session_index += 1
                last_ts_val = ts_val

            # --- COMPARATOR (Shared Sessions Only) ---
            def compare_tracks(t1, t2):
                k1 = t1["_raw_key"]
                k2 = t2["_raw_key"]

                hist1 = session_history.get(k1, {})
                hist2 = session_history.get(k2, {})

                common_sessions = set(hist1.keys()) & set(hist2.keys())

                if not common_sessions:
                    return 0

                t1_wins = 0
                t2_wins = 0

                for sid in common_sessions:
                    idx1 = hist1[sid]
                    idx2 = hist2[sid]
                    if idx1 < idx2:
                        t1_wins += 1
                    elif idx2 < idx1:
                        t2_wins += 1

                return t2_wins - t1_wins

            # --- HELPER: Process a block of same-artist tracks ---
            def process_artist_block(block):
                if not block: return []

                # 1. Score Albums (Max Score)
                album_max_scores = {}
                for t in block:
                    alb = t.get("Album Name", "")
                    if alb not in album_max_scores: album_max_scores[alb] = 0
                    if t["_score"] > album_max_scores[alb]: album_max_scores[alb] = t["_score"]

                # 2. Sort by Album Score then Name
                block.sort(key=lambda t: (
                    -album_max_scores.get(t.get("Album Name", ""), 0),
                    t.get("Album Name", "")
                ))

                # 3. Sort internally by Session History
                current_album_start = 0
                for k in range(len(block)):
                    is_last = (k == len(block) - 1)
                    if is_last or block[k].get("Album Name") != block[k+1].get("Album Name"):
                        album_slice = block[current_album_start : k+1]
                        if len(album_slice) > 1:
                            # Strict shared-session sort only within album
                            album_slice.sort(key=cmp_to_key(compare_tracks))

                        block[current_album_start : k+1] = album_slice
                        current_album_start = k + 1
                return block

            # --- PASS 3: SCORING & FINAL SORT ---
            self.update_progress(60, "Calculations...")
            all_unique_tracks = [v for v in track_map.values() if v["total_plays"] > 1]
            all_unique_tracks.sort(key=lambda x: x["total_plays"], reverse=True)
            top_11000 = all_unique_tracks[:11000]

            rec_w = self.val_recency.get() * 10000.0
            time_w = self.val_time.get() * 10000.0

            year_buckets = {}
            for d in top_11000:
                home_year = max(d["year_stats"].keys(), key=lambda yy: d["year_stats"][yy]["plays"])
                ys = d["year_stats"][home_year]
                y_start = datetime.datetime(home_year, 1, 1, tzinfo=datetime.timezone.utc).timestamp()

                score = (
                    ys["plays"] * 10000.0
                    + max(0.0, (ys["last_ts"] - y_start) / 86400.0) * rec_w
                    + (ys["ms"] / 60000.0) * time_w
                )

                if home_year not in year_buckets:
                    year_buckets[home_year] = []

                year_buckets[home_year].append({
                    "Track URI": d["main_uri"],
                    "Track Name": d["name"],
                    "Artist Name(s)": d["artist"],
                    "Album Name": d["album"],
                    "Year": home_year,
                    "Total Plays": d["total_plays"],
                    "_score": score,
                    "_raw_key": d["raw_key"]
                })

            final_list = []
            sorted_years = sorted(year_buckets.keys(), reverse=True)

            self.update_progress(80, "Applying Smart Cluster Fix...")

            for y in sorted_years:
                year_block = year_buckets[y]
                # 1. Base Sort: Score Descending
                year_block.sort(key=lambda x: -x["_score"])

                # 2. DISRUPTION FIXER LOOP
                i = 0
                while i < len(year_block) - 2:
                    curr_track = year_block[i]
                    intruder = year_block[i+1]
                    reunion = year_block[i+2]

                    curr_artist = curr_track.get("Artist Name(s)")
                    intruder_artist = intruder.get("Artist Name(s)")
                    reunion_artist = reunion.get("Artist Name(s)")

                    # Check pattern: A -> B -> A
                    if (curr_artist == reunion_artist) and (curr_artist != intruder_artist):
                        # FIX: Pull the Reunion track up
                        track_to_move = year_block.pop(i+2)
                        year_block.insert(i+1, track_to_move)

                        # --- CLUSTER RE-SORT LOGIC ---
                        # 1. Identify the full Artist Block built so far
                        block_start = i
                        while block_start > 0 and year_block[block_start-1].get("Artist Name(s)") == curr_artist:
                            block_start -= 1

                        block_end = i + 2
                        while block_end < len(year_block) and year_block[block_end].get("Artist Name(s)") == curr_artist:
                            block_end += 1

                        sub_block = year_block[block_start : block_end]

                        # Use the helper function to sort this specific cluster correctly (Album -> Session)
                        sorted_sub_block = process_artist_block(sub_block)

                        # Apply sorted cluster back to main list
                        year_block[block_start : block_end] = sorted_sub_block

                        # Continue loop without incrementing 'i' to catch chained disruptions
                        continue

                    i += 1

                # 3. Final Polish for existing contiguous blocks (ones that weren't "broken")
                # This ensures consistent sorting logic across the entire file
                grouped_list = []
                current_artist_block = []
                last_artist = None

                for track in year_block:
                    curr_artist = track.get("Artist Name(s)")

                    if last_artist is not None and curr_artist != last_artist:
                        grouped_list.extend(process_artist_block(current_artist_block))
                        current_artist_block = []

                    current_artist_block.append(track)
                    last_artist = curr_artist

                if current_artist_block:
                    grouped_list.extend(process_artist_block(current_artist_block))

                final_list.extend(grouped_list)

            self.final_uris = [t["Track URI"] for t in final_list]

            with open(self.output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "Track URI", "Track Name", "Artist Name(s)",
                        "Album Name", "Year", "Total Plays", "Score"
                    ],
                    extrasaction='ignore'
                )
                writer.writeheader()
                for r in final_list:
                    r["Score"] = f"{r['_score']:.2f}"
                    writer.writerow(r)

            self.finish_gui("Success", f"Saved {len(final_list)} tracks.", False)
        except Exception as e:
            self.finish_gui("Error", str(e), True)

    def update_progress(self, val, text):
        self.root.after(0, lambda: (self.progress_var.set(val), self.status_label.config(text=text)))

    def finish_gui(self, title, msg, err):
        def _u():
            self.is_running = False
            self.copy_button.config(state=tk.NORMAL if not err else tk.DISABLED)
            messagebox.showinfo(title, msg)
        self.root.after(0, _u)

if __name__ == "__main__":
    root = tk.Tk()
    app = HistoryMergerApp(root)
    root.mainloop()
