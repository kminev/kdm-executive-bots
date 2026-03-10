# KDM Ventures LLC — AI Executive Bots 🎨

Three Telegram bots powered by Claude AI to run your Children's Art Classes business.

| Bot | Role | Focus |
|-----|------|-------|
| **CFO Bot** | Chief Financial Officer | Bookkeeping, taxes, P&L, budgeting |
| **CMO Bot** | Chief Marketing Officer | Campaigns, flyers, social media copy |
| **COO Bot** | Chief Operating Officer | LLC compliance, operations, contracts |

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Create Telegram Bots](#2-create-telegram-bots)
3. [Get Anthropic API Key](#3-get-anthropic-api-key)
4. [Local Setup & Testing](#4-local-setup--testing)
5. [Push to GitHub](#5-push-to-github)
6. [Set Up Digital Ocean Droplet](#6-set-up-digital-ocean-droplet)
7. [Configure GitHub Secrets](#7-configure-github-secrets)
8. [Deploy via GitHub Actions](#8-deploy-via-github-actions)
9. [Test Your Bots](#9-test-your-bots)
10. [Uploading Files to Bots](#10-uploading-files-to-bots)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites

Install these on your local machine:
- [Python 3.12+](https://www.python.org/downloads/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/)
- A [GitHub](https://github.com) account
- A [Docker Hub](https://hub.docker.com) account (free)
- A [Digital Ocean](https://digitalocean.com) account

---

## 2. Create Telegram Bots

You need **3 separate bots** — one for CFO, CMO, and COO.

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Name it: `KDM CFO Bot` → username: `kdm_cfo_bot` (must end in `bot`)
4. **Copy the token** — looks like: `7123456789:AAF...`
5. Repeat for `KDM CMO Bot` and `KDM COO Bot`

You'll have 3 tokens total. Save them somewhere safe.

---

## 3. Get Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in / create account
3. Navigate to **API Keys** → **Create Key**
4. Copy and save the key (starts with `sk-ant-...`)

---

## 4. Local Setup & Testing

```bash
# Clone your repo (after pushing — see step 5 first if new)
git clone https://github.com/YOUR_USERNAME/kdm-bots.git
cd kdm-bots

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
# OR
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Create your .env file
cp .env.example .env
```

Edit `.env` with your real values:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
CFO_BOT_TOKEN=7123456789:AAF-your-cfo-token
CMO_BOT_TOKEN=7123456789:AAF-your-cmo-token
COO_BOT_TOKEN=7123456789:AAF-your-coo-token
```

Run locally:
```bash
python main.py
```

You should see:
```
INFO - CFO — Chief Financial Officer is running...
INFO - CMO — Chief Marketing Officer is running...
INFO - COO — Chief Operating Officer is running...
```

Open Telegram, find your bots, send `/start` — they should respond!

Test with Docker locally:
```bash
docker-compose up --build
```

Stop with `Ctrl+C` or `docker-compose down`.

---

## 5. Push to GitHub

```bash
# Initialize git (if not already)
git init
git add .
git commit -m "Initial commit: KDM Executive Bots"

# Create a new repo on github.com named: kdm-bots
# Then push:
git remote add origin https://github.com/YOUR_USERNAME/kdm-bots.git
git branch -M main
git push -u origin main
```

> ⚠️ **Never commit `.env`** — it's in `.gitignore` already.

---

## 6. Set Up Digital Ocean Droplet

### Create Droplet
1. Log in to [digitalocean.com](https://digitalocean.com)
2. Click **Create → Droplets**
3. Choose:
   - **Image**: Ubuntu 24.04 LTS
   - **Size**: Basic — $6/month (1 GB RAM is enough)
   - **Region**: New York or Chicago (closest to Arlington Heights, IL)
   - **Authentication**: SSH Key (recommended) or Password
4. Click **Create Droplet**
5. Copy your Droplet's **IP address**

### Install Docker on Droplet
SSH into your droplet:
```bash
ssh root@YOUR_DROPLET_IP
```

Install Docker:
```bash
# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Verify
docker --version
```

### Create .env on Droplet
```bash
mkdir -p /root/kdm-bots
nano /root/kdm-bots/.env
```

Paste your env variables:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
CFO_BOT_TOKEN=7123456789:AAF-your-cfo-token
CMO_BOT_TOKEN=7123456789:AAF-your-cmo-token
COO_BOT_TOKEN=7123456789:AAF-your-coo-token
```

Save: `Ctrl+X` → `Y` → `Enter`

---

## 7. Configure GitHub Secrets

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

Add these 5 secrets:

| Secret Name | Value |
|-------------|-------|
| `DOCKER_USERNAME` | Your Docker Hub username |
| `DOCKER_PASSWORD` | Your Docker Hub password |
| `DO_HOST` | Your Droplet IP address |
| `DO_USER` | `root` |
| `DO_SSH_KEY` | Your private SSH key (contents of `~/.ssh/id_rsa`) |

**To get your SSH private key:**
```bash
cat ~/.ssh/id_rsa
```
Copy the entire output including `-----BEGIN ... KEY-----` lines.

> If you used password auth for the Droplet, [follow this guide to add SSH](https://docs.digitalocean.com/products/droplets/how-to/add-ssh-keys/).

---

## 8. Deploy via GitHub Actions

Every push to `main` automatically:
1. Builds a Docker image
2. Pushes it to Docker Hub
3. SSHes into your Droplet
4. Pulls and restarts the container

Trigger your first deploy:
```bash
git add .
git commit -m "Trigger first deploy"
git push origin main
```

Watch it in: **GitHub → Your Repo → Actions tab**

---

## 9. Test Your Bots

1. Open Telegram
2. Find each bot by their username (e.g., `@kdm_cfo_bot`)
3. Send `/start`

**CFO Bot tests:**
- "What are common tax deductions for an arts education LLC in Illinois?"
- "Create a simple monthly budget template for my children's art classes"

**CMO Bot tests:**
- "Write a flyer for our summer art camp registration"
- "Give me 5 Instagram caption ideas for student artwork photos"

**COO Bot tests:**
- "What are my annual filing requirements for an Illinois LLC?"
- "Create an onboarding checklist for new art instructors"

---

## 10. Uploading Files to Bots

Each bot accepts uploaded files to use as additional context:

**CFO Bot** — Upload:
- Bank statements (PDF)
- P&L statements (PDF/TXT)
- Expense reports (TXT/CSV)
- Tax documents (PDF)

**CMO Bot** — Upload:
- Marketing books (PDF)
- Brand guidelines (PDF/TXT)
- Previous campaign materials (TXT)

**COO Bot** — Upload:
- LLC Operating Agreement (PDF)
- Contracts and leases (PDF)
- Policies and procedures (TXT)
- Vendor agreements (PDF)

Just drag and drop a file into the Telegram chat!

---

## 11. Troubleshooting

### Bots not responding
```bash
# Check container logs on Droplet
ssh root@YOUR_DROPLET_IP
docker logs kdm-executive-bots --tail 50
```

### Deployment failing
- Check GitHub Actions tab for error details
- Verify all 5 GitHub Secrets are set correctly
- Make sure SSH key is properly added to Droplet

### "Unauthorized" error from Telegram
- Your bot token is wrong — regenerate via @BotFather with `/token`

### "Authentication Error" from Anthropic
- Your API key is wrong or has no credits
- Check [console.anthropic.com](https://console.anthropic.com)

### Restart bots manually on Droplet
```bash
docker restart kdm-executive-bots
```

### View live logs
```bash
docker logs -f kdm-executive-bots
```

---

## File Structure

```
kdm-bots/
├── main.py                    # Entry point — runs all 3 bots
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container config
├── docker-compose.yml         # Local dev
├── .env.example               # Environment template (safe to commit)
├── .env                       # Your real secrets (NEVER commit)
├── .gitignore
├── bots/
│   ├── __init__.py
│   ├── base_bot.py            # Shared bot logic
│   ├── cfo_bot.py             # CFO — Finance
│   ├── cmo_bot.py             # CMO — Marketing
│   └── coo_bot.py             # COO — Operations
├── config/
│   ├── __init__.py
│   └── settings.py            # App settings
└── .github/
    └── workflows/
        └── deploy.yml         # Auto-deploy to Digital Ocean
```

---

## Monthly Costs

| Service | Cost |
|---------|------|
| Digital Ocean Droplet (1GB) | ~$6/month |
| Anthropic API | Pay-per-use (~$0.01–$0.05 per conversation) |
| Docker Hub | Free |
| GitHub | Free |
| Telegram | Free |

**Estimated total: ~$6–$15/month** depending on usage.

---

Built with ❤️ for KDM Ventures LLC — Children's Art Classes, Arlington Heights, IL
