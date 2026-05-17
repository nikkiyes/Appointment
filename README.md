# 🎓 Interview Management Bot

A production-ready Telegram bot for managing interview bookings, paid mock interviews, and an admin panel — built with aiogram 3, SQLAlchemy async, and Railway-ready architecture.

---

## ✨ Features

### 📅 Interview Booking
- 7-step guided registration flow
- Duplicate prevention (roll number + user ID)
- Auto-generated serial numbers (IM-2024-0001)
- Screenshot/PDF upload support
- Admin group notification with all details
- Edit form before final submission

### 🎯 Paid Mock Interview
- Dynamic pricing via admin panel
- UPI QR code generation
- UTR number or screenshot proof
- Payment expiry timer
- Duplicate UTR detection
- Admin approval/decline buttons in group

### 🔐 Admin Panel (Password Protected)
1. **View Registered Users** — paginated with search
2. **Paid Mock Interview Users** — approved payments list
3. **Revenue Dashboard** — total, daily, pending revenue
4. **Download CSV** — by date range or all students
5. **Schedule Interview** — set date/time, auto-notify student
6. **Send Meet Link** — direct to student
7. **Broadcast Message** — all registered users
8. **Search Student** — instant multi-field search
9. **Export Introductions** — CSV of all intros
10. **Pending Payments** — awaiting verification
11. **Approved Payments** — confirmed payments
12. **Statistics Dashboard** — full analytics
13. **Payment Settings** — price, UPI ID, payee, enable/disable
14. **Today's Interview List** — downloadable CSV

---

## 🚀 Railway Deployment

### Step 1: Get Bot Token
1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the steps
3. Copy the bot token

### Step 2: Deploy to Railway
1. Fork/clone this repo OR upload all files to a new Railway project
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variables (see below)

### Step 3: Set Environment Variables in Railway

Go to your Railway project → Variables tab and add:

| Variable | Value | Required |
|----------|-------|----------|
| `BOT_TOKEN` | Your bot token from BotFather | ✅ |
| `ADMIN_IDS` | Your Telegram user ID | ✅ |
| `ADMIN_GROUP_ID` | Group ID for notifications | ✅ |
| `ADMIN_PASSWORD` | Secure password for admin panel | ✅ |
| `FORCE_JOIN_CHANNEL` | @channelname (optional) | ❌ |
| `DATABASE_URL` | SQLite or PostgreSQL URL | ❌ |
| `DEFAULT_MOCK_PRICE` | e.g. `99.0` | ❌ |
| `DEFAULT_UPI_ID` | e.g. `name@upi` | ❌ |
| `DEFAULT_PAYEE_NAME` | e.g. `Selection Lab` | ❌ |

### Step 4: Find Your User ID
Send a message to [@userinfobot](https://t.me/userinfobot) to get your Telegram user ID.

### Step 5: Setup Admin Group
1. Create a Telegram group
2. Add your bot to the group as admin
3. Send a message in the group
4. Use [@getidsbot](https://t.me/getidsbot) to find the group ID (starts with `-100`)

---

## 📁 File Structure

```
main.py               — Bot entry point
config.py             — Environment variable settings
database.py           — SQLAlchemy models + DB init
states.py             — FSM conversation states
keyboards.py          — All inline/reply keyboards
utils.py              — QR code, CSV export, formatting
middlewares.py        — Rate limiting + channel check
scheduler.py          — Auto backup + payment expiry
handlers/
  __init__.py
  start_handler.py    — /start, home, cancel
  booking_handler.py  — Interview booking flow
  mock_interview_handler.py — Mock interview + payments
  admin_handler.py    — Full admin panel
  payment_handler.py  — (placeholder)
  channel_handler.py  — Force join
requirements.txt
railway.json
Procfile
.env.example
```

---

## 🔧 Local Development

```bash
# Clone / copy all files to a folder
pip install -r requirements.txt

# Copy and fill in your values
cp .env.example .env
# Edit .env with your bot token, admin IDs, etc.

python main.py
```

---

## 📊 Database

- Default: **SQLite** (`interview_bot.db`) — works great for Railway
- For PostgreSQL: set `DATABASE_URL=postgresql+asyncpg://...`
- Auto-backup creates timestamped `.db` copies every 24 hours

---

## 🛡️ Security Features

- Rate limiting (5 messages per 60 seconds per user)
- Admin panel password protection
- Admin session management
- Duplicate registration prevention
- Duplicate UTR detection
- Payment expiry timer
- Admin audit logs for all actions
- Force channel join (configurable)
- Multi-admin support

---

## 📱 User Flow

```
/start
├── 📅 Book Interview → 7-step form → Admin notified
├── 🎯 Mock Interview → Info → Pay → UTR/Screenshot → Admin approves
└── 🔐 Admin Panel → Password → Full dashboard
```

---

## 🆘 Support

If you have issues with deployment, check:
1. Bot token is correct
2. ADMIN_IDS is your actual Telegram user ID (not username)
3. ADMIN_GROUP_ID starts with `-100` for supergroups
4. Bot has admin rights in the group
