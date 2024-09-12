from util.constants import USERNAME_1, PW_1, USERNAME_2, PW_2

# Sample configuration for multiple accounts
accounts_config = {
    "account1": {
        "username": USERNAME_1,
        "password": PW_1,
        "start_hour": 18,
        "court": 1,
        "schedule": {
            "Monday": {
                "court": 1,
                "start_hour": 18
            },
            "Tuesday": {
                "court": 1,
                "start_hour": 19
            },
            "Wednesday": {
                "court": 1,
                "start_hour": 19
            },
            "Thursday": {
                "court": 1,
                "start_hour": 18
            },
            "Friday": {
                "court": 1,
                "start_hour": 18
            },
            "Saturday": {
                "court": 1,
                "start_hour": 18
            },
            "Sunday": {
                "court": 1,
                "start_hour": 19
            }
        }
    },
    "account2": {
        "username": USERNAME_2,
        "password": PW_2,
        "start_hour": 19,
        "court": 1,
        "schedule": {
            "Monday": {
                "court": 1,
                "start_hour": 19
            },
            "Tuesday": {
                "court": 1,
                "start_hour": 18
            },
            "Wednesday": {
                "court": 1,
                "start_hour": 18
            },
            "Thursday": {
                "court": 1,
                "start_hour": 19
            },
            "Friday": {
                "court": 1,
                "start_hour": 19
            },
            "Saturday": {
                "court": 1,
                "start_hour": 19
            },
            "Sunday": {
                "court": 1,
                "start_hour": 18
            }
        }
    }
}