import os
import django
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mcqplatform.settings_dev')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

creds_path = Path(__file__).parent / 'ADMIN_CREDENTIALS.txt'

existing = User.objects.filter(is_superuser=True).first()
if existing:
    msg = f"EXISTING_SUPERUSER: username={existing.username}, email={existing.email}\n"
    print(msg)
    creds_path.write_text(msg)
else:
    username = 'admin'
    email = 'admin@example.com'
    password = 'Admin!23456'
    user = User.objects.create_superuser(username=username, email=email, password=password)
    msg = f"CREATED_SUPERUSER: username={username}, email={email}, password={password}\n"
    print(msg)
    creds_path.write_text(msg)
