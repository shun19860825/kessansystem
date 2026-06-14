import json
import os
import re

# 販管費内訳のうち固定費として扱う項目（それ以外の販管費はすべて変動費とする）
FIXED_COST_ITEM_KEYS = [
    "sga_shipping_cost",       # 荷造発送費
    "sga_meeting_cost",        # 会議費
    "sga_entertainment_cost",  # 交際費
    "sga_commission_fee",      # 支払手数料
]

EXTRACTION_PROMPT = """
添付のPDFは企業の決算書（決算報告書）です。
「貸借対照表」「損益計算書」「販売費及び一般管理費内訳書」から
下記の項目をすべて抽出し、**JSONのみ**で回答してください（説明文不要）。
金額は円単位の数値で、カンマや円記号を除いた純粋な数値にしてください。
見つからない項目は0にしてください。

{
  "fiscal_year": "決算期（例: 2025年7月期。第◯期の場合は決算期末日の年月で「YYYY年M月期」の形式に変換）",
  "period_start": "損益計算書の自'期間開始日 YYYY-MM-DD",
  "period_end": "損益計算書の至'期間終了日 YYYY-MM-DD",

  "total_assets": "貸借対照表 資産の部合計",
  "total_liabilities": "貸借対照表 負債の部合計",
  "net_assets": "貸借対照表 純資産の部合計",

  "sales": "損益計算書 売上高合計",
  "cost_of_goods": "損益計算書 売上原価",
  "gross_profit": "損益計算書 売上総利益金額（粗利）",

  "sga_total": "損益計算書 販売費及び一般管理費合計",
  "sga_shipping_cost": "販売費及び一般管理費内訳書の「荷造発送費」",
  "sga_meeting_cost": "販売費及び一般管理費内訳書の「会議費」",
  "sga_entertainment_cost": "販売費及び一般管理費内訳書の「交際費」",
  "sga_commission_fee": "販売費及び一般管理費内訳書の「支払手数料」",

  "operating_profit": "損益計算書 営業利益金額",
  "non_operating_income": "損益計算書 営業外収益合計",
  "non_operating_expenses": "損益計算書 営業外費用合計",
  "ordinary_profit": "損益計算書 経常利益金額",
  "extraordinary_income": "損益計算書 特別利益合計",
  "extraordinary_loss": "損益計算書 特別損失合計",
  "pretax_profit": "損益計算書 税引前当期純利益金額",
  "net_profit": "損益計算書 当期純利益金額",

  "notes": "特記事項があれば"
}
"""


def process_pdf_with_gemini(pdf_path: str, api_key: str) -> dict:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    uploaded = genai.upload_file(pdf_path, mime_type="application/pdf")

    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "max_output_tokens": 65536,
        },
    )
    response = model.generate_content([uploaded, EXTRACTION_PROMPT])

    text = response.text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1)

    data = json.loads(text)
    data["source_file"] = os.path.basename(pdf_path)

    # 販管費内訳から固定費／変動費を算出
    # 固定費: 荷造発送費・会議費・交際費・支払手数料 / 変動費: それ以外の販管費
    fixed_costs = sum(float(data.get(k, 0) or 0) for k in FIXED_COST_ITEM_KEYS)
    sga_total = float(data.get("sga_total", 0) or 0)
    data["fixed_costs"] = fixed_costs
    data["variable_costs"] = sga_total - fixed_costs
    data["selling_expenses"] = 0
    data["general_admin_expenses"] = sga_total

    return data


def validate_api_key(api_key: str) -> tuple[bool, str]:
    """APIキーの有効性を確認する。(成否, エラーメッセージ) を返す。"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key.strip())
        genai.GenerativeModel("gemini-2.5-flash").generate_content("ping")
        return True, ""
    except Exception as e:
        return False, str(e)
