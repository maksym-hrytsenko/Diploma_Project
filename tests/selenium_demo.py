"""Standalone exploratory script for testing Selenium's Chrome WebDriver API.

Opens Google, dismisses the cookie consent dialog if present, and performs
a search. Used to verify Selenium browser automation in isolation before
relying on it elsewhere in the project.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

print("Starting in 3 seconds...")
time.sleep(3)

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

print("Opening Google...")
driver.get("https://www.google.com")

wait = WebDriverWait(driver, 10)

# Google shows a cookie consent dialog on first visit; dismiss it if present.
try:
    agree_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button"))
    )
    agree_button.click()
except:
    pass

search_box = wait.until(
    EC.presence_of_element_located((By.NAME, "q"))
)

# send_keys silently no-ops on an unfocused element, so click first.
search_box.click()

print("Typing search query...")
search_box.send_keys("Selenium Python")
search_box.send_keys(Keys.RETURN)

time.sleep(3)

print("Done!")