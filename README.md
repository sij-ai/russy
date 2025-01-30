# russy

**russy** is a simple **RSS-to-Matrix bot** that fetches RSS feeds and posts new entries to Matrix rooms. It runs persistently and requires minimal setup.

## Features
- **Fetches RSS feeds** and posts new entries to Matrix.  
- **Uses room aliases** and automatically resolves them to real room IDs.  
- **Minimal setup** – just edit `config.yaml` and run.  
- **Lightweight** – no database, state is stored in a simple YAML file.  

---

## Installation

1. **Install Dependencies**  
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure `config.yaml`**  
   Copy the example config and edit it:
   ```bash
   cp example-config.yaml config.yaml
   ```
   Set the **Matrix server**, bot credentials, and RSS feeds. Example:

   ```yaml
   matrix:
     server: "https://we2.ee"
     username: "@bot:we2.ee"
     password: "yourpassword"

   rss:
     - name: "Tech News"
       feed: "https://example.com/rss"
       room: "#tech:we2.ee"
       interval: 3600

     - name: "World News"
       feed: "https://news.com/world/feed"
       room: "#worldnews:matrix.org"
       interval: 60
   ```

---

## Usage

Run the bot with:
```bash
python russy.py
```

Once running, it will:
- **Join the configured Matrix rooms** if not already a member.  
- **Monitor RSS feeds** and post new articles as they appear.  
- **Run continuously**, checking for updates at regular intervals.  

To stop it, use **Ctrl+C**.

---

## Notes
- The bot **must be invited** to private Matrix rooms before it can join.  
- Room aliases (`#room:server`) must be valid and correctly mapped to room IDs.  
- By default, it checks feeds **once per hour** (configurable in `config.yaml`).