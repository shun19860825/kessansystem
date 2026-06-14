"""
担当者別売上実績表 PDF を Gemini AI で解析するモジュール。
対応フォーマット:
  - 担当者別商品別売上実績表
  - 担当者別得意先別売上実績表
"""

import json
import re
import tempfile
import os

PRODUCT_REPORT_PROMPT = """
このPDFは「担当者別商品別売上実績表」です。
担当者ごとに商品の売上データが記載されています。

以下のJSON形式で全データを抽出してください（「担当者計」「総合計」の行は含めないでください）:
{
  "period": "集計期間（例: 令和7年8月度～令和8年5月度）",
  "report_type": "product",
  "rows": [
    {
      "rep_code": "担当者コード（例: 000001）",
      "rep_name": "担当者名（例: 櫻井 武志）",
      "product_code": "商品コード",
      "product_name": "商品名",
      "unit": "単位",
      "quantity": 数量（数値）,
      "sales_amount": 純売上額（数値・カンマなし）,
      "gross_profit": 粗利額（数値・カンマなし）,
      "gross_profit_rate": 粗利率（数値・%記号なし）
    }
  ]
}

注意:
- 数値はカンマや円記号を除いた純粋な数値で返してください
- マイナス値（値引き等）もそのまま数値で返してください
- コードブロック（```）は不要です、JSONのみ返してください
"""

CUSTOMER_REPORT_PROMPT = """
このPDFは「担当者別得意先別売上実績表」です。
担当者ごとに得意先の売上データが記載されています。

以下のJSON形式で全データを抽出してください（「担当者計」「総合計」の行は含めないでください）:
{
  "period": "集計期間（例: 令和7年8月度～令和8年5月度）",
  "report_type": "customer",
  "rows": [
    {
      "rep_code": "担当者コード（例: 000001）",
      "rep_name": "担当者名（例: 櫻井 武志）",
      "customer_code": "得意先コード",
      "customer_name": "得意先名",
      "sales_amount": 純売上額（数値・カンマなし）,
      "gross_profit": 粗利額（数値・カンマなし）,
      "gross_profit_rate": 粗利率（数値・%記号なし）
    }
  ]
}

注意:
- 数値はカンマや円記号を除いた純粋な数値で返してください
- コードブロック（```）は不要です、JSONのみ返してください
"""


def detect_report_type(filename: str) -> str:
    """ファイル名からレポート種別を判定する。"""
    name = filename.lower()
    if "得意先" in filename or "tokuisaki" in name:
        return "customer"
    if "商品" in filename or "shohin" in name:
        return "product"
    return "unknown"


def _parse_json_response(text: str) -> dict:
    """Gemini のレスポンスから JSON を抽出してパースする。"""
    text = text.strip()
    # コードブロックを除去
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    return json.loads(text.strip())


def process_sales_report_pdf(pdf_path: str, api_key: str,
                              report_type: str = "unknown") -> dict:
    """
    売上実績表 PDF を Gemini で解析し、構造化データを返す。

    Returns:
        {
            "period": str,
            "report_type": "product" | "customer",
            "rows": [...],
        }
    """
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError("google-generativeai がインストールされていません")

    genai.configure(api_key=api_key)

    # レポート種別に応じたプロンプトを選択
    if report_type == "customer":
        prompt = CUSTOMER_REPORT_PROMPT
    elif report_type == "product":
        prompt = PRODUCT_REPORT_PROMPT
    else:
        # ファイル名から自動判定できなければ両方試みる
        prompt = PRODUCT_REPORT_PROMPT

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # 担当者別商品別売上実績表は数百行に及ぶことがあるため、
    # 出力トークン上限を引き上げ、JSON形式での出力を強制する
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "max_output_tokens": 65536,
        },
    )
    response = model.generate_content([
        {"mime_type": "application/pdf", "data": pdf_bytes},
        prompt,
    ])

    try:
        response_text = response.text
    except ValueError as e:
        finish_reason = ""
        if response.candidates:
            finish_reason = str(response.candidates[0].finish_reason)
        raise ValueError(f"Gemini から有効な応答が得られませんでした"
                         f"（finish_reason={finish_reason}）: {e}")

    try:
        data = _parse_json_response(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini のレスポンスを JSON に変換できませんでした: {e}\n"
                         f"レスポンス先頭: {response_text[:300]}")

    # rows が存在しない場合は空配列を設定
    data.setdefault("rows", [])
    data.setdefault("period", "")
    data.setdefault("report_type", report_type)

    return data
