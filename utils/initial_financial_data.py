"""
東京ブラインド工業株式会社 決算報告書（第72期）の初期データ。
自 令和6年8月1日 〜 至 令和7年7月31日
「東京ブラインド　決算書2025.07　　20250928.pdf」より抽出。

固定費／変動費の区分ルール:
  販売費及び一般管理費のうち
    - 荷造発送費・会議費・交際費・支払手数料 → 固定費
    - それ以外の販管費項目              → 変動費
  （utils/initial_financial_data.py と gemini_processor.py で共通の区分）
"""

TOKYO_BLIND_FY2025 = {
    "fiscal_year": "2025年7月期",
    "period_start": "2024-08-01",
    "period_end": "2025-07-31",

    # 貸借対照表
    "total_assets": 410_875_742,
    "total_liabilities": 309_434_397,
    "net_assets": 101_441_345,

    # 損益計算書
    "sales": 303_251_566,
    "cost_of_goods": 195_146_553,
    "gross_profit": 108_105_013,

    # 販管費（固定費: 荷造発送費588,182 + 会議費779,492 + 交際費786,390 + 支払手数料3,038,978 = 5,193,042）
    "fixed_costs": 5_193_042,
    "variable_costs": 89_406_749,  # 販管費合計94,599,791 - 固定費5,193,042
    "selling_expenses": 0,
    "general_admin_expenses": 94_599_791,

    "operating_profit": 13_505_222,
    "non_operating_income": 7_527_068,
    "non_operating_expenses": 4_779_351,
    "ordinary_profit": 16_252_939,
    "extraordinary_income": 109_090,
    "extraordinary_loss": 3_481_817,
    "net_profit": 9_568_725,

    "current_assets": 0,
    "current_liabilities": 0,
    "inventory": 0,
    "labor_cost": 0,

    "source_file": "東京ブラインド　決算書2025.07　　20250928.pdf",
    "notes": "第72期",
}


def insert_initial_financial_data(db) -> None:
    """既に同じ決算期のデータが存在しない場合のみ追加する。"""
    if db.financial_statement_exists(TOKYO_BLIND_FY2025["fiscal_year"]):
        return
    db.add_financial_statement(TOKYO_BLIND_FY2025)
