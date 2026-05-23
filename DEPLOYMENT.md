# Deployment Guide — ACR Cardiac Imaging Dashboard

## Platform: Hugging Face Spaces (Free Forever)

**Why Hugging Face Spaces?**
- ✅ 100% free — no payment ever, no credit card, no expiration
- ✅ No annoying emails about upgrades
- ✅ Docker support (our app runs perfectly)
- ✅ Custom URL: `https://YOUR-USERNAME-acr-cardiac.hf.space`
- ✅ Built for data science apps
- ✅ Private Spaces available (free)

---

## Step 1: Push Code to Your Personal GitHub

### First time setup:

```bash
cd /Users/arazak/projects/extreme-emu/personal-based-repos/geo-spatial-analysis

# Remove existing remote if it points to the work account
git remote remove origin 2>/dev/null

# Add your personal GitHub as origin
git remote add origin https://github.com/YOUR_PERSONAL_USERNAME/geo-spatial-analysis.git

# Stage all files
git add .
git commit -m "ACR Cardiac Imaging Dashboard - complete pipeline + web app"

# Push (you'll be prompted for GitHub credentials)
git push -u origin main
```

### If you need to create the repo first:
1. Go to **https://github.com/new**
2. Name: `geo-spatial-analysis`
3. Set to **Private** (recommended for research data)
4. Do NOT initialize with README (we already have one)
5. Click "Create repository"
6. Then run the push commands above

### For subsequent pushes:
```bash
git add .
git commit -m "your message here"
git push
```

---

## Step 2: Deploy to Hugging Face Spaces

### Option A: Push Directly to HF Space (Simplest)

1. Go to **https://huggingface.co** → Sign up (free, no card)
2. Click your avatar → **"New Space"**
3. Configure:
   | Setting | Value |
   |---------|-------|
   | Space name | `acr-cardiac-dashboard` |
   | License | MIT |
   | SDK | **Docker** |
   | Visibility | Public (token system handles auth) |
4. Click **"Create Space"**
5. Push your code to the Space:

```bash
# Add HF Space as a second remote
git remote add hf https://huggingface.co/spaces/YOUR_HF_USERNAME/acr-cardiac-dashboard

# Push to Hugging Face (triggers auto-build)
git push hf main
```

You'll need a Hugging Face access token:
1. Go to https://huggingface.co/settings/tokens
2. Create a token with "Write" permission
3. Use it as your password when git prompts

### After pushing:
- Build takes ~2-3 minutes
- Your app will be live at: **`https://YOUR_HF_USERNAME-acr-cardiac-dashboard.hf.space`**

---

## Step 3: Share with Your Team

Send these links to authorized users:

- **Dr. Naeem:**
  ```
  https://YOUR_HF_USERNAME-acr-cardiac-dashboard.hf.space/?token=acr-cardiac-2026
  ```

- **Shiloh Johnson:**
  ```
  https://YOUR_HF_USERNAME-acr-cardiac-dashboard.hf.space/?token=shiloh-analyst-2026
  ```

Anyone without a valid token only sees the login page.

---

## Managing Access Tokens

To add/remove users, edit `webapp/app.py`:

```python
VALID_TOKENS = {
    "acr-cardiac-2026": {"name": "Dr. Naeem", "role": "PI"},
    "shiloh-analyst-2026": {"name": "Shiloh Johnson", "role": "Analyst"},
    "new-person-token": {"name": "New Person", "role": "Reviewer"},
}
```

Then push to redeploy:
```bash
git add . && git commit -m "add new user" && git push hf main
```

---

## Running Locally

```bash
cd /Users/arazak/projects/extreme-emu/personal-based-repos/geo-spatial-analysis
/Users/arazak/.local/share/virtualenvs/gtac_app-_RU-K_pH/bin/python webapp/app.py
```

Open in **Chrome/Firefox** (NOT VS Code Simple Browser):
**http://localhost:8050/?token=acr-cardiac-2026**

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Map blank in VS Code Simple Browser | Normal — VS Code blocks external CDNs. Use Chrome/Firefox. |
| Build fails on HF | Check Space → "Logs" tab. Ensure `webapp/static/data/counties.geojson` is committed. |
| Port error locally | `PORT=8051 python webapp/app.py` |
| Git push rejected | `git pull hf main --allow-unrelated-histories` then push again |
