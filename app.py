import streamlit as st
import pandas as pd
import pdfplumber

# --- PDFからテーブルデータを抽出する関数 ---
def extract_data_from_pdf(pdf_file):
    records = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                # ヘッダー行の各要素の前後の空白を除去
                header = [col.strip() if isinstance(col, str) else col for col in table[0]]
                for row in table[1:]:
                    # 各セルの余分な空白をトリム
                    row = [cell.strip() if isinstance(cell, str) else cell for cell in row]
                    # ヘッダーとセル数が一致する場合のみレコードに追加
                    if len(row) == len(header):
                        records.append(dict(zip(header, row)))
    df = pd.DataFrame(records)
    return df

# --- 異動（部署の変更）を追跡する関数 ---
def track_transfers(df_prev, df_curr):
    # PDFによっては「名前」と「氏名」などの表記が異なるため、必要に応じてリネーム
    if "名前" in df_prev.columns and "氏名" not in df_prev.columns:
        df_prev.rename(columns={"名前": "氏名"}, inplace=True)
    if "名前" in df_curr.columns and "氏名" not in df_curr.columns:
        df_curr.rename(columns={"名前": "氏名"}, inplace=True)
    
    # 前年度・今年度で必要なカラムが存在するかチェック（ここでは「氏名」と「部署」を前提）
    required_columns = ["氏名", "部署"]
    missing_cols = [col for col in required_columns if col not in df_prev.columns or col not in df_curr.columns]
    if missing_cols:
        st.error(f"必要なカラムが不足しています: {missing_cols}")
        return pd.DataFrame()
    
    # 「氏名」をキーに前年度と今年度のデータをマージ
    df_merged = pd.merge(df_prev, df_curr, on="氏名", suffixes=('_prev', '_curr'))
    # 異動している（部署が変更された）行のみ抽出
    df_transfers = df_merged[df_merged["部署_prev"] != df_merged["部署_curr"]]
    # 表示用に必要なカラムを選択し、インデックスをリセット
    df_result = df_transfers[["氏名", "部署_prev", "部署_curr"]].reset_index(drop=True)
    return df_result

# --- Streamlit アプリのUI ---
st.set_page_config(page_title="職員異動追跡アプリ", layout="wide")
st.title("職員異動追跡アプリ")
st.markdown(
    """
    このアプリは、前年度と今年度のPDFから抽出した職員データを比較し、
    各職員がどこからどこへ異動（部署変更）したかを追跡します。
    サイドバーから前年度と今年度のPDFファイルをアップロードしてください。
    """
)

# サイドバーでPDFファイルをアップロード
st.sidebar.header("PDFファイルアップロード")
uploaded_prev = st.sidebar.file_uploader("前年度のPDFを選択", type="pdf", key="prev")
uploaded_curr = st.sidebar.file_uploader("今年度のPDFを選択", type="pdf", key="curr")

if uploaded_prev and uploaded_curr:
    st.info("PDFファイルの読み込み中...")
    df_prev = extract_data_from_pdf(uploaded_prev)
    df_curr = extract_data_from_pdf(uploaded_curr)
    
    st.subheader("前年度データ（抽出結果）")
    st.dataframe(df_prev)
    st.subheader("今年度データ（抽出結果）")
    st.dataframe(df_curr)
    
    st.info("異動の追跡中...")
    df_transfers = track_transfers(df_prev, df_curr)
    
    if not df_transfers.empty:
        st.subheader("【異動追跡結果】")
        st.dataframe(df_transfers)
    else:
        st.info("異動（部署の変更）が検出されませんでした。")
else:
    st.warning("前年度と今年度のPDFファイルをサイドバーからアップロードしてください。")
