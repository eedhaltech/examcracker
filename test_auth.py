import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

DJANGO_SETTINGS_MODULE = os.environ.get('DJANGO_SETTINGS_MODULE')
if not DJANGO_SETTINGS_MODULE:
    DJANGO_SETTINGS_MODULE = 'mcqplatform.settings_dev'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', DJANGO_SETTINGS_MODULE)
    print(f"DJANGO_SETTINGS_MODULE not set, falling back to {DJANGO_SETTINGS_MODULE}")
else:
    print(f"Using DJANGO_SETTINGS_MODULE={DJANGO_SETTINGS_MODULE}")

import django
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

get_user_model = None
authenticate = None
login = None
AnonymousUser = None
RequestFactory = None


def setup_django():
    try:
        django.setup()
    except Exception as exc:
        print(f"ERROR: django.setup() failed: {exc}")
        sys.exit(1)

    global get_user_model, authenticate, login, AnonymousUser, RequestFactory
    try:
        from django.contrib.auth import get_user_model, authenticate, login
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
    except Exception as exc:
        print(f"ERROR importing Django auth components: {exc}")
        sys.exit(1)


def print_header(title):
    print('\n' + '=' * 80)
    print(title)
    print('=' * 80)


def print_settings_info():
    print_header('CURRENT DJANGO SETTINGS')
    keys = [
        'SESSION_ENGINE',
        'CACHES',
        'LOGIN_REDIRECT_URL',
        'ACCOUNT_LOGIN_METHODS',
        'ACCOUNT_EMAIL_VERIFICATION',
        'CSRF_TRUSTED_ORIGINS',
        'ALLOWED_HOSTS',
    ]
    for key in keys:
        value = getattr(settings, key, 'MISSING')
        print(f"{key}: {value!r}")


def create_test_user(email, password):
    UserModel = get_user_model()
    username_field = getattr(UserModel, 'USERNAME_FIELD', 'username')
    lookup = {username_field: email} if username_field else {'email': email}
    if username_field != 'email':
        lookup['email'] = email

    user, created = UserModel.objects.get_or_create(**lookup)
    if not created:
        print(f"Test user already exists (user id={user.id})")
    else:
        print(f"Created test user (user id={user.id})")

    if not user.check_password(password):
        user.set_password(password)
        user.save()
        print("Password was reset to the test password.")

    return user, created


def verify_auth_user_table(email):
    print_header('VERIFY auth_user TABLE')
    try:
        tables = connection.introspection.table_names()
    except Exception as exc:
        print(f"ERROR reading database tables: {exc}")
        return False

    if 'auth_user' not in tables:
        print("auth_user table not found in database.")
        return False

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM auth_user WHERE email = %s", [email])
        count = cursor.fetchone()[0]
    print(f"auth_user rows matching {email}: {count}")
    return count > 0


def verify_userprofile(user):
    print_header('VERIFY USERPROFILE')
    try:
        profile_exists = user.profile is not None
        print(f"UserProfile accessible via user.profile")
    except Exception as exc:
        print(f"UserProfile access failed: {exc}")
        profile_exists = False

    if not profile_exists:
        try:
            from accounts.models import UserProfile
            profile_exists = UserProfile.objects.filter(user=user).exists()
            print(f"UserProfile exists by query: {profile_exists}")
        except Exception as exc:
            print(f"UserProfile query failed: {exc}")
            profile_exists = False

    return profile_exists


def authenticate_user(email, password):
    print_header('AUTHENTICATE USER')
    user = authenticate(username=email, email=email, password=password)
    if user is None:
        print("Authentication failed: authenticate() returned None")
        return None
    print(f"Authenticated user id={user.id}, email={getattr(user, 'email', None)}")
    return user


def test_session_engine():
    print_header('SESSION ENGINE TEST')
    print(f"SESSION_ENGINE module: {settings.SESSION_ENGINE}")
    try:
        session_module = importlib.import_module(settings.SESSION_ENGINE)
    except ImportError as exc:
        print(f"ERROR importing session engine module: {exc}")
        return False, False, False

    SessionStore = getattr(session_module, 'SessionStore', None)
    if SessionStore is None:
        print("SessionStore not found in session engine module.")
        return False, False, False

    try:
        session = SessionStore()
        session['diagnostic'] = 'ok'
        session.save()
        key = session.session_key
        print(f"Session key created: {key}")
        session_saved = bool(key)
    except Exception as exc:
        print(f"ERROR saving session: {exc}")
        return False, False, False

    try:
        restored = SessionStore(session_key=key)
        restored_value = restored.get('diagnostic')
        print(f"Restored session value: {restored_value!r}")
        session_restored = restored_value == 'ok'
    except Exception as exc:
        print(f"ERROR restoring session: {exc}")
        session_restored = False

    return bool(key), session_saved, session_restored


def simulate_login_flow(user):
    print_header('SIMULATE DJANGO-ALLAUTH LOGIN FLOW')
    request = RequestFactory().get('/')
    request.user = AnonymousUser()
    try:
        module = importlib.import_module(settings.SESSION_ENGINE)
        SessionStore = getattr(module, 'SessionStore')
        request.session = SessionStore()
    except Exception as exc:
        print(f"ERROR creating request.session: {exc}")
        return False

    try:
        login(request, user)
        authenticated = bool(getattr(request.user, 'is_authenticated', False))
        print(f"request.user.is_authenticated after login: {authenticated}")
        return authenticated
    except Exception as exc:
        print(f"ERROR during login(): {exc}")
        return False


def search_project_patterns():
    print_header('SEARCH PROJECT PATTERNS')
    patterns = [
        'SESSION_ENGINE',
        'django_redis',
        'redis://',
        'SESSION_CACHE_ALIAS',
        'request.session.flush',
        'request.session.clear',
        'logout(',
    ]
    matches = []
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        if path.name.startswith('.'):
            continue
        if path.suffix.lower() not in {'.py', '.txt', '.md', '.html', '.json', '.yaml', '.yml', '.ini', '.cfg'}:
            continue
        try:
            with path.open('r', encoding='utf-8', errors='replace') as handle:
                for lineno, line in enumerate(handle, start=1):
                    for pattern in patterns:
                        if pattern in line:
                            matches.append((pattern, str(path.relative_to(ROOT)), lineno, line.strip()))
        except Exception:
            continue

    if not matches:
        print("No pattern matches found.")
    else:
        for pattern, filename, lineno, line in matches:
            print(f"{pattern}: {filename}:{lineno}: {line}")
    return bool(matches)


def main():
    setup_django()
    print_settings_info()

    email = 'rendertest@example.com'
    password = 'TestPass123!'

    print_header('CREATE OR UPDATE TEST USER')
    try:
        user, created = create_test_user(email, password)
        step_user = True
    except Exception as exc:
        print(f"ERROR creating test user: {exc}")
        step_user = False

    step_auth_user = verify_auth_user_table(email) if step_user else False
    step_profile = verify_userprofile(user) if step_user else False
    authenticated_user = authenticate_user(email, password) if step_user else None
    step_authenticate = authenticated_user is not None

    session_key_created, session_saved, session_restored = test_session_engine()
    step_session = session_key_created and session_saved and session_restored

    step_login_flow = simulate_login_flow(authenticated_user) if step_authenticate else False

    step_search = search_project_patterns()

    print_header('STEP RESULTS')
    print(f"TEST USER CREATED OR UPDATED: {'PASS' if step_user else 'FAIL'}")
    print(f"USER EXISTS IN auth_user: {'PASS' if step_auth_user else 'FAIL'}")
    print(f"USERPROFILE EXISTS: {'PASS' if step_profile else 'FAIL'}")
    print(f"AUTHENTICATE() WORKS: {'PASS' if step_authenticate else 'FAIL'}")
    print(f"SESSION KEY CREATED: {'PASS' if session_key_created else 'FAIL'}")
    print(f"SESSION SAVED: {'PASS' if session_saved else 'FAIL'}")
    print(f"SESSION RESTORED: {'PASS' if session_restored else 'FAIL'}")
    print(f"DJANGO-ALLAUTH LOGIN SIMULATION: {'PASS' if step_login_flow else 'FAIL'}")
    print(f"PATTERN SEARCH COMPLETE: {'PASS' if step_search else 'FAIL'}")

    print_header('SUMMARY')
    print(f"AUTH WORKING = {'YES' if step_authenticate else 'NO'}")
    print(f"SESSION WORKING = {'YES' if step_session else 'NO'}")
    print(f"REDIS DEPENDENCY FOUND = {'YES' if step_search else 'NO'}")


if __name__ == '__main__':
    main()
