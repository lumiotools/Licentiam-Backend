from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import requests
import uvicorn
import json
import asyncio
import os
# Ensure pdc.py contains the function
from utils.pdc import login_and_get_token, extract_text_from_pdf_bytes
from llm import create_sheet
from pydantic import BaseModel
from typing import Optional
import openai


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
    fid: Optional[str] = None
    token: Optional[str] = None


@app.get("/get-token")
async def get_token():
    token = await asyncio.to_thread(login_and_get_token)
    return {"token": token}


@app.post("/get-pdf-data")
async def get_pdf_data(user: UserDetails):
    """Fetches the PDF data from FSMB API after login and extracts text."""
    if user.token:
        token = user.token
    else:
        token = await asyncio.to_thread(login_and_get_token)
    
    roasters = await get_roasters(token)

    if not roasters:
        raise HTTPException(
            status_code=401, detail="Failed to retrieve roasters.")

    # Find the user in the roasters list
    rosterEntryId = next(
        (roster['rosterEntryId'] for roster in roasters
         if roster['name'] == user.username and roster['displayBirthDate'] == user.birth_date),
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

        # Extract text from PDF bytes
        pdf_text = extract_text_from_pdf_bytes(response.content)

        res = create_sheet(pdf_text)

        return {'data': res,
                "token": token if not user.token else None}
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch PDF data: {e}")

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing PDF: {e}")


if __name__ == "__main__":
    ENV = os.getenv("ENV", "prod")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=(ENV == "dev")
    )
