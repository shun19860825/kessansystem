import random
from datetime import date, timedelta

AGENCIES = [
    ("東京商事",          "関東",   "田中太郎",  "2021-04-01"),
    ("大阪トレーディング", "近畿",   "山田花子",  "2021-07-01"),
    ("名古屋商会",        "中部",   "鈴木一郎",  "2021-10-01"),
    ("福岡代理店",        "九州",   "中村美子",  "2022-01-01"),
    ("札幌販売",          "北海道", "佐藤健",    "2022-04-01"),
    ("仙台商事",          "東北",   "伊藤恵",    "2022-07-01"),
    ("広島トレード",       "中国",   "渡辺司",    "2023-01-01"),
    ("横浜商会",          "関東",   "小林真",    "2023-06-01"),
    ("京都物産",          "近畿",   "加藤幸",    "2024-01-01"),
    ("神戸商事",          "近畿",   "吉田誠",    "2024-06-01"),
]

PRODUCTS = [
    ("製品A-100",  "電子部品", 15_000),
    ("製品B-200",  "機械部品", 45_000),
    ("製品C-300",  "化学品",   8_000),
    ("製品D-400",  "電子部品", 25_000),
    ("製品E-500",  "機械部品", 60_000),
    ("製品F-600",  "消耗品",   3_000),
    ("製品G-700",  "化学品",   12_000),
    ("製品H-800",  "電子部品", 35_000),
    ("製品I-900",  "消耗品",   5_000),
    ("製品J-1000", "機械部品", 80_000),
]

def insert_sample_data(db) -> None:
    cur = db.conn.execute("SELECT COUNT(*) FROM agencies")
    if cur.fetchone()[0] > 0:
        return

    random.seed(42)

    agency_ids  = [db.add_agency(n, r, c, s)   for n, r, c, s in AGENCIES]
    product_ids = [db.add_product(n, cat, p)    for n, cat, p  in PRODUCTS]
    prices      = {pid: PRODUCTS[i][2] for i, pid in enumerate(product_ids)}

    sales_rows = []
    start = date(2021, 1, 1)
    end   = date(2025, 12, 31)

    for agency_id in agency_ids:
        freq = random.randint(3, 12)
        cur_date = start
        while cur_date <= end:
            for _ in range(random.randint(1, freq)):
                pid  = random.choice(product_ids)
                qty  = random.randint(1, 20)
                unit = prices[pid] * (0.85 + random.random() * 0.30)
                sd   = cur_date + timedelta(days=random.randint(0, 27))
                if sd > end:
                    sd = end
                sales_rows.append((agency_id, pid, sd.isoformat(), qty, unit * qty))
            m = cur_date.month % 12 + 1
            y = cur_date.year + (1 if cur_date.month == 12 else 0)
            cur_date = date(y, m, 1)

    db.conn.executemany(
        "INSERT INTO sales_records (agency_id, product_id, sale_date, quantity, amount) VALUES (?,?,?,?,?)",
        sales_rows,
    )
    db.conn.commit()
