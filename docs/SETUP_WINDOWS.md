# Easy setup guide (Windows)

This is the no-experience-needed version. You do **not** need Node.js, a developer
account, or the command line. About 5 minutes, most of it waiting for a download.

---

## Step 1 — Install Python (one time)

1. Go to **<https://www.python.org/downloads/>** and click the big **Download Python**
   button.
2. Open the file you just downloaded.
3. **IMPORTANT:** on the very first screen, tick the box at the bottom that says
   **“Add python.exe to PATH”**. Then click **Install Now**.

   > If you miss that checkbox, the app can’t find Python. Just re-run the installer,
   > choose **Modify**, and make sure Python is added to PATH.
4. When it finishes, click **Close**.

> **“I’m told I can’t install software on this PC.”** That’s fine — this app only needs
> **Python** itself (which your answers said you already have). It does **not** need
> Node.js or admin rights to run. If Python is already installed, skip straight to Step 2.

---

## Step 2 — Get the app onto your computer

1. On the project’s GitHub page, click the green **`< > Code`** button → **Download ZIP**.
2. Find the ZIP in your **Downloads** folder, right-click it → **Extract All…** →
   **Extract**.
3. You now have a folder called **`FC-Mobile-Team-Selector`**. Put it somewhere handy,
   like your Desktop.

---

## Step 3 — Start it

1. Open the `FC-Mobile-Team-Selector` folder.
2. **Double-click `start.bat`.**
   - A black window appears. **Leave it open** — that’s the app running.
   - The **first time only**, it spends a minute or two setting itself up and downloading
     the Python packages it needs. You’ll see text scrolling. This is normal.
   - After that, your web browser opens automatically to the dashboard.
3. If the browser doesn’t open on its own, open it yourself and go to:
   **<http://127.0.0.1:8000>**

That’s it. 🎉

> **Windows SmartScreen warning?** If Windows says “Windows protected your PC”, click
> **More info → Run anyway**. That message appears for any `.bat` file that isn’t
> code-signed; the script is plain text you can open in Notepad to read.

---

## Step 4 — Try it with sample data (optional)

Want to see it working before entering your own players?

1. With the app **closed**, double-click `start.bat` once to let it finish setup, then
   close the black window.
2. In the folder, hold **Shift**, right-click an empty space → **Open PowerShell window
   here** (or **Open in Terminal**).
3. Paste this and press Enter:
   ```
   .\.venv\Scripts\python.exe seed_sample.py --replace
   ```
4. Double-click `start.bat` again. You’ll see a full 17-player demo squad. Delete those
   players any time from the **Players** tab when you’re ready to add your own.

---

## Everyday use

- **To start:** double-click `start.bat`.
- **To stop:** close the black window (or press <kbd>Ctrl</kbd>+<kbd>C</kbd> in it).
- **Your data** is saved automatically in `data\fcmobile.sqlite3`. Copy that file anywhere
  to back it up.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| *“Python was not found”* in the black window | Python isn’t on your PATH. Re-run the Python installer, choose **Modify**, tick **Add Python to PATH**, finish, then try `start.bat` again. |
| The black window flashes and closes instantly | Open the folder, right-click `start.bat` → **Edit** to confirm it’s intact, or run it from a PowerShell window (Shift+right-click → Open PowerShell here → type `.\start.bat`) so you can read the error. |
| Browser didn’t open | Go to **<http://127.0.0.1:8000>** manually. |
| “Port already in use” | You already have it running in another window — use that one, or close it and relaunch. The app also auto-tries other ports. |
| Dependencies failed to install | Check you have an internet connection for the first run (it downloads packages once). Delete the `.venv` folder and run `start.bat` again to retry cleanly. |
| I want to start completely fresh | Close the app, delete the `data` folder, relaunch. A new empty database is created. |

---

## What about connecting my EA account?

Short answer: not possible safely, and the app deliberately doesn’t try. There’s no public
FC Mobile API, and automating account login would break EA’s terms and could get your
account banned. Enter players manually (it’s quick) or bulk-import a CSV — see the main
[README](../README.md).
