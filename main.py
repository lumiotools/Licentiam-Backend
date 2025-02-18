from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import requests
import uvicorn
import json
import asyncio
import os
from utils.pdc import login_and_get_token  # Ensure pdc.py contains the function
from pydantic import BaseModel
from typing import Optional
from io import BytesIO
from fastapi.responses import StreamingResponse


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


@app.post("/get-pdf-data")
async def get_pdf_data(user: UserDetails):
    """Fetches the PDF data from FSMB API after login and returns it as a file."""
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

        # Return PDF as a response
        return StreamingResponse(BytesIO(response.content), media_type="application/pdf",
                                 headers={"Content-Disposition": "attachment; filename=report.pdf"})

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch PDF data: {e}")


if __name__ == "__main__":
    ENV = os.getenv("ENV", "prod")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=(ENV == "dev")
    )
