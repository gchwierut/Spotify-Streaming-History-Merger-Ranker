import json
import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from collections import defaultdict, deque
import zipfile
import re
import threading

class HistoryMergerApp:
    def __init__(self, root):
        self.root = root
        root.title("Merge Streaming Histories to CSV")
        root.geometry("600x650")

        self.zip_path = None
        self.output_path = None
        self.is_running = False
        self.stop_event = threading.Event()
        self.final_uris = []

        self.re_parens = re.compile(r'\s*[\(\[].*?[\)\]]')
        self.re_dash = re.compile(r'\s+[-–—]\s+')
        self.re_live = re.compile(r'\b(live|concert|ao vivo)\b', re.IGNORECASE)
        self.re_bad_brackets = re.compile(r'[\(\[]')
        self.re_bad_dash = re.compile(r'\s[-–—]|\s[-–—]\s')

        main_frame = tk.Frame(root, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        frame_top = tk.Frame(main_frame)
        frame_top.pack(fill=tk.X, pady=5)
        self.add_button = tk.Button(frame_top, text="1. Select ZIP File", command=self.select_zip, width=20)
        self.add_button.pack(side=tk.LEFT, padx=5)
        self.file_label = tk.Label(frame_top, text="No file selected", fg="gray", anchor="w")
        self.file_label.pack(side=tk.LEFT, padx=5, fill=tk.X)

        frame_mid = tk.Frame(main_frame)
        frame_mid.pack(fill=tk.X, pady=5)
        self.output_button = tk.Button(frame_mid, text="2. Save CSV As...", command=self.choose_output, width=20)
        self.output_button.pack(side=tk.LEFT, padx=5)
        self.out_label = tk.Label(frame_mid, text="No output selected", fg="gray", anchor="w")
        self.out_label.pack(side=tk.LEFT, padx=5, fill=tk.X)

        filter_frame = tk.LabelFrame(main_frame, text="Settings", padx=15, pady=10)
        filter_frame.pack(fill=tk.X, pady=15)
        row1 = tk.Frame(filter_frame)
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="Max tracks in result:", width=20, anchor="w").pack(side=tk.LEFT)
        self.max_tracks_var = tk.StringVar(value="10000")
        tk.Entry(row1, textvariable=self.max_tracks_var, width=10).pack(side=tk.LEFT)
        row2 = tk.Frame(filter_frame)
        row2.pack(fill=tk.X, pady=5)
        self.dedup_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row2, text="Ignore duplicate entries", variable=self.dedup_var).pack(side=tk.LEFT)

        self.run_button = tk.Button(main_frame, text="3. Process History", command=self.toggle_processing, state=tk.DISABLED, bg="#dddddd", height=2, font=("Arial", 10, "bold"))
        self.run_button.pack(pady=5, fill=tk.X)
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(pady=5, fill=tk.X)
        self.status_label = tk.Label(main_frame, text="Ready")
        self.status_label.pack(pady=5)

        self.copy_button = tk.Button(main_frame, text="4. Copy URIs to Clipboard", command=self.copy_uris, state=tk.DISABLED, bg="#dddddd", height=2)
        self.copy_button.pack(pady=10, fill=tk.X)

    def select_zip(self):
        path = filedialog.askopenfilename(filetypes=[("ZIP files", "*.zip")])
        if path:
            self.zip_path = path
            self.file_label.config(text=path.split('/')[-1], fg="black")
            self.update_state()

    def choose_output(self):
        out = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if out:
            self.output_path = out
            self.out_label.config(text=out.split('/')[-1], fg="black")
            self.update_state()

    def update_state(self):
        if self.zip_path and self.output_path and not self.is_running:
            self.run_button.config(state=tk.NORMAL, bg="#4CAF50", fg="white", text="3. Process History")
        elif self.is_running:
            self.run_button.config(state=tk.NORMAL, bg="#f44336", fg="white", text="STOP / CANCEL")
        else:
            self.run_button.config(state=tk.DISABLED, bg="#dddddd")

    def toggle_processing(self):
        if not self.is_running:
            self.is_running = True
            self.stop_event.clear()
            self.update_state()
            self.copy_button.config(state=tk.DISABLED, bg="#dddddd")
            self.status_label.config(text="Initializing...")
            self.progress_var.set(0)
            threading.Thread(target=self.run_process, daemon=True).start()
        else:
            self.stop_event.set()
            self.status_label.config(text="Stopping... Please wait.")
            self.run_button.config(state=tk.DISABLED)

    def copy_uris(self):
        if not self.final_uris:
            messagebox.showinfo("Info", "No URIs available to copy.")
            return
        try:
            self.root.clipboard_clear()
            text_to_copy = "\n".join(self.final_uris)
            self.root.clipboard_append(text_to_copy)
            self.root.update()
            messagebox.showinfo("Copied", f"Successfully copied {len(self.final_uris)} URIs to clipboard!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy to clipboard: {str(e)}")

    # --- LOGIC ---
    def normalize_track_name(self, track_name):
        if not track_name: return track_name
        normalized = track_name
        normalized = self.re_parens.sub('', normalized)
        normalized = normalized.split(',')[0]
        normalized = self.re_dash.split(normalized)[0]
        return normalized.strip().lower()

    def has_suffix_or_bad_chars(self, track_name):
        if not track_name: return False
        if self.re_bad_brackets.search(track_name): return True
        if ',' in track_name: return True
        if self.re_bad_dash.search(track_name): return True
        return False

    def is_live_version(self, track_name):
        if not track_name: return False
        return bool(self.re_live.search(track_name))

    def get_preferred_track_name(self, name1, name2):
        if not name1: return name2
        if not name2: return name1
        bad_1 = self.has_suffix_or_bad_chars(name1)
        bad_2 = self.has_suffix_or_bad_chars(name2)
        if not bad_1 and bad_2: return name1
        elif bad_1 and not bad_2: return name2
        is_live_1 = self.is_live_version(name1)
        is_live_2 = self.is_live_version(name2)
        if not is_live_1 and is_live_2: return name1
        elif is_live_1 and not is_live_2: return name2
        return name1 if len(name1) <= len(name2) else name2

    def extract_year(self, timestamp):
        if not timestamp: return 0
        try: return int(timestamp[:4])
        except: return 0

    def get_sorted_alternative_years(self, track_info, current_year):
        yc = track_info.get('raw_year_counts', {})
        candidates = []
        for y, count in yc.items():
            if y == current_year: continue
            if count > 0:
                candidates.append(y)
        candidates.sort(key=lambda y: yc[y], reverse=True)
        return candidates

    def try_insert_sorted_strict(self, main_list, track, spacing=6):
        """
        RIGOROUS insertion check.
        Checks if insertion at 'i' maintains spacing for:
        1. The new track relative to its Left Neighbors.
        2. The new track relative to its Right Neighbors (who will shift +1).
        3. Existing conflicts? No, existing list is assumed valid.
           But we must ensure we don't push a Right Neighbor closer to a Right-Right Neighbor?
           Wait, insertion only increases distance between Left and Right neighbors.
           So we ONLY need to check the New Track against Left and Right.
        """
        track_score = (-track.get('peak_year_count', 0), -track.get('listen_count', 0))

        artist = track.get('master_metadata_album_artist_name')
        album = track.get('master_metadata_album_album_name')

        # 1. Find Ideal Index
        ideal_idx = len(main_list)
        for i, entry in enumerate(main_list):
            entry_score = (-entry.get('peak_year_count', 0), -entry.get('listen_count', 0))
            if track_score < entry_score:
                ideal_idx = i
                break

        # 2. Find conflict indices in CURRENT list
        conflict_indices = []
        for i, t in enumerate(main_list):
            if (t.get('master_metadata_album_artist_name') == artist) or \
               (t.get('master_metadata_album_album_name') == album):
                conflict_indices.append(i)

        # 3. Scan for valid spot
        # We start at ideal_idx. If we can't fit there, we look further down.
        # This naturally "demotes" the track if it conflicts, preserving rank for others.

        for i in range(ideal_idx, len(main_list) + 1):
            valid = True

            # Check Left Neighbors (Indices < i)
            # Find closest conflict to the left
            # We want max(idx) where idx < i
            left_conflict = -9999
            for idx in conflict_indices:
                if idx < i:
                    left_conflict = idx
                else:
                    break # conflict_indices is sorted if we appended strictly?
                          # Yes, because we scan main_list linearly.

            # Distance check: i - left_conflict >= spacing
            if (i - left_conflict) < spacing:
                valid = False

            # Check Right Neighbors (Indices >= i)
            # These will shift to idx+1.
            # So the new track is at i. The conflict is at old_idx, which becomes old_idx+1.
            # Distance = (old_idx + 1) - i = old_idx - i + 1.

            if valid:
                for idx in conflict_indices:
                    if idx >= i:
                        # This is the closest right conflict
                        dist = idx - i + 1
                        if dist < spacing:
                            valid = False
                        break # Only need the closest one

            if valid:
                main_list.insert(i, track)
                return True

        return False

    def run_process(self):
        try:
            try:
                max_tracks = int(self.max_tracks_var.get())
                if max_tracks < 1: max_tracks = 10000
            except ValueError:
                self.finish_gui("Error", "Numeric fields must contain valid numbers", error=True)
                return

            dedup_enabled = self.dedup_var.get()
            self.final_uris = []

            track_data = defaultdict(lambda: {
                'count': 0, 'total_ms_played': 0, 'year_counts': defaultdict(int),
                'raw_year_counts': defaultdict(int),
                'first_ts': None, 'last_ts': None,
                'preferred_track_name': None,
                'preferred_metadata_entry': None, 'preferred_artist_name': None
            })

            seen_entries = set()
            all_fieldnames = set()
            processed_files = 0

            skipped_count = 0
            incognito_count = 0
            dup_count = 0
            sleep_count = 0
            spacing_rejects = 0

            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                all_files = zf.namelist()
                target_files = [n for n in all_files if n.split('/')[-1].startswith("Streaming_History_Audio_") and n.endswith(".json")]
                total_files = len(target_files)

                if total_files == 0:
                    self.finish_gui("Error", "No Streaming_History_Audio files found in ZIP", error=True)
                    return

                for name in target_files:
                    if self.stop_event.is_set():
                        self.finish_gui("Cancelled", "Processing cancelled.", error=False)
                        return

                    try:
                        with zf.open(name) as f:
                            data = json.loads(f.read().decode('utf-8-sig'))

                        history = data.get("items") or data.get("history") or [] if isinstance(data, dict) else data if isinstance(data, list) else []

                        for entry in history:
                            if isinstance(entry, dict):
                                # DEDUPLICATION (Always ON)
                                ts = entry.get("ts")
                                if not ts: continue
                                uid = entry.get("spotify_track_uri") or (entry.get("master_metadata_track_name") or "") + (entry.get("master_metadata_album_artist_name") or "")
                                unique_key = (ts, uid)

                                if unique_key in seen_entries:
                                    dup_count += 1
                                    continue
                                seen_entries.add(unique_key)

                                if entry.get("skipped") in (True, "True", "true"):
                                    skipped_count += 1
                                    continue
                                if entry.get("incognito_mode") in (True, "True", "true"):
                                    incognito_count += 1
                                    continue

                                all_fieldnames.update(entry.keys())
                                artist = entry.get("master_metadata_album_artist_name")
                                track_raw = entry.get("master_metadata_track_name")
                                if not track_raw: continue

                                artist_clean = artist.strip() if artist else ""
                                track_norm = self.normalize_track_name(track_raw)
                                year = self.extract_year(entry.get("ts"))
                                key = (artist_clean.lower(), track_norm)

                                info = track_data[key]
                                info['count'] += 1
                                info['year_counts'][year] += 1
                                info['raw_year_counts'][year] += 1
                                info['total_ms_played'] += entry.get("ms_played", 0)

                                ts = entry.get("ts")
                                if ts:
                                    if not info['first_ts'] or ts < info['first_ts']: info['first_ts'] = ts
                                    if not info['last_ts'] or ts > info['last_ts']: info['last_ts'] = ts

                                curr_pref = info['preferred_track_name']
                                chosen = self.get_preferred_track_name(curr_pref, track_raw)
                                info['preferred_track_name'] = chosen
                                if not info['preferred_artist_name']: info['preferred_artist_name'] = artist_clean
                                if curr_pref is None or chosen == track_raw:
                                    info['preferred_metadata_entry'] = entry.copy()

                        processed_files += 1
                        self.update_progress((processed_files / total_files) * 50, f"Reading file {processed_files}/{total_files}...")

                    except Exception as e:
                        print(f"Skipped file {name}: {e}")
                        continue

            if self.stop_event.is_set(): return

            self.update_progress(60, "Consolidating Tracks...")

            all_tracks_list = []
            for info in track_data.values():
                best = info['preferred_metadata_entry']
                if info['preferred_artist_name'].lower() == 'max richter' and best.get('master_metadata_album_album_name') == 'Sleep':
                    sleep_count += 1
                    continue

                yc = info['year_counts']
                peak_year = max(yc.keys(), key=lambda y: (yc[y], y)) if yc else 0

                row = best.copy()
                row.update({
                    'master_metadata_track_name': info['preferred_track_name'],
                    'master_metadata_album_artist_name': info['preferred_artist_name'],
                    'master_metadata_album_album_name': best.get('master_metadata_album_album_name'), # Explicitly ensure album
                    'listen_count': info['count'],
                    'peak_year': peak_year,
                    'peak_year_count': yc[peak_year],
                    'total_ms_played': info['total_ms_played'],
                    'first_listen_ts': info['first_ts'],
                    'last_listen_ts': info['last_ts'],
                    'raw_year_counts': info['raw_year_counts']
                })
                all_tracks_list.append(row)

            # SORT GLOBALLY BY LISTEN COUNT
            all_tracks_list.sort(key=lambda x: -x['listen_count'])

            self.update_progress(70, "Processing & Filling Quota...")

            # --- INFINITE FILL LOOP ---
            finalized_years = defaultdict(list)
            accepted_total = 0

            for track in all_tracks_list:
                if accepted_total >= max_tracks:
                    break

                # 1. Try Peak Year
                peak = track['peak_year']
                if self.try_insert_sorted_strict(finalized_years[peak], track, spacing=6):
                    accepted_total += 1
                    continue

                # 2. Try Alternative Years
                alts = self.get_sorted_alternative_years(track, peak)
                placed = False
                for alt_year in alts:
                    track['peak_year'] = alt_year
                    track['peak_year_count'] = track['raw_year_counts'][alt_year]

                    if self.try_insert_sorted_strict(finalized_years[alt_year], track, spacing=6):
                        accepted_total += 1
                        placed = True
                        break

                if not placed:
                    spacing_rejects += 1

            # Flatten results
            final_rows = []
            for y in sorted(finalized_years.keys(), reverse=True):
                final_rows.extend(finalized_years[y])

            # Store URIs
            self.final_uris = [row.get('spotify_track_uri', '') for row in final_rows if row.get('spotify_track_uri')]

            self.update_progress(90, "Writing CSV...")

            prio = ['peak_year', 'peak_year_count', 'listen_count', 'master_metadata_track_name',
                    'master_metadata_album_artist_name', 'master_metadata_album_album_name',
                    'total_ms_played', 'first_listen_ts', 'last_listen_ts', 'spotify_track_uri']
            fields = prio + sorted([f for f in all_fieldnames if f not in prio and f not in ['ms_played', 'ts']])

            with open(self.output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(final_rows)

            self.update_progress(100, "Done!")

            stats_msg = f"Success! Created {len(final_rows)} tracks."
            details = []
            if skipped_count: details.append(f"Skipped (Flag): {skipped_count}")
            if incognito_count: details.append(f"Incognito Mode: {incognito_count}")
            if dup_count: details.append(f"Duplicates Removed: {dup_count}")
            if sleep_count: details.append(f"Sleep Filtered: {sleep_count}")
            if spacing_rejects: details.append(f"Spacing Conflicts Skipped: {spacing_rejects}")
            details.append(f"Total Reviewed: {accepted_total + spacing_rejects}")

            if details:
                stats_msg += "\n\nStats:\n" + "\n".join(details)

            self.finish_gui("Done", stats_msg, error=False)

        except Exception as e:
            self.finish_gui("Error", str(e), error=True)

    def update_progress(self, val, text):
        def _update():
            self.progress_var.set(val)
            self.status_label.config(text=text)
        self.root.after(0, _update)

    def finish_gui(self, title, message, error=False):
        def _update():
            self.is_running = False
            self.progress_var.set(0)
            self.update_state()
            self.status_label.config(text=title)

            if not error and self.final_uris:
                self.copy_button.config(state=tk.NORMAL, bg="#2196F3", fg="white")
            else:
                self.copy_button.config(state=tk.DISABLED, bg="#dddddd", fg="black")

            if error:
                messagebox.showerror(title, message)
            else:
                messagebox.showinfo(title, message)
        self.root.after(0, _update)

if __name__ == "__main__":
    root = tk.Tk()
    app = HistoryMergerApp(root)
    root.mainloop()
