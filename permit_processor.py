import json
import logging
import requests
import datetime
import pytz
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from util.auth import authenticate
from util.constants import RIOC_URL
from util.time import wait_until_8am_est_edt

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def create_permit(court_id: str, start_time, stop_time, session_cookies: any = {}):
    
    permit_url = f'{RIOC_URL}/Permits'
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

    payload = {
        "Activity": "Tennis",
        "Events": [{
            "FacilityNames": ["Tennis Courts"],
            "FacilityIds": [court_id],
            "Dates": [{
                "Start": start_time,
                "Stop": stop_time
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
        response = requests.post(permit_url, json=payload, headers=headers, cookies=session_cookies)
        if response.status_code == 200:
            logger.info(f'Permit created successfully for {court_id} from {start_time} to {stop_time}')
        else:
            logger.error(f"Failed to create permit: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error creating permit: {e}")

def process_record(record):
    eastern = pytz.timezone('America/New_York')
    body = json.loads(record['body'])

    account_info = body['account_info']
    court_id = body['court']
    start_time = body['start_time']
    stop_time = body['stop_time']

    logger.info(f'Processing account {account_info["username"]} for court {court_id}, start: {start_time}, stop: {stop_time}')

    # Authenticate the account
    session_cookies = authenticate(account_info['username'], account_info['password'])
    if session_cookies is None:
        logger.error(f"Authentication failed for {account_info['username']}")
        return None

    # Check if we should wait until 8:00 AM or exit early
    if not wait_until_8am_est_edt():
        logger.info("Process exited because it's already past 8:00 AM.")
        return  # Exit early

    # Add delays based on day of the week
    weekday = datetime.datetime.now(tz=eastern).weekday()
    weekday_string = datetime.datetime.now(tz=eastern).strftime("%A")

    if weekday == 2 or weekday == 1:  # Tuesday or Wednesday, wait until 8:00:08
        logger.info(f"Its {weekday_string} so waiting for 8 seconds")
        time.sleep(8)
    elif weekday == 4:  # Friday, wait until 8:00:13
        logger.info(f"Its {weekday_string} so waiting for 13 seconds")
        time.sleep(13)
    else:  # Other days, wait until 8:00:10
        logger.info(f"Its {weekday_string} so waiting for 10 seconds")
        time.sleep(10)

    # Process permit creation
    create_permit(court_id, start_time, stop_time, session_cookies)
    return True

def process(event, context):
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_record, record): record for record in event['Records']}
        
        for future in as_completed(futures):
            record = futures[future]
            try:
                result = future.result()
                logger.info(f"Processing completed for record: {record['messageId']}")
            except Exception as e:
                logger.error(f"Error processing record {record['messageId']}: {str(e)}")

    return True
