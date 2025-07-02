import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import json, os, datetime, hashlib, zipfile, difflib, smtplib
from email.message import EmailMessage
from textblob import TextBlob
from tkcalendar import Calendar
from fpdf import FPDF
import threading, time
import speech_recognition as sr

# Setup folders and files
os.makedirs("notes", exist_ok=True)
for file in ["users.json", "locks.json", "reminders.json"]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)

current_user = None
backup_file = "backup_notes.zip"

# Password hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Emotion detection
def detect_emotion(text):
    polarity = TextBlob(text).sentiment.polarity
    if polarity > 0.2:
        return "😊 Positive"
    elif polarity < -0.2:
        return "😠 Negative"
    return "😐 Neutral"

# Smart suggestions helpers
def get_all_phrases():
    phrases = set()
    for fname in os.listdir("notes"):
        if fname.startswith(current_user):
            with open(os.path.join("notes", fname), encoding="utf-8") as f:
                words = f.read().split()
                for i in range(len(words)):
                    phrases.add(words[i].lower())
                    if i < len(words) - 1:
                        phrases.add(words[i].lower() + " " + words[i+1].lower())
    return phrases

def get_smart_suggestion(prefix):
    if len(prefix) < 3:
        return ""
    phrases = get_all_phrases()
    match = difflib.get_close_matches(prefix.lower(), phrases, n=1, cutoff=0.5)
    return match[0] if match else ""

# Reminder checking thread
def check_reminders():
    while True:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        with open("reminders.json") as f:
            reminders = json.load(f)
        for user, notes in reminders.items():
            for note, dt in notes.items():
                if dt == now and user == current_user:
                    messagebox.showinfo("Reminder", f"Reminder for: {note}")
        time.sleep(60)

# Email backup function
def send_backup_email():
    with zipfile.ZipFile(backup_file, 'w') as z:
        for fname in os.listdir("notes"):
            if fname.startswith(current_user):
                z.write(os.path.join("notes", fname), arcname=fname)
    try:
        msg = EmailMessage()
        msg['Subject'] = f"Notes Backup for {current_user}"
        msg['From'] = "niyogitangazayvette@gmail.com"
        msg['To'] = "niyogitangazayvette@gmail.com"
        msg.set_content("Attached is your latest backup.")

        with open(backup_file, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="zip", filename=backup_file)

        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login("niyogitangazayvette@gmail.com", "jscpstkmysmvsmdd")
        smtp.send_message(msg)
        smtp.quit()
        messagebox.showinfo("Email Backup", "Backup emailed!")
    except Exception as e:
        messagebox.showerror("Email Error", str(e))

# Export note to PDF
def export_to_pdf(content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in content.splitlines():
        pdf.cell(200, 10, txt=line, ln=True)
    path = filedialog.asksaveasfilename(defaultextension=".pdf")
    if path:
        pdf.output(path)
        messagebox.showinfo("PDF Export", "Note exported as PDF.")

# Main note app window
def open_note_app():
    global current_user
    login_window.destroy()
    autosave_delay = 60000  # 1 minute
    autosave_job = None

    def save_note():
        tag = tag_entry.get().strip() or "untagged"
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_user}_{tag}_{now}.txt"
        path = os.path.join("notes", filename)

        content = text_box.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Warning", "Cannot save empty note.")
            return

        full_content = f"🕒 Saved on: {datetime.datetime.now()}\n\n{content}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(full_content)

        pin = simpledialog.askstring("PIN", "Set a PIN (leave blank for none):", show="*")
        if pin:
            with open("locks.json", "r+") as f:
                locks = json.load(f)
                locks[filename] = pin
                f.seek(0)
                json.dump(locks, f, indent=2)
                f.truncate()

        refresh_notes()
        messagebox.showinfo("Saved", filename)

    def open_note():
        selected = note_listbox.get(tk.ACTIVE)
        if not selected:
            messagebox.showwarning("Warning", "Select a note to open.")
            return
        path = os.path.join("notes", selected)

        with open("locks.json") as f:
            locks = json.load(f)
        if selected in locks:
            pin = simpledialog.askstring("PIN", "Enter PIN:", show="*")
            if pin != locks[selected]:
                messagebox.showerror("Access Denied", "Wrong PIN")
                return

        with open(path, encoding="utf-8") as f:
            text_box.delete("1.0", tk.END)
            text_box.insert(tk.END, f.read())

        parts = selected.split('_')
        if len(parts) >= 3:
            tag_entry.delete(0, tk.END)
            tag_entry.insert(0, parts[1])

    def delete_note():
        selected = note_listbox.get(tk.ACTIVE)
        if not selected:
            messagebox.showwarning("Warning", "Select a note to delete.")
            return
        os.remove(os.path.join("notes", selected))
        refresh_notes()

    def delete_selected_notes():
        selected_indices = note_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Select notes to delete.")
            return
        if messagebox.askyesno("Confirm Delete", "Delete selected notes?"):
            for i in reversed(selected_indices):
                os.remove(os.path.join("notes", note_listbox.get(i)))
            refresh_notes()

    def refresh_notes(filter_text=""):
        note_listbox.delete(0, tk.END)
        for fname in os.listdir("notes"):
            if fname.startswith(current_user) and filter_text.lower() in fname.lower():
                note_listbox.insert(tk.END, fname)

    def analyze_emotion():
        txt = text_box.get("1.0", tk.END)
        emo = detect_emotion(txt)
        messagebox.showinfo("Emotion", emo)

    def update_suggestion(event=None):
        pos = text_box.index(tk.INSERT)
        line, col = map(int, pos.split('.'))
        line_text = text_box.get(f"{line}.0", f"{line}.end")
        word = line_text[:col].split()[-1] if line_text[:col].strip() else ""
        sug = get_smart_suggestion(word)
        suggestion_label.config(text=f"💡 {sug}" if sug else "")

    def toggle_mode():
        nonlocal dark
        dark = not dark
        bg, fg = ("black", "white") if dark else ("lightgreen", "black")
        for w in [text_box, note_listbox, tag_entry, suggestion_label, search_entry]:
            w.config(bg=bg, fg=fg)
        root.config(bg=bg)

    def choose_date():
        win = tk.Toplevel(root)
        cal = Calendar(win, selectmode='day')
        cal.pack(pady=10)
        tk.Button(win, text="Set Reminder", command=lambda: set_reminder(cal.get_date(), win)).pack()

    def set_reminder(date, win):
        time_str = simpledialog.askstring("Time", "HH:MM (24h):")
        if not time_str: return
        datetime_str = f"{date} {time_str}"
        with open("reminders.json", "r+") as f:
            reminders = json.load(f)
            reminders.setdefault(current_user, {})[text_box.get("1.0", "1.20")] = datetime_str
            f.seek(0)
            json.dump(reminders, f, indent=2)
            f.truncate()
        win.destroy()
        messagebox.showinfo("Reminder Set", datetime_str)

    def on_search_keyrelease(event=None):
        refresh_notes(search_entry.get())

    def auto_save():
        nonlocal autosave_job
        if autosave_job:
            root.after_cancel(autosave_job)
        autosave_job = root.after(autosave_delay, save_note)

    def speech_to_text():
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            messagebox.showinfo("Recording", "Speak now...")
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                text = recognizer.recognize_google(audio)
                text_box.insert(tk.END, text + " ")
            except sr.WaitTimeoutError:
                messagebox.showerror("Timeout", "No speech detected. Please try again.")
            except sr.UnknownValueError:
                messagebox.showerror("Error", "Could not understand audio.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    root = tk.Tk()
    root.title(current_user)
    root.geometry("950x600")
    root.config(bg="lightgreen")
    dark = False

    menu = tk.Menu(root)
    file_menu = tk.Menu(menu, tearoff=0)
    file_menu.add_command(label="Open", command=open_note)
    file_menu.add_command(label="Save", command=save_note)
    file_menu.add_command(label="Delete", command=delete_note)
    file_menu.add_command(label="Delete Selected", command=delete_selected_notes)
    file_menu.add_command(label="Export as PDF", command=lambda: export_to_pdf(text_box.get("1.0", tk.END)))
    file_menu.add_command(label="Email Backup", command=send_backup_email)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.quit)
    menu.add_cascade(label="File", menu=file_menu)
    root.config(menu=menu)

    left_frame = tk.Frame(root)
    left_frame.pack(side="left", fill="y", padx=5)

    tk.Label(left_frame, text="Search Notes", bg="lightgreen").pack()
    search_entry = tk.Entry(left_frame)
    search_entry.pack(fill="x", padx=5)
    search_entry.bind("<KeyRelease>", on_search_keyrelease)

    note_listbox = tk.Listbox(left_frame, width=40, selectmode=tk.MULTIPLE)
    note_listbox.pack(fill="y", expand=True, pady=5, padx=5)

    frame = tk.Frame(root)
    frame.pack(expand=True, fill="both")

    tag_entry = tk.Entry(frame)
    tag_entry.pack(fill="x")

    text_box = tk.Text(frame, font=("Arial", 12), wrap="word", bg="lightgreen")
    text_box.pack(expand=True, fill="both")
    text_box.bind("<KeyRelease>", update_suggestion)
    text_box.bind("<KeyRelease>", lambda e: auto_save())

    suggestion_label = tk.Label(root, text="", font=("Arial", 10, "italic"))
    suggestion_label.pack()

    btns = tk.Frame(root)
    btns.pack()
    tk.Button(btns, text="🌙 Toggle", command=toggle_mode).pack(side="left", padx=5)
    tk.Button(btns, text="📅 Calendar", command=choose_date).pack(side="left", padx=5)
    tk.Button(btns, text="😊 Analyze", command=analyze_emotion).pack(side="left", padx=5)
    tk.Button(btns, text="🎤 Speak", command=speech_to_text).pack(side="left", padx=5)

    refresh_notes()
    root.mainloop()

# Login/register UI
def check_login():
    global current_user
    username = entry_user.get().strip()
    password = entry_pass.get().strip()
    with open("users.json") as f:
        users = json.load(f)
    if username in users and users[username]["password"] == hash_password(password):
        current_user = username
        open_note_app()
    else:
        messagebox.showerror("Login Failed", "Wrong credentials")

def register_user():
    u, p = entry_user.get().strip(), entry_pass.get().strip()
    if not u or not p:
        messagebox.showwarning("Error", "Fill both fields")
        return
    with open("users.json", "r+") as f:
        users = json.load(f)
        if u in users:
            messagebox.showerror("Exists", "Username exists")
            return
        users[u] = {"password": hash_password(p), "registered_on": str(datetime.datetime.now())}
        f.seek(0)
        json.dump(users, f, indent=2)
        f.truncate()
    messagebox.showinfo("Success", "User registered")

login_window = tk.Tk()
login_window.title("Login")
login_window.geometry("300x250")
login_window.config(bg="lightgreen")

tk.Label(login_window, text="Username", bg="lightgreen").pack(pady=5)
entry_user = tk.Entry(login_window)
entry_user.pack()

tk.Label(login_window, text="Password", bg="lightgreen").pack(pady=5)
entry_pass = tk.Entry(login_window, show="*")
entry_pass.pack()

tk.Button(login_window, text="Login", command=check_login, bg="lightgray").pack(pady=10)
tk.Button(login_window, text="Register", command=register_user, bg="#d0f0d0").pack()

threading.Thread(target=check_reminders, daemon=True).start()

login_window.mainloop()
