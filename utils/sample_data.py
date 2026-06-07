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

FINANCIAL = [
    {"fiscal_year": "2020年3月期", "period_start": "2019-04-01", "period_end": "2020-03-31",
     "sales": 258_000, "cost_of_goods": 158_000, "gross_profit": 100_000,
     "fixed_costs": 42_000, "variable_costs": 34_000, "selling_expenses": 22_000,
     "general_admin_expenses": 18_000, "operating_profit": 18_000,
     "non_operating_income": 600, "non_operating_expenses": 1_400,
     "ordinary_profit": 17_200, "extraordinary_income": 0, "extraordinary_loss": 1_500,
     "net_profit": 11_000, "source_file": "サンプルデータ"},

    {"fiscal_year": "2021年3月期", "period_start": "2020-04-01", "period_end": "2021-03-31",
     "sales": 285_000, "cost_of_goods": 171_000, "gross_profit": 114_000,
     "fixed_costs": 45_000, "variable_costs": 38_000, "selling_expenses": 25_000,
     "general_admin_expenses": 20_000, "operating_profit": 26_000,
     "non_operating_income": 800, "non_operating_expenses": 1_200,
     "ordinary_profit": 25_600, "extraordinary_income": 0, "extraordinary_loss": 2_000,
     "net_profit": 16_000, "source_file": "サンプルデータ"},

    {"fiscal_year": "2022年3月期", "period_start": "2021-04-01", "period_end": "2022-03-31",
     "sales": 312_000, "cost_of_goods": 183_000, "gross_profit": 129_000,
     "fixed_costs": 47_000, "variable_costs": 41_000, "selling_expenses": 27_000,
     "general_admin_expenses": 22_000, "operating_profit": 32_000,
     "non_operating_income": 1_000, "non_operating_expenses": 1_100,
     "ordinary_profit": 31_900, "extraordinary_income": 500, "extraordinary_loss": 0,
     "net_profit": 22_000, "source_file": "サンプルデータ"},

    {"fiscal_year": "2023年3月期", "period_start": "2022-04-01", "period_end": "2023-03-31",
     "sales": 298_000, "cost_of_goods": 178_800, "gross_profit": 119_200,
     "fixed_costs": 48_000, "variable_costs": 39_000, "selling_expenses": 26_000,
     "general_admin_expenses": 23_000, "operating_profit": 23_200,
     "non_operating_income": 900, "non_operating_expenses": 1_300,
     "ordinary_profit": 22_800, "extraordinary_income": 0, "extraordinary_loss": 3_000,
     "net_profit": 14_000, "source_file": "サンプルデータ"},

    {"fiscal_year": "2024年3月期", "period_start": "2023-04-01", "period_end": "2024-03-31",
     "sales": 335_000, "cost_of_goods": 194_300, "gross_profit": 140_700,
     "fixed_costs": 49_000, "variable_costs": 43_000, "selling_expenses": 28_000,
     "general_admin_expenses": 24_000, "operating_profit": 39_700,
     "non_operating_income": 1_100, "non_operating_expenses": 1_000,
     "ordinary_profit": 39_800, "extraordinary_income": 2_000, "extraordinary_loss": 500,
     "net_profit": 28_000, "source_file": "サンプルデータ"},

    {"fiscal_year": "2025年3月期", "period_start": "2024-04-01", "period_end": "2025-03-31",
     "sales": 358_000, "cost_of_goods": 201_000, "gross_profit": 157_000,
     "fixed_costs": 50_000, "variable_costs": 46_000, "selling_expenses": 29_000,
     "general_admin_expenses": 25_000, "operating_profit": 53_000,
     "non_operating_income": 1_200, "non_operating_expenses": 900,
     "ordinary_profit": 53_300, "extraordinary_income": 0, "extraordinary_loss": 1_000,
     "net_profit": 37_000, "source_file": "サンプルデータ"},
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

    for fs in FINANCIAL:
        db.add_financial_statement(fs)
