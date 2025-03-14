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

# --- 抽出されたデータから「部署」と各役職のセルにある氏名を統合する変換関数 ---
def transform_extracted_data(df):
    # 対象となる役職カラムのリスト
    roles = ["部長", "課長・主幹", "課長補佐", "係長・相当職", "職員", "単労職", "会計年度職員", "臨時職員"]
    # 「部署」カラムの存在チェック
    if "部署" not in df.columns:
        st.error("部署カラムが存在しません。")
        return pd.DataFrame()
    # melt処理により、各役職カラムから「氏名」を抽出
    df_melt = df.melt(id_vars=["部署"], value_vars=roles, var_name="役職", value_name="氏名")
    # 氏名が空または欠損している行を除去
    df_melt = df_melt[df_melt["氏名"].notna() & (df_melt["氏名"].str.strip() != "")]
    return df_melt

# --- 前年度と今年度の変換済みデータから、異動（部署変更）を追跡する関数 ---
def track_transfers(df_prev, df_curr):
    # 「氏名」をキーに前年度と今年度のデータをマージ
    if "氏名" not in df_prev.columns or "氏名" not in df_curr.columns:
        st.error("氏名カラムが不足しています。")
        return pd.DataFrame()
    df_merged = pd.merge(df_prev, df_curr, on="氏名", suffixes=('_prev', '_curr'))
    # 「部署」カラムがマージ後に _prev, _curr として存在するかチェック
    if "部署_prev" not in df_merged.columns or "部署_curr" not in df_merged.columns:
        st.error("部署カラムが不足しています。")
        return pd.DataFrame()
    # 部署が異なる行を抽出（＝異動している）
    df_transfers = df_merged[df_merged["部署_prev"] != df_merged["部署_curr"]]
    # 表示用に必要なカラムのみを選択
    df_result = df_transfers[["氏名", "部署_prev", "部署_curr"]].reset_index(drop=True)
    return df_result

# --- Streamlit アプリのUI ---
st.set_page_config(page_title="職員異動追跡アプリ", layout="wide")
st.title("職員異動追跡アプリ")
st.markdown(
    """
    このアプリは、アップロードした複数のPDFファイルから職員データを抽出し、
    各年（例：令和5年、平成30年、平成31年など）の異動（部署変更）を追跡します。
    
    ※ 各PDFには「部署」カラムが存在し、職員の氏名は「部長」「課長・主幹」「課長補佐」
    「係長・相当職」「職員」「単労職」「会計年度職員」「臨時職員」のいずれかのカラムに記載されています。
    """
)

# サイドバーで複数のPDFファイルをアップロード
uploaded_files = st.sidebar.file_uploader("PDFファイルをアップロードしてください", type="pdf", accept_multiple_files=True)

if uploaded_files and len(uploaded_files) >= 2:
    # アップロードされたファイル名一覧を取得
    file_names = [file.name for file in uploaded_files]
    st.sidebar.markdown("### 比較するファイルを選択")
    file_prev_name = st.sidebar.selectbox("前年度のファイル", file_names, index=0)
    file_curr_name = st.sidebar.selectbox("今年度のファイル", file_names, index=1)
    
    # 選択されたファイルオブジェクトを取得
    file_prev = next(file for file in uploaded_files if file.name == file_prev_name)
    file_curr = next(file for file in uploaded_files if file.name == file_curr_name)
    
    st.info("PDFファイルの読み込み中...")
    df_prev_raw = extract_data_from_pdf(file_prev)
    df_curr_raw = extract_data_from_pdf(file_curr)
    
    st.subheader("前年度データ（抽出結果）")
    st.dataframe(df_prev_raw)
    st.subheader("今年度データ（抽出結果）")
    st.dataframe(df_curr_raw)
    
    st.info("データ変換中（各役職カラムから氏名を統合）...")
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
        st.info("異動（部署変更）が検出されませんでした。")
else:
    st.warning("2つ以上のPDFファイルをアップロードしてください。")
