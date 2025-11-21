"""
Club Wyndham scanner with network response capture and screenshot (set screen to 50%)
- Captures "availability-search" network responses
- Saves response data alongside screenshots
- Names files with date ranges

Prereqs:
- selenium 
- webdriver-manager
"""

import os
import json
import time
from datetime import datetime
import base64
import getpass

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options

# --------------------- Config ---------------------
# Hard codded setting, changable according to wyndham's updates.

START_URL = "https://clubwyndham.wyndhamdestinations.com/us/en/resorts/resort-search-results"
MONTHS_TO_SCAN = 9
STAY_LENGTH_DAYS = 3  # ie 1 -> 4

SHORT, MEDIUM, LONG = 5, 20, 40 #waits for UI calls

SCREEN_DIR = os.path.join(os.getcwd(), "screens/NewFolder")
os.makedirs(SCREEN_DIR, exist_ok=True)

# --------------------- Network Capture Setup ---------------------

class NetworkCapture:
    def __init__(self, driver):
        self.driver = driver
        self.captured_responses = {}
        self.enable_network_capture()
    
    def enable_network_capture(self):
        """Enable Chrome DevTools Protocol for network capture"""
        # Enable Network domain
        self.driver.execute_cdp_cmd('Network.enable', {
            'maxPostDataSize': 100000000  # Increase limit for large responses
        })
        
        # Enable Performance domain for additional logging
        self.driver.execute_cdp_cmd('Performance.enable', {})
        print("[Network] Network capture enabled")
    
    def get_availability_response(self):
        """
        Capture the most recent "availability-search" response
        Returns the response data or None if not found
        - availability-search is the name of the resoponse with room information
        """
        try:
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
                                            print(f"[Network] Captured availability-search response")
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
                                    print(f"[Network] Captured availability-search response (via loadingFinished)")
                                    
                        except Exception:
                            pass
                            
                except Exception as e:
                    continue
            
            return availability_data
            
        except Exception as e:
            print(f"[Network] Error capturing response: {e}")
            return None
    
    def clear_logs(self):
        # remove cache
        try:
            self.driver.get_log('performance')  # This clears the log buffer
        except:
            pass

# --------------------- Small helpers ---------------------

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
        (By.XPATH, "//*[@aria-label='Clear Dates']"),
        (By.XPATH, "//*[contains(@class,'clear') and contains(., 'Date')]"),
    ]
    for by, sel in candidates:
        if click_if_present(driver, by, sel, timeout=2):
            time.sleep(0.15)
            return True
    return False

def save_screenshot_and_response(driver, network_capture, start_day, end_day, resort_name="ClubWyndham"):
    # main method for scrapping screenshot and network response
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{resort_name}_{start_day}to{end_day}_{ts}"
    
    # Save screenshot
    screenshot_path = os.path.join(SCREEN_DIR, f"{base_name}.png")
    driver.save_screenshot(screenshot_path)
    print(f"[✓] Saved screenshot: {screenshot_path}")
    
    # Try to get and save network response
    response_data = network_capture.get_availability_response()
    if response_data:
        # Save network response
        response_filename = f"{start_day}to{end_day}_network-response_{ts}.txt"
        response_path = os.path.join(SCREEN_DIR, response_filename)
        
        # print JSON if it's structured data
        if isinstance(response_data, dict) or isinstance(response_data, list):
            with open(response_path, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, ensure_ascii=False)
        else:
            with open(response_path, 'w', encoding='utf-8') as f:
                f.write(str(response_data))
        
        print(f"[✓] Saved network response: {response_path}")
        
        # Also save a summary if it contains resort data
        # for testing purposes, remove later
        if isinstance(response_data, dict):
            summary = {
                'date_range': f"{start_day} to {end_day}",
                'timestamp': ts,
                'total_results': len(response_data.get('results', [])) if 'results' in response_data else 'N/A',
                'has_availability': bool(response_data.get('results', [])) if 'results' in response_data else 'Unknown'
            }
            
            summary_path = os.path.join(SCREEN_DIR, f"{base_name}_summary.json")
            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)
    else:
        print(f"[!] No network response captured for {start_day} to {end_day}")
    
    return screenshot_path

def wait_for_available_suites(driver, timeout=LONG):
    # book button on club wyndham site
    end_time = time.time() + timeout
    
    try:
        driver.execute_script("window.scrollTo(0, 0);")
    except Exception:
        pass
    
    loading_sel = (By.XPATH, "//*[contains(translate(., 'LOADINGAVAILABLESUITES', 'loadingavailablesuites'), 'loading available suites')]")
    book_btn_sel = (By.XPATH, "//aside//button[contains(., 'Book')] | //button[contains(., 'Book') and ancestor::aside]")
    book_btn_fallback = (By.XPATH, "//button[contains(., 'Book')]")
    
    while time.time() < end_time:
        try:
            loading_elems = driver.find_elements(*loading_sel)
            if any(e.is_displayed() for e in loading_elems):
                time.sleep(0.3)
                continue
            
            book_elems = driver.find_elements(*book_btn_sel)
            if not book_elems:
                book_elems = driver.find_elements(*book_btn_fallback)
            
            if any(e.is_displayed() for e in book_elems):
                return True
            
            time.sleep(0.3)
        except Exception:
            time.sleep(0.3)
    
    return False

# --------------------- Month panel helpers ---------------------

def month_containers(driver):
    """Returns (left_container, right_container) for the two visible month panels"""
    candidates = driver.find_elements(
        By.XPATH,
        "//div[.//table or .//button or .//a]"
    )
    blocks = []
    for el in candidates:
        try:
            if not el.is_displayed():
                continue
            r = el.rect
            if r.get('width', 0) < 250 or r.get('height', 0) < 180:
                continue
            blocks.append((el, r.get('x', 0), r.get('width', 0)))
        except Exception:
            pass
    
    blocks.sort(key=lambda t: t[1])
    
    def numeric_count(node):
        try:
            kids = node.find_elements(By.XPATH, ".//*[normalize-space(text())!='']")
            count = 0
            for k in kids:
                try:
                    t = (k.text or '').strip()
                    if t.isdigit() and k.is_displayed():
                        count += 1
                except Exception:
                    pass
            return count
        except Exception:
            return 0
    
    scored = []
    for el, x, w in blocks[:6]:
        scored.append((numeric_count(el), x, el))
    scored.sort(key=lambda t: (-t[0], t[1]))
    top = sorted(scored[:2], key=lambda t: t[1])
    if len(top) < 2:
        return (None, None)
    return top[0][2], top[1][2]

def enabled_day_numbers_by_panel(driver):
    left, right = month_containers(driver)
    def collect(container):
        if not container:
            return []
        nodes = container.find_elements(
            By.XPATH,
            ".//*[self::button or self::a or self::div or self::span][normalize-space(text())!='' "
            "and not(@aria-disabled='true') and not(contains(@class,'disabled'))]"
        )
        days = set()
        for n in nodes:
            try:
                t = (n.text or "").strip()
                if t.isdigit() and n.is_displayed() and n.is_enabled():
                    days.add(int(t))
            except Exception:
                pass
        return sorted(days)
    return collect(left), collect(right)

def all_day_numbers_by_panel(driver):
    left, right = month_containers(driver)
    def collect_all(container):
        if not container:
            return []
        nodes = container.find_elements(
            By.XPATH,
            ".//*[self::button or self::a or self::div or self::span][normalize-space(text())!='']"
        )
        days = set()
        for n in nodes:
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

# --------------------- Core per-month logic with network capture ---------------------

def process_month_left_panel(driver, network_capture):
    """Process month with network response capture"""
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
        
        # Wait for results and give network response time to arrive
        if wait_for_available_suites(driver, timeout=LONG):
            # Wait a bit more for network response to be fully captured
            time.sleep(1)
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
    
    # Use existing Chrome profile to skip 2FA
    # needs work, breaks chrome when implemented
    # username = getpass.getuser()  # Automatically gets current Windows username
    #chrome_options.add_argument(rf"--user-data-dir=C:\Users\{username}\AppData\Local\Google\Chrome\User Data")
    # chrome_options.add_argument(r"--profile-directory=Profile 1")
    # chrome_options.add_argument(r"--profile-directory=Default")
    
    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    try:
        # Initialize network capture
        network_capture = NetworkCapture(driver)
        
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
        
        print("\n[Network] Starting scan with network response capture...")
        print(f"[Network] Screenshots and responses will be saved to: {SCREEN_DIR}\n")
        
        for month_idx in range(MONTHS_TO_SCAN):
            print(f"\n---- Month {month_idx + 1} of {MONTHS_TO_SCAN} ----")
            try:
                process_month_left_panel(driver, network_capture)
            except Exception as e:
                print(f"Error processing month {month_idx + 1}: {e}")
            
            if month_idx < MONTHS_TO_SCAN - 1:
                ok = goto_next_month(driver)
                if not ok:
                    print("Stopping early; could not advance to next month.")
                    break
        
        print("\n" + "="*50)
        print("SCAN COMPLETE")
        print(f"Check {SCREEN_DIR} for:")
        print("  - Screenshots (.png files)")
        print("  - Network responses (*network-response*.txt files)")
        print("  - Summary files (*summary.json files)")
        print("="*50)
        print("\nBrowser will remain open for review.")
        
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
