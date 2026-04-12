"""
SQLite database manager for OJK BPR Konvensional Scraper.

Handles schema creation, metadata storage, data insertion,
and progress tracking for resume capability.
"""
import logging
import os
import sqlite3
from typing import Optional

from src import config

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: str = config.DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """Open database connection and create schema if needed."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_schema()
        logger.info(f"Database connected: {self.db_path}")

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Database closed.")

    def _create_schema(self):
        """Create all tables if they don't exist."""
        self.conn.executescript("""
            -- Reference: bulan (month options)
            CREATE TABLE IF NOT EXISTS bulan (
                value TEXT PRIMARY KEY,
                nama TEXT NOT NULL
            );

            -- Reference: tahun (year options)
            CREATE TABLE IF NOT EXISTS tahun (
                value TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS provinsi (
                code TEXT PRIMARY KEY,
                nama TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS kabupaten (
                code TEXT PRIMARY KEY,
                nama TEXT NOT NULL,
                provinsi_code TEXT NOT NULL,
                FOREIGN KEY (provinsi_code) REFERENCES provinsi(code)
            );

            CREATE TABLE IF NOT EXISTS bank (
                code TEXT PRIMARY KEY,
                nama TEXT NOT NULL,
                kabupaten_code TEXT NOT NULL,
                provinsi_code TEXT NOT NULL,
                FOREIGN KEY (kabupaten_code) REFERENCES kabupaten(code),
                FOREIGN KEY (provinsi_code) REFERENCES provinsi(code)
            );

            CREATE TABLE IF NOT EXISTS jenis_laporan (
                code TEXT PRIMARY KEY,
                nama TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS laporan_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                periode_bulan TEXT NOT NULL,
                periode_tahun TEXT NOT NULL,
                provinsi_code TEXT NOT NULL,
                kabupaten_code TEXT NOT NULL,
                bank_code TEXT NOT NULL,
                jenis_laporan_code TEXT NOT NULL,
                pos TEXT NOT NULL,
                nilai_periode TEXT,
                nilai_tahun_sebelumnya TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (provinsi_code) REFERENCES provinsi(code),
                FOREIGN KEY (kabupaten_code) REFERENCES kabupaten(code),
                FOREIGN KEY (bank_code) REFERENCES bank(code),
                FOREIGN KEY (jenis_laporan_code) REFERENCES jenis_laporan(code),
                UNIQUE(periode_bulan, periode_tahun, provinsi_code,
                       kabupaten_code, bank_code, jenis_laporan_code, pos)
            );

            -- Laporan 3: Kualitas Aset Produktif (6 value columns by collectibility)
            CREATE TABLE IF NOT EXISTS laporan_kualitas_aset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                periode_bulan TEXT NOT NULL,
                periode_tahun TEXT NOT NULL,
                provinsi_code TEXT NOT NULL,
                kabupaten_code TEXT NOT NULL,
                bank_code TEXT NOT NULL,
                pos TEXT NOT NULL,
                nilai_l TEXT,
                nilai_dpk TEXT,
                nilai_kl TEXT,
                nilai_d TEXT,
                nilai_m TEXT,
                nilai_jumlah TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (provinsi_code) REFERENCES provinsi(code),
                FOREIGN KEY (kabupaten_code) REFERENCES kabupaten(code),
                FOREIGN KEY (bank_code) REFERENCES bank(code),
                UNIQUE(periode_bulan, periode_tahun, provinsi_code,
                       kabupaten_code, bank_code, pos)
            );

            CREATE TABLE IF NOT EXISTS scrape_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                periode_bulan TEXT NOT NULL,
                periode_tahun TEXT NOT NULL,
                provinsi_code TEXT NOT NULL,
                kabupaten_code TEXT NOT NULL,
                bank_code TEXT NOT NULL,
                jenis_laporan_code TEXT NOT NULL,
                status TEXT DEFAULT 'done',
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(periode_bulan, periode_tahun, provinsi_code,
                       kabupaten_code, bank_code, jenis_laporan_code)
            );

            CREATE INDEX IF NOT EXISTS idx_laporan_periode
                ON laporan_data(periode_bulan, periode_tahun);
            CREATE INDEX IF NOT EXISTS idx_laporan_bank
                ON laporan_data(bank_code);
            CREATE INDEX IF NOT EXISTS idx_laporan_jenis
                ON laporan_data(jenis_laporan_code);
            CREATE INDEX IF NOT EXISTS idx_kualitas_aset_bank
                ON laporan_kualitas_aset(bank_code);
            CREATE INDEX IF NOT EXISTS idx_kualitas_aset_periode
                ON laporan_kualitas_aset(periode_bulan, periode_tahun);
            CREATE INDEX IF NOT EXISTS idx_progress_lookup
                ON scrape_progress(periode_bulan, periode_tahun,
                    provinsi_code, kabupaten_code, bank_code, jenis_laporan_code);
        """)
        self.conn.commit()
        logger.debug("Database schema verified.")

    # ── Metadata Insertion ──────────────────────────────────
    def save_bulan(self, value: str, nama: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO bulan (value, nama) VALUES (?, ?)",
            (value, nama)
        )
        self.conn.commit()

    def save_tahun(self, value: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO tahun (value) VALUES (?)",
            (value,)
        )
        self.conn.commit()

    def save_provinsi(self, code: str, nama: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO provinsi (code, nama) VALUES (?, ?)",
            (code, nama)
        )
        self.conn.commit()

    def save_kabupaten(self, code: str, nama: str, provinsi_code: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO kabupaten (code, nama, provinsi_code) VALUES (?, ?, ?)",
            (code, nama, provinsi_code)
        )
        self.conn.commit()

    def save_bank(self, code: str, nama: str, kabupaten_code: str, provinsi_code: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO bank (code, nama, kabupaten_code, provinsi_code) VALUES (?, ?, ?, ?)",
            (code, nama, kabupaten_code, provinsi_code)
        )
        self.conn.commit()

    def save_kualitas_aset_rows(
        self,
        periode_bulan: str,
        periode_tahun: str,
        provinsi_code: str,
        kabupaten_code: str,
        bank_code: str,
        rows: list[dict],
    ):
        """
        Batch insert Laporan Kualitas Aset rows.
        Each row dict has keys: 'pos', 'nilai_l', 'nilai_dpk', 'nilai_kl',
        'nilai_d', 'nilai_m', 'nilai_jumlah'
        """
        if not rows:
            return
        self.conn.executemany(
            """INSERT OR REPLACE INTO laporan_kualitas_aset
               (periode_bulan, periode_tahun, provinsi_code, kabupaten_code,
                bank_code, pos, nilai_l, nilai_dpk, nilai_kl, nilai_d, nilai_m, nilai_jumlah)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    periode_bulan, periode_tahun, provinsi_code, kabupaten_code,
                    bank_code,
                    r.get("pos", ""),
                    r.get("nilai_l", ""),
                    r.get("nilai_dpk", ""),
                    r.get("nilai_kl", ""),
                    r.get("nilai_d", ""),
                    r.get("nilai_m", ""),
                    r.get("nilai_jumlah", ""),
                )
                for r in rows
            ],
        )
        self.conn.commit()

    def save_jenis_laporan(self, code: str, nama: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO jenis_laporan (code, nama) VALUES (?, ?)",
            (code, nama)
        )
        self.conn.commit()

    # ── Data Insertion ──────────────────────────────────────
    def save_laporan_rows(
        self,
        periode_bulan: str,
        periode_tahun: str,
        provinsi_code: str,
        kabupaten_code: str,
        bank_code: str,
        jenis_laporan_code: str,
        rows: list[dict],
    ):
        """
        Batch insert laporan data rows.
        Each row dict has keys: 'pos', 'nilai_periode', 'nilai_tahun_sebelumnya'
        """
        if not rows:
            return
        self.conn.executemany(
            """INSERT OR REPLACE INTO laporan_data
               (periode_bulan, periode_tahun, provinsi_code, kabupaten_code,
                bank_code, jenis_laporan_code, pos, nilai_periode, nilai_tahun_sebelumnya)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    periode_bulan, periode_tahun, provinsi_code, kabupaten_code,
                    bank_code, jenis_laporan_code,
                    r.get("pos", ""),
                    r.get("nilai_periode", ""),
                    r.get("nilai_tahun_sebelumnya", ""),
                )
                for r in rows
            ],
        )
        self.conn.commit()

    # ── Progress Tracking ───────────────────────────────────
    def is_scraped(
        self, periode_bulan: str, periode_tahun: str,
        provinsi_code: str, kabupaten_code: str,
        bank_code: str, jenis_laporan_code: str,
    ) -> bool:
        """Check if a particular combination has already been scraped."""
        cur = self.conn.execute(
            """SELECT 1 FROM scrape_progress
               WHERE periode_bulan=? AND periode_tahun=?
                 AND provinsi_code=? AND kabupaten_code=?
                 AND bank_code=? AND jenis_laporan_code=?""",
            (periode_bulan, periode_tahun, provinsi_code, kabupaten_code,
             bank_code, jenis_laporan_code),
        )
        return cur.fetchone() is not None

    def mark_scraped(
        self, periode_bulan: str, periode_tahun: str,
        provinsi_code: str, kabupaten_code: str,
        bank_code: str, jenis_laporan_code: str,
        status: str = "done",
    ):
        """Mark a combination as scraped."""
        self.conn.execute(
            """INSERT OR REPLACE INTO scrape_progress
               (periode_bulan, periode_tahun, provinsi_code, kabupaten_code,
                bank_code, jenis_laporan_code, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (periode_bulan, periode_tahun, provinsi_code, kabupaten_code,
             bank_code, jenis_laporan_code, status),
        )
        self.conn.commit()

    def get_progress_count(self, periode_bulan: str, periode_tahun: str) -> int:
        """Count completed scrapes for a period."""
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM scrape_progress WHERE periode_bulan=? AND periode_tahun=?",
            (periode_bulan, periode_tahun),
        )
        return cur.fetchone()[0]

    def get_laporan_count(self, periode_bulan: str, periode_tahun: str) -> int:
        """Count total data rows for a period."""
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM laporan_data WHERE periode_bulan=? AND periode_tahun=?",
            (periode_bulan, periode_tahun),
        )
        return cur.fetchone()[0]
