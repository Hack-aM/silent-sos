# 🚀 Deployment Guide — Silent SOS System

## Option A: Deploy on Render (Recommended — Free Tier)

### Step 1: Push to GitHub

```bash
cd "d:\new women"

# Initialize git repo
git init
git add .
git commit -m "Initial commit: Silent SOS System"

# Create GitHub repo and push
git remote add origin https://github.com/YOUR_USERNAME/silent-sos-system.git
git push -u origin main
```

### Step 2: Deploy on Render

1. Go to [https://render.com](https://render.com) → Sign up free
2. Click **New → Web Service**
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` and configures everything

**Manual settings if needed:**

| Field | Value |
|---|---|
| Environment | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn --chdir backend "app:create_app()" --bind 0.0.0.0:$PORT --workers 2` |
| Root Directory | *(leave blank)* |

### Step 3: Set Environment Variables on Render

In the Render dashboard → **Environment**:

| Key | Value |
|---|---|
| `SECRET_KEY` | Click "Generate" for a random key |
| `TWILIO_ACCOUNT_SID` | From your Twilio console |
| `TWILIO_AUTH_TOKEN` | From your Twilio console |
| `TWILIO_FROM_NUMBER` | Your Twilio number e.g. `+14155552671` |

> ⚠️ **Do NOT use SQLite in production.** Render's filesystem resets on every deploy.
> Upgrade to PostgreSQL (free on Render): add a Render PostgreSQL instance and set
> `DATABASE_URL=postgresql://...` in environment variables.

---

## Option B: Deploy on Railway (Also Free)

1. Go to [https://railway.app](https://railway.app) → Login with GitHub
2. Click **New Project → Deploy from GitHub Repo**
3. Select your repo → Railway auto-detects Python
4. Set environment variables in the Railway dashboard
5. Railway automatically runs the `Procfile` start command

---

## Option C: Run Locally with Gunicorn (Production-like)

```bash
pip install gunicorn

cd "d:\new women"
gunicorn --chdir backend "app:create_app()" --bind 0.0.0.0:5000 --workers 2
```

---

## 📲 Enable SMS Alerts (Twilio Setup)

### Step 1: Create Twilio Account
1. Go to [https://twilio.com](https://twilio.com) → Sign up free
2. You get **$15 free credit** (~1000 SMS)

### Step 2: Get Credentials
From Twilio Console:
- **Account SID** → looks like `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- **Auth Token** → click to reveal
- **Phone Number** → Buy one (~$1/month) or use trial number

### Step 3: Update .env

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+14155552671
```

### Step 4: Install Twilio Package

```bash
python -m pip install twilio
```

### Step 5: Test

Trigger an SOS on the dashboard. Your emergency contacts will receive:

```
🚨 SILENT SOS ALERT 🚨
Priya Sharma has triggered an emergency SOS!

📍 Location: https://maps.google.com/?q=28.6139,77.2090
⚠️ Risk Level: HIGH (Score: 75/100)

Please contact them or call emergency services immediately.
— Silent SOS Safety System
```

---

## 🗃️ Upgrading SQLite → PostgreSQL

For production, replace SQLite with PostgreSQL:

```bash
pip install psycopg2-binary
```

Update `.env`:
```env
DATABASE_URL=postgresql://user:password@host:5432/silent_sos_db
```

Update `app.py`:
```python
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
```

No other code changes needed — SQLAlchemy handles the rest!
