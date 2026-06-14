"""
ビジネス分析ダッシュボード
- 製品売上一覧
- 代理店5年間売上推移
- 新規代理店リピート率
- 決算書PDF取り込み＆比較分析（Gemini AI）
"""

import os
import tempfile

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database import Database
from gemini_processor import process_pdf_with_gemini, validate_api_key
from sales_processor import detect_report_type, process_sales_report_pdf
from utils.sample_data import insert_sample_data
from utils.initial_sales_data import insert_initial_sales_data
from utils.initial_financial_data import insert_initial_financial_data

# ── ページ設定（必ず最初の st 呼び出し） ─────────────────────────────────────
st.set_page_config(
    page_title="ビジネス分析ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── カスタム CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
div[data-testid="metric-container"] {
    background: #f0f8ff;
    border: 1px solid #d0e4fb;
    border-radius: 10px;
    padding: 16px 20px;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)


# ── DB 初期化（サーバー全体で共有） ──────────────────────────────────────────
@st.cache_resource
def get_db() -> Database:
    db = Database()
    db.initialize()
    insert_sample_data(db)
    insert_initial_sales_data(db)
    insert_initial_financial_data(db)
    db.delete_financial_statements_by_source("サンプルデータ")
    return db


db = get_db()


# ── サイドバー ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 設定")

    # API キー（Streamlit Secrets → サイドバー入力の優先順）
    try:
        default_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        default_key = ""

    api_key = st.text_input(
        "Gemini API Key",
        value=default_key,
        type="password",
        placeholder="AIzaSy...",
        help="Google AI Studio（aistudio.google.com）でAPIキーを取得してください",
    ).strip()
    st.session_state["api_key"] = api_key

    if api_key:
        if st.button("🔌 接続テスト"):
            with st.spinner("確認中..."):
                ok, err = validate_api_key(api_key)
            if ok:
                st.success("接続成功！")
            else:
                st.error(f"接続失敗: {err}")

    st.divider()
    st.caption("**データ管理**")
    st.caption("データはサーバー上のSQLiteに保存されます。\nStreamlit Cloud に再デプロイするとリセットされます。")

    if st.button("🔄 サンプルデータをリセット", type="secondary"):
        db_path = db.db_path
        try:
            db.close()
        except Exception:
            pass
        if os.path.exists(db_path):
            os.remove(db_path)
        st.cache_resource.clear()
        st.rerun()

    st.divider()
    with st.expander("🚀 クラウドへのデプロイ方法"):
        st.markdown("""
**Streamlit Community Cloud（無料）**

1. このフォルダを GitHub にpush
2. [share.streamlit.io](https://share.streamlit.io) でサインイン
3. **New app** → リポジトリを選択 → `app.py` を指定
4. **Advanced settings → Secrets** に以下を追加:
   ```
   GEMINI_API_KEY = "AIzaSy..."
   ```
5. **Deploy** をクリック → 数分でURLが発行されます

デプロイ後はそのURLをブラウザで開くだけで、\n**Mac・Windows・スマホ**どこからでもアクセスできます。
        """)


# ── メインヘッダー ────────────────────────────────────────────────────────────
st.title("📊 ビジネス分析ダッシュボード")
st.divider()

# ── タブ ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📦 製品売上一覧",
    "📈 代理店売上推移",
    "🔄 新規代理店リピート率",
    "📋 決算書分析",
    "👤 担当者別売上実績",
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 ── 製品売上一覧（PDFデータ）
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("製品別売上一覧")

    # 古いキャッシュ対策
    if not hasattr(db, "get_pdf_product_summary"):
        st.cache_resource.clear()
        st.rerun()

    pdf_prod_rows = db.get_pdf_product_summary()

    if not pdf_prod_rows:
        st.info("PDFデータがありません。「👤 担当者別売上実績」タブからPDFを取り込んでください。")
    else:
        df_pdf = pd.DataFrame([dict(r) for r in pdf_prod_rows])
        df_pdf["total_sales"]           = df_pdf["total_sales"].astype(float)
        df_pdf["total_gross_profit"]    = df_pdf["total_gross_profit"].astype(float)
        df_pdf["total_quantity"]        = df_pdf["total_quantity"].astype(float)
        df_pdf["avg_gross_profit_rate"] = df_pdf["avg_gross_profit_rate"].astype(float)

        # ── KPI カード ─────────────────────────────────────────────────────
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("商品種類数",   f"{len(df_pdf):,} 種")
        k2.metric("総売上合計",   f"¥{df_pdf['total_sales'].sum()/1_000_000:.1f}M")
        k3.metric("総数量",       f"{df_pdf['total_quantity'].sum():,.0f}")
        k4.metric("集計担当者数", f"{df_pdf['rep_count'].max()} 名")

        st.divider()

        col_tbl, col_chart = st.columns([1.2, 1], gap="large")

        with col_tbl:
            # 担当者フィルター
            all_reps_t1 = ["全担当者"] + sorted(
                r["rep_name"]
                for r in db.get_rep_product_summary()
            )
            sel_rep_t1 = st.selectbox("担当者で絞り込み", all_reps_t1, key="t1_rep_filter")

            if sel_rep_t1 == "全担当者":
                df_view = df_pdf.copy()
            else:
                rows_filtered = db.get_rep_product_detail(rep_code=None)
                df_all_detail = pd.DataFrame([dict(r) for r in rows_filtered])
                df_view = (
                    df_all_detail[df_all_detail["rep_name"] == sel_rep_t1]
                    .groupby(["product_code", "product_name", "unit"], as_index=False)
                    .agg(
                        total_quantity=("quantity", "sum"),
                        total_sales=("sales_amount", "sum"),
                        total_gross_profit=("gross_profit", "sum"),
                        avg_gross_profit_rate=("gross_profit_rate", "mean"),
                        rep_count=("rep_name", "nunique"),
                    )
                    .sort_values("total_sales", ascending=False)
                )

            df_show = pd.DataFrame({
                "商品コード": df_view["product_code"],
                "商品名":     df_view["product_name"],
                "単位":       df_view["unit"].fillna("—"),
                "数量":       df_view["total_quantity"].map(lambda v: f"{v:,.2f}"),
                "純売上額":   df_view["total_sales"].map(lambda v: f"¥{v:,.0f}"),
                "粗利額":     df_view["total_gross_profit"].map(
                    lambda v: f"¥{v:,.0f}" if float(v) != 0 else "—"),
                "粗利率":     df_view["avg_gross_profit_rate"].map(
                    lambda v: f"{float(v):.1f}%" if float(v) != 0 else "—"),
                "担当者数":   df_view["rep_count"].astype(int),
            })
            st.dataframe(df_show, use_container_width=True, hide_index=True, height=500)

        with col_chart:
            chart_type = st.radio(
                "グラフ種別",
                ["売上 TOP20（棒）", "売上構成（円）"],
                horizontal=True,
                key="p_chart",
            )
            top20 = df_view.head(20).copy()
            top20["total_sales"] = top20["total_sales"].astype(float)

            if chart_type == "売上構成（円）":
                fig = px.pie(
                    top20, values="total_sales", names="product_name",
                    title="商品別売上構成 TOP20", hole=0.35,
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
            else:
                fig = px.bar(
                    top20.sort_values("total_sales"),
                    x="total_sales", y="product_name",
                    orientation="h",
                    title="商品別売上 TOP20",
                    labels={"total_sales": "純売上額（円）", "product_name": "商品名"},
                    color="total_sales",
                    color_continuous_scale="Blues",
                )
                fig.update_xaxes(tickformat=",.0f")
                fig.update_coloraxes(showscale=False)

            fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 ── 代理店売上推移
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("代理店別売上推移（過去5年）")

    agencies  = db.get_all_agencies()
    ag_names  = ["全代理店"] + [a["name"] for a in agencies]
    region_map = {a["name"]: a["region"] for a in agencies}

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        sel_agency = st.selectbox("代理店", ag_names, key="ag_sel")
    with c2:
        gran = st.selectbox("表示粒度", ["年次", "四半期", "月次"], key="gran_sel")
    with c3:
        chart_style = st.selectbox("グラフ種別", ["折れ線", "棒グラフ（積み上げ）"], key="ag_style")

    rows = db.get_agency_monthly_sales()
    if not rows:
        st.info("データがありません")
    else:
        df = pd.DataFrame([dict(r) for r in rows])
        df["month"]        = pd.to_datetime(df["month"] + "-01")
        df["total_amount"] = df["total_amount"].astype(float)

        if sel_agency != "全代理店":
            df = df[df["agency_name"] == sel_agency]

        if gran == "年次":
            df["period"] = df["month"].dt.year.astype(str) + "年"
            df["sort"]   = df["month"].dt.year
        elif gran == "四半期":
            df["period"] = (df["month"].dt.year.astype(str)
                            + "Q" + df["month"].dt.quarter.astype(str))
            df["sort"]   = df["month"].dt.year * 10 + df["month"].dt.quarter
        else:
            df["period"] = df["month"].dt.strftime("%Y-%m")
            df["sort"]   = df["month"].dt.year * 100 + df["month"].dt.month

        agg = (df.groupby(["agency_name", "period", "sort"])["total_amount"]
               .sum().reset_index().sort_values("sort"))

        if chart_style == "棒グラフ（積み上げ）":
            fig = px.bar(
                agg, x="period", y="total_amount", color="agency_name",
                barmode="stack",
                title=f"代理店別売上推移（{gran}・積み上げ）",
                labels={"total_amount": "売上（円）", "period": "期間",
                        "agency_name": "代理店名"},
                color_discrete_sequence=px.colors.qualitative.Plotly,
            )
        else:
            fig = px.line(
                agg, x="period", y="total_amount", color="agency_name",
                markers=True,
                title=f"代理店別売上推移（{gran}）",
                labels={"total_amount": "売上（円）", "period": "期間",
                        "agency_name": "代理店名"},
                color_discrete_sequence=px.colors.qualitative.Plotly,
            )

        fig.update_yaxes(tickformat=",.0f", title="売上（円）")
        fig.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=60),
        )
        st.plotly_chart(fig, use_container_width=True)

        # サマリーテーブル
        st.divider()
        st.markdown("**代理店サマリー（年次）**")
        df_yr = df.copy()
        df_yr["year"] = df_yr["month"].dt.year

        summary = []
        for ag_name in df_yr["agency_name"].unique():
            ag_yr = df_yr[df_yr["agency_name"] == ag_name].groupby("year")["total_amount"].sum()
            total5 = ag_yr.sum()
            last   = ag_yr.iloc[-1] if len(ag_yr) else 0
            if len(ag_yr) >= 2 and ag_yr.iloc[-2] != 0:
                yoy = (ag_yr.iloc[-1] - ag_yr.iloc[-2]) / ag_yr.iloc[-2] * 100
                yoy_str = f"{yoy:+.1f}%"
            else:
                yoy_str = "—"
            summary.append({
                "代理店名":   ag_name,
                "地域":       region_map.get(ag_name, "—"),
                "直近年売上": f"¥{last/10_000:.0f}万",
                "前年比":     yoy_str,
                "5年合計":    f"¥{total5/10_000:.0f}万",
            })

        st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 ── 新規代理店リピート率
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("新規代理店 リピート率分析")

    rate_rows   = db.get_new_agency_repeat_rates()
    detail_rows = db.get_agency_purchase_detail()

    total_ag  = sum(r["total_agencies"]  for r in rate_rows)
    repeat_ag = sum(r["repeat_agencies"] for r in rate_rows)
    rate_pct  = repeat_ag / total_ag * 100 if total_ag else 0
    last_new  = rate_rows[-1]["total_agencies"] if rate_rows else 0

    # KPI カード
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("総代理店数",      total_ag)
    k2.metric("リピート代理店数", repeat_ag)
    k3.metric("全体リピート率",   f"{rate_pct:.1f}%")
    k4.metric("直近年 新規",     last_new)

    st.divider()

    col_chart, col_table = st.columns([3, 2], gap="large")

    with col_chart:
        if rate_rows:
            df_rate = pd.DataFrame([dict(r) for r in rate_rows])
            df_rate["rate_pct"] = (df_rate["repeat_agencies"]
                                   / df_rate["total_agencies"] * 100).fillna(0)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_rate["start_year"], y=df_rate["total_agencies"],
                name="新規代理店数", marker_color="#90caf9",
                text=df_rate["total_agencies"], textposition="outside",
            ))
            fig.add_trace(go.Bar(
                x=df_rate["start_year"], y=df_rate["repeat_agencies"],
                name="リピート代理店数", marker_color="#1a73e8",
                text=df_rate["repeat_agencies"], textposition="outside",
            ))
            fig.add_trace(go.Scatter(
                x=df_rate["start_year"], y=df_rate["rate_pct"],
                name="リピート率", yaxis="y2",
                mode="lines+markers+text",
                text=[f"{v:.0f}%" for v in df_rate["rate_pct"]],
                textposition="top center",
                marker=dict(size=10, color="#ea4335"),
                line=dict(color="#ea4335", width=2.5),
            ))
            fig.update_layout(
                title="新規代理店数とリピート率（開始年別）",
                barmode="group",
                yaxis=dict(title="代理店数"),
                yaxis2=dict(title="リピート率 (%)", overlaying="y", side="right",
                            ticksuffix="%", range=[0, 120]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(t=60),
            )
            st.plotly_chart(fig, use_container_width=True)

            # 年別リピート率ヒートマップ風バー
            st.markdown("**年別リピート率**")
            df_rate_disp = df_rate[["start_year", "total_agencies",
                                    "repeat_agencies", "rate_pct"]].copy()
            df_rate_disp.columns = ["開始年", "新規代理店数", "リピート数", "リピート率(%)"]
            df_rate_disp["リピート率(%)"] = df_rate_disp["リピート率(%)"].map(
                lambda x: f"{x:.1f}%")
            st.dataframe(df_rate_disp, use_container_width=True, hide_index=True)

    with col_table:
        st.markdown("**代理店別詳細**")
        if detail_rows:
            df_d = pd.DataFrame([dict(r) for r in detail_rows])
            df_d["リピート"] = df_d["active_months"].apply(
                lambda x: "✅ あり" if x >= 2 else "❌ なし")
            df_d["累計売上"] = df_d["total_amount"].map(
                lambda x: f"¥{float(x)/10_000:.0f}万")
            df_show = df_d[["agency_name", "start_year", "region",
                             "active_months", "累計売上", "リピート"]]
            df_show = df_show.rename(columns={
                "agency_name":  "代理店名",
                "start_year":   "開始年",
                "region":       "地域",
                "active_months":"活動月数",
            })
            st.dataframe(df_show, use_container_width=True, hide_index=True, height=480)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 ── 決算書分析
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("決算書 取り込み・比較分析")

    stmts = list(db.get_all_financial_statements())

    col_left, col_right = st.columns([1, 2.2], gap="large")

    with col_left:
        st.markdown("**📁 取り込み済み決算書**")

        if stmts:
            df_list = pd.DataFrame([{
                "決算期":   s["fiscal_year"],
                "売上高":   f"¥{float(s['sales'] or 0)/10_000:.0f}万",
                "経常利益": f"¥{float(s['ordinary_profit'] or 0)/10_000:.0f}万",
                "取込元":   s["source_file"] or "—",
            } for s in stmts])
            st.dataframe(df_list, use_container_width=True, hide_index=True)

            all_years   = [s["fiscal_year"] for s in stmts]
            selected_years = st.multiselect(
                "比較する決算期を選択",
                options=all_years,
                default=all_years,
                key="fin_years",
            )

            st.divider()
            del_year = st.selectbox("削除する決算期", ["選択..."] + all_years)
            if del_year != "選択..." and st.button("🗑️ 削除", type="secondary"):
                target = next((s for s in stmts if s["fiscal_year"] == del_year), None)
                if target:
                    db.delete_financial_statement(target["id"])
                    st.success(f"削除: {del_year}")
                    st.cache_resource.clear()
                    st.rerun()
        else:
            st.info("決算書がまだありません")
            selected_years = []

        # PDF 取り込み
        st.divider()
        st.markdown("**📄 PDFを取り込む**")
        uploaded_pdf = st.file_uploader("決算書PDF", type=["pdf"], key="pdf_up")

        if uploaded_pdf:
            if st.button("🤖 Geminiで解析・取り込み", type="primary"):
                cur_key = st.session_state.get("api_key", "")
                if not cur_key:
                    st.error("サイドバーでAPIキーを設定してください")
                else:
                    with st.spinner("Gemini AIで解析中...（数秒かかります）"):
                        with tempfile.NamedTemporaryFile(
                                suffix=".pdf", delete=False) as tmp:
                            tmp.write(uploaded_pdf.read())
                            tmp_path = tmp.name
                        try:
                            data = process_pdf_with_gemini(tmp_path, cur_key)
                            db.add_financial_statement(data)
                            st.success(f"✅ 取り込み完了: {data.get('fiscal_year', uploaded_pdf.name)}")
                            st.cache_resource.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"エラー: {e}")
                        finally:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)

    with col_right:
        filtered = [s for s in stmts if s["fiscal_year"] in selected_years] \
                   if selected_years else stmts

        if not filtered:
            st.info("左側で表示する決算期を選択してください")
        else:
            years = [s["fiscal_year"] for s in filtered]

            chart_mode = st.radio(
                "グラフ種別",
                ["主要指標比較（棒）", "費用構造（積み上げ）", "利益率推移（折れ線）"],
                horizontal=True,
                key="fin_chart",
            )

            def v(s, key) -> float:
                return float(s[key] or 0) / 10_000

            # ─── 主要指標比較（棒） ───────────────────────────────────────────
            if chart_mode == "主要指標比較（棒）":
                metrics = [
                    ("売上高",   "sales"),
                    ("粗利",     "gross_profit"),
                    ("営業利益", "operating_profit"),
                    ("経常利益", "ordinary_profit"),
                    ("純利益",   "net_profit"),
                ]
                rows_list = [
                    {"指標": lbl, "決算期": s["fiscal_year"], "金額（万円）": v(s, key)}
                    for lbl, key in metrics for s in filtered
                ]
                fig = px.bar(
                    pd.DataFrame(rows_list),
                    x="決算期", y="金額（万円）", color="指標",
                    barmode="group", title="主要指標 年度別比較",
                    color_discrete_sequence=px.colors.qualitative.Plotly,
                )
                fig.update_yaxes(tickformat=",.0f")
                fig.update_layout(margin=dict(t=50))
                st.plotly_chart(fig, use_container_width=True)

            # ─── 費用構造（積み上げ） ─────────────────────────────────────────
            elif chart_mode == "費用構造（積み上げ）":
                df_cost = pd.DataFrame({
                    "決算期": years,
                    "売上原価": [v(s, "cost_of_goods") for s in filtered],
                    "固定費":   [v(s, "fixed_costs")   for s in filtered],
                    "変動費":   [v(s, "variable_costs") for s in filtered],
                    "販管費":   [v(s, "selling_expenses") + v(s, "general_admin_expenses")
                                 for s in filtered],
                })
                color_map = {
                    "売上原価": "#90caf9",
                    "固定費":   "#1a73e8",
                    "変動費":   "#fbbc04",
                    "販管費":   "#ea4335",
                }
                fig2 = go.Figure()
                for col_name, color in color_map.items():
                    fig2.add_trace(go.Bar(
                        x=df_cost["決算期"], y=df_cost[col_name],
                        name=col_name, marker_color=color,
                    ))
                sales_vals = [v(s, "sales") for s in filtered]
                fig2.add_trace(go.Scatter(
                    x=years, y=sales_vals,
                    name="売上高", mode="lines+markers",
                    marker=dict(size=10, color="black", symbol="diamond"),
                    line=dict(color="black", width=2),
                ))
                fig2.update_layout(
                    barmode="stack",
                    title="費用構造 積み上げ比較",
                    yaxis=dict(title="金額（万円）", tickformat=",.0f"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    margin=dict(t=60),
                )
                st.plotly_chart(fig2, use_container_width=True)

            # ─── 利益率推移（折れ線） ─────────────────────────────────────────
            else:
                def pct(s, num_key) -> float:
                    d = float(s["sales"] or 0)
                    return float(s[num_key] or 0) / d * 100 if d else 0

                df_pct = pd.DataFrame({
                    "決算期":     years,
                    "粗利率":     [pct(s, "gross_profit")    for s in filtered],
                    "営業利益率": [pct(s, "operating_profit") for s in filtered],
                    "経常利益率": [pct(s, "ordinary_profit")  for s in filtered],
                    "純利益率":   [pct(s, "net_profit")       for s in filtered],
                })
                fig3 = px.line(
                    df_pct.melt(id_vars="決算期", var_name="指標", value_name="利益率（%）"),
                    x="決算期", y="利益率（%）", color="指標",
                    markers=True, title="利益率 推移",
                    color_discrete_sequence=px.colors.qualitative.Plotly,
                )
                fig3.update_yaxes(ticksuffix="%")
                fig3.update_layout(
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    margin=dict(t=60),
                )
                st.plotly_chart(fig3, use_container_width=True)

            # ─── 貸借対照表 ───────────────────────────────────────────────────
            st.markdown("**貸借対照表**")
            bs_rows = []
            for lbl, key in [
                ("資産の部合計",   "total_assets"),
                ("負債の部合計",   "total_liabilities"),
                ("純資産の部合計", "net_assets"),
            ]:
                row = {"指標": lbl}
                for s in filtered:
                    row[s["fiscal_year"]] = f"¥{v(s, key):,.0f}万"
                bs_rows.append(row)
            st.dataframe(
                pd.DataFrame(bs_rows), use_container_width=True, hide_index=True
            )

            # ─── 数値比較表 ───────────────────────────────────────────────────
            st.markdown("**数値比較表**")

            def pretax(s) -> float:
                """税引前当期純利益 = 経常利益 + 特別利益 - 特別損失"""
                return (float(s["ordinary_profit"] or 0)
                        + float(s["extraordinary_income"] or 0)
                        - float(s["extraordinary_loss"] or 0))

            cmp_rows = []
            for lbl, key in [
                ("売上高",   "sales"),
                ("売上原価", "cost_of_goods"),
                ("営業利益", "operating_profit"),
                ("経常利益", "ordinary_profit"),
            ]:
                row = {"指標": lbl}
                for s in filtered:
                    row[s["fiscal_year"]] = f"¥{v(s, key):,.0f}万"
                cmp_rows.append(row)

            row = {"指標": "税引前当期純利益"}
            for s in filtered:
                row[s["fiscal_year"]] = f"¥{pretax(s)/10_000:,.0f}万"
            cmp_rows.append(row)

            row = {"指標": "当期純利益"}
            for s in filtered:
                row[s["fiscal_year"]] = f"¥{v(s, 'net_profit'):,.0f}万"
            cmp_rows.append(row)

            # ─── 内訳・利益率（参考） ───────────────────────────────────────────
            for lbl, key in [
                ("粗利",       "gross_profit"),
                ("固定費",     "fixed_costs"),
                ("変動費",     "variable_costs"),
                ("販売費",     "selling_expenses"),
                ("一般管理費", "general_admin_expenses"),
            ]:
                row = {"指標": lbl}
                for s in filtered:
                    row[s["fiscal_year"]] = f"¥{v(s, key):,.0f}万"
                cmp_rows.append(row)

            for lbl, num_key in [
                ("粗利率",     "gross_profit"),
                ("営業利益率", "operating_profit"),
                ("経常利益率", "ordinary_profit"),
            ]:
                row = {"指標": lbl}
                for s in filtered:
                    d = float(s["sales"] or 0)
                    n = float(s[num_key] or 0)
                    row[s["fiscal_year"]] = f"{n/d*100:.1f}%" if d else "—"
                cmp_rows.append(row)

            st.dataframe(
                pd.DataFrame(cmp_rows), use_container_width=True, hide_index=True
            )

    # ─── 出力 ─────────────────────────────────────────────────────────────────
    if stmts:
        st.divider()
        st.markdown("### 📤 決算書データの出力")

        def _rate(s, key):
            d = float(s["sales"] or 0)
            n = float(s[key] or 0)
            return round(n / d * 100, 1) if d else None

        def _pretax(s):
            return (float(s["ordinary_profit"] or 0)
                    + float(s["extraordinary_income"] or 0)
                    - float(s["extraordinary_loss"] or 0))

        EXPORT_ITEMS = [
            ("自",                  lambda s: s["period_start"] or ""),
            ("至",                  lambda s: s["period_end"] or ""),
            ("売上高",              lambda s: float(s["sales"] or 0)),
            ("売上原価",            lambda s: float(s["cost_of_goods"] or 0)),
            ("売上総利益（粗利）",   lambda s: float(s["gross_profit"] or 0)),
            ("固定費",              lambda s: float(s["fixed_costs"] or 0)),
            ("変動費",              lambda s: float(s["variable_costs"] or 0)),
            ("販売費",              lambda s: float(s["selling_expenses"] or 0)),
            ("一般管理費",          lambda s: float(s["general_admin_expenses"] or 0)),
            ("営業利益",            lambda s: float(s["operating_profit"] or 0)),
            ("営業外収益",          lambda s: float(s["non_operating_income"] or 0)),
            ("営業外費用",          lambda s: float(s["non_operating_expenses"] or 0)),
            ("経常利益",            lambda s: float(s["ordinary_profit"] or 0)),
            ("特別利益",            lambda s: float(s["extraordinary_income"] or 0)),
            ("特別損失",            lambda s: float(s["extraordinary_loss"] or 0)),
            ("税引前当期純利益",     _pretax),
            ("当期純利益",          lambda s: float(s["net_profit"] or 0)),
            ("資産の部合計",        lambda s: float(s["total_assets"] or 0)),
            ("負債の部合計",        lambda s: float(s["total_liabilities"] or 0)),
            ("純資産の部合計",      lambda s: float(s["net_assets"] or 0)),
            ("粗利率(%)",           lambda s: _rate(s, "gross_profit")),
            ("営業利益率(%)",       lambda s: _rate(s, "operating_profit")),
            ("経常利益率(%)",       lambda s: _rate(s, "ordinary_profit")),
            ("純利益率(%)",         lambda s: _rate(s, "net_profit")),
            ("取込元",              lambda s: s["source_file"] or ""),
        ]
        fn_map = dict(EXPORT_ITEMS)

        default_items = [
            "売上高", "売上原価", "売上総利益（粗利）",
            "営業利益", "経常利益", "当期純利益",
            "資産の部合計", "負債の部合計", "純資産の部合計",
        ]
        selected_items = st.multiselect(
            "出力する科目を選択",
            options=[lbl for lbl, _ in EXPORT_ITEMS],
            default=default_items,
            key="export_items",
        )

        export_targets = [s for s in stmts if s["fiscal_year"] in selected_years] \
                         if selected_years else stmts

        if not export_targets:
            st.info("左側で出力する決算期を選択してください")
        elif not selected_items:
            st.info("出力する科目を選択してください")
        else:
            export_rows = []
            for s in export_targets:
                row = {"決算期": s["fiscal_year"]}
                for lbl in selected_items:
                    row[lbl] = fn_map[lbl](s)
                export_rows.append(row)

            df_export = pd.DataFrame(export_rows)
            st.dataframe(df_export, use_container_width=True, hide_index=True)

            csv_bytes = df_export.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 CSVダウンロード",
                data=csv_bytes,
                file_name="決算書データ.csv",
                mime="text/csv",
            )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 ── 担当者別売上実績
# ═══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("担当者別売上実績")

    all_reports = list(db.get_all_sales_reports())

    # ── サイドパネル：レポート選択 & PDF アップロード ─────────────────────
    col_side, col_main = st.columns([1, 2.5], gap="large")

    with col_side:
        st.markdown("**📁 取り込み済みレポート**")

        if all_reports:
            report_options = {f"{r['period']} [{r['report_type']}]": r["id"]
                              for r in all_reports}
            selected_labels = st.multiselect(
                "表示するレポートを選択",
                options=list(report_options.keys()),
                default=list(report_options.keys()),
                key="rep_report_sel",
            )
            selected_ids = [report_options[lbl] for lbl in selected_labels]

            st.divider()
            del_label = st.selectbox(
                "削除するレポート",
                ["選択..."] + list(report_options.keys()),
                key="rep_del_sel",
            )
            if del_label != "選択..." and st.button("🗑️ 削除", type="secondary", key="rep_del_btn"):
                db.delete_sales_report(report_options[del_label])
                st.success(f"削除: {del_label}")
                st.cache_resource.clear()
                st.rerun()
        else:
            selected_ids = []
            st.info("レポートがありません")

        # ── PDF アップロード ────────────────────────────────────────────
        st.divider()
        st.markdown("**📄 PDFを取り込む**")
        st.caption("担当者別商品別 または 担当者別得意先別 売上実績表PDFをアップロードしてください。")

        uploaded_sales_pdf = st.file_uploader(
            "売上実績表 PDF",
            type=["pdf"],
            key="sales_pdf_up",
        )
        if uploaded_sales_pdf:
            rtype_hint = detect_report_type(uploaded_sales_pdf.name)
            rtype_labels = {
                "product":  "担当者別商品別",
                "customer": "担当者別得意先別",
                "unknown":  "自動判定",
            }
            st.caption(f"判定種別: {rtype_labels.get(rtype_hint, '不明')}")

            if st.button("🤖 Geminiで解析・取り込み", type="primary", key="sales_pdf_btn"):
                cur_key = st.session_state.get("api_key", "")
                if not cur_key:
                    st.error("サイドバーでGemini API Keyを設定してください")
                else:
                    with st.spinner("Gemini AIで解析中...（大きなPDFは数十秒かかります）"):
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                            tmp.write(uploaded_sales_pdf.read())
                            tmp_path = tmp.name
                        try:
                            result = process_sales_report_pdf(tmp_path, cur_key, rtype_hint)
                            period  = result.get("period", uploaded_sales_pdf.name)
                            rtype   = result.get("report_type", rtype_hint)
                            rows    = result.get("rows", [])

                            report_id = db.add_sales_report(
                                period, "", "", rtype, uploaded_sales_pdf.name
                            )

                            if rtype == "product":
                                batch = [
                                    (r.get("rep_code", ""),
                                     r.get("rep_name", ""),
                                     r.get("product_code", ""),
                                     r.get("product_name", ""),
                                     r.get("unit", ""),
                                     float(r.get("quantity", 0) or 0),
                                     float(r.get("sales_amount", 0) or 0),
                                     float(r.get("gross_profit", 0) or 0),
                                     float(r.get("gross_profit_rate", 0) or 0))
                                    for r in rows
                                ]
                                db.add_rep_product_sales_batch(report_id, batch)
                            else:
                                batch = [
                                    (r.get("rep_code", ""),
                                     r.get("rep_name", ""),
                                     r.get("customer_code", ""),
                                     r.get("customer_name", ""),
                                     float(r.get("sales_amount", 0) or 0),
                                     float(r.get("gross_profit", 0) or 0),
                                     float(r.get("gross_profit_rate", 0) or 0))
                                    for r in rows
                                ]
                                db.add_rep_customer_sales_batch(report_id, batch)

                            st.success(
                                f"✅ 取り込み完了: {period}（{len(rows):,}行）"
                            )
                            st.cache_resource.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"エラー: {e}")
                        finally:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)

    # ── メインコンテンツ ────────────────────────────────────────────────────
    with col_main:
        # 商品別サマリー取得
        prod_summary = list(db.get_rep_product_summary(selected_ids if selected_ids else None))
        cust_summary = list(db.get_rep_customer_summary(selected_ids if selected_ids else None))

        if not prod_summary and not cust_summary:
            st.info("データがありません。左のパネルからPDFを取り込んでください。")
        else:
            # ── KPI カード ─────────────────────────────────────────────
            total_sales = sum(float(r["total_sales"] or 0) for r in prod_summary)
            top_rep     = prod_summary[0]["rep_name"] if prod_summary else "—"
            rep_count   = len(prod_summary)

            k1, k2, k3 = st.columns(3)
            k1.metric("総売上", f"¥{total_sales/1_000_000:.1f}百万")
            k2.metric("担当者数", rep_count)
            k3.metric("トップ担当者", top_rep)

            st.divider()

            # ── 担当者別売上比較（横棒グラフ） ─────────────────────────
            if prod_summary:
                df_prod_sum = pd.DataFrame([dict(r) for r in prod_summary])
                df_prod_sum["total_sales"] = df_prod_sum["total_sales"].astype(float)

                fig_bar = px.bar(
                    df_prod_sum.sort_values("total_sales"),
                    x="total_sales",
                    y="rep_name",
                    orientation="h",
                    title="担当者別 純売上額",
                    labels={"total_sales": "純売上額（円）", "rep_name": "担当者"},
                    color="total_sales",
                    color_continuous_scale="Blues",
                    text=df_prod_sum.sort_values("total_sales")["total_sales"].map(
                        lambda v: f"¥{v/1_000_000:.1f}M"
                    ),
                )
                fig_bar.update_traces(textposition="outside")
                fig_bar.update_xaxes(tickformat=",.0f")
                fig_bar.update_coloraxes(showscale=False)
                fig_bar.update_layout(margin=dict(l=0, r=60, t=40, b=0))
                st.plotly_chart(fig_bar, use_container_width=True)

                # ── 担当者別シェア（円グラフ） ────────────────────────
                with st.expander("担当者別売上シェア（円グラフ）"):
                    fig_pie = px.pie(
                        df_prod_sum,
                        values="total_sales",
                        names="rep_name",
                        title="担当者別 売上シェア",
                        hole=0.35,
                    )
                    fig_pie.update_traces(textinfo="percent+label", textposition="inside")
                    fig_pie.update_layout(margin=dict(l=0, r=0, t=40, b=0))
                    st.plotly_chart(fig_pie, use_container_width=True)

            st.divider()

            # ── 担当者別売上一覧テーブル ──────────────────────────────
            view_mode = st.radio(
                "詳細表示",
                ["商品別売上", "得意先別売上"],
                horizontal=True,
                key="rep_view_mode",
            )

            # 担当者フィルター
            all_rep_names = sorted({r["rep_name"] for r in (prod_summary + cust_summary)})
            sel_rep = st.selectbox(
                "担当者で絞り込み",
                ["全担当者"] + all_rep_names,
                key="rep_filter",
            )
            filter_code = None
            if sel_rep != "全担当者":
                # rep_code を特定
                for r in (prod_summary + cust_summary):
                    if r["rep_name"] == sel_rep:
                        filter_code = r["rep_code"]
                        break

            if view_mode == "商品別売上":
                detail_rows = list(db.get_rep_product_detail(
                    selected_ids if selected_ids else None, filter_code
                ))
                if not detail_rows:
                    st.info("商品別データがありません。PDFを取り込んでください。")
                else:
                    df_detail = pd.DataFrame([dict(r) for r in detail_rows])
                    df_detail["sales_amount"]  = df_detail["sales_amount"].astype(float)
                    df_detail["gross_profit"]  = df_detail["gross_profit"].astype(float)
                    df_detail["quantity"]      = df_detail["quantity"].astype(float)

                    # 担当者ごとに集計した上位商品グラフ
                    top_n = df_detail[df_detail["product_code"] != "summary"].nlargest(15, "sales_amount")
                    if not top_n.empty:
                        fig_prod = px.bar(
                            top_n.sort_values("sales_amount"),
                            x="sales_amount",
                            y="product_name",
                            color="rep_name",
                            orientation="h",
                            title="商品別売上 TOP15",
                            labels={"sales_amount": "売上（円）", "product_name": "商品名",
                                    "rep_name": "担当者"},
                        )
                        fig_prod.update_xaxes(tickformat=",.0f")
                        fig_prod.update_layout(margin=dict(l=0, r=0, t=40, b=0))
                        st.plotly_chart(fig_prod, use_container_width=True)

                    # テーブル表示
                    st.markdown(f"**商品別売上一覧** （{len(df_detail):,}件）")
                    df_show = pd.DataFrame({
                        "担当者":   df_detail["rep_name"],
                        "商品コード": df_detail["product_code"],
                        "商品名":   df_detail["product_name"],
                        "単位":     df_detail["unit"],
                        "数量":     df_detail["quantity"].map(lambda v: f"{v:,.2f}"),
                        "純売上額": df_detail["sales_amount"].map(lambda v: f"¥{v:,.0f}"),
                        "粗利額":   df_detail["gross_profit"].map(
                            lambda v: f"¥{v:,.0f}" if v != 0 else "—"),
                        "粗利率":   df_detail["gross_profit_rate"].map(
                            lambda v: f"{v:.1f}%" if v != 0 else "—"),
                    })
                    st.dataframe(df_show, use_container_width=True,
                                 hide_index=True, height=480)

            else:  # 得意先別売上
                cust_rows = list(db.get_rep_customer_detail(
                    selected_ids if selected_ids else None, filter_code
                ))
                if not cust_rows:
                    st.info("得意先別データがありません。担当者別得意先別売上実績表PDFを取り込んでください。")
                else:
                    df_cust = pd.DataFrame([dict(r) for r in cust_rows])
                    df_cust["sales_amount"] = df_cust["sales_amount"].astype(float)
                    df_cust["gross_profit"] = df_cust["gross_profit"].astype(float)

                    top_cust = df_cust.nlargest(15, "sales_amount")
                    fig_cust = px.bar(
                        top_cust.sort_values("sales_amount"),
                        x="sales_amount",
                        y="customer_name",
                        color="rep_name",
                        orientation="h",
                        title="得意先別売上 TOP15",
                        labels={"sales_amount": "売上（円）", "customer_name": "得意先",
                                "rep_name": "担当者"},
                    )
                    fig_cust.update_xaxes(tickformat=",.0f")
                    fig_cust.update_layout(margin=dict(l=0, r=0, t=40, b=0))
                    st.plotly_chart(fig_cust, use_container_width=True)

                    st.markdown(f"**得意先別売上一覧** （{len(df_cust):,}件）")
                    df_cust_show = pd.DataFrame({
                        "担当者":     df_cust["rep_name"],
                        "得意先コード": df_cust["customer_code"],
                        "得意先名":   df_cust["customer_name"],
                        "純売上額":   df_cust["sales_amount"].map(lambda v: f"¥{v:,.0f}"),
                        "粗利額":     df_cust["gross_profit"].map(
                            lambda v: f"¥{v:,.0f}" if v != 0 else "—"),
                        "粗利率":     df_cust["gross_profit_rate"].map(
                            lambda v: f"{v:.1f}%" if v != 0 else "—"),
                    })
                    st.dataframe(df_cust_show, use_container_width=True,
                                 hide_index=True, height=480)
