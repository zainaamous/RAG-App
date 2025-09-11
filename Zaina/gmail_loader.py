import os, pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from langchain_core.documents import Document
import base64
from email import message_from_bytes

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('gmail', 'v1', credentials=creds)
    return service

def fetch_emails(service, max_results=5):
    results = service.users().messages().list(userId='me', maxResults=max_results).execute()
    messages = results.get('messages', [])
    docs = []
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
        subject = headers.get('Subject', '')
        sender = headers.get('From', '')
        date = headers.get('Date', '')
        snippet = msg_data.get('snippet', '')
        body = ''
        # Try to get the plain text body
        if 'parts' in msg_data['payload']:
            for part in msg_data['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                    break
        else:
            if 'body' in msg_data['payload'] and 'data' in msg_data['payload']['body']:
                body = base64.urlsafe_b64decode(msg_data['payload']['body']['data']).decode('utf-8', errors='ignore')
        content = f"Subject: {subject}\nFrom: {sender}\nDate: {date}\n\n{body or snippet}"
        doc = Document(
            page_content=content,
            metadata={
                "doc_uid": msg['id'],
                "subject": subject,
                "from": sender,
                "date": date,
                "source": "gmail"
            }
        )
        docs.append(doc)
    return docs