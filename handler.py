import time
import datetime
import logging
import requests
import concurrent.futures
from config.accounts import accounts_config
from util.constants import RIOC_URL

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Sample facilities map
tennis_facilities_map = {
    1: "036dfea4-c487-47b0-b7fe-c9cbe52b7c98",
    2: "175bdff8-016e-46ab-a9df-829fe40c0754",
    3: "9bdef00b-afa0-4b6b-bf9a-75899f7f97c7",
    4: "d311851d-ce53-49fc-9662-42adcda26109",
    5: "8a5ca8e8-3be0-4145-a4ef-91a69671295b",
    6: "77c7f42c-8891-4818-a610-d5c1027c62fe"
}

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
        logger.info(f'resp headers {response.headers}')
        logger.info(f'resp body {response.content.decode()}')
        
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

# Function to check for conflicts
def conflict_check(tennis_facility_id: str, start_time: datetime, stop_time: datetime, session_cookies):
    conflict_url = f'{RIOC_URL}/Permits/ConflictCheck'
    
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
        'User-Agent': 'Mozilla/5.0',
        'Accept': '*/*'
    }

    payload = {
        "FacilityNames": ["Tennis Courts"],
        "FacilityIds": [tennis_facility_id],  # Assuming facility ID 1 for Tennis Courts
        "Dates": [{
            "Start": start_time.isoformat(),
            "Stop": stop_time.isoformat()
        }]
    }
    
    logger.info(f'Checking conflict --> url: {conflict_url} headers: {headers} payload: {payload}')

    try:
        response = requests.post(conflict_url, json=payload, headers=headers, cookies=session_cookies)
        logger.info(f'Conflict check response: {response.content.decode()}')

        # Check if the response is an empty array
        if response.status_code == 200:
            conflict_data = response.json()
            if conflict_data:  # If the array has elements, there's a conflict
                logger.info(f"Conflict detected: {conflict_data}")
                return True
            else:
                logger.info("No conflict detected.")
                return False
        else:
            logger.error(f"Failed to check for conflicts: {response.status_code} - {response.text}")
            return True  # Assume conflict if the check fails
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred during conflict check: {str(e)}")
        return True  # Assume conflict if the check fails

# Wait until the next minute before running the logic
def wait_until_next_minute():
    now = datetime.datetime.now()
    next_minute = now + datetime.timedelta(minutes=1)
    target_time = next_minute.replace(second=0, microsecond=0)

    time_difference = (target_time - now).total_seconds()
    logger.info(f"Waiting for {time_difference:.2f} seconds until {target_time}.")
    time.sleep(time_difference)

# Function to create a permit
def create_permit(court_id: str, start_time, stop_time, session_cookies: any = {}):
    permit_url = f'{RIOC_URL}/Permits'

    # Headers for the request
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Origin': RIOC_URL,
        'Referer': f'{RIOC_URL}/Permits/New',
        'X-Requested-With': 'XMLHttpRequest'
    }

    # Sample payload for creating the permit
    payload = {
        "Activity": "Tennis",
        "Events": [{
            "FacilityNames": ["Tennis Courts"],
            "FacilityIds": [court_id],
            "Dates": [{
                "Start": start_time.isoformat(),
                "Stop": stop_time.isoformat()
            }]
        }],
        "Responses": [
            {"Id": "11e79e5d3daf4712b9e6418d2691b976", "StringValue": "Tennis", "CheckboxValue": []},
            {"Id": "af8966101be44676b4ee564b052e1e87", "StringValue": "2", "CheckboxValue": []},
            {"Id": "f28f0dbea8b5438495778b0bb0ddcd93", "StringValue": "No", "CheckboxValue": []},
            {"Id": "d46cb434558845fb9e0318ab6832e427","StringValue": "No","CheckboxValue": []},
            {"Id": "1221940f5cca4abdb5288cfcbe284820","StringValue": "No","CheckboxValue": []},
            {"Id": "3754dcef7216446b9cc4bf1cd0f12a2e","StringValue": "Yes","CheckboxValue": ["Yes"]},
            {"Id": "0ce54956c4b14746ae5d364507da1e85","StringValue": "No","CheckboxValue": []},
            {"Id": "6b1dda4172f840c7879662bcab1819db","StringValue": "No","CheckboxValue": []},
            {"Id": "06b3f73192a84fd6b88758e56a64c3ad","StringValue": "No","CheckboxValue": ["No"]},
            {"Id": "a31f4297075e4dab8c0ef154f2b9b1c1","StringValue": "None","CheckboxValue": []}
        ]
    }

    logger.info(f' Creating Permit --> url: {permit_url} headers: {headers} payload: {payload} cookies: {session_cookies}')

    try:
        # Make the request to create the permit, passing the session cookies
        response = requests.post(permit_url, json=payload, headers=headers, cookies=session_cookies)
        logger.info(f'Permit creation response headers: {response.headers}')
        logger.info(f'Permit creation response body: {response.content.decode()}')

        # Check if permit creation was successful
        if response.status_code == 200:
            logger.info('Permit created successfully!')
        else:
            logger.error(f"Failed to create permit: {response.status_code} - {response.text}")

    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred during permit creation: {str(e)}")

# Function to process an individual account
def process_account(account_name, account_info):
    current_time = datetime.datetime.now().time()
    logger.info(f'Starting process for {account_name} at {str(current_time)}')
    
    username = account_info['username']
    password = account_info['password']
    start_hour = account_info['start_hour'] #default start hour
    court_id = tennis_facilities_map.get(account_info['court']) #default court id

    # Authenticate to the RIOC URL
    session_cookies = authenticate(username, password)

    if session_cookies:
        logger.info(f'Authenticated successfully for {account_name}')

        # Calculate dates two days from today
        today = datetime.datetime.now()
        start_time = today + datetime.timedelta(days=2)

        # Get the full weekday name as a string
        weekday_name = start_time.strftime('%A')
        logger.info(f"Weekday name: {weekday_name}")  # Example output: "Wednesday"
        start_hour = account_info['schedule'][weekday_name]['start_hour']
        court_id = tennis_facilities_map.get(account_info['schedule'][weekday_name]['court'])

        start_time = start_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        stop_time = start_time + datetime.timedelta(hours=1)

        # Check for conflicts
        conflict_exists = conflict_check(court_id, start_time, stop_time, session_cookies)

        if not conflict_exists:
            logger.info(f"No conflict detected for {account_name}. Proceeding to create permit.")
            create_permit(court_id, start_time, stop_time, session_cookies)
        else:
            logger.info(f"Conflict detected for {account_name}. Skipping permit creation.")
    else:
        logger.error(f"Authentication failed for {account_name}")

def run(event, context):
    current_time = datetime.datetime.now().time()
    logger.info("Your cron function ran at " + str(current_time))

    # Wait until exactly the next minute
    wait_until_next_minute()

    # Introduce a delay for specific seconds
    weekday = datetime.datetime.today().weekday()

    if weekday == 2:  # Wednesday, wait until 8:00:08
        logger.info(f"Its {weekday} so waiting for 8 seconds")
        time.sleep(8)
    elif weekday == 4:  # Friday, wait until 8:00:13
        logger.info(f"Its {weekday} so waiting for 13 seconds")
        time.sleep(13)
    else:  # Other days, wait until 8:00:10
        logger.info(f"Its {weekday} so waiting for 10 seconds")
        time.sleep(10)

    # Run all account processes in parallel using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for account_name, account_info in accounts_config.items():
            futures.append(executor.submit(process_account, account_name, account_info))

        # Wait for all futures to complete
        concurrent.futures.wait(futures)
    
    logger.info("All account processes completed.")
