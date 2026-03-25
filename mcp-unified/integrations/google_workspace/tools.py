"""
MCP Tools for Google Workspace Integration.

Provides tools for Gmail, Calendar, People (Contacts), and Sheets.
"""

import json
import base64
from email.mime.text import MIMEText
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import Context

from .client import get_google_client


async def gmail_list_messages(
    ctx: Context,
    query: Optional[str] = None,
    max_results: int = 10
) -> str:
    """
    List Gmail messages based on a query.
    
    Args:
        query: Gmail search query (e.g. 'from:someone@example.com', 'is:unread')
        max_results: Maximum number of messages to return (default: 10)
    """
    try:
        client = get_google_client()
        gmail = client.gmail
        
        results = gmail.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get("messages", [])
        
        # Hydrate messages with basic info (Snippet)
        hydrated_messages = []
        for msg in messages:
            msg_detail = gmail.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()
            
            headers = msg_detail.get("payload", {}).get("headers", [])
            header_dict = {h["name"]: h["value"] for h in headers}
            
            hydrated_messages.append({
                "id": msg["id"],
                "threadId": msg["threadId"],
                "snippet": msg_detail.get("snippet", ""),
                "from": header_dict.get("From", ""),
                "subject": header_dict.get("Subject", ""),
                "date": header_dict.get("Date", "")
            })
            
        return json.dumps({
            "success": True,
            "messages": hydrated_messages
        }, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def gmail_send_message(
    ctx: Context,
    to: str,
    subject: str,
    body: str
) -> str:
    """
    Send an email via Gmail.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Plain text body of the email
    """
    try:
        client = get_google_client()
        gmail = client.gmail
        
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        
        sent_message = gmail.users().messages().send(
            userId="me",
            body={"raw": raw_message}
        ).execute()
        
        return json.dumps({
            "success": True,
            "message_id": sent_message["id"],
            "status": "sent"
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def calendar_list_events(
    ctx: Context,
    calendar_id: str = "primary",
    time_min: Optional[str] = None,
    max_results: int = 10
) -> str:
    """
    List events from a Google Calendar.
    
    Args:
        calendar_id: Calendar ID (default: 'primary')
        time_min: Start time in ISO format (e.g. '2026-03-12T00:00:00Z')
        max_results: Maximum events to return
    """
    try:
        client = get_google_client()
        calendar = client.calendar
        
        results = calendar.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        
        events = results.get("items", [])
        
        simplified_events = []
        for event in events:
            simplified_events.append({
                "id": event["id"],
                "summary": event.get("summary", "No Title"),
                "start": event.get("start", {}).get("dateTime", event.get("start", {}).get("date")),
                "end": event.get("end", {}).get("dateTime", event.get("end", {}).get("date")),
                "status": event.get("status"),
                "htmlLink": event.get("htmlLink")
            })
            
        return json.dumps({
            "success": True,
            "events": simplified_events
        }, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def people_list_contacts(
    ctx: Context,
    page_size: int = 20
) -> str:
    """
    List contacts from Google People API.
    """
    try:
        client = get_google_client()
        people = client.people
        
        results = people.people().connections().list(
            resourceName="people/me",
            pageSize=page_size,
            personFields="names,emailAddresses,phoneNumbers"
        ).execute()
        
        connections = results.get("connections", [])
        
        simplified_contacts = []
        for person in connections:
            names = person.get("names", [])
            display_name = names[0].get("displayName") if names else "Unknown"
            
            emails = [e.get("value") for e in person.get("emailAddresses", [])]
            phones = [p.get("value") for p in person.get("phoneNumbers", [])]
            
            simplified_contacts.append({
                "resourceName": person.get("resourceName"),
                "name": display_name,
                "emails": emails,
                "phones": phones
            })
            
        return json.dumps({
            "success": True,
            "contacts": simplified_contacts
        }, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def people_search_contacts(
    ctx: Context,
    query: str
) -> str:
    """
    Search contacts from Google People API by name, email, or phone.
    
    Args:
        query: Search string
    """
    try:
        client = get_google_client()
        people = client.people
        
        results = people.people().searchContacts(
            query=query,
            readMask="names,emailAddresses,phoneNumbers"
        ).execute()
        
        results_list = results.get("results", [])
        
        simplified_contacts = []
        for result in results_list:
            person = result.get("person", {})
            names = person.get("names", [])
            display_name = names[0].get("displayName") if names else "Unknown"
            
            emails = [e.get("value") for e in person.get("emailAddresses", [])]
            phones = [p.get("value") for p in person.get("phoneNumbers", [])]
            
            simplified_contacts.append({
                "resourceName": person.get("resourceName"),
                "name": display_name,
                "emails": emails,
                "phones": phones
            })
            
        return json.dumps({
            "success": True,
            "query": query,
            "contacts": simplified_contacts
        }, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def sheets_read_values(
    ctx: Context,
    spreadsheet_id: str,
    range_name: str
) -> str:
    """
    Read values from a Google Sheet.
    
    Args:
        spreadsheet_id: ID of the spreadsheet
        range_name: Range in A1 notation (e.g. 'Sheet1!A1:D10')
    """
    try:
        client = get_google_client()
        sheets = client.sheets
        
        result = sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get("values", [])
        
        return json.dumps({
            "success": True,
            "values": values
        }, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
