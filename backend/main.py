from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import requests
import uvicorn
import json
import asyncio
import os
from datetime import datetime
from utils.pdc import login_and_get_token, extract_text_from_pdf_bytes
from llm import create_sheet
from pydantic import BaseModel
from typing import Optional
from crm import add_provider, upload_licenses, get_crm_auth_token, Provider, Licenses


load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Welcome"}


def change_name(data):
    name = ""
    if data['lastName']:
        name += data['lastName'] + ', '
    if data['firstName']:
        name += data['firstName'] + ' '
    if data['middleName']:
        name += data['middleName']
    if data['suffix']:
        name += ', ' + data['suffix']

    return name


@app.get("/get-roasters")
async def get_roasters(token: Optional[str] = None):
    """Fetches the roster list from FSMB API after login."""

    if not token:
        token = await asyncio.to_thread(login_and_get_token)

    if not token:
        raise HTTPException(
            status_code=401, detail="Failed to login and get token.")

    URL = 'https://pdc-appapi.fsmb.org/roster/practitioner/list?pageSize=10000&pageIndex=0&customerId=7881'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    # Make request to FSMB API
    try:
        response = requests.get(URL, headers=headers)
        response.raise_for_status()
        data = response.json()['items']
        for i in data:
            i['name'] = change_name(i)
        return data

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch roasters: {e}")


class UserDetails(BaseModel):
    username: str
    birth_date: str
    email: Optional[str] = None
    phone: Optional[str] = None
    fid: Optional[str] = None
    pdcToken: Optional[str] = None
    crmToken: Optional[str] = None


@app.get("/get-token")
async def get_token():
    pdcToken = await asyncio.to_thread(login_and_get_token)
    crmToken = await asyncio.to_thread(get_crm_auth_token)
    return {"pdcToken": pdcToken, "crmToken": crmToken}


@app.post("/get-pdf-data")
async def get_pdf_data(user: UserDetails):
    """Fetches the PDF data from FSMB API after login and extracts text."""
    if user.pdcToken:
        token = user.pdcToken
    else:
        token = await asyncio.to_thread(login_and_get_token)

    roasters = await get_roasters(token)

    if not roasters:
        raise HTTPException(
            status_code=401, detail="Failed to retrieve roasters.")

    # Find the user in the roasters list
    rosterEntryId = next(
        (roster['rosterEntryId'] for roster in roasters
         if f"{roster['lastName']}, {roster['firstName']} {roster['middleName']}".strip() == user.username and roster['displayBirthDate'] == user.birth_date),
        None
    )

    if not rosterEntryId:
        raise HTTPException(
            status_code=404, detail="User not found in roasters.")

    # FSMB API request
    URL = 'https://pdc-appapi.fsmb.org/download/practitioner/report'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    data = {
        "rosterEntryIds": [rosterEntryId],
        "customerId": 7881,
    }

    try:
        response = requests.post(URL, headers=headers, json=data)
        response.raise_for_status()
        
        print(f"PDF Data Fetched... ${response.status_code}")

        # Extract text from PDF bytes
        pdf_text = extract_text_from_pdf_bytes(response.content)

        res = create_sheet(pdf_text, user.birth_date)

        return {'data': res,
                "token": token if not user.pdcToken else None}
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch PDF data: {e}")

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing PDF: {e}")


@app.post("/create-licence-entry")
async def create_licence_entry(user: UserDetails):
    """Fetches the PDF data from FSMB API after login and extracts text."""
    
    async def progress_stream():
        try:
            # Initial validation
            if not user.email or not user.phone or not len(user.phone) == 10:
                yield f"data: {{'progress': 0, 'step': 'error', 'message': 'Invalid email or phone number'}}\n\n"
                return
            
            # Starting process
            yield f"data: {{'progress': 5, 'step': 'start', 'message': 'Starting license retrieval process...'}}\n\n"
            
            # Step 1a: Getting authentication token (10%)
            yield f"data: {{'progress': 10, 'step': 'authentication', 'message': 'Authenticating with FSMB...'}}\n\n"
            
            if user.pdcToken:
                token = user.pdcToken
            else:
                token = await asyncio.to_thread(login_and_get_token)
            
            # Step 1b: Fetching roasters (20%)
            yield f"data: {{'progress': 20, 'step': 'fetch_roasters', 'message': 'Retrieving practitioner roster...'}}\n\n"
            
            roasters = await get_roasters(token)

            if not roasters:
                raise HTTPException(
                    status_code=401, detail="Failed to retrieve roasters.")

            # Step 1c: Finding user in roster (25%)
            yield f"data: {{'progress': 25, 'step': 'find_user', 'message': 'Locating user information...'}}\n\n"
            
            # Find the user in the roasters list
            rosterEntryId = next(
                (roster['rosterEntryId'] for roster in roasters
                if f"{roster['lastName']}, {roster['firstName']} {roster['middleName']}".strip() == user.username and roster['displayBirthDate'] == user.birth_date),
                None
            )

            if not rosterEntryId:
                raise HTTPException(
                    status_code=404, detail="User not found in roasters.")
                
            roaster = next((roster for roster in roasters if roster['rosterEntryId'] == rosterEntryId), None)

            # Step 1d: Requesting PDF report (35%)
            yield f"data: {{'progress': 35, 'step': 'request_report', 'message': 'Requesting license report from FSMB...'}}\n\n"
            
            # FSMB API request
            URL = 'https://pdc-appapi.fsmb.org/download/practitioner/report'
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }
            data = {
                "rosterEntryIds": [rosterEntryId],
                "customerId": 7881,
            }

            response = requests.post(URL, headers=headers, json=data)
            response.raise_for_status()
            
            # Step 1e: Processing PDF data (45%)
            yield f"data: {{'progress': 45, 'step': 'process_pdf', 'message': 'Extracting license information from report...'}}\n\n"
            
            print(f"PDF Data Fetched... {response.status_code}")

            # Extract text from PDF bytes
            pdf_text = extract_text_from_pdf_bytes(response.content)
            
            yield f"data: {{'progress': 50, 'step': 'process_pdf', 'message': 'Processing license information...'}}\n\n"
            
            licenceData = create_sheet(pdf_text, user.birth_date)
            
            # Step 2: Processing Provider Data (60%)
            yield f"data: {{'progress': 60, 'step': 'process_data', 'message': 'Preparing provider information for CRM...'}}\n\n"
            
            provider = Provider(
                firstName=roaster["firstName"],
                lastName=roaster["lastName"],
                email=user.email,
                phoneNumber=user.phone,
                profession=licenceData["user_data"]["profession"],
                npi=licenceData["user_data"]["npi"],
                birthDate=licenceData["user_data"]["birthDate"],
            )
            
            # Step 3: Adding Provider to CRM (75%)
            yield f"data: {{'progress': 75, 'step': 'add_provider', 'message': 'Adding provider to CRM system...'}}\n\n"
            
            userId = add_provider(provider, authToken=user.crmToken)
            
            # Prepare license data (85%)
            yield f"data: {{'progress': 85, 'step': 'prepare_licenses', 'message': 'Preparing license data for upload...'}}\n\n"
            
            licenses = [
                Licenses(
                    state=licence["state_code"],
                    licenseNumber=licence["license_number"],
                    licenseType="Medical License",
                    issueDate=licence["issue_date"],
                    expirationDate=licence["expiration_date"],
                ) for licence in licenceData["licenses"]
            ]
            
            # Step 4: Uploading Licenses (95%)
            yield f"data: {{'progress': 95, 'step': 'upload_licenses', 'message': 'Uploading licenses to CRM...'}}\n\n"
            
            upload_licenses(userId, licenses, authToken=user.crmToken)
            
            # Process complete (100%)
            yield f"data: {{'progress': 100, 'step': 'complete', 'message': 'Process completed successfully!', 'userId': '{userId}'}}\n\n"

        except Exception as e:
            # Format error message for SSE, escaping single quotes
            error_message = str(e).replace("'", "\\'")
            yield f"data: {{'progress': 0, 'step': 'error', 'message': 'Error: {error_message}'}}\n\n"
        
    return StreamingResponse(
        progress_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    ENV = os.getenv("ENV", "prod")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=(ENV == "dev")
    )
