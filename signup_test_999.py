import os
import sqlite3
import requests
from bs4 import BeautifulSoup
import time

BASE_URL = 'http://127.0.0.1:8000'
DB = os.path.join(os.path.dirname(__file__), 'db.sqlite3')

# count users before
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM auth_user')
before = cur.fetchone()[0]
cur.execute('SELECT EXISTS(SELECT 1 FROM auth_user WHERE email=?)', ('test999@example.com',))
exists_before = bool(cur.fetchone()[0])
print('USERS_BEFORE', before)
print('TEST999_EXISTS_BEFORE', exists_before)
conn.close()

# perform signup via HTTP
s = requests.Session()
print('\nGET signup page...')
res = s.get(f'{BASE_URL}/accounts/signup/')
print('GET status:', res.status_code)
if res.status_code != 200:
    print('Failed to GET signup page')
    raise SystemExit(1)

soup = BeautifulSoup(res.text, 'html.parser')
csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
if not csrf:
    print('CSRF not found')
    raise SystemExit(1)

token = csrf['value']
email = 'test999@example.com'
password = 'TestPass123!'
print('Posting signup for', email)
post = s.post(f'{BASE_URL}/accounts/signup/', data={
    'csrfmiddlewaretoken': token,
    'email': email,
    'password1': password,
    'password2': password,
}, allow_redirects=False)
print('POST status:', post.status_code)
print('POST headers:', {k:v for k,v in post.headers.items() if k.lower() in ('location','set-cookie')})

# small wait
time.sleep(0.5)
# check DB after
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM auth_user')
after = cur.fetchone()[0]
cur.execute('SELECT EXISTS(SELECT 1 FROM auth_user WHERE email=?)', (email,))
exists_after = bool(cur.fetchone()[0])
print('\nUSERS_AFTER', after)
print('TEST999_EXISTS_AFTER', exists_after)

# check userprofile
cur.execute('SELECT EXISTS(SELECT 1 FROM accounts_userprofile up JOIN auth_user u ON up.user_id=u.id WHERE u.email=?)', (email,))
profile_exists = bool(cur.fetchone()[0])
print('USERPROFILE_EXISTS', profile_exists)
conn.close()

# verify password via Django ORM
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mcqplatform.settings_dev')
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.filter(email=email).first()
if user:
    print('User.username', user.username)
    print('check_password:', user.check_password(password))
else:
    print('User not found in ORM')

# report
print('\nSUMMARY:')
print('- user_created:', exists_after)
print('- user_logged_in_via_post_redirect:', post.status_code == 302)
print('- session_cookie_set:', any('sessionid' in c for c in post.headers.get('set-cookie','').split(',')))
print('- profile_created:', profile_exists)
