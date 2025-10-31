
# -*- coding: utf-8 -*-
"""
Club Wyndham month scanner (updated: only screenshot when real availability exists)
- Iterates month-by-month (left panel month only)
- For each enabled start day S in the left panel, compute end = S + STAY_LENGTH_DAYS.
- Proceed ONLY if the computed end day is clickable in the correct panel.
- After selecting S -> end, wait specifically for VISIBLE 'Book' buttons (suite cards).
  Take a screenshot ONLY then. Skip empty states and skip "Loading available suites".

Prereqs:
  pip install selenium webdriver-manager

Run:
  python wyndham_scan_9months.py
"""

import os
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException

from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options

# --------------------- Config ---------------------

START_URL = "https://clubwyndham.wyndhamdestinations.com/us/en/resorts/wyndham/club-wyndham-nashville?owner=true"
MONTHS_TO_SCAN = 9 # Set number of months we are covering (ie, Start Oct - July)
STAY_LENGTH_DAYS = 3  # S -> S+3 = 4-day window (3 nights)

SHORT, MEDIUM, LONG = 5, 20, 40

SCREEN_DIR = os.path.join(os.getcwd(), "screens/Nashville")
os.makedirs(SCREEN_DIR, exist_ok=True)

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

def take_page_screenshot(driver, start_day, end_day, resort_name="ClubWyndham"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{resort_name}_{start_day}-{end_day}_{ts}.png"
    path = os.path.join(SCREEN_DIR, fname)
    driver.save_screenshot(path)
    print(f"[✓] Saved screenshot: {path}")
    return path

def wait_for_available_suites(driver, timeout=LONG):
    """
    Wait ONLY for *real availability* (suite cards with a visible 'Book' button).
    Ignore intermediate states like 'Loading available suites' and skip empty results.
    Returns True iff at least one visible 'Book' button appears before timeout.
    """
    end_time = time.time() + timeout

    # Ensure top of page (right rail usually visible without extra scroll)
    try:
        driver.execute_script("window.scrollTo(0, 0);")
    except Exception:
        pass

    # Case-insensitive contains('loading available suites')
    loading_sel = (By.XPATH, "//*[contains(translate(., 'LOADINGAVAILABLESUITES', 'loadingavailablesuites'), 'loading available suites')]")
    book_btn_sel = (By.XPATH, "//aside//button[contains(., 'Book')] | //button[contains(., 'Book') and ancestor::aside]")
    # Generic fallback in case aside isn't used:
    book_btn_fallback = (By.XPATH, "//button[contains(., 'Book')]")

    while time.time() < end_time:
        try:
            # If there is a loading overlay, just keep waiting
            loading_elems = driver.find_elements(*loading_sel)
            if any(e.is_displayed() for e in loading_elems):
                time.sleep(0.3)
                continue

            # Real availability -> 'Book' buttons visible
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
    """
    Returns (left_container, right_container) for the two visible month panels.
    We locate month-like blocks and sort by x-position, then choose the two densest
    in numeric day labels.
    """
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

# --------------------- Core per-month logic (updated) ---------------------

def process_month_left_panel(driver):
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

        clear_dates(driver)
        if not click_day_in_panel(driver, start, panel="left"):
            print(f"Could not click start {start} in left; skipping.")
            continue

        if not click_day_in_panel(driver, end_day, panel=end_panel):
            print(f"Could not click end {end_day} in {end_panel} after start {start}; skipping.")
            clear_dates(driver)
            continue

        # Wait only for real availability (visible 'Book' button)
        if wait_for_available_suites(driver, timeout=LONG):
            take_page_screenshot(driver, start, end_day)
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
    # To reuse a Chrome profile (skip 2FA), set your paths and uncomment:
    # chrome_options.add_argument(r"--user-data-dir=C:\Users\YOURNAME\AppData\Local\Google\Chrome\User Data")
    # chrome_options.add_argument(r"--profile-directory=Profile 5")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=chrome_options
    )

    try:
        driver.get(START_URL)
        time.sleep(2)

        # Cookie banners / consent (best-effort)
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

        for month_idx in range(MONTHS_TO_SCAN):
            print(f"\n---- Month {month_idx + 1} of {MONTHS_TO_SCAN} ----")
            try:
                process_month_left_panel(driver)
            except Exception as e:
                print(f"Error processing month {month_idx + 1}: {e}")
            if month_idx < MONTHS_TO_SCAN - 1:
                ok = goto_next_month(driver)
                if not ok:
                    print("Stopping early; could not advance to next month.")
                    break

        print("\nDone. Browser will remain open for review.")
        # driver.quit()

    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        print(f"Fatal error: {e}")
    # finally:
    #     driver.quit()

if __name__ == "__main__":
    main()
