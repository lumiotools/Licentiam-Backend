import requests
from pydantic import BaseModel
from typing import List, Optional
import os
import re
import imaplib
import time
import email
from email.header import decode_header
from dotenv import load_dotenv
load_dotenv()


class Provider(BaseModel):
    firstName: str
    lastName: Optional[str] = None
    email: str
    phoneNumber: str
    profession: str
    npi: str
    birthDate: Optional[str] = None


class Licenses(BaseModel):
    expirationDate: Optional[str]
    issueDate: Optional[str]
    licenseNumber: str
    licenseType: str
    state: str


def get_crm_auth_token():
    print("Logging in to CRM...")
    loginResponse = requests.post("https://api.licentiam.com/api/admin/auth/login", json={
        "data": {
            "email": os.getenv("CRM_EMAIL"),
            "password": os.getenv("CRM_PASSWORD")
        }
    })

    device_token = loginResponse.json(
    )["errors"][0]["metadata"]["device_token"]

    print("Sending OTP request...")

    requests.post("https://api.licentiam.com/api/admin/verification/code", json={
        "data": {
            "type": "email",
        }
    },
        headers={
        "Devicetoken": f"Bearer {device_token}"
    })

    OTP = None

    while OTP is None:
        print("Waiting for OTP...")
        time.sleep(5)
        OTP = get_crm_mail_otp()

    deviceResponse = requests.post("https://api.licentiam.com/api/admin/verification/device", json={
        "data": {
            "verification_code": OTP
        }
    },
        headers={
        "Devicetoken": f"Bearer {device_token}"
    })

    authToken = deviceResponse.json()["data"]["auth_token"]

    print(authToken)

    return authToken


def get_crm_mail_otp():
    OTP = None
    # Connect to the Gmail IMAP server
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(os.getenv("CRM_EMAIL"), os.getenv("CRM_APP_PASSWORD"))

    # Select the mailbox you want to monitor (e.g., 'inbox')
    mail.select("inbox")

    # Search for all unread emails
    status, messages = mail.search(None, 'UNSEEN')

    # Convert messages to a list of email IDs
    email_ids = messages[0].split()

    # Process each email
    for email_id in email_ids:
        # Fetch the email by ID
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                # Parse the email content
                msg = email.message_from_bytes(response_part[1])
                # Decode the email subject
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
                # Decode the sender's email address
                from_ = msg.get("From")

                print("Found Mail:", subject, from_)
                print("="*50)

                if subject != "Your Licentiam verification code." or from_ != "Licentiam <contact@licentiam.com>":
                    break

                # Extract email body
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(
                            part.get("Content-Disposition"))
                        if content_type == "text/plain" and "attachment" not in content_disposition:
                            body = part.get_payload(decode=True).decode()
                            break
                else:
                    body = msg.get_payload(decode=True).decode()

                # Extract OTP using regex (Assuming it's a 6-digit code)
                otp_match = re.search(r'\b\d{6}\b', body)
                OTP = otp_match.group()

                if OTP:
                    print("Found OTP:", OTP)

    # Close the connection and logout
    mail.close()
    mail.logout()

    return OTP


if __name__ == "__main__":
    get_crm_auth_token()


def add_provider(provider: Provider, authToken: str):
    if not authToken:
        authToken = get_crm_auth_token()

    # GraphQL mutation payload
    payload = {
        "operationName": "AddUser",
        "variables": {
            "data": {
                "firstName": provider.firstName,
                "lastName": provider.lastName,
                "email": provider.email,
                "phoneNumber": f"({provider.phoneNumber[0:3]}) {provider.phoneNumber[3:6]} - {provider.phoneNumber[6:]}"
            }
        },
        "query": """
        mutation AddUser($data: User_CreateAttributes!) {
          addUser(data: $data) {
            user {
              ...UserAttributes
              uncategorizedDocumentsCount
              inProgressApplicationsCount
              documentRequestsCount
              admin {
                ...AdminAttributes
                __typename
              }
              __typename
            }
            __typename
          }
        }

        fragment UserAttributes on User {
          id
          email
          firstName
          middleName
          lastName
          phoneNumber
          phoneExtension
          groupName
          professionalType
          billingPlan
          subscriptionPlan
          adminId
          superAdminId
          archived
          portalAccessEnabled
          __typename
        }

        fragment AdminAttributes on Admin {
          id
          email
          phoneNumber
          adminType
          firstName
          lastName
          archived
          token
          users {
            ...UserAttributes
            __typename
          }
          tasks {
            ...TaskAttributes
            __typename
          }
          __typename
        }

        fragment TaskAttributes on Task {
          id
          adminId
          title
          description
          completed
          completedAt
          __typename
        }
        """
    }

    headers = {
        "Authorization": f"Bearer {authToken}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://api.licentiam.com/api/admin/graphql", json=payload, headers=headers)

    response.raise_for_status()
    
    try:
      userId = response.json()["data"]["addUser"]["user"]["id"]
      print("Provider added successfully!")
    except:
      print("Error adding provider!")
      print("Error:", response.json()["errors"][0]["message"])
      raise Exception(response.json()["errors"][0]["message"])

    requests.post("https://api.licentiam.com/api/admin/graphql", json={
        "operationName": "UpdateUserProfile",
        "variables": {
            "userId": userId,
            "data": {
                "firstName": provider.firstName,
                "lastName": provider.lastName,
                "middleName": None,
                "professionalType": provider.profession,
                "npiNumber": provider.npi,
                "ssn": None,
                "specialty": None,
                "subSpecialty": None,
                "legacySpecialty": None,
                "gender": None,
                "address": None,
                "addressCity": None,
                "addressState": None,
                "addressZip": None,
                "birthDate": provider.birthDate,
                "birthPlace": None,
                "birthCertDocumentId": None,
                "driversLicenseDocumentId": None,
                "driversLicenseExpirationDate": None,
                "driversLicenseNumber": None,
                "driversLicenseState": None,
                "passportPhotoId": None,
                "passportDocumentId": None,
                "passportExpirationDate": None,
                "resumeDocumentId": None,
                "authAndReleaseDocumentId": None,
                "weight": None,
                "height": None,
                "eyeColor": None,
                "hairColor": None,
                "ethnicity": None,
                "usCitizen": None,
                "citizenship": None,
                "visaNumber": None,
                "greenCardNumber": None,
                "memberOfMilitary": None,
                "currentActiveDuty": None,
                "highSchoolName": None,
                "highSchoolLocation": None,
                "highSchoolGraduationDate": None,
                "manager": None,
                "otherPhoneNumbers": [],
                "otherEmails": [],
                "practiceAddresses": []
            }
        },
        "query": "mutation UpdateUserProfile($documentData: [Document_CreateAttributes!], $removeDocuments: JSON, $data: UserProfile_UpdateAttributes, $userId: ID!) {\n  updateUserProfile(\n    documentData: $documentData\n    removeDocuments: $removeDocuments\n    data: $data\n    userId: $userId\n  ) {\n    userProfile {\n      ...UserProfileAttributes\n      authAndReleaseDocument {\n        ...DocumentAttributes\n        __typename\n      }\n      birthCertDocument {\n        ...DocumentAttributes\n        __typename\n      }\n      driversLicenseDocument {\n        ...DocumentAttributes\n        __typename\n      }\n      passportPhoto {\n        ...DocumentAttributes\n        __typename\n      }\n      passportDocument {\n        ...DocumentAttributes\n        __typename\n      }\n      resumeDocument {\n        ...DocumentAttributes\n        __typename\n      }\n      __typename\n    }\n    user {\n      ...UserAttributes\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment UserProfileAttributes on UserProfile {\n  id\n  userId\n  npiNumber\n  ssn\n  specialty\n  subSpecialty\n  legacySpecialty\n  gender\n  address\n  addressCity\n  addressState\n  addressZip\n  birthDate\n  birthPlace\n  birthCertDocumentId\n  driversLicenseDocumentId\n  driversLicenseExpirationDate\n  driversLicenseNumber\n  driversLicenseState\n  passportPhotoId\n  passportDocumentId\n  passportExpirationDate\n  resumeDocumentId\n  authAndReleaseDocumentId\n  weight\n  height\n  eyeColor\n  hairColor\n  ethnicity\n  usCitizen\n  citizenship\n  visaNumber\n  greenCardNumber\n  memberOfMilitary\n  currentActiveDuty\n  highSchoolName\n  highSchoolLocation\n  highSchoolGraduationDate\n  manager\n  createdAt\n  otherPhoneNumbers {\n    id\n    phone\n    extension\n    __typename\n  }\n  otherEmails {\n    id\n    email\n    __typename\n  }\n  practiceAddresses {\n    id\n    address\n    addressType\n    city\n    state\n    zip\n    __typename\n  }\n  __typename\n}\n\nfragment UserAttributes on User {\n  id\n  email\n  firstName\n  middleName\n  lastName\n  phoneNumber\n  phoneExtension\n  groupName\n  professionalType\n  billingPlan\n  subscriptionPlan\n  adminId\n  superAdminId\n  archived\n  portalAccessEnabled\n  __typename\n}\n\nfragment DocumentAttributes on Document {\n  id\n  key\n  size\n  fileName\n  fileType\n  category\n  categoryGroup\n  archived\n  customCategoryId\n  resourceId\n  createdAt\n  notificationSentAt\n  metadata\n  __typename\n}\n"
    },
        headers={"Authorization": f"Bearer {authToken}",
                 "Content-Type": "application/json"
                 })

    return userId


def upload_licenses(userId: str, licenses: List[Licenses], authToken: str):

    if not authToken:
        authToken = get_crm_auth_token()

    response = requests.post("https://api.licentiam.com/api/admin/graphql", json={
        "operationName": "BatchCreateLicenses",
        "variables": {
            "userId": userId,
            "data": [
                {
                    "state": license.state,
                    "licenseNumber": license.licenseNumber,
                    "licenseType": license.licenseType,
                    "issueDate": license.issueDate,
                    "expirationDate": license.expirationDate,
                } for license in licenses
            ]
        },
        "query": "mutation BatchCreateLicenses($data: [License_CreateAttributes!]!, $userId: ID!) {\n  batchCreateLicenses(data: $data, userId: $userId) {\n    success\n    licenses {\n      ...LicenseAttributes\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment LicenseAttributes on License {\n  id\n  userId\n  documentId\n  status\n  stage\n  legacyLicenseType\n  licenseType\n  licenseSubtype\n  licenseNumber\n  state\n  issueDate\n  expirationDate\n  currentlyUtilized\n  subscriptionPlan\n  prescriber\n  archived\n  createdAt\n  __typename\n}\n"
    },
        headers={"Authorization": f"Bearer {authToken}",
                 "Content-Type": "application/json"
                 })

    response.raise_for_status()

    return True
