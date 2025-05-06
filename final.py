import sys
import os
import tkinter as tk
from tkinter import messagebox
import firebase_admin
from firebase_admin import credentials, firestore
import bcrypt
import uuid
from datetime import datetime
from firebase_admin.firestore import SERVER_TIMESTAMP
from firebase_admin import storage
from tkinter import filedialog
from firebase_admin import storage
from supabase import create_client, Client
import re
import webbrowser
import tkinter.filedialog as filedialog
from tkinter import scrolledtext
import cv2
from PIL import Image, ImageTk
import socket
import numpy as np
import pickle
import struct
import threading
from tkinter import Toplevel, Frame, Label, Listbox, Entry, Button, END, LEFT, BOTH, Y, X
import tempfile
import time
import sounddevice as sd
from scipy.io.wavfile import write
import numpy as np
import subprocess
from datetime import datetime
import wave

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

json_path = os.path.join(base_path, "networkapp-fab62-firebase-adminsdk-fbsvc-69c7879b05.json")
running = True
# Initialize Firebase
cred = credentials.Certificate(json_path)
firebase_admin.initialize_app(cred, {
    'storageBucket': 'networkapp-fab62.appspot.com'
})
db = firestore.client()
bucket = storage.bucket()
def check_online_users():
    """ Periodically checks user activity and marks them offline if inactive. """
    while running is True:
        if running is False: os._exit(0)
        try:
            if running is False: break
            # Step 0: Write and fetch current server time
            server_time_ref = db.collection("server_time").document("now")
            server_time_ref.set({"timestamp": firestore.SERVER_TIMESTAMP})

            time.sleep(1)  # Give Firestore 1 sec to populate timestamp

            server_snapshot = server_time_ref.get()
            server_time = server_snapshot.to_dict().get("timestamp")

            if not isinstance(server_time, datetime):
                print("[ERROR] Could not retrieve server time.")
                wait_with_check(30)
                continue

            users_ref = db.collection("users").stream()

            for user_doc in users_ref:
                user_data = user_doc.to_dict()
                username = user_doc.id
                alive = user_data.get("alive", 0)
                last_check = user_data.get("last_check", None)

                # Reset alive and set new last_check
                db.collection("users").document(username).update({
                    "alive": 0,
                    "last_check": firestore.SERVER_TIMESTAMP
                })

                if alive == 0 and isinstance(last_check, datetime):
                    if last_check.tzinfo:
                        last_check = last_check.replace(tzinfo=None)
                    if server_time.tzinfo:
                        server_time = server_time.replace(tzinfo=None)

                    elapsed_time = (server_time - last_check).total_seconds()
                    print(elapsed_time)
                    if elapsed_time > 30:
                        db.collection("users").document(username).update({
                            "status": "offline",
                            "active_session": None,
                            "IP": None
                        })

            wait_with_check(30)  # Replace time.sleep(30)
        except Exception as e:
            print(f"[ERROR] in check_online_users: {e}")
            wait_with_check(5)  # Wait before retrying

def wait_with_check(seconds):
    """ Sleep in small increments so we can check if we should stop. """
    interval = 0.5  # check every 0.5 sec
    total = 0
    while running and total < seconds:
        time.sleep(interval)
        total += interval

class VideoStreamer:
    def __init__(self, host_ip, port, root, username, channel, stop_callback=None):
        self.host_ip = host_ip
        self.port = port
        self.root = root
        self.username = username
        self.channel = channel
        self.stop_callback = stop_callback

        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.comment_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.comment_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.clients = []
        self.audio_clients = []
        self.comment_clients = []
        self.running = False

        # File paths
        self.base_dir = os.path.join(tempfile.gettempdir(), f"stream_{channel}")
        os.makedirs(self.base_dir, exist_ok=True)
        self.video_path = os.path.join(self.base_dir, "stream_video.avi")
        self.audio_path = os.path.join(self.base_dir, "stream_audio.wav")
        self.merged_path = os.path.join(self.base_dir, "merged_stream.mp4")
        self.comment_file = os.path.join(self.base_dir, "comments.txt")

        self.init_stream_window()

    def init_stream_window(self):
        self.stream_win = Toplevel(self.root)
        self.stream_win.title(f"{self.username}'s Stream")

        center_frame = Frame(self.stream_win)
        center_frame.pack(side=LEFT, fill=BOTH, expand=True)
        self.video_label = Label(center_frame)
        self.video_label.pack(fill=BOTH, expand=True)

        right_frame = Frame(self.stream_win)
        right_frame.pack(side=LEFT, fill=Y)
        Label(right_frame, text="Comments").pack()
        self.comments_listbox = Listbox(right_frame, height=10, width=30)
        self.comments_listbox.pack(fill=BOTH, expand=True)
        self.comment_entry = Entry(right_frame)
        self.comment_entry.pack(fill=X)
        Button(right_frame, text="Send Comment", command=self.add_comment).pack()

        Button(self.stream_win, text="End Stream", command=self.stop).pack(side='bottom', pady=10)

        threading.Thread(target=self.sync_comments_file, daemon=True).start()

    def sync_comments_file(self):
        last_seen = 0
        while self.running:
            if not os.path.exists(self.comment_file):
                continue
            with open(self.comment_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[last_seen:]:
                    self.comments_listbox.insert(END, line.strip())
                last_seen = len(lines)
            time.sleep(1)

    def add_comment(self):
        text = self.comment_entry.get().strip()
        if text:
            message = f"{self.username}: {text}"
            self.comments_listbox.insert(END, message)
            self.comment_entry.delete(0, END)
            with open(self.comment_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")
            for client in self.comment_clients[:]:
                try:
                    client.sendall(pickle.dumps(message))
                except:
                    self.comment_clients.remove(client)

    def start_stream(self):
        try:
            self.video_socket.bind((self.host_ip, self.port))
            self.comment_socket.bind((self.host_ip, self.port + 1))
        except OSError as e:
            print(f"[ERROR] Could not bind to ports: {e}")
            return

        self.video_socket.listen(5)
        self.comment_socket.listen(5)
        self.running = True

        threading.Thread(target=self.accept_video_clients, daemon=True).start()
        threading.Thread(target=self.accept_comment_clients, daemon=True).start()
        threading.Thread(target=self.stream_video, daemon=True).start()
        threading.Thread(target=self.record_audio, daemon=True).start()
        threading.Thread(target=self.stream_video, daemon=True).start()
        threading.Thread(target=self.stream_audio, daemon=True).start()
        threading.Thread(target=self.stream_comments, daemon=True).start()

    def record_audio(self):
        print("[INFO] Recording audio...")
        fs = 44100
        self.audio_data = sd.rec(int(fs * 1), samplerate=fs, channels=2)
        sd.wait()
        write(self.audio_path, fs, self.audio_data.astype(np.int16))

    def stream_audio(self):
        print("[INFO] Streaming audio...")
        fs = 44100
        seconds = 1  # 1 second chunks
    
        with sd.InputStream(samplerate=fs, channels=2, dtype='int16') as stream:
            with wave.open(self.audio_path, 'wb') as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(fs)

                while self.running:
                    audio_chunk = stream.read(int(fs * seconds))[0]
                    wf.writeframes(audio_chunk.tobytes())
                    for client in self.audio_clients[:]:
                        try:
                            client.sendall(audio_chunk.tobytes())
                        except:
                            self.audio_clients.remove(client)

    def accept_audio_clients(self):
        while self.running:
            try:
                client_socket, _ = self.audio_socket.accept()
                self.audio_clients.append(client_socket)
            except:
                break
    
    def accept_video_clients(self):
        while self.running:
            try:
                client_socket, _ = self.video_socket.accept()
                self.clients.append(client_socket)
            except:
                break

    def accept_comment_clients(self):
        while self.running:
            try:
                comment_client, _ = self.comment_socket.accept()
                self.comment_clients.append(comment_client)
            except:
                break
    def stream_comments(self):
        comment_file = "comments.txt"
        print("[INFO] Starting comment stream...")
        if not os.path.exists(comment_file):
            with open(comment_file, "w") as f:
                f.write("")
    
        last_seen = ""
        while self.running:
            try:
                with open(comment_file, "r") as f:
                    comments = f.read()
                    if comments != last_seen:
                        new_comment = comments[len(last_seen):]
                        last_seen = comments
                        for client in self.comment_clients[:]:
                            try:
                                client.sendall(new_comment.encode())
                            except:
                                self.comment_clients.remove(client)
            except Exception as e:
                print(f"[ERROR] reading comment file: {e}")
            time.sleep(1)
    
    def stream_video(self):
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FPS, 16)

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) // 2)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) // 2)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(self.video_path, fourcc, 16.0, (width, height))

        last_frame_time = 0
        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.resize(frame, (width, height))
            frame = cv2.flip(frame, 1)
            out.write(frame)

            if self.stream_win.winfo_exists():
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk)

            data = pickle.dumps(frame)
            message = struct.pack("Q", len(data)) + data
            for client in self.clients[:]:
                try:
                    client.sendall(message)
                except:
                    self.clients.remove(client)

            elapsed = time.time() - last_frame_time
            if elapsed < 1 / 16:
                time.sleep((1 / 16) - elapsed)
            last_frame_time = time.time()

        cap.release()
        out.release()
        cv2.destroyAllWindows()

    def stop(self):
        self.running = False
        
        db.collection("channels").document(self.channel).set({
            "is_streaming": False,
            "owner": self.username
        })
        
        # Close all client sockets
        for client in self.clients:
            client.close()
        for client in self.comment_clients:
            client.close()
        self.video_socket.close()
        self.comment_socket.close()

        if self.stream_win.winfo_exists():
            self.stream_win.destroy()

        # Merge audio + video file if recorded
        try:
            command = [
                "ffmpeg",
                "-y",
                "-i", self.video_path,  # Merged video+audio
                "-i", self.audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                self.merged_path
            ]
            subprocess.run(command, check=True)
            print(f"[INFO] Merged and saved to {self.merged_path}")
            messagebox.showinfo("Merge Complete", f"Video with audio saved to:\n\n{self.merged_path}")

        except Exception as e:
            print(f"[ERROR] merging audio + video: {e}")  
            return



class VideoViewer:
    def __init__(self, root, streamer_ip, port, username, channel):
        self.root = root
        self.streamer_ip = streamer_ip
        self.port = port
        self.username = username
        self.channel = channel

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.comment_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.stream_win = Toplevel(self.root)
        self.stream_win.title(f"Viewing Stream - {channel}")

        center_frame = Frame(self.stream_win)
        center_frame.pack(side=LEFT, fill=BOTH, expand=True)
        self.video_label = Label(center_frame)
        self.video_label.pack(fill=BOTH, expand=True)

        right_frame = Frame(self.stream_win)
        right_frame.pack(side=LEFT, fill=Y)
        Label(right_frame, text="Comments").pack()
        self.comment_listbox = Listbox(right_frame)
        self.comment_listbox.pack(fill=BOTH, expand=True)
        self.comment_entry = Entry(right_frame)
        self.comment_entry.pack(fill=X)
        Button(right_frame, text="Send", command=self.send_comment).pack()
        Button(self.stream_win, text="Disconnect", command=self.disconnect).pack(side="bottom", pady=5)

        # Sync comment file
        self.comment_file = os.path.join(tempfile.gettempdir(), f"stream_{channel}/comments.txt")
        self.last_seen = 0
        threading.Thread(target=self.sync_comment_file, daemon=True).start()
        threading.Thread(target=self.receive_stream, daemon=True).start()
        threading.Thread(target=self.receive_comments, daemon=True).start()

    def sync_comment_file(self):
        while True:
            if os.path.exists(self.comment_file):
                with open(self.comment_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines[self.last_seen:]:
                        self.comment_listbox.insert(END, line.strip())
                    self.last_seen = len(lines)
            time.sleep(1)

    def receive_stream(self):
        self.client_socket.connect((self.streamer_ip, self.port))
        data = b""
        payload_size = struct.calcsize("Q")
        while True:
            while len(data) < payload_size:
                packet = self.client_socket.recv(4 * 1024)
                if not packet:
                    return
                data += packet
            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("Q", packed_msg_size)[0]
            while len(data) < msg_size:
                data += self.client_socket.recv(4 * 1024)
            frame_data = data[:msg_size]
            data = data[msg_size:]
            frame = pickle.loads(frame_data)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)

    def receive_comments(self):
        try:
            self.comment_socket.connect((self.streamer_ip, self.port + 1))
            while True:
                data = self.comment_socket.recv(4096)
                if not data:
                    break
                comment = pickle.loads(data)
                self.comment_listbox.insert(END, comment)
        except Exception as e:
            print(f"[ERROR] receiving comment: {e}")

    def send_comment(self):
        text = self.comment_entry.get().strip()
        if text:
            message = f"{self.username}: {text}"
            try:
                self.comment_socket.sendall(pickle.dumps(message))
            except:
                pass
            with open(self.comment_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")
            self.comment_listbox.insert(END, message)
            self.comment_entry.delete(0, END)

    def disconnect(self):
        self.client_socket.close()
        self.comment_socket.close()
        self.stream_win.destroy()

class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Chat App")
        self.username = None
        self.is_guest = False
        self.session_id = None
        self.is_invisible = False
        self.create_login_screen()
        SUPABASE_URL = "https://ttmgqheohwmiavcnabix.supabase.co"
        SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR0bWdxaGVvaHdtaWF2Y25hYml4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDMxNzkxODUsImV4cCI6MjA1ODc1NTE4NX0.E17CFr1F-Sjq7D-2T_sdxdIOM_AR9-51tl2ct6AzpmM"

        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.supabase_bucket = "chat-app-database"  # Replace with your bucket name

    def open_link(event):
        selected = event.widget.curselection()
        if selected:
            text = event.widget.get(selected[0])
            if "http" in text:  # Detects if it's a URL
                url = text.split(": ", 1)[1]  # Extract URL part
                webbrowser.open(url)
                # Bind click event to message list
        self.message_listbox.bind("<Double-Button-1>", open_link)

    def create_login_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        
        tk.Label(self.root, text="Username:").pack()
        self.username_entry = tk.Entry(self.root)
        self.username_entry.pack()
        
        tk.Label(self.root, text="Password:").pack()
        self.password_entry = tk.Entry(self.root, show="*")
        self.password_entry.pack()
        
        tk.Button(self.root, text="Login", command=self.login).pack()
        tk.Button(self.root, text="Register", command=self.register).pack()
        tk.Button(self.root, text="Guest", command=self.enter_as_guest).pack()
    
    def register(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Username and password required!")
            return
        
        user_doc = db.collection("users").document(username).get()
        if user_doc.exists:
            messagebox.showerror("Error", "Username already exists! Choose another.")
            return
        
        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        db.collection("users").document(username).set({
            "password": hashed_pw.decode(),
            "status": "offline",
            "active_session": None
        })
        messagebox.showinfo("Success", "User registered! Please log in.")
    
    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            messagebox.showerror("Error", "Username and password required!")
            return

        user_ref = db.collection("users").document(username)
        user_doc = user_ref.get()

        if user_doc.exists:
            user_data = user_doc.to_dict()
            stored_hash = user_data["password"].encode()

            if bcrypt.checkpw(password.encode(), stored_hash):
                active_session = user_data.get("active_session")
            
                # Generate a unique session ID
                self.session_id = str(uuid.uuid4())
                user_ref.update({"active_session": self.session_id, "status": "online"})  # Lock login

                self.username = username
                self.is_guest = False
                messagebox.showinfo("Login Successful", f"Welcome, {self.username}!")
                self.root.withdraw()
                self.create_chat_screen()
                return

        messagebox.showerror("Error", "Invalid username or password")

    def logout(self):
        if self.username and not self.is_guest:
            user_ref = db.collection("users").document(self.username)
            user_doc = user_ref.get()

            if user_doc.exists:
                active_session = user_doc.to_dict().get("active_session")
                if active_session == self.session_id:
                    user_ref.update({"active_session": None, "status": "offline"})
        self.create_login_screen()
        self.root.deiconify()
        self.chat_screen.destroy()  # Close chat window
        

    def enter_as_guest(self):
        self.username = "Guest"
        self.is_guest = True
        self.create_chat_screen()

    def create_chat_screen(self):
        self.chat_screen = tk.Toplevel(self.root)
        self.chat_screen.title("Chat")
        self.chat_screen.protocol("WM_DELETE_WINDOW", self.on_closing)
        # Create main layout frames
        self.left_frame = tk.Frame(self.chat_screen)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.middle_frame = tk.Frame(self.chat_screen)
        self.middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.right_frame = tk.Frame(self.chat_screen)
        self.right_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.buttons_frame = tk.Frame(self.middle_frame)
        self.buttons_frame.pack(fill=tk.X)
        
        self.message_listbox = tk.Listbox(self.middle_frame)
        self.message_listbox.pack(fill=tk.BOTH, expand=True)
        name = self.username
        self.users_label = tk.Label(self.left_frame, text=f"Welcome: {name}")
        self.users_label.pack()
        
        # Online users list
        self.online_users_label = tk.Label(self.left_frame, text="Online Users")
        self.online_users_label.pack()
        self.online_users_listbox = tk.Listbox(self.left_frame)
        self.online_users_listbox.pack(fill=tk.BOTH, expand=True)

        #Invisible toggle
        self.invisible_button = tk.Button(self.left_frame, text="Go Invisible", command=self.toggle_invisible)
        self.invisible_button.pack(pady=5)
        
        self.logout_button = tk.Button(self.left_frame, text="Log Out", command=self.logout)
        self.logout_button.pack(pady=5)
        
        # Channel selection
        self.channel_label = tk.Label(self.right_frame, text="Select a Channel")
        self.channel_label.pack()
        self.channel_listbox = tk.Listbox(self.right_frame)
        self.channel_listbox.pack(fill=tk.BOTH, expand=True)
        self.channel_listbox.bind("<<ListboxSelect>>", self.load_messages)

        # Create Channel button
        self.new_channel_entry = tk.Entry(self.right_frame)  # Entry field for new channel
        self.new_channel_entry.pack(fill=tk.X, pady=5)
        self.create_channel_button = tk.Button(self.right_frame, text="Create Channel", command=self.create_channel)
        self.create_channel_button.pack(pady=5)

        # Messages area
        self.messages_text = tk.Text(self.middle_frame, state=tk.DISABLED, wrap=tk.WORD)
        self.messages_text.pack(fill=tk.BOTH, expand=True)

        # Input field
        self.message_entry = tk.Entry(self.middle_frame)
        self.message_entry.pack(fill=tk.X)
        self.message_entry.bind("<Return>", lambda event: self.send_message())

        # Send button
        self.send_button = tk.Button(self.buttons_frame, text="Send", command=self.send_message)
        self.send_button.pack()
        self.send_file_button = tk.Button(self.buttons_frame, text="Send File", command=self.upload_file)
        self.send_file_button.pack(side=tk.LEFT, expand=True)

        self.stream_button = tk.Button(self.buttons_frame, text="Stream", command=self.start_stream)
        self.stream_button.pack(side=tk.LEFT, expand=True)
        self.join_stream_button = tk.Button(self.buttons_frame, text="Join Stream", command=self.join_stream)
        self.join_stream_button.pack(side=tk.LEFT, expand=True)
        
        # Load initial data
        
        self.load_online_users()
        self.listen_to_channels()

        # Refresh online users every 20 seconds
        self.chat_screen.after(20000, self.refresh_online_users)

        
    def refresh_online_users(self):
        self.load_online_users()
        db.collection("users").document(self.username).update({
                "alive": 1
        })
        self.chat_screen.after(30000, self.refresh_online_users)

    def display_message(self, message):
        """Displays a new message and auto-scrolls to the latest one."""
        self.message_display.config(state=tk.NORMAL)
        self.message_display.insert(tk.END, message + "\n")
        self.message_display.config(state=tk.DISABLED)
        self.message_display.yview(tk.END)  # Auto-scroll to the latest message

    def upload_file(self):
        if self.is_guest is True: return
        selected = self.channel_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Select a channel first!")
            return

        file_path = filedialog.askopenfilename()
        if not file_path:
            return  # User canceled

        timestamp = datetime.utcnow()

        file_name = os.path.basename(file_path)
        id = timestamp.strftime("%Y-%m-%d-%H-%M-%S-%f")
        file_destination = f"uploads/{self.username}/{id}"  # Path inside bucket

        try:
            # Upload file to Supabase Storage
            with open(file_path, "rb") as file_data:
                self.supabase.storage.from_("chat-app-database").upload(file_destination, file_data)

            # Store only the file name, not the full URL
            channel_name = self.channel_listbox.get(selected[0])
            message_id = timestamp.strftime("%Y-%m-%d-%H-%M-%S-%f")  # Format to YYYY-MM-DD-HH-MM-SS-microseconds
            db.collection("channels").document(channel_name).collection("messages").document(message_id).set({
                "type": "file",
                "file_name": file_name,
                "file_path": file_destination,  # Store only the storage path
                "user": self.username,
                "timestamp": timestamp.timestamp()
            })  
        except Exception as e:
            messagebox.showerror("Upload Error", f"Failed to upload: {e}")

    def load_messages(self, event):
        selected = self.channel_listbox.curselection()
        if not selected:
            return

        channel_name = self.channel_listbox.get(selected[0])
        self.message_listbox.delete(0, tk.END)

        if hasattr(self, "messages_listener"):
            self.messages_listener.unsubscribe()

        def on_snapshot(col_snapshot, changes, read_time):
            self.message_listbox.delete(0, tk.END)
            self.file_links = {}  # Store file messages for downloading

            messages = []
    
            for doc in col_snapshot:
                msg_data = doc.to_dict()
                sender = msg_data.get("user", "Unknown")
                msg_type = msg_data.get("type", "text")
                timestamp = msg_data.get("timestamp", 0)
                sender_display = f"{sender} (YOU)" if sender == self.username else sender
    
                if msg_type == "file":
                    file_name = msg_data.get("file_name", "Unknown File")
                    file_path = msg_data.get("file_path", "")
                    display_text = f"{sender_display} sent a file: {file_name}"
                    self.file_links[display_text] = file_path  # Store for download
                else:
                    text = msg_data.get("text", "")
                    display_text = f"{sender_display}: {text}"

                messages.append((timestamp, display_text))  # Store messages with timestamp

            # Sort messages by timestamp to ensure correct order
            messages.sort(key=lambda x: x[0])

            messages.reverse()

            # Insert sorted messages into the listbox
            for _, display_text in messages:
                self.message_listbox.insert(0, display_text)
                
            self.message_listbox.yview_moveto(1.0)

        self.messages_listener = (
            db.collection("channels")
            .document(channel_name)
            .collection("messages")
            .order_by("timestamp")
            .on_snapshot(on_snapshot)
        )

        # Bind double-click event for opening/downloading files
        self.message_listbox.bind("<Double-Button-1>", self.handle_message_click)

        
    def toggle_invisible(self):
        self.is_invisible = not self.is_invisible
        status = "invisible" if self.is_invisible else "online"
        db.collection("users").document(self.username).update({"status": status})
        self.invisible_button.config(text="Go Online" if self.is_invisible else "Go Invisible")
        self.load_online_users()  # Refresh online users list

    def load_online_users(self):
        self.online_users_listbox.delete(0, tk.END)
        users = db.collection("users").where("status", "in", ["online"]).stream()
        for user in users:
            user_data = user.to_dict()
            if user_data["status"] != "invisible":
                self.online_users_listbox.insert(tk.END, user.id)

    def listen_to_channels(self):
        def on_snapshot(col_snapshot, changes, read_time):
            # Firestore listener runs in background thread — use `after()` to update Tkinter safely
            self.root.after(0, self.update_channel_listbox, col_snapshot)

        self.channel_watch = db.collection("channels").on_snapshot(on_snapshot)

    def update_channel_listbox(self, col_snapshot):
        self.channel_listbox.delete(0, tk.END)
        for doc in col_snapshot:
            self.channel_listbox.insert(tk.END, doc.id)


    def load_messages(self, event):
        selected = self.channel_listbox.curselection()
        if not selected:
            return

        channel_name = self.channel_listbox.get(selected[0])
        self.message_listbox.delete(0, tk.END)

        if hasattr(self, "messages_listener"):
            self.messages_listener.unsubscribe()

        def on_snapshot(col_snapshot, changes, read_time):
            self.message_listbox.delete(0, tk.END)
            self.file_links = {}  # Store file messages for easy retrieval

            for doc in col_snapshot:
                msg_data = doc.to_dict()
                sender = msg_data.get("user", "Unknown")
                text = msg_data.get("text", "")
                file_name = msg_data.get("file_name")
                file_path = msg_data.get("file_path")  # Path in Supabase Storage

                sender_display = f"{sender} (YOU)" if sender == self.username else sender

                if file_name and file_path:
                    # Display file name but store the path for downloading
                    display_text = f"{sender_display} sent a file: {file_name}"
                    self.file_links[display_text] = file_path  # Store file path
                else:
                    display_text = f"{sender_display}: {text}"

                self.message_listbox.insert(tk.END, display_text)

        self.messages_listener = (
            db.collection("channels")
            .document(channel_name)
            .collection("messages")
            .order_by("timestamp")
            .on_snapshot(on_snapshot)
        )

        # Bind double-click event for opening/downloading files
        self.message_listbox.bind("<Double-Button-1>", self.handle_message_click)


    def handle_message_click(self, event):
        selected = self.message_listbox.curselection()
        if not selected:
            return

        message_text = self.message_listbox.get(selected[0])

        # Check if this message is a file
        if message_text in self.file_links:
            file_path = self.file_links[message_text]

            # Ask user where to save the file
            save_path = filedialog.asksaveasfilename(initialfile=message_text.split(": ")[-1])
            if not save_path:
                return  # User canceled download

            try:
                # Download from Supabase Storage
                file_content = self.supabase.storage.from_("chat-app-database").download(file_path)

                # Save file to user’s selected location
                with open(save_path, "wb") as f:
                    f.write(file_content)

                messagebox.showinfo("Download Complete", f"File saved to {save_path}")
            except Exception as e:
                messagebox.showerror("Download Error", f"Failed to download: {e}")

        # If it's a text message, check if it contains a URL and open it
        elif "http" in message_text:
            parts = message_text.split(": ", 1)
            if len(parts) > 1:
                url = parts[1]  # Extract URL part
                webbrowser.open(url)


    def send_message(self):
        if self.is_guest is True: return
        selected = self.channel_listbox.curselection()
        if not selected:
            return

        channel_name = self.channel_listbox.get(selected[0])
        message_text = self.message_entry.get().strip()

        if message_text:
            timestamp = datetime.utcnow()
            message_id = timestamp.strftime("%Y-%m-%d-%H-%M-%S-%f")  # Format to YYYY-MM-DD-HH-MM-SS-microseconds

            db.collection("channels").document(channel_name).collection("messages").document(message_id).set({
                "type": "text", 
                "text": message_text,
                "user": self.username,
                "timestamp": timestamp.timestamp()  # Store as UNIX timestamp for ordering
            })

            self.message_entry.delete(0, tk.END)

            
    def create_channel(self):
        new_channel_name = self.new_channel_entry.get().strip()
        if new_channel_name:
            channel_doc = db.collection("channels").document(new_channel_name).get()
            if channel_doc.exists:
                messagebox.showerror("Error", "Channel already exists!")
                return
            db.collection("channels").document(new_channel_name).set({})
            
            db.collection("channels").document(new_channel_name).set({
                "is_streaming": False, 
                "owner": self.username  # Store as UNIX timestamp for ordering
            })
            
            messagebox.showinfo("Success", f"Channel '{new_channel_name}' created!")
            self.new_channel_entry.delete(0, tk.END)

    def start_stream(self):
        if self.is_guest is True: return;
        selected = self.channel_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Please select a channel first!")
            return

        channel_name = self.channel_listbox.get(selected[0])
        name = self.username  # Already a string, not an Entry field
        host_ip = socket.gethostbyname(socket.gethostname())

        # Step 1: Verify owner
        channel_doc = db.collection("channels").document(channel_name).get()
        if not channel_doc.exists:
            messagebox.showerror("Error", "Channel does not exist.")
            return

        channel_data = channel_doc.to_dict()
        owner = channel_data.get("owner")
        if owner != name:
            messagebox.showerror("Permission Denied", "Only the channel owner can start the stream.")
            return

        # Step 2: Mark stream as active in Firestore
        db.collection("channels").document(channel_name).update({"is_streaming": True})

        # Step 3: Find available port
        port = 9999
        while True:
            try:
                # Try binding a test socket to check if the port is free
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.bind((host_ip, port))
                test_socket.close()
                break  # Found a free port
            except OSError:
                port += 2  # Skip both video (port) and comment (port+1)

        # Step 4: Store streaming info in Firestore
        db.collection("streamers").document(name).set({
            "ip": host_ip,
            "port": port,
            "channel": channel_name
        })

        # Step 5: Start streaming
        self.streamer_instance = VideoStreamer(
            host_ip, port, self.root, name, channel_name,
            stop_callback=lambda: db.collection("channels").document(channel_name).update({
                "is_streaming": False
            })
        )
        threading.Thread(target=self.streamer_instance.start_stream, daemon=True).start()

        messagebox.showinfo("Stream Started", f"Streaming at {host_ip}:{port} on channel '{channel_name}'")


    def join_stream(self):
        if self.is_guest is True: return
        selected = self.channel_listbox.curselection()
        if not selected or self.is_guest:
            messagebox.showerror("Error", "Please select a channel first!")
            return

        channel_name = self.channel_listbox.get(selected[0])
        name = self.username  # Already a string

        # Step 1: Verify is_streaming is True
        channel_doc = db.collection("channels").document(channel_name).get()
        if not channel_doc.exists:
            messagebox.showerror("Error", "Selected channel does not exist.")
            return

        channel_data = channel_doc.to_dict()
        if not channel_data.get("is_streaming", False):
            messagebox.showerror("Error", f"No active stream in '{channel_name}'.")
            return

        # Step 2: Find streamers associated with this channel
        all_streamers = db.collection("streamers").stream()
        streamer_list = []
        for doc in all_streamers:
            data = doc.to_dict()
            if data.get("channel") == channel_name:
                streamer_list.append((doc.id, data["ip"], data["port"], channel_name))

        if not streamer_list:
            messagebox.showerror("Error", f"No active streamers found in '{channel_name}'.")
            return

        # Step 3: GUI for selecting a streamer
        self.streamer_window = tk.Toplevel(self.root)
        self.streamer_window.title("Select Streamer")

        tk.Label(self.streamer_window, text=f"Available Streams in '{channel_name}':").pack()
        self.streamer_listbox = tk.Listbox(self.streamer_window)

        for idx, (streamer_name, ip, port, channel) in enumerate(streamer_list):
            self.streamer_listbox.insert(idx, f"{streamer_name} ({ip}:{port}:{channel})")

        self.streamer_listbox.pack()
        tk.Button(self.streamer_window, text="Join", command=lambda: self.connect_to_stream(streamer_list)).pack()


    def connect_to_stream(self, streamer_list):
        selected_idx = self.streamer_listbox.curselection()
        if not selected_idx:
            messagebox.showerror("Error", "Please select a stream to join.")
            return
        name, ip, port, channel = streamer_list[selected_idx[0]]
        VideoViewer(root, ip, port, name, channel)
        self.streamer_window.destroy()

    def open_streaming_screen(self, mode="viewer"):
        # Create a new window for streaming
        stream_win = tk.Toplevel(self.root)
        stream_win.title("Streaming Screen")

        # Left: List of joiners (stub)
        left_frame = tk.Frame(stream_win)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(left_frame, text="Joiners").pack()
        joiners_listbox = tk.Listbox(left_frame, height=10, width=20)
        joiners_listbox.pack(fill=tk.BOTH, expand=True)
        joiners_listbox.insert(tk.END, "User1")
        joiners_listbox.insert(tk.END, "User2")

        # Center: Video stream area (stub)
        center_frame = tk.Frame(stream_win)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        video_label = tk.Label(center_frame)
        video_label.pack(fill=tk.BOTH, expand=True)

        cap = cv2.VideoCapture(0)

        def update_frame():
            ret, frame = cap.read()
            if ret:
                # Convert BGR to RGB
                frame = cv2.flip(frame, 1)  # 1 = horizontal flip

                # Convert BGR to RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)
                video_label.imgtk = imgtk
                video_label.configure(image=imgtk)
            if stream_win.winfo_exists():
                video_label.after(10, update_frame)

        update_frame()

        
        
        # Right: Comments
        right_frame = tk.Frame(stream_win)
        right_frame.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(right_frame, text="Comments").pack()
        comments_listbox = tk.Listbox(right_frame, height=10, width=30)
        comments_listbox.pack(fill=tk.BOTH, expand=True)
        comment_entry = tk.Entry(right_frame)
        comment_entry.pack(fill=tk.X)
        tk.Button(right_frame, text="Send Comment", command=lambda: comments_listbox.insert(tk.END, f"{self.username}: {comment_entry.get()}")).pack()

        # Bottom: Disconnect button
        disconnect_button = tk.Button(stream_win, text="Disconnect", command=lambda: self.disconnect_stream(stream_win))
        disconnect_button.pack(side=tk.BOTTOM, pady=10)

    def disconnect_stream(self, stream_win):
        # When disconnecting, mark channel as not streaming (stub)
        selected = self.channel_listbox.curselection()
        if selected:
            channel_name = self.channel_listbox.get(selected[0])
            db.collection("channels").document(channel_name).update({"is_streaming": False})
        stream_win.destroy()
        
    def on_closing(root):
        """ This function will stop the background thread when the app is closed. """
        global running
        running = False  # Stop the thread gracefully
        os._exit(0)
        sys.exit()

def on_closing(root):
        """ This function will stop the background thread when the app is closed. """
        global running
        running = False  # Stop the thread gracefully
        root.quit()  # Close the Tkinter app
        os._exit(0)
        sys.exit()


if __name__ == "__main__":
    # Start the check_online_users thread
    threading.Thread(target=check_online_users, daemon=True).start()

    # Create and run the Tkinter app
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()
    root.protocol("WM_DELETE_WINDOW", on_closing(root))
    
    print("end!")

