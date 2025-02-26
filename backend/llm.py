from openai import OpenAI
from pydantic import BaseModel
from typing import List, Optional
import json
from dateutil import parser
from datetime import timezone
from dotenv import load_dotenv
load_dotenv()

def parse_to_iso8601(date_str):
    try:
        # Parse the date string into a datetime object
        dt = parser.parse(date_str)
        # Convert to UTC and format as ISO 8601 string
        return dt.isoformat()
    except (ValueError, OverflowError) as e:
        return None

class Row(BaseModel):
    state: str
    state_code: str
    license_number: str
    issue_date: str
    expiration_date: str


class UserData(BaseModel):
    firstName: str
    lastName: Optional[str] = None
    npi: str
    email: Optional[str]
    profession: str
    group: str


class Response(BaseModel):
    user_data: UserData
    licenses: List[Row]


PROMPT_TEMPLATE = """
You are provided with data extracted from a PDF related to a single individual. Your task is to parse the data and structure it into the following JSON format using the given Pydantic models.

The data includes:

1. **User Information**:
   - **Name**: Full name of the individual.
   - **NPI**: National Provider Identifier.
   - **Email** (optional): Contact email.
   - **Profession**: Professional designation (e.g., MD, DO).
   - **Group**: Affiliated organization or health group.

2. **Licensing Information**:
   - **State**: State where the license is issued.
   - **License Number**: Unique license number.
   - **Issue Date**: Date when the license was issued.
   - **Expiration Date**: License expiration date.

### Expected JSON Output:

```json
{
  "user_data": {
    "name": "Kristie Miller",
    "npi": "1831480821",
    "email": "KristieMiller@beluga.com",
    "profession": "MD",
    "group": "Beluga Health"
  },
  "rows": [
    {
      "state": "ALABAMA",
      "license_number": "MD.50214",
      "issue_date": "12-05-2024",
      "expiration_date": "12-31-2024"
    }
  ]
}
```

**Notes:**
- Email is optional and can be null if not provided.
- Dates should maintain the format `MM-DD-YYYY`.
- Only one individual's data is provided per extraction.
- The `rows` list should support multiple licenses if they exist in the data.
"""

client = OpenAI()


def create_sheet(context: str, birthDate: str):

    messages = [
        {'role': "system", 'content': PROMPT_TEMPLATE},
        {'role': "user", 'content': context}
    ]

    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=messages,
        response_format=Response,
        temperature=0.0,
    )

    response_data = completion.choices[0].message.parsed
    
    with open("constants/professions.json", "r") as file:
        professions = json.load(file)
        for profession in professions:
            if  response_data.user_data.profession == profession["abbrev"]:
                response_data.user_data.profession = profession["id"]
                break
    
    for license in response_data.licenses:
        license.issue_date = parse_to_iso8601(license.issue_date)
        license.expiration_date = parse_to_iso8601(license.expiration_date)

    response_data = response_data.model_dump()
    
    response_data["user_data"]["birthDate"] = parse_to_iso8601(birthDate)
    return response_data
