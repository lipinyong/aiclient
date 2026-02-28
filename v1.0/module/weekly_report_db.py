import sqlite3
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "weekly_reports.db"


def get_connection():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weekly_report_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            week_number INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            summary TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, week_number)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_year_week 
        ON weekly_report_summary(year, week_number)
    """)
    conn.commit()
    conn.close()


def save_weekly_summary(year: int, week_number: int, start_date: str, 
                        end_date: str, summary: str) -> Dict[str, Any]:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO weekly_report_summary (year, week_number, start_date, end_date, summary, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(year, week_number) DO UPDATE SET
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                summary = excluded.summary,
                updated_at = excluded.updated_at
        """, (year, week_number, start_date, end_date, summary, datetime.now().isoformat()))
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        return {"success": True, "id": row_id, "message": f"周报摘要已保存: {year}年第{week_number}周"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_weekly_summary(year: int, week_number: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM weekly_report_summary 
        WHERE year = ? AND week_number = ?
    """, (year, week_number))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_summaries_by_year(year: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM weekly_report_summary 
        WHERE year = ? 
        ORDER BY week_number
    """, (year,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_summaries() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM weekly_report_summary 
        ORDER BY year DESC, week_number DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_weekly_summary(year: int, week_number: int) -> Dict[str, Any]:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM weekly_report_summary 
            WHERE year = ? AND week_number = ?
        """, (year, week_number))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        if affected > 0:
            return {"success": True, "message": f"已删除: {year}年第{week_number}周"}
        return {"success": False, "message": "记录不存在"}
    except Exception as e:
        return {"success": False, "error": str(e)}


init_db()
