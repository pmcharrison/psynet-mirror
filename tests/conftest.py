import datetime
import os
import urllib.parse
from pathlib import Path

import pytest
from selenium.webdriver.remote.webdriver import WebDriver

pytest_plugins = ["pytest_dallinger", "pytest_psynet"]
# import psynet.pytest_psynet  # noqa


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture screenshot on test failure."""
    print("Calling pytest_runtest_makereport")
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed:
        driver = getattr(item.instance, "driver", None)
        print(f"Driver: {driver}")
        print(f"isinstance(driver, WebDriver): {isinstance(driver, WebDriver)}")
        if isinstance(driver, WebDriver):
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            screenshot_file = (
                screenshots_dir / f"{item.nodeid.replace('::', '_')}_{timestamp}.png"
            )
            driver.save_screenshot(str(screenshot_file))
            print(f"Screenshot saved to {screenshot_file}")

            ci_project_url = os.getenv("CI_PROJECT_URL")
            ci_job_id = os.getenv("CI_JOB_ID")

            if ci_project_url and ci_job_id:
                encoded_filename = urllib.parse.quote(str(screenshot_file))
                artifact_url = (
                    f"{ci_project_url}/-/jobs/{ci_job_id}/artifacts/{encoded_filename}"
                )
                print(f"Screenshot artifact URL: {artifact_url}")
            else:
                print(
                    "CI_PROJECT_URL or CI_JOB_ID not set. Cannot construct artifact URL."
                )
