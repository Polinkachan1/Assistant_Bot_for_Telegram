import time
import schedule


def pending() -> None:
    while True:
        schedule.run_pending()
        time.sleep(1)


def add_reminder(time, function, *args, **kwargs) -> None:
    schedule.every().day.at(time).do(function, *args, **kwargs)


def cancel_job():
    return schedule.CancelJob
