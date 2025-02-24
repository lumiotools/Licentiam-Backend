from openai import OpenAI
from pydantic import BaseModel
from typing import List, Optional


class Row(BaseModel):
    state: str
    license_number: str
    issue_date: str
    expiration_date: str


class UserData(BaseModel):
    name: str
    npi: str
    email: Optional[str]
    profession: str
    group: str


class Response(BaseModel):
    user_data: UserData
    rows: List[Row]


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


def create_sheet(context: str):

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
    
    response_text = completion.choices[0].message.parsed

    return response_text
