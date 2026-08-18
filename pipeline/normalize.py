import re
from datetime import datetime
from dateutil import parser
import pandas as pd

def normalize_phone(phone: str) -> str:
    """Extracts only digits. Keeps the last 10 digits if more exist."""
    if pd.isna(phone) or not phone:
        return None
    # Remove all non-digits
    digits = re.sub(r'\D', '', str(phone))
    if len(digits) >= 10:
        return digits[-10:]
    return None

def normalize_email(email: str) -> str:
    """Lowercases, trims, and removes prefixes like 'alt.'"""
    if pd.isna(email) or not str(email).strip():
        return None
    e = str(email).strip().lower()
    if e.startswith('alt.'):
        e = e[4:]
    return e

def normalize_city(city: str) -> str:
    """Standardizes city synonyms to a canonical name."""
    if pd.isna(city) or not str(city).strip():
        return None
    c = str(city).strip().lower()
    
    mapping = {
        'gurgaon': 'gurugram',
        'bengaluru': 'bangalore',
        'blore': 'bangalore',
        'bombay': 'mumbai',
        'calcutta': 'kolkata'
    }
    
    return mapping.get(c, c).title()

def normalize_ctc(ctc_value) -> float:
    """Converts LPA floats (e.g. 4.2) and absolute numbers into float INR."""
    if pd.isna(ctc_value) or str(ctc_value).strip() == '':
        return None
    
    try:
        val = float(str(ctc_value).replace(',', '').strip())
        if val == 0:
            return None
            
        # Heuristic: if it's < 200, assume it's in Lakhs (LPA)
        if val < 200:
            return val * 100000.0
        return float(val)
    except ValueError:
        return None

def normalize_rate(rate_value) -> float:
    """Extracts rate and standardizes to hourly INR float."""
    if pd.isna(rate_value) or str(rate_value).strip() == '':
        return None
        
    s = str(rate_value).lower().strip()
    
    # Check if k/month
    if 'k/month' in s:
        num = re.sub(r'[^\d.]', '', s)
        try:
            monthly = float(num) * 1000
            # standard 160 hrs/month
            return round(monthly / 160.0, 2)
        except ValueError:
            return None
            
    # Check if /hr
    if '/hr' in s:
        num = re.sub(r'[^\d.]', '', s)
        try:
            return float(num)
        except ValueError:
            return None
            
    # Default numeric fallback
    num = re.sub(r'[^\d.]', '', s)
    try:
        return float(num) if num else None
    except ValueError:
        return None

def normalize_verified(val) -> int:
    """Standardizes boolean string into 1 or 0."""
    if pd.isna(val) or str(val).strip() == '':
        return None
        
    s = str(val).strip().lower()
    if s in ('y', 'yes', 'true', '1'):
        return 1
    if s in ('n', 'no', 'false', '0'):
        return 0
    return None

def normalize_date(date_string) -> str:
    """Standardizes dates into ISO YYYY-MM-DD format."""
    if pd.isna(date_string) or str(date_string).strip() == '':
        return None
        
    try:
        # dateutil parser is very robust for "7 Jul 2026", "2026/07/07", etc.
        d = parser.parse(str(date_string).strip())
        return d.strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return None

def normalize_skills(skills_val) -> list[str]:
    """Splits skills by comma or pipe, strips whitespace, lowercases/titles correctly."""
    if pd.isna(skills_val) or not str(skills_val).strip():
        return []
        
    s = str(skills_val)
    # Split by comma or pipe
    tokens = re.split(r'[,|]', s)
    
    cleaned = []
    for token in tokens:
        t = token.strip()
        if not t:
            continue
        # Optional: standardize casing. E.g. "python" -> "Python"
        # We can just use standard Title case except for specific ones like n8n or MySQL
        if t.lower() == 'n8n':
            cleaned.append('n8n')
        elif t.lower() == 'mysql':
            cleaned.append('MySQL')
        elif t.lower() == 'javascript':
            cleaned.append('JavaScript')
        else:
            cleaned.append(t.title())
            
    # Deduplicate while preserving order
    return list(dict.fromkeys(cleaned))

def normalize_status(status_val) -> str:
    """Standardizes gig status to 'Active', 'Inactive', 'Paused'."""
    if pd.isna(status_val) or not str(status_val).strip():
        return None
        
    s = str(status_val).strip().lower()
    if s == 'active':
        return 'Active'
    if s == 'inactive':
        return 'Inactive'
    if s == 'paused':
        return 'Paused'
        
    return None
