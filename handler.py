import random
import time
import datetime
import logging
import requests
import json
import concurrent.futures
import pytz
from requests.cookies import RequestsCookieJar
from tabulate import tabulate

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

# Define which days to book based on current weekday
def get_days_to_book():
    eastern = pytz.timezone('America/New_York')
    today = datetime.datetime.now(tz=eastern).weekday()  # 0 is Monday, 6 is Sunday

    if today == 0:  # Monday, book for Tuesday and Wednesday (offset 1, 2)
        return [1, 2]
    elif today == 1:  # Tuesday, book for Thursday (offset 2)
        return [2]
    elif today == 2:  # Wednesday, book for Friday (offset 2)
        return [2]
    elif today == 3:  # Thursday, book for Saturday (offset 2)
        return [2]
    elif today == 4:  # Friday, book for Sunday (offset 2) and Monday (offset 3)
        return [2, 3]
    return []

# Function to get the priority list of courts and times by weekday
def get_court_and_time_priority_by_weekday():
    return {
        1: [(3, 18), (3, 19), (2, 18), (2, 19)],  # Tuesday
        2: [(3, 18), (3, 19), (5, 18), (5, 19)],  # Wednesday
        3: [(6, 18), (6, 19), (2, 18), (2, 19)],  # Thursday
        4: [(3, 18), (3, 19), (5, 18), (5, 19)],  # Friday
        5: [(3, 11), (3, 12), (5, 11), (5, 12)],  # Saturday
        6: [(3, 11), (3, 12), (2, 11), (2, 12)],  # Sunday
        0: [(6, 18), (6, 19), (2, 18), (2, 19)]   # Monday
    }

# Randomize accounts for assignment
def randomize_accounts():
    accounts = list(accounts_config.values())
    random.shuffle(accounts)
    return accounts

# Helper function to calculate the actual day of the week based on offset
def get_weekday_from_offset(offset):
    eastern = pytz.timezone('America/New_York')
    today = datetime.datetime.now(tz=eastern)  # 0 is Monday, 6 is Sunday
    target_day = today + datetime.timedelta(days=offset)
    return target_day

# Assign accounts to courts and times based on priority list
def assign_accounts_to_courts_and_times(days_to_book):
    assignments = []
    accounts = randomize_accounts()
    priority_courts_and_times = get_court_and_time_priority_by_weekday()
    for offset in days_to_book:
        target_day = get_weekday_from_offset(offset)  # Convert offset to actual weekday
        courts_and_times = priority_courts_and_times.get(target_day.weekday(), [])
        # Assign accounts to the priority courts/times for the calculated weekday
        for i, (court, start_hour) in enumerate(courts_and_times):
            if i < len(accounts):
                account = accounts[i]
                assignments.append((account, tennis_facilities_map.get(court), start_hour, offset))  # Use the offset for booking
            else:
                logger.info(f"Not enough accounts for court {court} at {start_hour} on day {target_day}, skipping.")
    
    return assignments

# Function to preprocess account with the assigned court, time, and day
def preprocess_account_with_assignment(account_info, court, start_hour, days_from_today):
    # logger.info(f"Preprocessing account {account_info['username']} for court {court} at hour {start_hour}, booking {days_from_today} days from today")

    # Authenticate the account
    session_cookies = authenticate(account_info['username'], account_info['password'])
    
    if session_cookies is None:
        logger.error(f"Authentication failed for {account_info['username']}")
        return None, None
    
    # Calculate the reservation time
    eastern = pytz.timezone('America/New_York')
    today = datetime.datetime.now(tz=eastern)
    start_time = today.replace(hour=start_hour, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_from_today)
    stop_time = start_time + datetime.timedelta(hours=1)

    #remove tz as rioc already reads iso as default EASTERN
    start_time = start_time.replace(tzinfo=None)
    stop_time = stop_time.replace(tzinfo=None)

    # Check conflict
    conflict_free = conflict_check(court, start_time, stop_time, session_cookies)
    return session_cookies, (conflict_free, court, start_time, stop_time)

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

        # Check if the response is an empty array
        if response.status_code == 200:
            conflict_data = response.json()
            if conflict_data:  # If the array has elements, there's a conflict
                return False
            else:
                return True   # Returns True if no conflict
        else:
            logger.error(f"Failed to check for conflicts: {response.status_code} - {response.text}")
            return False  # Assume conflict if the check fails
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred during conflict check: {str(e)}")
        return False  # Assume conflict if the check fails

# Wait until the next minute before running the logic
def wait_until_next_minute():
    now = datetime.datetime.now()
    next_minute = now + datetime.timedelta(minutes=1)
    target_time = next_minute.replace(second=0, microsecond=0)

    time_difference = (target_time - now).total_seconds()
    logger.info(f"Waiting for {time_difference:.2f} seconds until {target_time}.")
    time.sleep(time_difference)

# Wait until it's 8:00 AM EST/EDT
def wait_until_8am_est_edt():
    # Define the timezone for Eastern Time (EST/EDT)
    eastern = pytz.timezone('America/New_York')

    # Get the current time in the Eastern Time Zone
    now = datetime.datetime.now(tz=eastern)
    
    # Calculate the next 8:00 AM
    next_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    
    # If the current time is already past 8:00 AM today, schedule for the next day
    if now >= next_8am:
        next_8am = next_8am + datetime.timedelta(days=1)
        return False  # Return False to indicate the process should not continue


    # Calculate the time difference
    time_difference = (next_8am - now).total_seconds()
    
    # Log and wait until 8:00 AM
    logger.info(f"Waiting for {time_difference / 60:.2f} minutes until 8:00 AM EST/EDT.")
    time.sleep(time_difference)
    return True  # Return True to indicate the process can continue

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

# Execution phase: Create permits at exactly the specified time
def create_permits(account_info, session_cookies, conflict_results):
    # logger.info(f"create_permits --> Executing permit creation for {account_info['username']} account_info: {account_info} conflict_results {conflict_results}")
    
    for (conflict_free, court_id, start_time, stop_time) in conflict_results:

        logger.info(f"create_permits --> Creating permit for court user {account_info['username']} and court {court_id}  at {start_time}.")
        create_permit(court_id, start_time, stop_time, session_cookies)

# Custom serialization function for non-serializable objects
def custom_serializer(obj):
    if isinstance(obj, RequestsCookieJar):
        # Convert RequestsCookieJar to a dict
        return {c.name: c.value for c in obj}
    elif isinstance(obj, datetime.datetime):
        # Convert datetime to ISO format
        return obj.isoformat()
    else:
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# Function to display account data in tabular format using pandas
def display_account_data_in_table(account_data):
    # Convert to a list of rows
    rows = []
    for account, bookings in account_data.items():
        for booking in bookings[1]:
            conflict_free, court, start_time, end_time = booking
            rows.append([account, conflict_free, court, start_time, end_time])
    
    # Display table
    logger.info(tabulate(rows, headers=["Account", "conflict_free", "Court", "Start Time", "End Time"], tablefmt="grid"))

def run(event, context):
    eastern = pytz.timezone('America/New_York')
    current_time = datetime.datetime.now(tz=eastern)
    logger.info("Your cron function ran at " + str(current_time.time()))

    # Determine which days to book based on the current weekday
    days_to_book = get_days_to_book()
    logger.info(f"LOG days_to_book {days_to_book}")

    if not days_to_book:
        logger.info(f"No days to book today {current_time}. Exiting.")
        return

    # Assign accounts to courts and times based on the priority list
    assignments = assign_accounts_to_courts_and_times(days_to_book)
    logger.info(f"assignments {json.dumps(assignments)}")
    
    # Preprocess accounts: Authenticate and check conflicts
    account_data = {}
    conflict_account_data = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_preprocess = {
            executor.submit(preprocess_account_with_assignment, account_info, court, start_hour, day): account_info
            for account_info, court, start_hour, day in assignments
        }
        for future in concurrent.futures.as_completed(future_preprocess):
            account_info = future_preprocess[future]
            session_cookies, conflict_results = future.result()
            if session_cookies and conflict_results[0] == True:  # if no session cookie or has conflict, don't add
                if account_info['username'] in account_data:
                    # If the account already exists in the dictionary, append the conflict results
                    account_data[account_info['username']][1].append(conflict_results)
                else:
                    # If the account is not yet in the dictionary, add it with the conflict results
                    account_data[account_info['username']] = (session_cookies, [conflict_results])
            else: # add to failure list
                if account_info['username'] in conflict_account_data:
                    # If the account already exists in the dictionary, append the conflict results
                    conflict_account_data[account_info['username']][1].append(conflict_results)
                else:
                    # If the account is not yet in the dictionary, add it with the conflict results
                    conflict_account_data[account_info['username']] = (session_cookies, [conflict_results])

    logger.info(f"LOG account_data {json.dumps(account_data, default=custom_serializer)}")
    logger.info(f"LOG conflict_account_data {json.dumps(conflict_account_data, default=custom_serializer)}")

    # Check if we should wait until 8:00 AM or exit early
    if not wait_until_8am_est_edt():
        logger.info("Process exited because it's already past 8:00 AM.")
        return  # Exit early

    # Introduce a delay for specific seconds
    weekday = datetime.datetime.now(tz=eastern).weekday()
    weekday_string = datetime.datetime.now(tz=eastern).strftime("%A")

    if weekday == 2:  # Wednesday, wait until 8:00:08
        logger.info(f"Its {weekday_string} so waiting for 8 seconds")
        time.sleep(8)
    elif weekday == 4:  # Friday, wait until 8:00:13
        logger.info(f"Its {weekday_string} so waiting for 13 seconds")
        time.sleep(13)
    else:  # Other days, wait until 8:00:10
        logger.info(f"Its {weekday_string} so waiting for 10 seconds")
        time.sleep(10)

    # Execute account permit creation at the intended time
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for username, (session_cookies, conflict_results) in account_data.items():
            account_info = next(info for info in accounts_config.values() if info['username'] == username)
            futures.append(executor.submit(create_permits, account_info, session_cookies, conflict_results))
        concurrent.futures.wait(futures)
    
    # Display the account_data in tabular format
    try:
        display_account_data_in_table(account_data)
        display_account_data_in_table(conflict_account_data)
    except:
        logger.info(f"Failed to create table of successful/failed reservations")

    logger.info("All account processes completed.")
