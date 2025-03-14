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
    return pd.DataFrame(records)

# --- 抽出されたデータから「部署」と各役職のセルにある氏名を統合する関数 ---
def transform_extracted_data(df):
    # 対象となる役職カラムのリスト（必要に応じて調整してください）
    roles = ["部長", "課長・主幹", "課長補佐", "係長・相当職", "職員", "単労職", "会計年度職員", "臨時職員"]
    # 「部署」カラムの存在チェック
    if "部署" not in df.columns:
        st.error("部署カラムが存在しません。")
        return pd.DataFrame()
    # melt処理により、各役職カラムから「氏名」を抽出し、1列に統合
    df_melt = df.melt(id_vars=["部署"], value_vars=roles, var_name="役職", value_name="氏名")
    # 氏名が空または欠損している行を除去
    df_melt = df_melt[df_melt["氏名"].notna() & (df_melt["氏名"].str.strip() != "")]
    return df_melt

# --- 前年度と現年度の変換済みデータから、異動（部署変更）を追跡する関数 ---
def track_transfers(df_prev, df_curr):
    # 「氏名」をキーにマージ（各ファイルで同一の氏名で登録されていることが前提）
    if "氏名" not in df_prev.columns or "氏名" not in df_curr.columns:
        st.error("氏名カラムが不足しています。")
        return pd.DataFrame()
    df_merged = pd.merge(df_prev, df_curr, on="氏名", suffixes=('_prev', '_curr'))
    # マージ後の「部署」カラムの存在確認
    if "部署_prev" not in df_merged.columns or "部署_curr" not in df_merged.columns:
        st.error("部署カラムが不足しています。")
        return pd.DataFrame()
    # 前年度と現年度で部署が異なるレコード（＝異動している）を抽出
    df_transfers = df_merged[df_merged["部署_prev"] != df_merged["部署_curr"]]
    return df_transfers[["氏名", "部署_prev", "部署_curr"]].reset_index(drop=True)

# --- Streamlit アプリのUI ---
st.set_page_config(page_title="職員異動追跡アプリ", layout="wide")
st.title("職員異動追跡アプリ")
st.markdown(
    """
    このアプリは、前年分と現年度のPDFファイルをそれぞれアップロードすることで、
    各職員がどこからどこへ部署異動したかを追跡します。

    ※ 各PDFには「部署」カラムが存在し、職員の氏名は
    「部長」「課長・主幹」「課長補佐」「係長・相当職」
    「職員」「単労職」「会計年度職員」「臨時職員」のいずれかのカラムに記載されています。
    """
)

# サイドバーに前年度用、現年度用のファイルアップロードエリアを設置
st.sidebar.header("前年分のPDFファイルアップロード")
prev_file = st.sidebar.file_uploader("前年分のPDFを選択", type="pdf", key="prev")

st.sidebar.header("現年度のPDFファイルアップロード")
curr_file = st.sidebar.file_uploader("現年度のPDFを選択", type="pdf", key="curr")

if prev_file and curr_file:
    st.info("PDFファイルを読み込み中...")
    # PDFからデータ抽出
    df_prev_raw = extract_data_from_pdf(prev_file)
    df_curr_raw = extract_data_from_pdf(curr_file)
    
    st.subheader("前年分データ（抽出結果）")
    st.dataframe(df_prev_raw)
    st.subheader("現年度データ（抽出結果）")
    st.dataframe(df_curr_raw)
    
    st.info("データ変換中（各役職カラムから氏名を統合）...")
    df_prev_transformed = transform_extracted_data(df_prev_raw)
    df_curr_transformed = transform_extracted_data(df_curr_raw)
    
    st.subheader("前年分データ（変換後）")
    st.dataframe(df_prev_transformed)
    st.subheader("現年度データ（変換後）")
    st.dataframe(df_curr_transformed)
    
    st.info("異動追跡中...")
    df_transfers = track_transfers(df_prev_transformed, df_curr_transformed)
    
    if df_transfers.empty:
        st.info("部署異動が検出されませんでした。")
    else:
        st.subheader("【異動追跡結果】")
        st.dataframe(df_transfers)
else:
    st.warning("前年分と現年度のPDFファイルをそれぞれアップロードしてください。")
