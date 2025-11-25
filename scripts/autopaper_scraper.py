#!/usr/bin/env python3
"""
Automates bulk searches on https://autopapersearch.com using Selenium.

For each account autoTest1..autoTest100 (or the range specified via CLI
arguments), the script will:
1. Attempt to log in with password 123456, registering the account if it
   does not already exist.
2. Populate the search form with the requested parameters and start the query.
3. Poll the history page until the CSV download becomes available.
4. Download the CSV, rename it to include the username, and store it in the
   results directory.
5. Record login, CSV-ready, and download completion timestamps in
   performance.csv.

Requirements:
  pip install selenium
  Ensure Chrome/Chromium and a matching chromedriver are available.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "https://autopapersearch.com"
LOGIN_URL = f"{BASE_URL}/login.html"
REGISTER_URL = f"{BASE_URL}/register.html"
INDEX_URL = f"{BASE_URL}/index.html"
HISTORY_URL = f"{BASE_URL}/history.html"

DEFAULT_PASSWORD = "123456"
SEARCH_QUESTION = "VR眩晕检测"
SEARCH_REQUIREMENTS = "实时检测"

RESULTS_DIR = Path("results")
PERFORMANCE_FILE = Path("performance.csv")

# How long to wait (seconds) for key operations.
LOGIN_WAIT = 15
REGISTER_WAIT = 20
REDIRECT_WAIT = 30
HISTORY_TIMEOUT = 600
DOWNLOAD_TIMEOUT = 180


@dataclass
class AccountResult:
    username: str
    login_time: datetime
    csv_ready_time: datetime
    download_ready_time: datetime
    downloaded_file: Path


def configure_driver(download_dir: Path, headless: bool) -> webdriver.Chrome:
    """Create a Chrome driver configured for automated downloads."""
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    if headless:
        chrome_options.add_argument("--headless=new")

    prefs = {
        "download.default_directory": str(download_dir.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    return webdriver.Chrome(options=chrome_options)


def open_login_page(driver: webdriver.Chrome) -> datetime:
    """Navigate to the login page and return the timestamp of the first visit."""
    visit_time = datetime.now()
    driver.get(LOGIN_URL)
    WebDriverWait(driver, LOGIN_WAIT).until(
        EC.presence_of_element_located((By.ID, "loginForm"))
    )
    return visit_time


def submit_login(driver: webdriver.Chrome, username: str, password: str) -> bool:
    """Submit the login form and return True if the main page loads."""
    wait = WebDriverWait(driver, LOGIN_WAIT)
    wait.until(EC.presence_of_element_located((By.ID, "username")))

    driver.find_element(By.ID, "username").clear()
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "password").clear()
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.ID, "loginBtn").click()

    try:
        wait.until(EC.presence_of_element_located((By.ID, "startSearchBtn")))
    except TimeoutException:
        return False

    # If the element exists but we are still on the login page, treat it as failure.
    current_url = driver.current_url
    if "login.html" in current_url:
        return False
    return True


def register_account(driver: webdriver.Chrome, username: str, password: str) -> None:
    """Register a new account."""
    driver.get(REGISTER_URL)
    wait = WebDriverWait(driver, REGISTER_WAIT)
    wait.until(EC.presence_of_element_located((By.ID, "registerForm")))

    driver.find_element(By.ID, "username").clear()
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "password").clear()
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.ID, "confirmPassword").clear()
    driver.find_element(By.ID, "confirmPassword").send_keys(password)
    driver.find_element(By.ID, "registerBtn").click()

    # Successful registration redirects back to the login page.
    WebDriverWait(driver, REGISTER_WAIT).until(
        EC.presence_of_element_located((By.ID, "loginForm"))
    )


def populate_search_form(driver: webdriver.Chrome) -> None:
    """Fill the search form with the desired values."""
    wait = WebDriverWait(driver, LOGIN_WAIT)
    wait.until(EC.presence_of_element_located((By.ID, "question")))

    question = driver.find_element(By.ID, "question")
    question.clear()
    question.send_keys(SEARCH_QUESTION)

    requirements = driver.find_element(By.ID, "requirements")
    requirements.clear()
    requirements.send_keys(SEARCH_REQUIREMENTS)

    include_all_years = driver.find_element(By.ID, "includeAllYears")
    if not include_all_years.is_selected():
        include_all_years.click()

    # Wait for the folder checkboxes to load and select all of them.
    checkboxes = WebDriverWait(driver, LOGIN_WAIT).until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "#folders input[type='checkbox']")
        )
    )
    for cb in checkboxes:
        if not cb.is_selected():
            driver.execute_script("arguments[0].click();", cb)


def start_search(driver: webdriver.Chrome) -> str:
    """Trigger the search and return the query index if available."""
    driver.find_element(By.ID, "startSearchBtn").click()

    WebDriverWait(driver, REDIRECT_WAIT).until(
        EC.url_contains("history.html")
    )
    return extract_query_index(driver.current_url)


def extract_query_index(url: str) -> str:
    """Pull focus_query from the URL, if present."""
    parsed = urlparse(url)
    query_values = parse_qs(parsed.query).get("focus_query")
    if query_values:
        return query_values[0]
    return ""


def wait_for_csv_and_download(
    driver: webdriver.Chrome,
    username: str,
    download_dir: Path,
    query_index: str,
    timeout: int = HISTORY_TIMEOUT,
) -> Tuple[datetime, datetime, Path]:
    """Refresh the history page until the CSV button is available, then download."""
    deadline = time.time() + timeout
    csv_ready_time: Optional[datetime] = None

    while time.time() < deadline:
        history_url = HISTORY_URL
        if query_index:
            history_url = f"{history_url}?focus_query={query_index}"

        driver.get(history_url)
        try:
            WebDriverWait(driver, LOGIN_WAIT).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".card"))
            )
        except TimeoutException:
            time.sleep(3)
            continue

        target_card = locate_query_card(driver, query_index)
        if not target_card:
            time.sleep(3)
            continue

        try:
            csv_button = target_card.find_element(By.CSS_SELECTOR, ".btn.btn-csv")
        except NoSuchElementException:
            time.sleep(5)
            continue

        csv_ready_time = datetime.now()
        pre_download_snapshot = snapshot_directory(download_dir)
        csv_button.click()
        downloaded_path = wait_for_new_download(
            download_dir, pre_download_snapshot, DOWNLOAD_TIMEOUT
        )
        if not downloaded_path:
            raise TimeoutError("CSV download failed to complete in time.")

        final_path = rename_download(downloaded_path, username, download_dir)
        download_ready_time = datetime.now()
        return csv_ready_time, download_ready_time, final_path

    raise TimeoutError("Timed out waiting for CSV export to become available.")


def locate_query_card(driver: webdriver.Chrome, query_index: str):
    """Find the history card corresponding to the query index (or fall back to the newest card)."""
    cards = driver.find_elements(By.CSS_SELECTOR, ".card")
    if not cards:
        return None

    if query_index:
        for card in cards:
            if query_index in card.text:
                return card
    return cards[0]


def snapshot_directory(directory: Path) -> Dict[str, Tuple[int, float]]:
    """Capture the current files in a directory (name -> (size, mtime))."""
    snapshot: Dict[str, Tuple[int, float]] = {}
    for path in directory.iterdir():
        if path.is_file():
            stat = path.stat()
            snapshot[path.name] = (stat.st_size, stat.st_mtime)
    return snapshot


def wait_for_new_download(
    directory: Path,
    previous_state: Dict[str, Tuple[int, float]],
    timeout: int,
) -> Optional[Path]:
    """Wait for a new or updated file to appear in directory."""
    end_time = time.time() + timeout
    while time.time() < end_time:
        for path in directory.iterdir():
            if path.is_dir():
                continue
            if path.suffix == ".crdownload":
                continue

            stat = path.stat()
            prior = previous_state.get(path.name)
            if prior is None or stat.st_mtime > prior[1]:
                # Ensure no temporary .crdownload is lingering for this file.
                temp_path = path.with_suffix(path.suffix + ".crdownload")
                if temp_path.exists():
                    continue
                return path

        time.sleep(1)
    return None


def rename_download(downloaded_file: Path, username: str, results_dir: Path) -> Path:
    """Rename the downloaded CSV to include the username prefix."""
    new_name = f"{username}_{downloaded_file.name}"
    destination = results_dir / new_name

    counter = 1
    while destination.exists():
        destination = results_dir / f"{username}_{counter}_{downloaded_file.name}"
        counter += 1

    downloaded_file.replace(destination)
    return destination


def ensure_results_directory(path: Path) -> None:
    """Create the results directory if needed."""
    path.mkdir(parents=True, exist_ok=True)


def append_performance_row(account_result: AccountResult) -> None:
    """Append an entry to performance.csv, creating the file with headers if needed."""
    is_new_file = not PERFORMANCE_FILE.exists()
    with PERFORMANCE_FILE.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if is_new_file:
            writer.writerow(["ID", "loginTime", "csvReadyTime", "downloadReadyTime"])
        writer.writerow(
            [
                account_result.username,
                account_result.login_time.strftime("%Y-%m-%d %H:%M:%S"),
                account_result.csv_ready_time.strftime("%Y-%m-%d %H:%M:%S"),
                account_result.download_ready_time.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )


def process_account(user_id: int, headless: bool) -> AccountResult:
    """Run the automation for a single account."""
    username = f"autoTest{user_id}"
    ensure_results_directory(RESULTS_DIR)

    driver = configure_driver(RESULTS_DIR, headless=headless)
    try:
        login_time = open_login_page(driver)

        if not submit_login(driver, username, DEFAULT_PASSWORD):
            register_account(driver, username, DEFAULT_PASSWORD)
            # After registration we should already be back at login.html.
            if not submit_login(driver, username, DEFAULT_PASSWORD):
                raise RuntimeError(f"Login failed for {username} after registration.")

        driver.get(INDEX_URL)
        populate_search_form(driver)
        query_index = start_search(driver)

        csv_ready_time, download_ready_time, downloaded_file = wait_for_csv_and_download(
            driver, username, RESULTS_DIR, query_index
        )

        return AccountResult(
            username=username,
            login_time=login_time,
            csv_ready_time=csv_ready_time,
            download_ready_time=download_ready_time,
            downloaded_file=downloaded_file,
        )
    finally:
        driver.quit()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk automation for autopapersearch.com accounts."
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=1,
        help="First numeric suffix to use (default: 1).",
    )
    parser.add_argument(
        "--end-id",
        type=int,
        default=100,
        help="Last numeric suffix to use (default: 100).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome in headless mode.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    if args.start_id < 1 or args.end_id < args.start_id:
        print("Invalid ID range.", file=sys.stderr)
        return 1

    ensure_results_directory(RESULTS_DIR)

    for idx in range(args.start_id, args.end_id + 1):
        username = f"autoTest{idx}"
        print(f"[+] Processing {username}...")
        try:
            result = process_account(idx, headless=args.headless)
        except Exception as exc:
            print(f"[!] Failed for {username}: {exc}", file=sys.stderr)
            continue

        append_performance_row(result)
        print(
            f"[✓] {username} complete: CSV at {result.downloaded_file.name} "
            f"(login {result.login_time.strftime('%H:%M:%S')}, "
            f"ready {result.csv_ready_time.strftime('%H:%M:%S')}, "
            f"downloaded {result.download_ready_time.strftime('%H:%M:%S')})"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
