from util.constants import RIOC_URL
import logging
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Function to authenticate with the RIOC URL
def authenticate(username: str, password: str):
    # The login URL
    login_url = f'{RIOC_URL}/Account/Login'
    
    # Headers for the request
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Referer': login_url  # Set this to the login URL or homepage URL, depending on the site behavior
    }

    # Payload for login
    payload = {
        'email': username,  # Your email
        'password': password      # Your password
    }

    logger.info(f'Authenticating --> url: {login_url} headers: {headers} payload: {payload}')
    try:
        # Send the POST request to log in
        response = requests.post(login_url, data=payload, headers=headers, allow_redirects=False)
        
        # Check if login was successful (e.g., status code 200 or similar success criteria)  
        if response.status_code == 302:
            logger.info(f'Login successful! {response.cookies}')
            return response.cookies
        else:
            logger.error(f"Failed to login: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred during login: {str(e)}")
        return None