import os
import sqlite3
from datetime import datetime


class Database:
    def __init__(self, db_path: str = ""):
        if not db_path:
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "business_analytics.db")
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def initialize(self) -> None:
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS agencies (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL UNIQUE,
                region     TEXT,
                contact    TEXT,
                start_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS products (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                category   TEXT,
                unit_price REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sales_records (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                agency_id  INTEGER NOT NULL,
                product_id INTEGER,
                sale_date  DATE NOT NULL,
                quantity   INTEGER DEFAULT 1,
                amount     REAL NOT NULL,
                FOREIGN KEY (agency_id)  REFERENCES agencies(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
            CREATE TABLE IF NOT EXISTS financial_statements (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                fiscal_year            TEXT NOT NULL,
                period_start           DATE,
                period_end             DATE,
                sales                  REAL DEFAULT 0,
                cost_of_goods          REAL DEFAULT 0,
                gross_profit           REAL DEFAULT 0,
                fixed_costs            REAL DEFAULT 0,
                variable_costs         REAL DEFAULT 0,
                selling_expenses       REAL DEFAULT 0,
                general_admin_expenses REAL DEFAULT 0,
                operating_profit       REAL DEFAULT 0,
                non_operating_income   REAL DEFAULT 0,
                non_operating_expenses REAL DEFAULT 0,
                ordinary_profit        REAL DEFAULT 0,
                extraordinary_income   REAL DEFAULT 0,
                extraordinary_loss     REAL DEFAULT 0,
                net_profit             REAL DEFAULT 0,
                source_file            TEXT,
                notes                  TEXT,
                created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    # ── agencies ──────────────────────────────────────────────────────────────

    def get_all_agencies(self) -> list:
        return self.conn.execute("SELECT * FROM agencies ORDER BY name").fetchall()

    def add_agency(self, name: str, region: str = "", contact: str = "", start_date: str = "") -> int:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO agencies (name, region, contact, start_date) VALUES (?,?,?,?)",
            (name, region, contact, start_date or None),
        )
        self.conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        return self.conn.execute("SELECT id FROM agencies WHERE name=?", (name,)).fetchone()["id"]

    # ── products ──────────────────────────────────────────────────────────────

    def add_product(self, name: str, category: str = "", unit_price: float = 0) -> int:
        cur = self.conn.execute(
            "INSERT INTO products (name, category, unit_price) VALUES (?,?,?)",
            (name, category, unit_price),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_product_sales_summary(self) -> list:
        return self.conn.execute("""
            SELECT p.name   AS product_name,
                   p.category,
                   COALESCE(SUM(sr.quantity), 0) AS total_quantity,
                   COALESCE(SUM(sr.amount),   0) AS total_revenue,
                   COUNT(DISTINCT sr.agency_id)  AS agency_count
            FROM products p
            LEFT JOIN sales_records sr ON p.id = sr.product_id
            GROUP BY p.id
            ORDER BY total_revenue DESC
        """).fetchall()

    # ── sales ─────────────────────────────────────────────────────────────────

    def add_sale(self, agency_id: int, product_id: int, sale_date: str,
                 quantity: int, amount: float) -> None:
        self.conn.execute(
            "INSERT INTO sales_records (agency_id, product_id, sale_date, quantity, amount) VALUES (?,?,?,?,?)",
            (agency_id, product_id, sale_date, quantity, amount),
        )
        self.conn.commit()

    def get_agency_monthly_sales(self, years: int = 5) -> list:
        start_year = datetime.now().year - years + 1
        return self.conn.execute("""
            SELECT a.name                          AS agency_name,
                   strftime('%Y-%m', sr.sale_date) AS month,
                   SUM(sr.amount)                  AS total_amount
            FROM sales_records sr
            JOIN agencies a ON sr.agency_id = a.id
            WHERE CAST(strftime('%Y', sr.sale_date) AS INTEGER) >= ?
            GROUP BY sr.agency_id, month
            ORDER BY a.name, month
        """, (start_year,)).fetchall()

    # ── repeat rate ───────────────────────────────────────────────────────────

    def get_new_agency_repeat_rates(self) -> list:
        return self.conn.execute("""
            SELECT strftime('%Y', a.start_date) AS start_year,
                   COUNT(DISTINCT a.id)          AS total_agencies,
                   COUNT(DISTINCT CASE WHEN pc.purchase_count >= 2 THEN a.id END) AS repeat_agencies
            FROM agencies a
            LEFT JOIN (
                SELECT agency_id,
                       COUNT(DISTINCT strftime('%Y-%m', sale_date)) AS purchase_count
                FROM sales_records
                GROUP BY agency_id
            ) pc ON a.id = pc.agency_id
            WHERE a.start_date IS NOT NULL
            GROUP BY start_year
            ORDER BY start_year
        """).fetchall()

    def get_agency_purchase_detail(self) -> list:
        return self.conn.execute("""
            SELECT a.name                            AS agency_name,
                   strftime('%Y', a.start_date)      AS start_year,
                   a.region,
                   COUNT(DISTINCT strftime('%Y-%m', sr.sale_date)) AS active_months,
                   COALESCE(SUM(sr.amount), 0)       AS total_amount
            FROM agencies a
            LEFT JOIN sales_records sr ON a.id = sr.agency_id
            WHERE a.start_date IS NOT NULL
            GROUP BY a.id
            ORDER BY start_year, total_amount DESC
        """).fetchall()

    # ── financial statements ──────────────────────────────────────────────────

    def add_financial_statement(self, data: dict) -> int:
        cur = self.conn.execute("""
            INSERT INTO financial_statements (
                fiscal_year, period_start, period_end,
                sales, cost_of_goods, gross_profit,
                fixed_costs, variable_costs,
                selling_expenses, general_admin_expenses,
                operating_profit, non_operating_income, non_operating_expenses,
                ordinary_profit, extraordinary_income, extraordinary_loss,
                net_profit, source_file, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("fiscal_year"), data.get("period_start"), data.get("period_end"),
            data.get("sales", 0) or 0, data.get("cost_of_goods", 0) or 0,
            data.get("gross_profit", 0) or 0,
            data.get("fixed_costs", 0) or 0, data.get("variable_costs", 0) or 0,
            data.get("selling_expenses", 0) or 0, data.get("general_admin_expenses", 0) or 0,
            data.get("operating_profit", 0) or 0, data.get("non_operating_income", 0) or 0,
            data.get("non_operating_expenses", 0) or 0, data.get("ordinary_profit", 0) or 0,
            data.get("extraordinary_income", 0) or 0, data.get("extraordinary_loss", 0) or 0,
            data.get("net_profit", 0) or 0, data.get("source_file"), data.get("notes"),
        ))
        self.conn.commit()
        return cur.lastrowid

    def get_all_financial_statements(self) -> list:
        return self.conn.execute(
            "SELECT * FROM financial_statements ORDER BY fiscal_year"
        ).fetchall()

    def delete_financial_statement(self, stmt_id: int) -> None:
        self.conn.execute("DELETE FROM financial_statements WHERE id=?", (stmt_id,))
        self.conn.commit()

    def close(self) -> None:
        if self.conn:
            self.conn.close()
