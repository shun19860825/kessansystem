"""
担当者別売上実績表のサンプル初期データ。
令和7年8月度～令和8年5月度 (2025/08 - 2026/05) の実績データ。

PDFファイルをアップロードすると詳細データに更新されます。
"""

PERIOD       = "令和7年8月度～令和8年5月度"
PERIOD_START = "2025-08-01"
PERIOD_END   = "2026-05-31"

# 担当者別 売上合計（担当者別商品別売上実績表より）
# (rep_code, rep_name, quantity, sales_amount, gross_profit, gross_profit_rate)
REP_PRODUCT_SUMMARY = [
    ("000001", "櫻井 武志",   42.00,   412_782,        0, 0.0),
    ("000018", "大竹 佑樹", 5_174.94, 68_849_856,      0, 0.0),
    ("000024", "岩崎 健夫", 3_460.50, 48_659_231,      0, 0.0),
    ("000026", "佐藤 由紀", 1_053.00, 11_040_280,      0, 0.0),
    ("000028", "櫻井 和希", 3_124.30, 70_393_067,      0, 0.0),
    ("000029", "中嶋 幸志", 1_906.40, 41_023_830,      0, 0.0),
    ("000032", "藤巻 竜也",     1.00,     20_000,      0, 0.0),
]

# 担当者コード 000001（櫻井 武志）の商品別詳細
# (product_code, product_name, unit, quantity, sales_amount, gross_profit, gross_profit_rate)
REP_001_PRODUCTS = [
    ("30CU000000000", "ｿﾉﾀﾒｰｶｰｶｰﾃﾝｿﾉﾀ",          "ヶ所",  1.00,  14_720,  14_720, 100.0),
    ("32B2000000000", "ﾍﾞﾈﾁｱ25 ﾎﾟｰﾙ式",            "台",   2.00,  26_640,  26_640, 100.0),
    ("409020013",     "梱包輸送費",                  "式",   5.00,  33_080,  33_080, 100.0),
    ("409090150",     "請求値引き",                  "式",   0.00,  -1_188,  -1_188, 100.0),
    ("50BIN00000000", "吸音 インテリックス 生地",    "m",   24.00, 337_640, 337_640, 100.0),
    ("5VFBA20129400", "チェーンロック 透明",          "セット", 2.00,      90,      90, 100.0),
    ("5VS55C111B000", "操作チェーン ブラウン",        "-",   8.00,   1_800,   1_800, 100.0),
]


def insert_initial_sales_data(db) -> None:
    """初期データが存在しない場合のみ挿入する。"""
    cur = db.conn.execute("SELECT COUNT(*) FROM sales_reps_reports")
    if cur.fetchone()[0] > 0:
        return

    # ── 担当者別商品別売上実績表（サマリー） ─────────────────────────────
    product_report_id = db.add_sales_report(
        PERIOD, PERIOD_START, PERIOD_END,
        report_type="product_summary",
        source_file="担当者別商品別売上実績表202508～202605.PDF（サマリー）",
    )

    # 000001 は商品明細あり、その他は合計行のみ
    product_rows = [
        ("000001", "櫻井 武志",
         code, name, unit, qty, sales, gp, gpr)
        for code, name, unit, qty, sales, gp, gpr in REP_001_PRODUCTS
    ]
    for rep_code, rep_name, qty, sales, gp, gpr in REP_PRODUCT_SUMMARY:
        if rep_code == "000001":
            continue  # 詳細行を使用
        product_rows.append((
            rep_code, rep_name,
            "summary", "（合計・詳細はPDF取り込みで追加）",
            "", qty, sales, gp, gpr,
        ))

    db.add_rep_product_sales_batch(product_report_id, product_rows)
