import csv
import pandas as pd

def load_and_repair_source1(filepath: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Source 1: Naukri Applicants
    Known issues: None structurally confirmed that break parsing, 
    but we will check for empty rows.
    """
    issues = []
    clean_rows = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        for i, row in enumerate(reader, start=2):
            if all(cell.strip() == '' for cell in row):
                issues.append(f"Source 1, Row {i}: EMPTY ROW — dropped")
                continue
            
            clean_rows.append(row)
            
    df = pd.DataFrame(clean_rows, columns=header)
    return df, issues

def load_and_repair_source2(filepath: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Source 2: Gig Workers
    Known issues: 
    - Empty row
    - Column shifted row (skills in email column)
    """
    issues = []
    clean_rows = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        for i, row in enumerate(reader, start=2):
            if all(cell.strip() == '' for cell in row):
                issues.append(f"Source 2, Row {i}: EMPTY ROW — dropped")
                continue
                
            # Heuristic for shifted row: email is col 0, but if it has commas and no @, it's skills
            # row format should be: email_id, worker_name, rate, location, status, skill_tags
            if len(row) > 0 and ',' in row[0] and '@' not in row[0]:
                issues.append(f"Source 2, Row {i}: COLUMN SHIFT DETECTED — realigning")
                # Rotate left by 1
                row = row[1:] + [row[0]]
                
            clean_rows.append(row)
            
    df = pd.DataFrame(clean_rows, columns=header)
    return df, issues

def load_and_repair_source3(filepath: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Source 3: CBNexus Contacts
    Known issues: 
    - Repeated header row injected
    """
    issues = []
    clean_rows = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        for i, row in enumerate(reader, start=2):
            if all(cell.strip() == '' for cell in row):
                issues.append(f"Source 3, Row {i}: EMPTY ROW — dropped")
                continue
                
            if [c.strip() for c in row] == [c.strip() for c in header]:
                issues.append(f"Source 3, Row {i}: REPEATED HEADER — dropped")
                continue
                
            clean_rows.append(row)
            
    df = pd.DataFrame(clean_rows, columns=header)
    return df, issues
