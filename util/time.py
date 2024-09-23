import pytz
import datetime
import time

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
    print(f"Waiting for {time_difference / 60:.2f} minutes until 8:00 AM EST/EDT.")
    time.sleep(time_difference)
    return True  # Return True to indicate the process can continue

# Wait until the next minute before running the logic
def wait_until_next_minute():
    now = datetime.datetime.now()
    next_minute = now + datetime.timedelta(minutes=1)
    target_time = next_minute.replace(second=0, microsecond=0)

    time_difference = (target_time - now).total_seconds()
    print(f"Waiting for {time_difference:.2f} seconds until {target_time}.")
    time.sleep(time_difference)