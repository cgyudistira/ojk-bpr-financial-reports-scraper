import os
import re
import logging
from typing import Dict

import pandas as pd

from src import config
from src.database import Database

logger = logging.getLogger(__name__)


def clean_number(val) -> str:
    """Clean a number string from Indonesian formatting."""
    if pd.isna(val) or val is None:
        return ""
        
    val = str(val).strip().replace("\xa0", "").replace(" ", "")
    if val == "" or val.lower() in ["-", "0", "n/a", "null"]:
       return "0"
       
    # If it looks like a number (digits, dots, commas, minus)
    if re.match(r'^-?[\d.,]+$', val):
        return val
        
    return val


def determine_report_type_by_sheet(sheet_name: str) -> str:
    """Match Excel sheet name to OJK REPORT_TYPES keys."""
    sn_lower = str(sheet_name).lower()
    
    # We find the matching report name in the config
    for r_id, r_name in config.REPORT_TYPES.items():
        # Usually SSRS puts the title in the sheet name, sometimes truncated
        r_name_base = r_name.replace("Laporan ", "").lower()
        if r_name_base in sn_lower:
            return r_id
            
    # Fallbacks based on common heuristics
    if "posisi keuangan" in sn_lower or "neraca" in sn_lower:
        return "BPK-901-000001"
    elif "laba rugi" in sn_lower:
        return "BPK-901-000002"
    elif "kualitas aset" in sn_lower or "kap" in sn_lower:
        return "BPK-901-000003"
    elif "komitmen" in sn_lower:
        return "BPK-901-000004"
    elif "informasi lainnya" in sn_lower:
        return "BPK-901-000005"
        
    return None


def parse_excel_to_sqlite(file_path: str, db: Database, 
                          bulan: str, tahun: str, prov_code: str, 
                          city_code: str, bank_code: str) -> Dict[str, int]:
    """
    Reads the SSRS Excel export and saves valid data rows into SQLite.
    Returns a dict mapping report_id to the number of rows successfully parsed.
    """
    results = {rep_id: 0 for rep_id in config.REPORT_TYPES.keys()}
    
    if not os.path.exists(file_path):
        logger.error(f"Excel file not found: {file_path}")
        return results

    try:
        # Load the Excel file. SSRS often creates messy multi-sheet files
        xl = pd.ExcelFile(file_path)
    except Exception as e:
        logger.error(f"Failed to load Excel file (might be corrupted HTML format?): {e}")
        # Sometimes SSRS saves HTML tables with an .xls extension!
        try:
            # Fallback to HTML parsing via pandas
            tables = pd.read_html(file_path)
            # If there's only one table, it merged all reports
            logger.warning(f"Excel file {file_path} is actually an HTML file. Parsed {len(tables)} tables.")
            
            # Very basic fallback for HTML-based XLS: 
            # We treat the entire thing as Posisi Keuangan for now, 
            # or try to split it. SSRS puts titles in the rows.
            # Due to time constraints, this edge case requires careful handling of raw text.
            # Usually we hope it's a real Excel file!
            return _parse_html_fallback(tables, db, bulan, tahun, prov_code, city_code, bank_code, results)
        except Exception as html_err:
            logger.error(f"HTML fallback failed: {html_err}")
            return results

    for sheet_name in xl.sheet_names:
        report_id = determine_report_type_by_sheet(sheet_name)
        
        # If we can't determine it, we assume we skip it
        if not report_id:
            continue
            
        try:
            # Read the sheet, skipping meaningless SSRS padding rows at the very top.
            # We don't skip rows natively because SSRS formatting is unpredictable.
            df = xl.parse(sheet_name, header=None)
            
            structured_rows = []
            found_header = False
            
            pos_col = 0
            val1_col = 1
            val2_col = 2
            
            for idx, row in df.iterrows():
                # Convert row to list of strings, dropping pure NaNs
                cells = [str(x).replace('\\n', ' ').strip() for x in row if pd.notna(x)]
                if len(cells) < 2:
                    continue
                    
                joined = " ".join(cells).lower()
                
                # Detect the header row
                if not found_header:
                    if "pos" in joined and ("posisi" in joined or "tanggal" in joined):
                        found_header = True
                        
                        # Find exactly which indices contain the values in the sparse DataFrame row
                        valid_indices = [i for i, x in enumerate(row) if pd.notna(x) and str(x).strip()]
                        if len(valid_indices) >= 3:
                            pos_col = valid_indices[0]
                            val1_col = valid_indices[1]
                            val2_col = valid_indices[2]
                        elif len(valid_indices) >= 2:
                             # Laporan Informasi Lainnya often has different structure
                            pos_col = valid_indices[0]
                            val1_col = valid_indices[1]
                    continue
                    
                if not found_header:
                    continue
                
                # We are in the data section
                pos_text = str(row[pos_col]).strip() if pos_col < len(row) and pd.notna(row[pos_col]) else ""
                
                if not pos_text or pos_text.lower() in ("pos", "", "satuan rp."):
                    continue
                    
                val1 = str(row[val1_col]).strip() if val1_col < len(row) and pd.notna(row[val1_col]) else ""
                
                # Some reports (Laporan Informasi Lainnya) only have 2 logical columns 
                # (e.g. Nama Direktur vs Saham percentage). 
                val2 = ""
                if val2_col < len(row) and pd.notna(row[val2_col]):
                    val2 = str(row[val2_col]).strip()
                    
                val1 = clean_number(val1)
                val2 = clean_number(val2)
                
                structured_rows.append({
                    "pos": pos_text,
                    "nilai_periode": val1,
                    "nilai_tahun_sebelumnya": val2
                })
                
            if structured_rows:
                db.save_laporan_rows(
                    bulan, tahun, prov_code, city_code, bank_code, report_id, structured_rows
                )
                results[report_id] = len(structured_rows)
                
        except Exception as e:
            logger.error(f"Error parsing sheet '{sheet_name}' mapped to '{report_id}': {e}", exc_info=True)
            
    return results


def _parse_html_fallback(tables: list, db: Database, bulan: str, tahun: str, 
                         prov_code: str, city_code: str, bank_code: str, results: dict) -> dict:
    """Fallback parser if SSRS serves an HTML file disguised as .xls"""
    # Simply iterate through the largest tables and treat them as sequential outputs
    report_keys = list(config.REPORT_TYPES.keys())
    report_idx = 0
    
    # Sort tables by size (rows x cols) descending, assume the top 5 are our reports
    valid_tables = [t for t in tables if t.shape[0] > 5 and t.shape[1] > 1]
    
    # Heuristic: the UI outputs them in order if we selected them in order
    for t in valid_tables:
        if report_idx >= len(report_keys):
            break
            
        report_id = report_keys[report_idx]
        structured_rows = []
        
        for idx, row in t.iterrows():
            cells = [str(x) for x in row if pd.notna(x)]
            if len(cells) >= 2:
                # Naive assignment, HTML tables from SSRS are deeply nested
                # For a true production system, better HTML crawling is needed than pd.read_html
                pos = str(cells[0]).strip()
                val1 = clean_number(cells[-2]) if len(cells) > 2 else clean_number(cells[-1])
                val2 = clean_number(cells[-1]) if len(cells) > 2 else ""
                
                if pos and pos.lower() not in ('pos', 'satuan rp.'):
                    structured_rows.append({
                        "pos": pos,
                        "nilai_periode": val1,
                        "nilai_tahun_sebelumnya": val2
                    })
                    
        if len(structured_rows) > 5:
            db.save_laporan_rows(
                bulan, tahun, prov_code, city_code, bank_code, report_id, structured_rows
            )
            results[report_id] = len(structured_rows)
            report_idx += 1
            
    return results
