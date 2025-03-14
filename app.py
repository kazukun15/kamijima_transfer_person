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

# --- 抽出されたデータから、部署と各役職のセルにある氏名を統合する変換関数 ---
def transform_extracted_data(df):
    # 対象となる役職カラムのリスト
    roles = ["部長", "課長・主幹", "課長補佐", "係長・相当職", "職員", "単労職", "会計年度職員", "臨時職員"]
    # 「部署」カラムが存在するかチェック
    if "部署" not in df.columns:
        st.error("部署カラムが存在しません。")
        return pd.DataFrame()
    # melt処理により、各役職カラムから「氏名」を抽出（新たな列「役職」と「氏名」に変換）
    df_melt = df.melt(id_vars=["部署"], value_vars=roles, var_name="役職", value_name="氏名")
    # 氏名が空または欠損している行を除去
    df_melt = df_melt[df_melt["氏名"].notna() & (df_melt["氏名"].str.strip() != "")]
    return df_melt

# --- 前年度と今年度の変換済みデータから、異動（部署変更）を追跡する関数 ---
def track_transfers(df_prev, df_curr):
    # 必要なカラムの存在チェック
    missing_cols = [col for col in ["氏名", "部署"] if col not in df_prev.columns or col not in df_curr.columns]
    if missing_cols:
        st.error(f"必要なカラムが不足しています: {missing_cols}")
        return pd.DataFrame()
    # 「氏名」をキーにマージ（※各PDFで同じ職員が同一の氏名で登録されていることが前提）
    df_merged = pd.merge(df_prev, df_curr, on="氏名", suffixes=('_prev', '_curr'))
    # 前年度と今年度の部署が異なる場合のみ抽出
    df_transfers = df_merged[df_merged["部署_prev"] != df_merged["部署_curr"]]
    # 表示用に必要なカラムのみを抽出
    df_result = df_transfers[["氏名", "部署_prev", "部署_curr"]].reset_index(drop=True)
    return df_result

# --- Streamlit アプリのUI ---
st.set_page_config(page_title="職員異動追跡アプリ", layout="wide")
st.title("職員異動追跡アプリ")
st.markdown(
    """
    このアプリは、前年度と今年度のPDFから抽出した職員データを比較し、
    各職員がどこからどこへ異動（部署変更）したかを追跡します。
    
    各PDFには「部署」カラムが存在し、職員の氏名は
    「部長」「課長・主幹」「課長補佐」「係長・相当職」「職員」「単労職」
    「会計年度職員」「臨時職員」のいずれかのカラムに記載されています。
    
    サイドバーから前年度と今年度のPDFファイルをアップロードしてください。
    """
)

# サイドバーでPDFファイルをアップロード
st.sidebar.header("PDFファイルアップロード")
uploaded_prev = st.sidebar.file_uploader("前年度のPDFを選択", type="pdf", key="prev")
uploaded_curr = st.sidebar.file_uploader("今年度のPDFを選択", type="pdf", key="curr")

if uploaded_prev and uploaded_curr:
    st.info("PDFファイルの読み込み中...")
    df_prev_raw = extract_data_from_pdf(uploaded_prev)
    df_curr_raw = extract_data_from_pdf(uploaded_curr)
    
    st.subheader("前年度データ（抽出結果）")
    st.dataframe(df_prev_raw)
    st.subheader("今年度データ（抽出結果）")
    st.dataframe(df_curr_raw)
    
    st.info("データ変換中（役職カラムから氏名を抽出）...")
    df_prev_transformed = transform_extracted_data(df_prev_raw)
    df_curr_transformed = transform_extracted_data(df_curr_raw)
    
    st.subheader("前年度データ（変換後）")
    st.dataframe(df_prev_transformed)
    st.subheader("今年度データ（変換後）")
    st.dataframe(df_curr_transformed)
    
    st.info("異動の追跡中...")
    df_transfers = track_transfers(df_prev_transformed, df_curr_transformed)
    
    if not df_transfers.empty:
        st.subheader("【異動追跡結果】")
        st.dataframe(df_transfers)
    else:
        st.info("異動（部署の変更）が検出されませんでした。")
else:
    st.warning("前年度と今年度のPDFファイルをサイドバーからアップロードしてください。")
