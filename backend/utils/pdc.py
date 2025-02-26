import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from langchain_community.document_loaders import PyPDFLoader
import tempfile


def local_storage_has_key(driver, key):
    return driver.execute_script(f"return localStorage.getItem('{key}') !== null")


def login_and_get_token():
    """Logs into FSMB and extracts the authentication token from local storage."""

    # Set up Chrome options
    chrome_options = Options()
    # Run in headless mode for backend usage
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    # Helps in containerized environments
    chrome_options.add_argument("--disable-dev-shm-usage")

    token = None

    # Initialize WebDriver using context manager to ensure cleanup
    with webdriver.Chrome(options=chrome_options) as driver:
        try:
            print("Logging into FSMB...")
            # Step 1: Open FSMB login page
            driver.get("https://pdc-reports.fsmb.org/")

            print("Waiting for login form...")
            
            # Wait for the login form
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "Username")))
            
            print("Filling in login details...")

            # Fill in login details
            username_field = driver.find_element(By.NAME, "Username")
            password_field = driver.find_element(By.NAME, "Password")
            
            print("Logging in...")

            username_field.send_keys(os.getenv("FSMB_USERNAME"))
            password_field.send_keys(os.getenv("FSMB_PASSWORD"))
            password_field.send_keys(Keys.RETURN)
            
            print("Waiting for login to complete...")

            # Wait for login to complete by checking URL change or dashboard presence
            WebDriverWait(driver, 30).until(lambda d: local_storage_has_key(
                d, "02d544b8-5953-409e-acac-6e9dc1245c51-b2c_1_signin.47d5d385-8b25-48c4-87bc-719b6e01c6c2-pdcreports.b2clogin.com-idtoken-03c06422-233c-4bba-b656-9f61071e6633----"))

            print("Login successful!")
            
            # Step 2: Extract local storage data
            raw_local_storage_data = driver.execute_script("""
                let data = {};
                for (let key of Object.keys(localStorage)) {
                    data[key] = localStorage.getItem(key);
                }
                return data;
            """)
            
            # Parse local storage data
            
            print("Extracting token...")

            parsed_local_storage_data = {}
            for key, value in raw_local_storage_data.items():
                print(f"Key: {key}, Value: {value}")
                try:
                    # Try to parse as JSON
                    print(f"Trying to parse JSON: {key}")
                    parsed_local_storage_data[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # Keep as string if not JSON
                    print(f"Failed to parse JSON: {key}")
                    parsed_local_storage_data[key] = value

            for key, value in parsed_local_storage_data.items():
                print(f"Key: {key}, Value: {value}")
                if isinstance(value, dict) and value.get("credentialType") == "IdToken":
                    print("Found token!")
                    token = value.get("secret")
                    print(str(token))
                    break

        except Exception as e:
            print(f"Error during FSMB login: {e}")

    return token


def extract_text_from_pdf_bytes(pdf_bytes):
    temp_pdf_path = None
    try:
        # Create a temporary file without locking (Windows compatible)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            tmp_pdf.write(pdf_bytes)
            temp_pdf_path = tmp_pdf.name  # Store temp file path

        # Use PyPDFLoader with the temp file path
        loader = PyPDFLoader(temp_pdf_path)
        pages = loader.load()

        # Combine text from all pages
        text = "\n".join([page.page_content for page in pages])
        return text

    except Exception as e:
        raise Exception(f"Failed to extract text: {e}")

    finally:
        # Cleanup: Delete the temporary file after processing
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
