import boto3
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
from util.constants import RIOC_URL, PERMIT_QUEUE_URL

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
        1: [[(3, 17)], [(3, 18)], [(3, 19)], [(2, 17)], [(2, 18)], [(2, 19)]],  # Tuesday
        2: [[(3, 17)], [(3, 18)], [(3, 19)], [(5, 17)], [(5, 18)], [(5, 19)]],  # Wednesday
        3: [[(6, 17)], [(6, 18)], [(6, 19)], [(2, 17)], [(2, 18)], [(2, 19)]],  # Thursday
        4: [[(3, 17)], [(3, 18)], [(3, 19)], [(5, 17)], [(5, 18)], [(5, 19)]],  # Friday
        5: [[(3, 15)], [(3, 14)], [(3, 13)], [(5, 15)], [(5, 14)], [(5, 13)]],  # Saturday
        6: [[(6, 15),(3,15)], [(6, 14),(3,14)], [(5, 15)], [(5, 14)], [(6, 13),(3,13)], [(5, 13),(4,13)], [(4,15)], [(4,14)]],  # Sunday
        0: [[(6, 18),(3,18)], [(6, 19),(3,19)], [(2, 18)], [(2, 19)]]   # Monday
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
        for i, court_and_time_w_backups in enumerate(courts_and_times):
            if i < len(accounts):
                account = accounts[i]
                assignments.append((account, court_and_time_w_backups, offset))  # Use the offset for booking
            else:
                logger.info(f"Not enough accounts for {i}th at {court_and_time_w_backups} on day {target_day}, skipping.")
    
    return assignments

# Function to preprocess account with the assigned court, time, and day
def preprocess_account_with_assignment(account_info, court_and_time_w_backups, days_from_today):
    # logger.info(f"Preprocessing account {account_info['username']} for court {court} at hour {start_hour}, booking {days_from_today} days from today")

    # Authenticate the account
    session_cookies = authenticate(account_info['username'], account_info['password'])
    
    if session_cookies is None:
        logger.error(f"Authentication failed for {account_info['username']}")
        return None, None
    
    for (court, start_hour) in court_and_time_w_backups:
        court_id = tennis_facilities_map.get(court)
        # Calculate the reservation time
        eastern = pytz.timezone('America/New_York')
        today = datetime.datetime.now(tz=eastern)
        start_time = today.replace(hour=start_hour, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_from_today)
        stop_time = start_time + datetime.timedelta(hours=1)

        #remove tz as rioc already reads iso as default EASTERN
        start_time = start_time.replace(tzinfo=None)
        stop_time = stop_time.replace(tzinfo=None)

        # Check conflict
        conflict_free = conflict_check(court_id, start_time, stop_time, session_cookies)
        if conflict_free:
            return session_cookies, (conflict_free, court_id, start_time, stop_time)
    
    return session_cookies, (False, None, None, None)

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

# Initialize SQS client
sqs = boto3.client('sqs')

def send_to_sqs(account_info, court, start_time, stop_time, queue_url):
    message_body = {
        'account_info': account_info,
        'court': court,
        'start_time': start_time.isoformat(),
        'stop_time': stop_time.isoformat(),
    }
    
    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body)
        )
        logger.info(f"Message sent to SQS: {response['MessageId']}")
    except Exception as e:
        logger.error(f"Failed to send message to SQS: {e}")

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
            executor.submit(preprocess_account_with_assignment, account_info, court_and_time_w_backups, day): account_info
            for account_info, court_and_time_w_backups, day in assignments
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
                
                # send to sqs for processing
                court_id = conflict_results[1] #already court id
                start_time = conflict_results[2]
                stop_time = conflict_results[3]
                send_to_sqs(account_info, court_id, start_time, stop_time, PERMIT_QUEUE_URL)
            else: # add to failure list
                if account_info['username'] in conflict_account_data:
                    # If the account already exists in the dictionary, append the conflict results
                    conflict_account_data[account_info['username']][1].append(conflict_results)
                else:
                    # If the account is not yet in the dictionary, add it with the conflict results
                    conflict_account_data[account_info['username']] = (session_cookies, [conflict_results])

    logger.info(f"LOG account_data {json.dumps(account_data, default=custom_serializer)}")
    logger.info(f"LOG conflict_account_data {json.dumps(conflict_account_data, default=custom_serializer)}")
    
    # Display the account_data in tabular format
    try:
        display_account_data_in_table(account_data)
        display_account_data_in_table(conflict_account_data)
    except:
        logger.info(f"Failed to show table of successful/failed reservations")

    logger.info("All account processes completed.")
