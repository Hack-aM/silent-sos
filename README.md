# 🛡️ Silent SOS — Women Safety Emergency System

> **A production-style AI-powered emergency alert system designed to help women silently trigger SOS alerts during unsafe situations — without drawing attention.**

---

## 🚨 Problem Statement

Every 16 minutes, a crime against women is reported in India alone. In dangerous situations, victims often **cannot speak or call for help openly**. Silent SOS solves this by allowing:

- One-tap emergency activation
- Silent GPS location capture
- Automatic audio evidence recording
- AI-powered danger level analysis
- Instant alert to trusted emergency contacts

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔐 **Auth System** | Secure signup/login with hashed passwords |
| 🗺️ **GPS Capture** | Real-time location via browser Geolocation API |
| 🎙️ **Audio Recording** | MediaRecorder API — silent microphone evidence |
| 🤖 **AI Analysis** | Keyword detection + audio energy → danger score |
| 👥 **Contact Manager** | Add/delete up to 10 trusted emergency contacts |
| 📊 **Alert History** | Full history with risk levels, timestamps, GPS |
| 🌑 **Dark UI** | Premium dark-mode mobile-first dashboard |

---

## 🏗️ Architecture

```
Browser (HTML/CSS/JS)
        │
        │ REST API (JSON)
        ▼
Flask Backend (Python)
        ├── auth_routes.py   — Login / Register / Logout
        ├── sos_routes.py    — SOS Alert + Audio Upload + Dashboard
        ├── contact_routes.py— Emergency Contact CRUD
        │
        ├── ai/
        │   └── danger_analyzer.py  — STT + Keyword Detection + librosa
        │
        └── SQLite Database
            ├── users
            ├── emergency_contacts
            └── alerts
```

---

## 🛠️ Tech Stack

**Frontend:** HTML5, CSS3 (custom dark design system), Vanilla JavaScript  
**Backend:** Python 3.10+, Flask 3.0, Flask-SQLAlchemy, Flask-CORS  
**Database:** SQLite (dev) → PostgreSQL-ready  
**AI/ML:** SpeechRecognition (Google STT), librosa (audio energy), keyword NLP  
**Security:** Werkzeug password hashing, signed sessions, IDOR protection, XSS prevention  

---

## 📁 Project Structure

```
Silent-SOS-System/
├── backend/
│   ├── app.py                  ← Flask entry point
│   ├── models.py               ← SQLAlchemy DB models
│   ├── routes/
│   │   ├── auth_routes.py      ← /api/register, /api/login, /api/logout
│   │   ├── sos_routes.py       ← /api/send-sos, /api/upload-audio, /api/alerts
│   │   └── contact_routes.py   ← /api/contacts CRUD
│   ├── ai/
│   │   └── danger_analyzer.py  ← AI danger analysis pipeline
│   ├── database/
│   │   └── db.py               ← Shared SQLAlchemy instance
│   └── utils/
│       └── validators.py       ← Input validation + security helpers
│
├── frontend/
│   ├── templates/
│   │   ├── login.html
│   │   ├── signup.html
│   │   └── dashboard.html
│   └── static/
│       ├── css/style.css       ← Full design system
│       └── js/app.js           ← Dashboard logic + SOS flow
│
├── uploads/audio/              ← Saved audio evidence files
├── requirements.txt
├── .env                        ← Secrets (never commit!)
└── README.md
```

---

## ⚡ Quick Setup

### Prerequisites
- Python 3.10+
- pip

### 1. Clone & install dependencies

```bash
git clone https://github.com/yourusername/silent-sos-system.git
cd silent-sos-system

pip install -r requirements.txt
```

### 2. Configure environment

```bash
# Edit .env file
SECRET_KEY=your-super-secret-key-here
```

### 3. Run the server

```bash
cd backend
python app.py
```

### 4. Open the app

```
http://localhost:5000
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/register` | Create new user account |
| POST | `/api/login` | Authenticate user, create session |
| POST | `/api/logout` | Clear session |
| GET  | `/api/me` | Get current user info |
| GET  | `/api/dashboard` | Dashboard data + stats |
| POST | `/api/send-sos` | Create SOS alert with GPS |
| POST | `/api/upload-audio` | Upload audio + run AI analysis |
| GET  | `/api/alerts` | Fetch alert history |
| GET  | `/api/contacts` | List emergency contacts |
| POST | `/api/contacts` | Add emergency contact |
| PUT  | `/api/contacts/<id>` | Update contact |
| DELETE | `/api/contacts/<id>` | Delete contact |

---

## 🔒 Security Architecture

| Threat | Defense |
|---|---|
| Password breach | Werkzeug PBKDF2-HMAC-SHA256 hashing |
| Session forgery | Flask signed session cookies (SECRET_KEY) |
| IDOR attacks | Server-side user_id ownership check on every request |
| XSS attacks | `escapeHtml()` on all rendered user content |
| Malicious uploads | File extension whitelist (wav/mp3/webm/ogg only) |
| Path traversal | `os.path.basename()` + regex sanitization on filenames |
| Email enumeration | Vague error message on failed login |

---

## 🚀 Future Roadmap

- [ ] 📱 React Native mobile app
- [ ] 📲 WhatsApp / SMS alerts via Twilio
- [ ] 🗺️ Live GPS tracking map
- [ ] 😱 Scream detection (CNN on audio spectrograms)
- [ ] 😰 Voice stress analysis (librosa pitch features)
- [ ] ⌚ Smartwatch shake trigger
- [ ] 👮 Real-time police dashboard integration
- [ ] 🔇 Offline mode with cached alerts
- [ ] 🌐 OpenAI Whisper for better speech-to-text

---

## 👩‍💻 Built With ❤️ for Women's Safety

> *"Technology should protect, not just connect."*

---

**License:** MIT | **Status:** MVP / Hackathon Ready
