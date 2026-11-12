import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import feedparser
import google.generativeai as genai
from urllib.parse import quote  # 解決 URL 空白字元轉碼問題

# ==========================================
# 1. 頁面配置與側邊欄金鑰設定
# ==========================================
st.set_page_config(page_title="總體經濟、金融與 NLP 市場情緒儀表板", layout="wide")
st.title("🌐 總體經濟、金融指標與 AI 輿論情緒即時儀表板 (含 NVIDIA 專區)")

st.sidebar.header("⚙️ 設定與金鑰")

# 1.1 檢查 FRED API Key
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 FRED API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入 FRED API Key:", type="password")

# 1.2 檢查 Gemini API Key (NLP 情緒分析用)
gemini_key = None
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=gemini_key)
    st.sidebar.success("已自動讀取 Gemini API Key！")
else:
    gemini_input = st.sidebar.text_input("請輸入 Gemini API Key (情緒分析用):", type="password")
    if gemini_input:
        gemini_key = gemini_input
        genai.configure(api_key=gemini_key)

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()

# ==========================================
# 2. 數據抓取函式 (FRED, yfinance, RSS 新聞)
# ==========================================
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    data = {
        "CPI 物價指數": fred.get_series("CPIAUCSL"),
        "10年期美債殖利率": fred.get_series("DGS10"),
        "美國失業率": fred.get_series("UNRATE"),
        "聯邦基金利率": fred.get_series("FEDFUNDS")
    }
    df = pd.DataFrame(data).ffill().tail(365)
    return df

@st.cache_data(ttl=600)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "台灣加權指數": "^TWII",
        "NVIDIA (輝達)": "NVDA",  # 新增 NVIDIA 股價追蹤
        "布蘭特原油": "BZ=F",
        "美元/台幣匯率": "TWD=X"
    }
    # yfinance 下載多個 ticker 時可能回傳 MultiIndex，取 Close 欄位
    df = yf.download(list(tickers.values()), period="1y")["Close"]
    
    # 確保欄位名稱正確對應
    inv_tickers = {v: k for k, v in tickers.items()}
    df = df.rename(columns=inv_tickers)
    return df

@st.cache_data(ttl=1800)
def fetch_google_news(keyword="Federal Reserve Inflation"):
    safe_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=en-US"
    feed = feedparser.parse(url)
    return [entry.title for entry in feed.entries[:8]]

# ==========================================
# 3. 頁面渲染邏輯
# ==========================================
if fred_key:
    try:
        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()

        # 第一區塊：核心總經 KPI 卡片
        st.subheader("📊 關鍵總體經濟指標 (FRED)")
        col1, col2, col3, col4 = st.columns(4)
        
        latest_cpi = macro_df["CPI 物價指數"].dropna().iloc[-1]
        col1.metric("CPI 物價指數", f"{latest_cpi:.1f}")
        
        latest_rate = macro_df["10年期美債殖利率"].dropna().iloc[-1]
        rate_prev = macro_df["10年期美債殖利率"].dropna().iloc[-2]
        col2.metric("10年美債殖利率", f"{latest_rate:.2f}%", f"{latest_rate - rate_prev:+.2f}%")
        
        latest_unemp = macro_df["美國失業率"].dropna().iloc[-1]
        col3.metric("美國失業率", f"{latest_unemp:.1f}%")
        
        latest_fed = macro_df["聯邦基金利率"].dropna().iloc[-1]
        col4.metric("聯邦基金利率", f"{latest_fed:.2f}%")

        st.write("---")

        # 第二區塊：分頁儀表板 (新增 NVIDIA 專區頁籤)
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 金融市場與輝達 (yfinance)", 
            "🏛️ 總體經濟趨勢 (FRED)", 
            "📰 NLP 市場新聞與鷹鴿情緒",
            "🤖 NVIDIA 專區與 AI 輿情"
        ])
        
        # 頁籤 1: 金融市場
        with tab1:
            market_choice = st.selectbox("選擇金融市場標的：", market_df.columns)
            fig1 = px.line(market_df, y=market_choice, title=f"{market_choice} 近一年走勢")
            st.plotly_chart(fig1, use_container_width=True)
            
        # 頁籤 2: 總體經濟
        with tab2:
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns)
            fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢")
            st.plotly_chart(fig2, use_container_width=True)

        # 頁籤 3: NLP 市場新聞與情緒分析
        with tab3:
            st.subheader("📰 即時財經新聞與 LLM 鷹鴿派情緒分析")
            
            search_kw = st.text_input("🔍 輸入新聞關鍵字 (預設: Federal Reserve Inflation):", value="Federal Reserve Inflation", key="kw_macro")
            news_titles = fetch_google_news(search_kw)

            nlp_col1, nlp_col2 = st.columns([1, 1])

            with nlp_col1:
                st.markdown("### 📌 最新財經新聞標題 (RSS)")
                if news_titles:
                    for i, title in enumerate(news_titles, 1):
                        st.write(f"**{i}.** {title}")
                else:
                    st.warning("查無相關新聞標題，請嘗試更換關鍵字。")

            with nlp_col2:
                st.markdown("### 🤖 Gemini AI 鷹鴿派與情緒打分")
                if gemini_key:
                    if st.button("🚀 開始分析市場情緒", type="primary", key="btn_macro"):
                        if news_titles:
                            with st.spinner("Gemini 正在剖析文本立場與鷹鴿情緒中..."):
                                try:
                                    news_text = "\n".join([f"- {t}" for t in news_titles])
                                    prompt = f"你是一位專業總體經濟分析師。請分析以下 8 條新聞標題：\n{news_text}\n\n" \
                                             f"請以繁體中文輸出結構化報告：\n" \
                                             f"1. 整體市場情緒分數 (0~100)\n" \
                                             f"2. 貨幣政策立場判定 (鷹派/鴿派/中立)\n" \
                                             f"3. 重點分析與逐條評分表格 (Markdown Format)"
                                    
                                    model = genai.GenerativeModel("gemini-2.5-flash") # 確保模型名稱相容
                                    response = model.generate_content(prompt)
                                    st.markdown(response.text)
                                except Exception as e:
                                    st.error(f"AI 分析時發生錯誤: {e}")
                        else:
                            st.warning("尚無新聞數據可供分析。")
                else:
                    st.warning("👈 請在側邊欄輸入 Gemini API Key 以啟用 AI 文本情緒分析功能。")

        # 頁籤 4: NVIDIA 專區與 AI 輿情
        with tab4:
            st.subheader("🚀 NVIDIA (輝達 - NVDA) 即時股價與新聞輿情分析")
            
            # 顯示 NVDA 近期股價走勢
            if "NVIDIA (輝達)" in market_df.columns:
                fig_nvda = px.line(market_df, y="NVIDIA (輝達)", title="NVIDIA (NVDA) 近一年股價走勢", color_discrete_sequence=["#76b900"])
                st.plotly_chart(fig_nvda, use_container_width=True)
            
            st.write("---")
            
            nvda_col1, nvda_col2 = st.columns([1, 1])
            
            # 抓取 NVIDIA 最新新聞
            nvda_news = fetch_google_news("NVIDIA AI stock news")
            
            with nvda_col1:
                st.markdown("### 📌 NVIDIA 最新新聞標題 (RSS)")
                if nvda_news:
                    for i, title in enumerate(nvda_news, 1):
                        st.write(f"**{i}.** {title}")
                else:
                    st.warning("目前找不到關於 NVIDIA 的最新新聞。")
                    
            with nvda_col2:
                st.markdown("### 🤖 Gemini AI 針對 NVIDIA 輿情與投資價值分析")
                if gemini_key:
                    if st.button("🚀 分析 NVIDIA 輿情與市場影響", type="primary", key="btn_nvda"):
                        if nvda_news:
                            with st.spinner("Gemini 正在分析 NVIDIA 相關新聞與市場情緒..."):
                                try:
                                    nvda_text = "\n".join([f"- {t}" for t in nvda_news])
                                    prompt = f"你是一位資深半導體與人工智慧產業分析師。請分析以下關於 NVIDIA (輝達) 的新聞標題：\n{nvda_text}\n\n" \
                                             f"請以繁體中文輸出結構化報告：\n" \
                                             f"1. 整體市場情緒分數 (0~100) 與利多/利空判定\n" \
                                             f"2. 關鍵技術、供應鏈或財報題重點摘要\n" \
                                             f"3. 對 NVIDIA 短期股價可能的潛在影響與風險評估"
                                    
                                    model = genai.GenerativeModel("gemini-2.5-flash")
                                    response = model.generate_content(prompt)
                                    st.markdown(response.text)
                                except Exception as e:
                                    st.error(f"AI 分析時發生錯誤: {e}")
                        else:
                            st.warning("尚無足夠的新聞數據供分析。")
                else:
                    st.warning("👈 請在側邊欄輸入 Gemini API Key 以啟用 AI 分析。")

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
