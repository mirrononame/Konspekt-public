# Konspekt

[Українська](README.md) · **English** · [Русский](README.ru.md)

Step-by-step guide with screenshots: [docs/GUIDE.en.md](docs/GUIDE.en.md).

Record a lecture and have a 3–4 page PDF summary by the evening. The audio is transcribed for free on your PC,
and the notes are written by your own Claude. No API key is needed, a regular Claude subscription is enough.
Built for students of Politechnika Wrocławska: the timetable comes from USOS, materials from ePortal.
The interface is available in Ukrainian, English or Russian (Settings → "Interface language"); notes can be in Polish, Ukrainian or Russian.

What it does:
- **Lectures.** Recording from a phone or PC, audio, Teams video, slides, board photos. Subject and date are matched to the timetable.
- **Notes.** "Za 1 minutę", plain-language explanations, typical mistakes, self-check questions. All notes of a subject can be merged into one PDF.
- **Labs and projects.** Drop in the task, press "Copy request" and work with Claude in a separate chat. A log remembers where you stopped.
- **Semester.** Deadlines from ePortal, credit conditions, grades, a calendar on your phone, notifications.
- **Sharing.** Give your finished notes to a classmate as one file.

Everything is stored in the `data/` folder on your PC. Nothing is sent anywhere except what you yourself let Claude read.

## What you need
- Windows 10 or 11.
- A Claude subscription (Pro or Max) and the [Claude Desktop](https://claude.ai/download) app.
- Python 3.10+. If it's missing, `start.bat` will try to install it.
- For transcription: ~3 GB of free space. An NVIDIA GPU makes it several times faster, but it works without one.

## Installation (5 minutes)
1. Download the code: **Code → Download ZIP** and unpack it, e.g. into `Documents\Konspekt`.
   Or `git clone` if you use git.
2. Double-click **`start.bat`**. The first run creates the environment and installs dependencies (needs internet).
   The browser opens at `http://127.0.0.1:8765`.
3. Run **`create-shortcut.bat`**: a "Konspekt" shortcut appears on the desktop and, if you want, autostart with Windows.

## First steps in the app
1. **Language.** Settings → "Interface language" → Українська, English or Русский.
2. **Timetable.** Settings → "USOS — timetable" → paste the link from USOSweb ("Mój plan" → "Udostępnij plan").
   Subjects and classes appear by themselves. You can also add them manually: More → Timetable.
3. **Transcription.** Settings → "Local transcription" → "Install". The model (~1.6 GB) downloads during the first transcription.
4. **ePortal** (optional). Settings → "ePortal" → "Connect". The app gets only an access key, like the Moodle mobile app. The password is not stored.

## Connect Claude
Claude reads the `data/` folder and writes the notes there. The instructions for it (`data/CLAUDE.md`) are put there by the app.

1. Open **Claude Desktop → Cowork** and create a project "Konspekt".
2. Choose `data` from the app folder as the project folder. The exact path is in Settings → "Connect Claude" → "Folder path".
3. Paste the text from the "Project instructions" button there into the project instructions:
   > This is the Konspekt app folder. First read CLAUDE.md in this folder and follow it.
   > Don't open the backups and trash folders. Reply to me in English, briefly.
4. Add a lecture in the app, then write **"Process new lectures"** in a new project chat.
   The PDF appears in the app a few seconds after Claude finishes.

Instead of Cowork you can use Claude Code: run `claude` in the `data` folder and write the same phrase.

**A lab or a project.** On the lab page (or "Subject → Project") press "Copy request" and paste it into a new project chat.
Claude reads the task, your code and the log of previous chats, and adds to the log at the end. The next chat continues from the same place.

## Sharing notes with a classmate
**You:** Settings → "Sharing notes" → tick the subjects → "Download pack". Send the `.zip` any way you like.
The pack contains what helps to study: PDF notes, lab instructions, task descriptions, subject memory, topic plan.
Audio, your notes, grades and access keys never go into it. Transcripts, slides and projects are added only if you tick them.

**Your friend:** Settings → "Sharing notes" → drop the `.zip` → "Import". The app first shows what it will add.
Subjects are matched by name, new ones are added to the timetable. Your own notes are never overwritten:
if your friend already has notes for the same class, that class is skipped.

## Phone
- **At home** — `start-lan.bat`, the app is available on your home Wi-Fi.
- **Anywhere** — `tailscale-setup.bat`. The free Tailscale opens the app only to your devices at `https://<pc>.<network>.ts.net`.
  Install Tailscale on the phone, sign in with the same account and add the page to the home screen.

The PC must be on and Konspekt running.

## Data and security
- `data/` — plain files: notes (`lectures/<id>/output/`), subject memory, timetable. A daily archive goes to `data/backups/`.
- `secrets/` — ePortal, USOS and notification keys. This folder is separate from `data/`, so Claude with access to `data` doesn't see them.
- Both folders are in `.gitignore`: if you fork the repository, they won't end up on GitHub.
- **Updating:** replace everything except `data/` and `secrets/`, then restart `start.bat`.

## For developers
- FastAPI + plain JS without a build step. Server — `app/server.py`, Claude protocol — `app/CLAUDE.md` and `app/protocol/`.
- Interface translations — `app/static/i18n/en.json`, `ru.json` (key — the Ukrainian text, value — the translation).
- Tests: `pip install -r requirements-dev.txt`, `playwright install chromium`, `python -m pytest -q tests`.
  Tests run on synthetic data in a temporary folder.
- What changed — `CHANGELOG.md` (in Ukrainian). Notes for Claude Code, if you develop the app with it — `CLAUDE.md`.

## License
MIT — see `LICENSE`.
