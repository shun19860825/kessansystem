import json
import os
import re

EXTRACTION_PROMPT = """
添付のPDFは企業の決算書（損益計算書・財務諸表）です。
下記の項目をすべて抽出し、**JSONのみ**で回答してください（説明文不要）。
金額は万円単位の数値で。見つからない項目はnullにしてください。

{
  "fiscal_year": "決算年度（例: 2024年3月期）",
  "period_start": "期間開始日YYYY-MM-DD",
  "period_end": "期間終了日YYYY-MM-DD",
  "sales": 売上高,
  "cost_of_goods": 売上原価,
  "gross_profit": 売上総利益（粗利）,
  "fixed_costs": 固定費合計,
  "variable_costs": 変動費合計,
  "selling_expenses": 販売費,
  "general_admin_expenses": 一般管理費,
  "operating_profit": 営業利益,
  "non_operating_income": 営業外収益,
  "non_operating_expenses": 営業外費用,
  "ordinary_profit": 経常利益,
  "extraordinary_income": 特別利益,
  "extraordinary_loss": 特別損失,
  "net_profit": 当期純利益,
  "notes": "特記事項があれば"
}
"""


def process_pdf_with_gemini(pdf_path: str, api_key: str) -> dict:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    uploaded = genai.upload_file(pdf_path, mime_type="application/pdf")

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content([uploaded, EXTRACTION_PROMPT])

    text = response.text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1)

    data = json.loads(text)
    data["source_file"] = os.path.basename(pdf_path)
    return data


def validate_api_key(api_key: str) -> bool:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        genai.GenerativeModel("gemini-1.5-flash").generate_content("ping")
        return True
    except Exception:
        return False
