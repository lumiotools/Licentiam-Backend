import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def local_storage_has_key(driver, key):
    return driver.execute_script(f"return localStorage.getItem('{key}') !== null")

def login_and_get_token():
    """Logs into FSMB and extracts the authentication token from local storage."""
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode for backend usage
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")  # Helps in containerized environments
    
    token = None

    # Initialize WebDriver using context manager to ensure cleanup
    with webdriver.Chrome(options=chrome_options) as driver:
        try:
            # Step 1: Open FSMB login page
            driver.get("https://pdc-reports.fsmb.org/")
            
            # Wait for the login form
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "Username")))
            
            # Fill in login details
            username_field = driver.find_element(By.NAME, "Username")
            password_field = driver.find_element(By.NAME, "Password")

            username_field.send_keys(os.getenv("FSMB_USERNAME"))
            password_field.send_keys(os.getenv("FSMB_PASSWORD"))
            password_field.send_keys(Keys.RETURN)

            # Wait for login to complete by checking URL change or dashboard presence
            WebDriverWait(driver, 10).until(lambda d: local_storage_has_key(d, "02d544b8-5953-409e-acac-6e9dc1245c51-b2c_1_signin.47d5d385-8b25-48c4-87bc-719b6e01c6c2-pdcreports.b2clogin.com-idtoken-03c06422-233c-4bba-b656-9f61071e6633----"))

            # Step 2: Extract local storage data
            raw_local_storage_data = driver.execute_script("""
                let data = {};
                for (let key of Object.keys(localStorage)) {
                    data[key] = localStorage.getItem(key);
                }
                return data;
            """)
            
            parsed_local_storage_data = {}
            for key, value in raw_local_storage_data.items():
                try:
                    parsed_local_storage_data[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    parsed_local_storage_data[key] = value  # Keep as string if not JSON

            for key, value in parsed_local_storage_data.items():
                if isinstance(value, dict) and value.get("credentialType") == "IdToken":
                    token = value.get("secret")
                    break
            
        except Exception as e:
            print(f"Error during FSMB login: {e}")

    return token 
