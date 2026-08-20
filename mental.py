import streamlit as st
import sqlite3
import pandas as pd
import datetime
import plotly.express as px

# データベースファイルの指定
DB_FILE = "mental_health_data.db"

# データベースの初期化
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_records (
                date TEXT PRIMARY KEY,
                mental_state INTEGER,
                suicidal_ideation TEXT,
                stress_level INTEGER
            )
        ''')
        conn.commit()

# 旧データ（〇、△、×）を新表記に統一するヘルパー関数
def normalize_suicidal(val):
    mapping = {
        "×": "なし",
        "△": "わからない",
        "〇": "あり",
        "なし": "なし",
        "わからない": "わからない",
        "あり": "あり"
    }
    return mapping.get(val, "なし")

# データの挿入・更新
def save_record(date_str, mental, suicidal, stress):
    normalized_suicidal = normalize_suicidal(suicidal)
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO daily_records (date, mental_state, suicidal_ideation, stress_level)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                mental_state=excluded.mental_state,
                suicidal_ideation=excluded.suicidal_ideation,
                stress_level=excluded.stress_level
        ''', (date_str, mental, normalized_suicidal, stress))
        conn.commit()

# 特定月のデータ取得
def get_monthly_records(year, month):
    prefix = f"{year}-{month:02d}-%"
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM daily_records WHERE date LIKE ? ORDER BY date ASC", 
            conn, 
            params=(prefix,)
        )
    if not df.empty:
        df['suicidal_ideation'] = df['suicidal_ideation'].apply(normalize_suicidal)
    return df

# 全データの取得（分析用）
def get_all_records():
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query("SELECT * FROM daily_records ORDER BY date ASC", conn)
    if not df.empty:
        df['suicidal_ideation'] = df['suicidal_ideation'].apply(normalize_suicidal)
    return df

# データの削除
def delete_record(date_str):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM daily_records WHERE date = ?", (date_str,))
        conn.commit()

# アプリの初期化
init_db()

st.set_page_config(page_title="メンタルヘルスチェッカー", layout="wide")

# サイドメニューによるページ選択
st.sidebar.title("メニュー")
page = st.sidebar.radio("ページを選択してください", ["データ入力・履歴", "データ分析"])

# ----------------- 1ページ目：データ入力・履歴 -----------------
if page == "データ入力・履歴":
    st.title("📝 日々の記録と履歴")
    
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.subheader("今日の状態を入力")
        input_date = st.date_input("日付", datetime.date.today())
        date_str = input_date.strftime("%Y-%m-%d")
        
        # 既存データがある場合は初期値として読み込む
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mental_state, suicidal_ideation, stress_level FROM daily_records WHERE date = ?", (date_str,))
            existing = cursor.fetchone()
        
        if existing:
            st.info(f"※ {date_str} のデータは既に存在します。保存すると更新されます。")
            default_mental = int(existing[0])
            default_suicidal = normalize_suicidal(existing[1])
            default_stress = int(existing[2])
        else:
            default_mental = 5
            default_suicidal = "なし"
            default_stress = 5

        # 数値手入力ボックス
        mental_state = st.number_input(
            "精神状態 (1:最悪 〜 9:最高)", 
            min_value=1, 
            max_value=9, 
            value=default_mental, 
            step=1
        )
        
        # ドロップダウン形式に変更（「なし」をデフォルトに設定）
        suicidal_options = ["なし", "わからない", "あり"]
        suicidal_idx = suicidal_options.index(default_suicidal) if default_suicidal in suicidal_options else 0
        suicidal_ideation = st.selectbox("希死念慮", suicidal_options, index=suicidal_idx)
        
        # 数値手入力ボックス
        stress_level = st.number_input(
            "ストレスの総量 (0:なし 〜 9:最大)", 
            min_value=0, 
            max_value=9, 
            value=default_stress, 
            step=1
        )
        
        if st.button("データを保存する", type="primary"):
            save_record(date_str, mental_state, suicidal_ideation, stress_level)
            st.success(f"{date_str} のデータを保存しました。")
            st.rerun()

    with col2:
        st.subheader("履歴一覧 (1ヶ月分表示)")
        
        # 表示年月のセッション状態管理
        if 'view_year' not in st.session_state:
            st.session_state.view_year = datetime.date.today().year
        if 'view_month' not in st.session_state:
            st.session_state.view_month = datetime.date.today().month

        # 年月の手動選択
        years_list = list(range(2020, datetime.date.today().year + 5))
        months_list = list(range(1, 13))
        
        c_yr, c_mo = st.columns(2)
        with c_yr:
            selected_year = st.selectbox("表示年", years_list, index=years_list.index(st.session_state.view_year))
        with c_mo:
            selected_month = st.selectbox("表示月", months_list, index=months_list.index(st.session_state.view_month))
            
        st.session_state.view_year = selected_year
        st.session_state.view_month = selected_month

        # 「前へ」「次へ」ボタン
        btn_prev, _, btn_next = st.columns([1, 2, 1])
        with btn_prev:
            if st.button("← 前の月"):
                if st.session_state.view_month == 1:
                    st.session_state.view_month = 12
                    st.session_state.view_year -= 1
                else:
                    st.session_state.view_month -= 1
                st.rerun()
        with btn_next:
            if st.button("次の月 →"):
                if st.session_state.view_month == 12:
                    st.session_state.view_month = 1
                    st.session_state.view_year += 1
                else:
                    st.session_state.view_month += 1
                st.rerun()

        # データ取得と表示
        df_monthly = get_monthly_records(st.session_state.view_year, st.session_state.view_month)
        
        if not df_monthly.empty:
            display_df = df_monthly.rename(columns={
                'date': '日付',
                'mental_state': '精神状態(1-9)',
                'suicidal_ideation': '希死念慮',
                'stress_level': 'ストレスの総量(0-9)'
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # 削除機能
            st.write("---")
            st.caption("選択した日付のデータを削除できます。変更（修正）する場合は、左側の入力欄から同じ日付で再度入力し保存してください。")
            delete_date_str = st.selectbox("削除する日付を選択", df_monthly['date'].tolist())
            if st.button("選択した日付のデータを削除"):
                delete_record(delete_date_str)
                st.success(f"{delete_date_str} のデータを削除しました。")
                st.rerun()
        else:
            st.info("選択された月のデータは登録されていません。")

# ----------------- 2ページ目：データ分析 -----------------
elif page == "データ分析":
    st.title("📈 メンタルデータ分析")
    st.write("各指標の年間推移を比較できます。")
    
    df_all = get_all_records()
    
    if not df_all.empty:
        # 日付処理
        df_all['date_dt'] = pd.to_datetime(df_all['date'])
        df_all['year'] = df_all['date_dt'].dt.year.astype(str)
        df_all['month_day'] = df_all['date_dt'].dt.strftime('%m-%d')
        
        # 希死念慮の新数値マッピング (なし:0, わからない:1, あり:2)
        mapping = {"なし": 0, "わからない": 1, "あり": 2}
        df_all['suicidal_num'] = df_all['suicidal_ideation'].map(mapping)
        
        # 比較する年の選択
        unique_years = sorted(df_all['year'].unique())
        selected_years = st.multiselect("比較対象にする年を選択してください", unique_years, default=unique_years)
        
        # 横軸調整（1年間のタイムラインに重ねるための擬似日付設定）
        df_all['pseudo_date'] = pd.to_datetime('2024-' + df_all['month_day'], errors='coerce')
        df_all = df_all.dropna(subset=['pseudo_date']).sort_values('pseudo_date')
        
        # フィルタリング
        df_filtered = df_all[df_all['year'].isin(selected_years)]
        
        if not df_filtered.empty:
            # 1. 精神状態の推移
            st.subheader("1. 精神状態の推移（1:最悪 〜 9:最高）")
            fig_mental = px.line(
                df_filtered, 
                x='pseudo_date', 
                y='mental_state', 
                color='year',
                markers=True,
                labels={'pseudo_date': '月-日', 'mental_state': '精神状態', 'year': '年'}
            )
            fig_mental.update_layout(
                xaxis_tickformat='%m-%d',
                yaxis=dict(range=[0.5, 9.5], dtick=1),
                hovermode="x unified"
            )
            st.plotly_chart(fig_mental, use_container_width=True)
            
            # 2. 希死念慮の推移
            st.subheader("2. 希死念慮の推移")
            fig_suicidal = px.line(
                df_filtered, 
                x='pseudo_date', 
                y='suicidal_num', 
                color='year',
                markers=True,
                labels={'pseudo_date': '月-日', 'suicidal_num': '希死念慮', 'year': '年'}
            )
            fig_suicidal.update_layout(
                xaxis_tickformat='%m-%d',
                yaxis=dict(
                    tickvals=[0, 1, 2],
                    ticktext=['なし', 'わからない', 'あり'],
                    range=[-0.5, 2.5]
                ),
                hovermode="x unified"
            )
            st.plotly_chart(fig_suicidal, use_container_width=True)
            
            # 3. ストレスの総量の推移
            st.subheader("3. ストレスの総量の推移（0:なし 〜 9:最大）")
            fig_stress = px.line(
                df_filtered, 
                x='pseudo_date', 
                y='stress_level', 
                color='year',
                markers=True,
                labels={'pseudo_date': '月-日', 'stress_level': 'ストレスの総量', 'year': '年'}
            )
            fig_stress.update_layout(
                xaxis_tickformat='%m-%d',
                yaxis=dict(range=[-0.5, 9.5], dtick=1),
                hovermode="x unified"
            )
            st.plotly_chart(fig_stress, use_container_width=True)
            
        else:
            st.warning("選択された年のデータがありません。")
            
    else:
        st.info("分析するための十分なデータがありません。まずは「データ入力・履歴」から入力を開始してください。")