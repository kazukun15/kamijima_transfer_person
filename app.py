import streamlit as st
import pandas as pd
import pdfplumber
import tempfile
import camelot
import os
from io import StringIO

# --- Camelotを用いてPDFからテーブルデータを抽出する関数 ---
def extract_data_from_pdf_camelot(pdf_file):
    # 一時ファイルに保存（Camelotはファイルパスで動作します）
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(pdf_file.read())
        tmp_path = tmp_file.name

    try:
        tables = camelot.read_pdf(tmp_path, pages='all', flavor='stream')
    except Exception as e:
        st.error(f"Camelotでの抽出中にエラーが発生しました: {e}")
        os.remove(tmp_path)
        return pd.DataFrame()
    
    os.remove(tmp_path)  # 一時ファイルの削除

    if tables.n == 0:
        st.error("Camelotがテーブルを検出できませんでした。")
        return pd.DataFrame()
    
    # 複数テーブルが検出された場合は結合
    df_list = [table.df for table in tables]
    df_merged = pd.concat(df_list, ignore_index=True)
    
    # 最初の行をヘッダーとして設定（レイアウトに応じて調整が必要）
    header = df_merged.iloc[0]
    df = pd.DataFrame(df_merged.iloc[1:].values, columns=header)
    return df

# --- PDFからテーブルデータを抽出する（Camelotが使えない場合はpdfplumberも試す） ---
def extract_data_from_pdf(pdf_file):
    # まずCamelotで抽出を試みる
    df = extract_data_from_pdf_camelot(pdf_file)
    if df.empty:
        st.info("Camelotでの抽出ができなかったため、pdfplumberで試みます。")
        pdf_file.seek(0)  # ファイルポインタを先頭に戻す
        records = []
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    header = [col.strip() if isinstance(col, str) else col for col in table[0]]
                    for row in table[1:]:
                        row = [cell.strip() if isinstance(cell, str) else cell for cell in row]
                        if len(row) == len(header):
                            records.append(dict(zip(header, row)))
        df = pd.DataFrame(records)
    return df

# --- 抽出されたデータから「課名」と各役職のセルにある氏名を統合する関数 ---
def transform_extracted_data(df):
    roles = ["部長", "課長・主幹", "課長補佐", "係長・相当職", 
             "職員", "単労職", "会計年度職員", "臨時職員"]
    if "課名" not in df.columns:
        st.error("抽出されたデータに『課名』カラムが見つかりませんでした。抽出処理を確認してください。")
        return pd.DataFrame()
    df_melt = df.melt(id_vars=["課名"], value_vars=roles, var_name="役職", value_name="氏名")
    df_melt = df_melt[df_melt["氏名"].notna() & (df_melt["氏名"].str.strip() != "")]
    return df_melt

# --- 前年分と現年度の変換済みデータ（CSVから再読み込みしたもの）から、異動（課名変更）を追跡する関数 ---
def track_transfers(df_prev, df_curr):
    if "氏名" not in df_prev.columns or "氏名" not in df_curr.columns:
        st.error("氏名カラムが不足しています。")
        return pd.DataFrame()
    df_merged = pd.merge(df_prev, df_curr, on="氏名", suffixes=('_prev', '_curr'))
    if "課名_prev" not in df_merged.columns or "課名_curr" not in df_merged.columns:
        st.error("課名カラムが不足しています。")
        return pd.DataFrame()
    df_transfers = df_merged[df_merged["課名_prev"] != df_merged["課名_curr"]]
    return df_transfers[["氏名", "課名_prev", "課名_curr"]].reset_index(drop=True)

# --- Streamlit アプリのUI ---
st.set_page_config(page_title="職員異動追跡アプリ", layout="wide")
st.title("職員異動追跡アプリ")
st.markdown(
    """
    このアプリは、前年分と現年度のPDFファイルをそれぞれアップロードすることで、
    各職員がどこからどこへ課名変更（異動）したかを追跡し、
    CSVに変換したデータを使って分析を実施します。

    ※ 各PDFには「課名」カラムが存在し、職員の氏名は「部長」「課長・主幹」
    「課長補佐」「係長・相当職」「職員」「単労職」「会計年度職員」「臨時職員」
    のいずれかのカラムに記載されています。
    """
)

st.sidebar.header("前年分のPDFファイルアップロード")
prev_file = st.sidebar.file_uploader("前年分のPDFを選択", type="pdf", key="prev")

st.sidebar.header("現年度のPDFファイルアップロード")
curr_file = st.sidebar.file_uploader("現年度のPDFを選択", type="pdf", key="curr")

if prev_file and curr_file:
    st.info("PDFファイルを読み込み中...")
    # PDFからデータ抽出
    df_prev_raw = extract_data_from_pdf(prev_file)
    curr_file.seek(0)
    df_curr_raw = extract_data_from_pdf(curr_file)
    
    # すべてのセルを文字列に変換（applymap を使用）
    df_prev_raw = df_prev_raw.applymap(lambda x: "" if pd.isna(x) else str(x))
    df_curr_raw = df_curr_raw.applymap(lambda x: "" if pd.isna(x) else str(x))
    
    st.subheader("前年分データ（抽出結果）")
    st.dataframe(df_prev_raw)
    st.subheader("現年度データ（抽出結果）")
    st.dataframe(df_curr_raw)
    
    st.info("データ変換中（各役職カラムから氏名を統合）...")
    df_prev_transformed = transform_extracted_data(df_prev_raw)
    df_curr_transformed = transform_extracted_data(df_curr_raw)
    
    # 変換後も全セルを文字列に変換
    df_prev_transformed = df_prev_transformed.applymap(lambda x: "" if pd.isna(x) else str(x))
    df_curr_transformed = df_curr_transformed.applymap(lambda x: "" if pd.isna(x) else str(x))
    
    st.subheader("前年分データ（変換後）")
    st.dataframe(df_prev_transformed)
    st.subheader("現年度データ（変換後）")
    st.dataframe(df_curr_transformed)
    
    st.info("CSV形式に変換して再読み込み中...")
    csv_prev = df_prev_transformed.to_csv(index=False)
    csv_curr = df_curr_transformed.to_csv(index=False)
    
    df_prev_csv = pd.read_csv(StringIO(csv_prev))
    df_curr_csv = pd.read_csv(StringIO(csv_curr))
    
    st.subheader("CSVから再読み込みした前年分データ")
    st.dataframe(df_prev_csv)
    st.subheader("CSVから再読み込みした現年度データ")
    st.dataframe(df_curr_csv)
    
    st.info("異動追跡中...")
    df_transfers = track_transfers(df_prev_csv, df_curr_csv)
    
    if df_transfers.empty:
        st.info("課名異動が検出されませんでした。")
    else:
        st.subheader("【異動追跡結果】")
        st.dataframe(df_transfers)
        csv_transfers = df_transfers.to_csv(index=False)
        st.download_button(
            label="異動分析結果をCSVでダウンロード",
            data=csv_transfers,
            file_name="transfers_analysis.csv",
            mime="text/csv"
        )
else:
    st.warning("前年分と現年度のPDFファイルをそれぞれアップロードしてください。")
