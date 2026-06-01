# MCQ Platform

A web-based MCQ practice platform built with Python/Django. Students can practice topic-wise questions, get instant evaluation, and track performance over time. Freemium model — 5 free attempts/day, unlimited for members.

## Tech Stack

- Python 3.11, Django 4.2
- PostgreSQL 15
- Redis (cache + Celery broker)
- Celery (async tasks)
- django-allauth (Google OAuth + email login)
- HTMX (cascading dropdowns, dynamic UI)
- Chart.js (analytics donut chart)
- Whitenoise (static files)
- Gunicorn + Nginx (production)

---

## Local Development Setup

### 1. Clone and create virtual environment

```bash
git clone <repo-url>
cd mcqplatform
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your database credentials, secret key, etc.
```

### 4. Set up PostgreSQL

```sql
CREATE DATABASE mcqplatform;
CREATE USER mcquser WITH PASSWORD 'mcqpassword';
GRANT ALL PRIVILEGES ON DATABASE mcqplatform TO mcquser;
```

### 5. Run migrations

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Collect static files

```bash
python manage.py collectstatic
```

### 7. Start Redis (required for sessions and Celery)

```bash
redis-server
```

### 8. Start Celery worker (separate terminal)

```bash
celery -A mcqplatform worker --loglevel=info
```

### 9. Run development server

```bash
python manage.py runserver
```

Visit http://127.0.0.1:8000

---

## Import Questions via CSV

```bash
python manage.py import_questions --file /path/to/questions.csv
```

CSV format (header required):
```
course,topic,subtopic,question_type,question,option_a,option_b,option_c,option_d,correct_answer,reason,level
```

A sample file is at `static/sample_questions.csv`.

You can also upload CSV directly from the Django admin:
`/admin/questions/question/upload-csv/`

---

## Django Admin

- URL: `/admin/`
- Manage courses, topics, subtopics, questions (with image upload)
- Upload questions in bulk via CSV
- Manage promo ads (3 positions: sidebar, closing, interstitial)
- Manage membership subscriptions
- View quiz attempts and answers

---

## Apps

| App | Purpose |
|---|---|
| `accounts` | User profiles, membership, Google OAuth, daily attempt tracking |
| `questions` | Course/Topic/SubTopic/Question/Option models, CSV import |
| `quiz` | Quiz sessions, attempts, answers, scoring, level system |
| `analytics` | Performance dashboard, donut chart, weak area detection |
| `payments` | Membership plans (Razorpay stub — not wired yet) |
| `ads` | Custom promo ad management |

---

## Access Rules

| Feature | Free | Member |
|---|---|---|
| Daily attempts | 5 | Unlimited |
| Difficulty levels | 1–2 only | All (1–5) |
| Countdown timer | No | Yes |
| Analytics dashboard | Blurred | Full |
| Ads | Shown | Hidden |

---

## Production Deployment (Ubuntu 22.04)

### 1. Install system packages

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv postgresql nginx redis-server
```

### 2. Set up project

```bash
sudo mkdir -p /var/www/mcqplatform
sudo chown www-data:www-data /var/www/mcqplatform
cd /var/www/mcqplatform
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure .env with DEBUG=False, ALLOWED_HOSTS, etc.

### 4. Run migrations and collect static

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 5. Install systemd services

```bash
sudo cp systemd/gunicorn.socket /etc/systemd/system/
sudo cp systemd/gunicorn.service /etc/systemd/system/
sudo cp systemd/celery.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn.socket celery
```

### 6. Configure Nginx

```bash
sudo cp nginx/mcqplatform.conf /etc/nginx/sites-available/mcqplatform
sudo ln -s /etc/nginx/sites-available/mcqplatform /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 7. SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## Daily PostgreSQL Backup (cron)

```bash
# Add to crontab: crontab -e
0 2 * * * pg_dump mcqplatform | gzip > /backups/mcqplatform_$(date +\%Y\%m\%d).sql.gz
```

---

## Payments (Coming Soon)

Razorpay integration is now wired in the payments app. When deploying:
1. Install: `pip install razorpay`
2. Configure `RazorpaySettings` in the Django admin under Payments
3. Provide the following fields in admin settings:
   - Razorpay Key ID
   - Razorpay Key Secret
   - Razorpay Webhook Secret
   - Razorpay Webhook URL
4. Run migrations to add the new fields: `python manage.py migrate`
5. The payments app now supports Razorpay checkout, payment success/failure pages, a webhook endpoint, and user payment history.
