import requests
from bs4 import BeautifulSoup
import sys

# Test signup
session = requests.Session()
base_url = "http://127.0.0.1:8000"

# Step 1: GET signup page to get CSRF token
print("Step 1: Getting signup page...")
response = session.get(f"{base_url}/accounts/signup/")
print(f"Status: {response.status_code}")

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    if csrf_token:
        token = csrf_token['value']
        print(f"CSRF Token: {token[:20]}...")
        
        # Step 2: POST signup
        print("\nStep 2: Submitting signup...")
        signup_data = {
            'csrfmiddlewaretoken': token,
            'email': 'testuser_' + str(int(__import__('time').time())) + '@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        }
        
        print(f"Email: {signup_data['email']}")
        
        response = session.post(
            f"{base_url}/accounts/signup/",
            data=signup_data,
            allow_redirects=False
        )
        
        print(f"POST Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if 'Location' in response.headers:
            print(f"Redirect to: {response.headers['Location']}")
        
        # Save for next step
        with open('test_email.txt', 'w') as f:
            f.write(signup_data['email'])
        
    else:
        print("ERROR: CSRF token not found!")
        sys.exit(1)
else:
    print(f"ERROR: Could not get signup page (status {response.status_code})")
    sys.exit(1)
