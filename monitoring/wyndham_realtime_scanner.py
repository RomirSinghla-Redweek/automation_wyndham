#!/usr/bin/env python3
"""
Combined Wyndham scanner with real-time CSV generation
This script navigates the calendar UI, captures network responses, and updates CSV in real-time
"""

import os
import json
import csv
import time
from datetime import datetime
import base64
import getpass
from pathlib import Path
import threading
from collections import defaultdict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options

# --------------------- Config ---------------------

START_URL = "https://clubwyndham.wyndhamdestinations.com/us/en/resorts/resort-search-results"
MONTHS_TO_SCAN = 9
STAY_LENGTH_DAYS = 3  # S -> S+3 = 4-day window (3 nights)

SHORT, MEDIUM, LONG = 5, 20, 40

SCREEN_DIR = os.path.join(os.getcwd(), "screens/NewFolder")
os.makedirs(SCREEN_DIR, exist_ok=True)

# CSV output configuration
CSV_OUTPUT_FILE = os.path.join(SCREEN_DIR, "wyndham_availability_realtime.csv")
CSV_LOCK = threading.Lock()  # Thread safety for CSV operations

# --------------------- CSV Handler Class ---------------------

class RealtimeCSVHandler:
    """
    Handles real-time CSV generation and updates as network responses are captured
    """
    
    def __init__(self, output_file):
        self.output_file = output_file
        self.all_data = []
        self.unique_combinations = {}
        self.fieldnames = ['date', 'offeringId', 'inventoryOfferingHashKey', 'invenOffrngLabel', 'availableCount']
        
        # Initialize CSV file with headers
        self._initialize_csv()
    
    def _initialize_csv(self):
        """Create CSV file with headers"""
        with CSV_LOCK:
            with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                writer.writeheader()
            print(f"[CSV] Initialized real-time CSV file: {self.output_file}")
    
    def parse_network_response(self, response_data, source_info=""):
        """
        Parse network response and extract availability data
        
        Args:
            response_data (dict): JSON response data from network capture
            source_info (str): Optional info about the source (e.g., date range)
        
        Returns:
            list: List of dictionaries containing parsed availability data
        """
        data_rows = []
        
        try:
            # Check if resorts exist in the response
            if not response_data or 'resorts' not in response_data or not response_data['resorts']:
                return data_rows
            
            for resort in response_data['resorts']:
                if not resort.get('hasAvailableUnits', False):
                    continue
                
                # Get resort offerings
                resort_offerings = resort.get('resortOfferings', [])
                
                for offering in resort_offerings:
                    offering_id = offering.get('offeringId', '')
                    offering_label = offering.get('offeringLabel', '')
                    
                    # Handle Presidential Reserve offerings specially
                    if 'Presidential Reserve' in offering_label:
                        if 'Presidential Reserve' not in offering_id:
                            display_offering_id = f"{offering_id} Presidential Reserve"
                        else:
                            display_offering_id = offering_id
                    else:
                        display_offering_id = offering_id
                    
                    # Get accommodation classes
                    accommodation_classes = offering.get('accomdationClasses', [])
                    
                    for accommodation in accommodation_classes:
                        # Get calendar days with availability
                        calendar_days = accommodation.get('calendarDays', [])
                        
                        for day in calendar_days:
                            if not day.get('available', False):
                                continue
                            
                            date = day.get('date', '')
                            
                            # Get inventory offerings for this day
                            inventory_offerings = day.get('inventoryOfferings', [])
                            
                            for inventory in inventory_offerings:
                                # Extract required fields
                                available_count = inventory.get('availableCount', '0')
                                inventory_hash_key = inventory.get('inventoryOfferingHashKey', '')
                                inventory_label = inventory.get('invenOffrngLabel', '')
                                
                                # Handle Presidential Reserve labels
                                if 'Presidential Reserve' in offering_label and 'Presidential Reserve' not in inventory_label:
                                    inventory_label = f"{inventory_label} (Presidential Reserve)"
                                
                                # Only add rows with actual availability
                                if int(available_count) > 0:
                                    row = {
                                        'date': date,
                                        'offeringId': display_offering_id,
                                        'inventoryOfferingHashKey': inventory_hash_key,
                                        'invenOffrngLabel': inventory_label,
                                        'availableCount': available_count
                                    }
                                    data_rows.append(row)
            
            if data_rows:
                print(f"[CSV] Parsed {len(data_rows)} availability records from {source_info}")
            
        except Exception as e:
            print(f"[CSV] Error parsing response data: {e}")
        
        return data_rows
    
    def update_csv_realtime(self, new_data, source_info=""):
        """
        Update CSV file with new data in real-time
        
        Args:
            new_data (dict or list): New response data to add
            source_info (str): Information about the source
        """
        if isinstance(new_data, dict):
            # Parse the network response
            parsed_rows = self.parse_network_response(new_data, source_info)
        else:
            parsed_rows = new_data
        
        if not parsed_rows:
            return
        
        with CSV_LOCK:
            # Add to our internal data store
            self.all_data.extend(parsed_rows)
            
            # Update unique combinations
            new_unique_rows = []
            for row in parsed_rows:
                key = (row['date'], row['offeringId'], row['inventoryOfferingHashKey'], row['invenOffrngLabel'])
                
                # Only keep if this is a new combination
                if key not in self.unique_combinations:
                    self.unique_combinations[key] = row
                    new_unique_rows.append(row)
            
            # Append new unique rows to CSV
            if new_unique_rows:
                try:
                    with open(self.output_file, 'a', newline='', encoding='utf-8') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                        for row in new_unique_rows:
                            writer.writerow(row)
                    
                    print(f"[CSV] Added {len(new_unique_rows)} new unique rows to CSV (Total: {len(self.unique_combinations)})")
                except Exception as e:
                    print(f"[CSV] Error updating CSV file: {e}")
    
    def regenerate_sorted_csv(self):
        """
        Regenerate the entire CSV file with sorted data
        Useful to call periodically or at the end to ensure proper sorting
        """
        with CSV_LOCK:
            try:
                # Sort all unique data
                sorted_data = sorted(self.unique_combinations.values(), 
                                   key=lambda x: (x['date'], x['offeringId'], x['invenOffrngLabel']))
                
                # Rewrite the entire CSV
                with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                    writer.writeheader()
                    for row in sorted_data:
                        writer.writerow(row)
                
                print(f"[CSV] Regenerated sorted CSV with {len(sorted_data)} rows")
            except Exception as e:
                print(f"[CSV] Error regenerating CSV: {e}")

# --------------------- Enhanced Network Capture with CSV Integration ---------------------

class NetworkCaptureWithCSV:
    def __init__(self, driver, csv_handler):
        self.driver = driver
        self.csv_handler = csv_handler
        self.captured_responses = {}
        self.enable_network_capture()
    
    def enable_network_capture(self):
        """Enable Chrome DevTools Protocol for network capture"""
        # Enable Network domain
        self.driver.execute_cdp_cmd('Network.enable', {
            'maxPostDataSize': 100000000  # Increase limit for large responses
        })
        
        # Optional: Enable Performance domain for additional logging
        self.driver.execute_cdp_cmd('Performance.enable', {})
        
        print("[Network] Network capture enabled with real-time CSV updates")
    
    def get_availability_response(self, source_info=""):
        """
        Capture the most recent availability-search response and update CSV in real-time
        
        Args:
            source_info (str): Information about the date range being processed
            
        Returns:
            dict: The response data or None if not found
        """
        try:
            # Get performance logs
            logs = self.driver.get_log('performance')
            
            availability_data = None
            latest_timestamp = 0
            
            for log in logs:
                try:
                    message = json.loads(log['message'])
                    
                    # Check for Network.responseReceived events
                    if 'Network.responseReceived' in str(message.get('message', {}).get('method', '')):
                        params = message['message']['params']
                        response = params.get('response', {})
                        url = response.get('url', '')
                        
                        # Check if this is an availability-search endpoint
                        if 'availability-search' in url:
                            request_id = params.get('requestId')
                            timestamp = params.get('timestamp', 0)
                            
                            # Only process if this is newer than what we have
                            if timestamp > latest_timestamp:
                                try:
                                    # Get the response body
                                    response_body = self.driver.execute_cdp_cmd(
                                        'Network.getResponseBody',
                                        {'requestId': request_id}
                                    )
                                    
                                    if response_body and 'body' in response_body:
                                        # Parse the response
                                        body_text = response_body['body']
                                        
                                        # Handle base64 encoded responses
                                        if response_body.get('base64Encoded'):
                                            body_text = base64.b64decode(body_text).decode('utf-8')
                                        
                                        try:
                                            availability_data = json.loads(body_text)
                                            latest_timestamp = timestamp
                                            print(f"[Network] Captured availability-search response for {source_info}")
                                            
                                            # Update CSV in real-time
                                            self.csv_handler.update_csv_realtime(availability_data, source_info)
                                            
                                        except json.JSONDecodeError:
                                            # Response might not be JSON
                                            availability_data = {'raw_response': body_text}
                                            latest_timestamp = timestamp
                                            
                                except Exception as e:
                                    # Request might not have a body yet
                                    pass
                    
                    # Also check for Network.loadingFinished events with data
                    elif 'Network.loadingFinished' in str(message.get('message', {}).get('method', '')):
                        params = message['message']['params']
                        request_id = params.get('requestId')
                        
                        # Try to get response for this request
                        try:
                            # First get the request info to check URL
                            request_will_be_sent = None
                            for earlier_log in logs:
                                earlier_msg = json.loads(earlier_log['message'])
                                if 'Network.requestWillBeSent' in str(earlier_msg.get('message', {}).get('method', '')):
                                    if earlier_msg['message']['params'].get('requestId') == request_id:
                                        request_will_be_sent = earlier_msg['message']['params']
                                        break
                            
                            if request_will_be_sent and 'availability-search' in request_will_be_sent.get('request', {}).get('url', ''):
                                response_body = self.driver.execute_cdp_cmd(
                                    'Network.getResponseBody',
                                    {'requestId': request_id}
                                )
                                
                                if response_body and 'body' in response_body:
                                    body_text = response_body['body']
                                    if response_body.get('base64Encoded'):
                                        body_text = base64.b64decode(body_text).decode('utf-8')
                                    
                                    availability_data = json.loads(body_text)
                                    print(f"[Network] Captured availability-search response (via loadingFinished) for {source_info}")
                                    
                                    # Update CSV in real-time
                                    self.csv_handler.update_csv_realtime(availability_data, source_info)
                                    
                        except Exception:
                            pass
                            
                except Exception as e:
                    continue
            
            return availability_data
            
        except Exception as e:
            print(f"[Network] Error capturing response: {e}")
            return None
    
    def clear_logs(self):
        """Clear performance logs to avoid memory issues"""
        try:
            self.driver.get_log('performance')  # This clears the log buffer
        except:
            pass

# --------------------- Small helpers (same as original) ---------------------

def wait_click(driver, by, selector, timeout=MEDIUM, scroll=True):
    el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, selector)))
    if scroll:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass
    el.click()
    return el

def click_if_present(driver, by, selector, timeout=SHORT):
    try:
        el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, selector)))
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass
        el.click()
        return True
    except Exception:
        return False

def clear_dates(driver):
    candidates = [
        (By.XPATH, "//button[contains(., 'Clear Dates')]"),
        (By.XPATH, "//a[contains(., 'Clear Dates')]"),
        (By.XPATH, "//button[@aria-label='Clear dates']"),
    ]
    for by, sel in candidates:
        if click_if_present(driver, by, sel, timeout=3):
            time.sleep(0.15)
            return True
    print("Clear dates control not found; trying to click both date inputs...")
    try:
        ci = driver.find_element(By.XPATH, "//*[@aria-label='Check-in' or @placeholder[contains(.,'Check')] or @name='checkin']")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", ci)
        ci.click()
        time.sleep(0.1)
        co = driver.find_element(By.XPATH, "//*[@aria-label='Check-out' or @placeholder[contains(.,'Check')] or @name='checkout']")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", co)
        co.click()
        time.sleep(0.1)
    except Exception:
        pass
    return False

def wait_for_available_suites(driver, timeout=LONG):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//*[contains(@class,'available') or contains(@class,'suite') or contains(@class,'room')]"
            ))
        )
        time.sleep(0.5)
        return True
    except TimeoutException:
        return False

def save_screenshot_and_response(driver, network_capture, start_day, end_day):
    """Modified to work with NetworkCaptureWithCSV"""
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    
    # Format date range info
    date_range = f"day{start_day:02d}_to_day{end_day:02d}"
    
    # Take screenshot
    screen_path = os.path.join(SCREEN_DIR, f"screen_{timestamp}_{date_range}.png")
    driver.save_screenshot(screen_path)
    
    # Response is already saved to CSV in real-time by get_availability_response
    # We can optionally still save the JSON file for backup
    response_data = network_capture.get_availability_response(f"days {start_day}-{end_day}")
    if response_data:
        response_path = os.path.join(SCREEN_DIR, f"screen_{timestamp}_{date_range}_network-response.txt")
        with open(response_path, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, indent=2)
    
    print(f"[Screenshot] Saved: {date_range}")

def month_containers(driver):
    try:
        containers = driver.find_elements(By.XPATH, "//*[contains(@class,'month') and contains(@class,'container')]")
        if len(containers) >= 2:
            return containers[0], containers[1]
    except Exception:
        pass
    try:
        containers = driver.find_elements(By.XPATH, "//*[@role='grid' or contains(@class,'calendar')]")
        if len(containers) >= 2:
            return containers[0], containers[1]
    except Exception:
        pass
    return None, None

def enabled_day_numbers_by_panel(driver):
    left, right = month_containers(driver)
    if not left:
        return [], []
    
    def collect_enabled(container):
        if not container:
            return set()
        days = set()
        for n in container.find_elements(By.XPATH, ".//*[not(@aria-disabled='true') and not(contains(@class,'disabled'))]"):
            try:
                t = (n.text or "").strip()
                if t.isdigit() and n.is_enabled() and n.is_displayed():
                    days.add(int(t))
            except Exception:
                pass
        return sorted(days)
    
    return collect_enabled(left), collect_enabled(right)

def all_day_numbers_by_panel(driver):
    left, right = month_containers(driver)
    if not left:
        return [], []
    
    def collect_all(container):
        if not container:
            return set()
        days = set()
        for n in container.find_elements(By.XPATH, ".//*"):
            try:
                t = (n.text or "").strip()
                if t.isdigit() and n.is_displayed():
                    days.add(int(t))
            except Exception:
                pass
        return sorted(days)
    return collect_all(left), collect_all(right)

def click_day_in_panel(driver, day, panel="left"):
    left, right = month_containers(driver)
    container = left if panel == "left" else right
    if not container:
        return False
    try:
        el = WebDriverWait(container, 5).until(
            EC.element_to_be_clickable((
                By.XPATH,
                f".//*[self::button or self::a or self::div or self::span][normalize-space(text())='{day}' "
                "and not(@aria-disabled='true') and not(contains(@class,'disabled'))]"
            ))
        )
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass
        el.click()
        return True
    except Exception:
        return False

# --------------------- Core per-month logic with real-time CSV ---------------------

def process_month_left_panel(driver, network_capture):
    """Process month with real-time CSV updates"""
    left_enabled, right_enabled = enabled_day_numbers_by_panel(driver)
    left_all, right_all = all_day_numbers_by_panel(driver)
    
    if not left_all:
        print("No day labels found in left panel; skipping this month.")
        return
    
    days_in_left = max(left_all)
    
    for start in left_enabled:
        end = start + STAY_LENGTH_DAYS
        if end <= days_in_left:
            end_day = end
            end_panel = "left"
            end_clickable = end_day in left_enabled
        else:
            end_day = end - days_in_left
            end_panel = "right"
            end_clickable = end_day in right_enabled
        
        if not end_clickable:
            clear_dates(driver)
            time.sleep(0.15)
            print(f"Skip start {start}: end {end_day} in {end_panel} not selectable.")
            continue
        
        # Clear any previous network logs
        network_capture.clear_logs()
        
        clear_dates(driver)
        if not click_day_in_panel(driver, start, panel="left"):
            print(f"Could not click start {start} in left; skipping.")
            continue
        
        if not click_day_in_panel(driver, end_day, panel=end_panel):
            print(f"Could not click end {end_day} in {end_panel} after start {start}; skipping.")
            clear_dates(driver)
            continue
        
        # Wait for results and capture response (CSV is updated automatically)
        if wait_for_available_suites(driver, timeout=LONG):
            time.sleep(1)  # Wait a bit more for network response
            save_screenshot_and_response(driver, network_capture, start, end_day)
        else:
            print(f"[No Availability] {start}->{end_day} ({end_panel}) - skipping screenshot.")
        
        clear_dates(driver)
        time.sleep(0.15)

# --------------------- Month navigation ---------------------

def goto_next_month(driver):
    candidates = [
        (By.XPATH, "//*[@aria-label='Next Month']"),
        (By.XPATH, "//button[contains(@aria-label, 'Next') and contains(@aria-label, 'Month')]"),
        (By.XPATH, "//button[.//*[name()='svg' or @class][contains(@class,'chevron') or contains(@class,'right')]]"),
        (By.XPATH, "//*[contains(@class,'next') and (self::button or self::a)]"),
        (By.XPATH, "//span[contains(.,'›') or contains(.,'»')]"),
    ]
    for by, sel in candidates:
        if click_if_present(driver, by, sel, timeout=3):
            time.sleep(0.4)
            clear_dates(driver)
            return True
    print("Next Month control not found/clickable.")
    return False

# --------------------- Entry ---------------------

def main():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    
    # Enable performance logging for network capture
    chrome_options.set_capability('goog:loggingPrefs', {
        'performance': 'ALL',
        'browser': 'ALL'
    })
    
    # Add experimental options for better network capture
    chrome_options.add_experimental_option('perfLoggingPrefs', {
        'enableNetwork': True,
        'enablePage': False,
    })
    
    # Optional: Use existing Chrome profile to skip 2FA
    # username = getpass.getuser()
    # chrome_options.add_argument(rf"--user-data-dir=C:\Users\{username}\AppData\Local\Google\Chrome\User Data")
    # chrome_options.add_argument(r"--profile-directory=Default")
    
    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    try:
        # Initialize CSV handler
        csv_handler = RealtimeCSVHandler(CSV_OUTPUT_FILE)
        
        # Initialize network capture with CSV integration
        network_capture = NetworkCaptureWithCSV(driver, csv_handler)
        
        driver.get(START_URL)
        time.sleep(2)
        
        # Cookie banners / consent
        click_if_present(driver, By.XPATH, "//*[contains(., 'Accept') and contains(., 'Cookies')]", timeout=2)
        click_if_present(driver, By.XPATH, "//button[contains(., 'Accept')]", timeout=2)
        
        # Attempt "View Availability" early
        view_variants = [
            (By.XPATH, "//button[contains(., 'View Availability')]"),
            (By.XPATH, "//a[contains(., 'View Availability')]"),
        ]
        for by, sel in view_variants:
            if click_if_present(driver, by, sel, timeout=2):
                break
        
        input("Log in & pass 2FA in the browser, navigate to the 2-month calendar.\n"
              "When the calendar is visible, press ENTER here to start... ")
        
        for by, sel in view_variants:
            click_if_present(driver, by, sel, timeout=2)
        
        print("\n[Network] Starting scan with real-time CSV generation...")
        print(f"[CSV] Real-time updates will be saved to: {CSV_OUTPUT_FILE}")
        print(f"[Screenshots] Will be saved to: {SCREEN_DIR}\n")
        
        for month_idx in range(MONTHS_TO_SCAN):
            print(f"\n---- Month {month_idx + 1} of {MONTHS_TO_SCAN} ----")
            try:
                process_month_left_panel(driver, network_capture)
            except Exception as e:
                print(f"Error processing month {month_idx + 1}: {e}")
            
            # Optionally regenerate sorted CSV after each month
            if (month_idx + 1) % 3 == 0:  # Every 3 months
                csv_handler.regenerate_sorted_csv()
            
            if month_idx < MONTHS_TO_SCAN - 1:
                ok = goto_next_month(driver)
                if not ok:
                    print("Stopping early; could not advance to next month.")
                    break
        
        # Final CSV regeneration to ensure proper sorting
        print("\n[CSV] Performing final CSV sort and cleanup...")
        csv_handler.regenerate_sorted_csv()
        
        print("\n" + "="*50)
        print("SCAN COMPLETE WITH REAL-TIME CSV GENERATION")
        print(f"Results saved to:")
        print(f"  - CSV file: {CSV_OUTPUT_FILE}")
        print(f"  - Screenshots: {SCREEN_DIR}/*.png")
        print(f"  - Network responses: {SCREEN_DIR}/*network-response*.txt")
        print(f"\nTotal unique availability records: {len(csv_handler.unique_combinations)}")
        print("="*50)
        print("\nBrowser will remain open for review.")
        
    except KeyboardInterrupt:
        print("Interrupted by user.")
        print(f"Partial results saved to: {CSV_OUTPUT_FILE}")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
