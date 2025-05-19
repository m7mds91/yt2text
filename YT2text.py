import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import subprocess
import whisper
import os
import torch
import traceback
from tkinterdnd2 import DND_FILES, TkinterDnD


class YouTubeTranscriberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎧 YouTube & File Transcriber (Manual Only)")
        self.root.geometry("940x780")

        self.language_var = tk.StringVar(value="English")
        self.link_var = tk.StringVar()
        self.model_choice_var = tk.StringVar(value="medium")
        self.transcript_text = ""
        self.device_label_var = tk.StringVar(value="Detecting device...")
        self.show_progress_var = tk.BooleanVar(value=True)
        self.current_input_path = None

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device_label_var.set(
            f"✅ Using GPU: {torch.cuda.get_device_name(0)}"
            if self.device == "cuda"
            else "🖥 Using CPU"
        )

        self.create_widgets()

    def create_widgets(self):
        tk.Label(self.root, text="🎥 YouTube Video URL (or leave empty to use dropped file):").pack(pady=(10, 0))
        tk.Entry(self.root, textvariable=self.link_var, width=110).pack(pady=5)

        tk.Label(self.root, text="🌍 Select Language:").pack()
        ttk.Combobox(self.root, textvariable=self.language_var, values=["English", "Arabic"]).pack()

        options_frame = tk.Frame(self.root)
        options_frame.pack(pady=10)
        tk.Checkbutton(options_frame, text="📊 Show Progress Bar", variable=self.show_progress_var).grid(row=0, column=0, padx=10)

        model_frame = tk.Frame(self.root)
        model_frame.pack(pady=5)
        tk.Label(model_frame, text="🧩 Select Whisper Model:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Combobox(model_frame, textvariable=self.model_choice_var, values=["small", "medium", "large"], width=10).pack(side=tk.LEFT)

        tk.Label(self.root, textvariable=self.device_label_var, fg="blue").pack(pady=(5, 0))

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="🎬 Start Transcription", command=self.start_transcription_thread).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="💾 Export Transcript", command=self.export_transcript).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🔄 Reset / Clear All", command=self.reset_gui).pack(side=tk.LEFT, padx=5)

        self.progress_bar = ttk.Progressbar(self.root, mode="indeterminate", length=300)
        self.progress_bar.pack(pady=5)

        tk.Label(self.root, text="📂 Or drag and drop a local audio/video file below:").pack(pady=(10, 0))
        self.drop_area = tk.Label(self.root, text="🪄 Drop file here", relief="groove", borderwidth=2, height=2)
        self.drop_area.pack(fill=tk.X, padx=40, pady=10)

        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_file_drop)

        tk.Label(self.root, text="📝 Transcript:").pack()
        self.text_area = tk.Text(self.root, wrap=tk.WORD, height=25)
        self.text_area.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

    def handle_file_drop(self, event):
        filepath = event.data.strip().strip("{").strip("}")
        if not os.path.exists(filepath):
            messagebox.showerror("Invalid File", "The dropped file does not exist.")
            return
        self.current_input_path = filepath
        self.link_var.set("")
        self.log(f"📂 File selected: {filepath}")

    def start_transcription_thread(self):
        thread = threading.Thread(target=self.transcribe_video)
        thread.start()

    def get_duration_with_ffmpeg(self, filepath):
        try:
            result = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                filepath
            ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            return float(result.stdout)
        except Exception as e:
            self.log(f"⚠️ Failed to get duration: {e}")
            return 0

    def transcribe_video(self):
        self.text_area.delete(1.0, tk.END)
        self.transcript_text = ""
        is_youtube_file = False

        if self.show_progress_var.get():
            self.progress_bar.start()

        try:
            input_path = self.link_var.get().strip()
            if input_path.startswith("http"):
                self.log("⏬ Downloading YouTube audio...")
                audio_file = "audio.mp3"
                subprocess.run([
                    "yt-dlp", "-f", "bestaudio",
                    "-x", "--audio-format", "mp3",
                    "-o", audio_file, input_path
                ], check=True)
                is_youtube_file = True
            elif self.current_input_path and os.path.exists(self.current_input_path):
                self.log(f"📂 Using dropped file: {self.current_input_path}")
                audio_file = self.current_input_path
            else:
                messagebox.showwarning("No Input", "Please paste a YouTube URL or drop a file.")
                self.progress_bar.stop()
                return

            self.log("🧩 Selected model: " + self.model_choice_var.get())
            model = whisper.load_model(self.model_choice_var.get()).to(self.device)

            lang = self.language_var.get()
            whisper_lang = "en" if lang == "English" else "ar"

            self.log("🔍 Transcribing...")
            result = model.transcribe(audio_file, language=whisper_lang, fp16=(self.device == "cuda"))

            self.transcript_text = result["text"]
            self.text_area.insert(tk.END, self.transcript_text)

            if is_youtube_file and os.path.exists(audio_file):
                os.remove(audio_file)
                self.log("🧹 Deleted temporary file: audio.mp3")

        except Exception as e:
            self.log("❌ Error during transcription")
            self.log(traceback.format_exc())
            messagebox.showerror("Transcription Failed", str(e))
        finally:
            self.progress_bar.stop()

    def export_transcript(self):
        if not self.transcript_text:
            messagebox.showwarning("⚠️ No Transcript", "No transcript available to export.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.transcript_text)
            messagebox.showinfo("✅ Saved", "Transcript exported successfully.")

    def reset_gui(self):
        self.link_var.set("")
        self.language_var.set("English")
        self.model_choice_var.set("medium")
        self.current_input_path = None
        self.transcript_text = ""
        self.text_area.delete(1.0, tk.END)

        # 🧹 Delete YouTube audio file if exists
        if os.path.exists("audio.mp3"):
            try:
                os.remove("audio.mp3")
                self.log("🧹 Removed old YouTube file: audio.mp3")
            except Exception as e:
                self.log(f"⚠️ Could not delete audio.mp3: {e}")

        self.log("🔄 Reset complete.")

    def log(self, message):
        self.text_area.insert(tk.END, message + "\n")
        self.text_area.see(tk.END)


# Run the app
if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = YouTubeTranscriberApp(root)
    root.mainloop()
