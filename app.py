import streamlit as st
import pandas as pd
import pdfplumber
import requests
import json
import os  # ファイルの存在確認に使用

# st.secretsからGemini APIキーを取得
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# --- PDFからテーブルデータを抽出する関数 ---
def extract_data_from_pdf(pdf_file):
    records = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                header = table[0]
                for row in table[1:]:
                    if len(row) == len(header):
                        records.append(dict(zip(header, row)))
    df = pd.DataFrame(records)
    return df

# --- Gemini APIを呼び出し、テキスト正規化を行う関数 ---
def call_gemini_normalization(text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [{"text": f"以下のテキストを正規化してください: {text}"}]
        }]
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        result = response.json()
        normalized_text = result.get("contents", [{}])[0].get("parts", [{}])[0].get("text", "")
        return normalized_text
    else:
        st.error(f"Gemini API エラー: {response.status_code} {response.text}")
        return text

# --- DataFrameの指定カラムに対して正規化処理を実行する関数 ---
def normalize_dataframe(df, columns):
    df_normalized = df.copy()
    for col in columns:
        if col in df_normalized.columns:
            # 各セルが文字列の場合、Geminiで正規化を実施
            df_normalized[col] = df_normalized[col].apply(lambda x: call_gemini_normalization(x) if isinstance(x, str) else x)
    return df_normalized

# --- 前年度と今年度の差分（例：部署変更）を計算する関数 ---
def compute_diff(df_prev, df_curr):
    merge_cols = ['氏名']
    # マージに必要なキーが存在するか確認
    missing_cols = [col for col in merge_cols if col not in df_prev.columns or col not in df_curr.columns]
    if missing_cols:
        st.error(f"マージに必要なカラムが存在しません: {missing_cols}")
        return pd.DataFrame()
    df_merged = pd.merge(df_prev, df_curr, on=merge_cols, suffixes=('_prev', '_curr'))
    # 例として「部署」列の値が異なる行を抽出
    if '部署_prev' in df_merged.columns and '部署_curr' in df_merged.columns:
        df_diff = df_merged[df_merged['部署_prev'] != df_merged['部署_curr']]
    else:
        st.error("【部署】列が存在しません。")
        df_diff = pd.DataFrame()
    return df_diff

# --- スタイル関数: 状態に応じた色分け（例：異動→青、新規→赤、派遣→緑、休職→紫、昇格は枠線付き） ---
def style_row(row):
    status = row.get('状態', '')
    styles = []
    if status == "異動":
        styles = ['color: blue'] * len(row)
    elif status == "新規":
        styles = ['color: red'] * len(row)
    elif status == "派遣":
        styles = ['color: green'] * len(row)
    elif status == "休職":
        styles = ['color: purple'] * len(row)
    else:
        styles = [''] * len(row)
    # 例：昇格の場合、最初のセルに枠線を追加
    if row.get('昇格', '') == "True":
        styles[0] = styles[0] + "; border: 2px solid black"
    return styles

# --- Streamlit UI ---
st.set_page_config(page_title="職員異動差分表示アプリ", layout="wide")
st.title("職員異動差分表示アプリ")
st.markdown("PDFから抽出した職員データをGemini APIで正規化し、前年度と今年度の差分（部署の変更など）を表示します。")

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
    
    # PDF抽出後、必要に応じてカラム名のリネーム例（例："名前" -> "氏名"）
    if "名前" in df_prev.columns:
        df_prev.rename(columns={"名前": "氏名"}, inplace=True)
    if "名前" in df_curr.columns:
        df_curr.rename(columns={"名前": "氏名"}, inplace=True)
    
    # Gemini APIによる正規化対象（例：部署列）の処理
    if "部署" in df_prev.columns and "部署" in df_curr.columns:
        st.info("Gemini API による正規化処理中...")
        df_prev_norm = normalize_dataframe(df_prev, ["部署"])
        df_curr_norm = normalize_dataframe(df_curr, ["部署"])
    else:
        st.warning("【部署】列が存在しないため、正規化処理はスキップします。")
        df_prev_norm = df_prev
        df_curr_norm = df_curr
    
    st.subheader("前年度データ（正規化後）")
    st.dataframe(df_prev_norm)
    st.subheader("今年度データ（正規化後）")
    st.dataframe(df_curr_norm)
    
    st.info("異動差分の計算中...")
    df_diff = compute_diff(df_prev_norm, df_curr_norm)
    
    st.subheader("【異動差分一覧】")
    if not df_diff.empty:
        st.dataframe(df_diff.style.apply(style_row, axis=1))
    else:
        st.info("異動差分は検出されませんでした。")
    
    # 画像ファイルの存在チェックを追加
    if os.path.exists("app_diagram.png"):
        st.markdown("### アプリ全体の構成図")
        st.image("app_diagram.png", caption="アプリ全体の構成とデータフロー")
    else:
        st.warning("アプリ全体の構成図 (app_diagram.png) が見つかりません。")

    if os.path.exists("gemini_normalization_diagram.png"):
        st.markdown("### Gemini 正規化フロー")
        st.image("gemini_normalization_diagram.png", caption="PDFデータ正規化の全体フロー")
    else:
        st.warning("Gemini 正規化フロー図 (gemini_normalization_diagram.png) が見つかりません。")
else:
    st.warning("前年度と今年度のPDFファイルをサイドバーからアップロードしてください。")
