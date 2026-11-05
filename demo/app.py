import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf
from fredapi import Fred

# 導入 Google GenAI SDK
from google import genai

# 頁面基本配置
st.set_page_config(page_title="總體經濟與金融即時儀表板", layout="wide")
st.title("🌐 全球總體經濟與金融指標即時儀表板")

# 側邊欄：輸入 API Key 與刷新控制
st.sidebar.header("⚙️ 設定與金鑰")

# 優先使用 Streamlit Secrets，若無則讓學生在側邊欄輸入
if "FRED_API_KEY" in st.secrets:
  fred_key = st.secrets["FRED_API_KEY"]
  st.sidebar.success("已自動讀取 FRED API Key！")
else:
  fred_key = st.sidebar.text_input("請輸入你的 FRED API Key:", type="password")

# 設定 Gemini API Key 欄位
if "GEMINI_API_KEY" in st.secrets:
  gemini_key = st.secrets["GEMINI_API_KEY"]
else:
  gemini_key = st.sidebar.text_input(
      "請輸入你的 Gemini API Key:", type="password"
  )

if st.sidebar.button("手動刷新數據"):
  st.cache_data.clear()


# 1. 抓取 FRED 數據 (設快取 1 小時)
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
  fred = Fred(api_key=api_key)
  data = {
      "CPI 物價指數": fred.get_series("CPIAUCSL"),
      "10年期美債殖利率": fred.get_series("DGS10"),
      "美國失業率": fred.get_series("UNRATE"),
      "聯邦基金利率": fred.get_series("FEDFUNDS"),
  }
  df = pd.DataFrame(data).ffill().tail(365)
  return df


# 2. 抓取 Market 數據 (設快取 10 分鐘)
@st.cache_data(ttl=600)
def get_market_data():
  tickers = {
      "S&P 500": "^GSPC",
      "台灣加權指數": "^TWII",
      "布蘭特原油": "BZ=F",
      "美元/台幣匯率": "TWD=X",
  }
  df = yf.download(list(tickers.values()), period="1y")["Close"]
  df.rename(columns={v: k for k, v in tickers.items()}, inplace=True)
  return df


# 頁面渲染邏輯
if fred_key:
  try:
    macro_df = get_fred_data(fred_key)
    market_df = get_market_data()

    # 第一區塊：核心 KPI 卡片
    st.subheader("📊 關鍵總體經濟指標 (FRED)")
    col1, col2, col3, col4 = st.columns(4)

    latest_cpi = macro_df["CPI 物價指數"].dropna().iloc[-1]
    col1.metric("CPI 物價指數", f"{latest_cpi:.1f}")

    latest_rate = macro_df["10年期美債殖利率"].dropna().iloc[-1]
    rate_prev = macro_df["10年期美債殖利率"].dropna().iloc[-2]
    col2.metric(
        "10年美債殖利率",
        f"{latest_rate:.2f}%",
        f"{latest_rate - rate_prev:+.2f}%",
    )

    latest_unemp = macro_df["美國失業率"].dropna().iloc[-1]
    col3.metric("美國失業率", f"{latest_unemp:.1f}%")

    latest_fed = macro_df["聯邦基金利率"].dropna().iloc[-1]
    col4.metric("聯邦基金利率", f"{latest_fed:.2f}%")

    # 第二區塊：互動式圖表
    st.write("---")
    st.subheader("📈 市場走勢與總體指標折線圖")

    tab1, tab2 = st.tabs(["金融市場走勢 (yfinance)", "總體經濟趨勢 (FRED)"])

    with tab1:
      market_choice = st.selectbox("選擇金融市場標的：", market_df.columns)
      fig1 = px.line(
          market_df, y=market_choice, title=f"{market_choice} 近一年走勢"
      )
      st.plotly_chart(fig1, use_container_width=True)

    with tab2:
      macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns)
      fig2 = px.line(
          macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢"
      )
      st.plotly_chart(fig2, use_container_width=True)

    # 第三區塊：AI 總體經濟摘要
    st.write("---")
    st.subheader("🤖 AI 總體經濟解讀")

    if st.button("✨ 產生 AI 總體經濟摘要"):
      if not gemini_key:
        st.warning("請先在側邊欄輸入您的 Gemini API Key！")
      else:
        with st.spinner("AI 正在分析最新總經數據中..."):
          try:
            # 初始化 Google GenAI 用戶端
            client = genai.Client(api_key=gemini_key)

            # 組合傳給模型的提示詞與數據上下文
            prompt = f"""
                        你是一位專業的華爾街總體經濟分析師。請根據以下最新數據，為投資人撰寫一份精簡的總體經濟短評（大約 200 字左右）：
                        - 最新 CPI 物價指數：{latest_cpi:.1f}
                        - 10年期美債殖利率：{latest_rate:.2f}% (變動：{latest_rate - rate_prev:+.2f}%)
                        - 美國失業率：{latest_unemp:.1f}%
                        - 聯邦基金利率：{latest_fed:.2f}%
                        
                        請從通膨、就業與利率政策的角度切口，分析當前的總經環境與市場可能的解讀。
                        """

            # 調用 gemini-2.5-flash 模型生成內容
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
            )

            # 顯示結果
            st.success("分析完成！")
            st.write(response.text)

          except Exception as ai_e:
            st.error(f"生成摘要失敗，請檢查 Gemini API Key 或網路。錯誤：{ai_e}")

  except Exception as e:
    st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
  st.info("👈 請先在側邊欄輸入 FRED API Key 以啟動儀表板。")
