import time

import schedule


def pending() -> None:
    while True:
        schedule.run_pending()
        time.sleep(1)
