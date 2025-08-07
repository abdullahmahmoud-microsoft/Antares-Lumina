<h1>
  <img src="lumina-logo.png" alt="Antares Lumina Logo" width="40" style="vertical-align: middle;"/>
  Antares Lumina
</h1>

**Antares Lumina** is an intelligent, context-aware assistant designed to help engineers search, learn from, and contribute to organizational knowledge in real-time. Think of it as a junior engineer on your team — one that never forgets what it's taught and improves with every interaction.

This dogfood CLI version lets users interact with Lumina locally, feeding it links, notes, and transcripts — all of which are indexed and searchable for smarter, faster responses across the team.

---

## Purpose

Antares Lumina serves as a searchable, growing knowledge base powered by:

- Eng Hub documentation
- Meeting transcripts
- Written user-provided insights
- Internal tools and deployment patterns

It helps reduce tribal knowledge, accelerates onboarding, and ensures that learnings from one person can help many others.

---

## Setup Instructions

### ⚙ Prerequisites

- Python 3.9+
- Git

### One-Time Setup (First-Time Only)

Run the setup script from the project root:

```bash
setup_lumina.bat
```

This will:
- Create a virtual environment
- Install required dependencies into that venv
- Ensure paths and folders (like `MeetingTranscripts/`) exist

### Regular Use (After Setup)

Once set up, start Lumina with:

```bash
run_lumina.bat
```

---

## How to Use

Once running, Lumina will prompt you in the terminal.

### What You Can Do

- **Ask Questions**: Type any question and Lumina will search across indexed knowledge and answer. If no answer is returned, please provide that knowledge!
- **Upload EngHub Docs**: Paste a link to an EngHub page and type "upload this" or "store this knowledge".
- **Batch Upload Links**: Save multiple links in the file named `EngHubLinks.txt`, then type:
  ```
  upload links from EngHubLinks.txt
  ```
- **Store Notes or Learnings**: Type any of:
  ```
  store this in the knowledge base
  save this note
  add context
  ```
  Then enter your note across multiple lines. Type `END` when you're done.

- **Upload Meeting Transcripts**: Place `.txt` files in the `MeetingTranscripts/` folder, then type:
  ```
  upload meeting transcript
  ```

- **Give Feedback**: After each response, you can type "feedback". You’ll be prompted to leave feedback (thumbs up/down or written comments). We will review these and improve the system accordingly.

- **Shortcuts**: Type `help` at any time to see supported commands.

---

## Contact & Support

For any issues, ideas, or contributions, please reach out to:

**Abdullah Abou Mahmoud - Engineer**  
`aaboumahmoud@microsoft.com`

**Steve Henry - TPM**  
`shenry@microsoft.com`

---

## Reminder

Lumina is only as good as the knowledge you give it.

Please upload clean, accurate, and meaningful content so that everyone on the team can benefit.

If Lumina is missing knowledge, treat it like a new engineer and give it that knowledge!

---

## Notes

This CLI version is part of the **internal dogfood release**. It's evolving rapidly, so make sure to pull the latest changes regularly from the GitHub repo.

Stay tuned for Teams integration and even smarter agent updates, and welcome to Lumina!
