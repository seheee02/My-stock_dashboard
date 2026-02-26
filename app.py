import streamlit as st
import yfinance as yf
import json
import os
import pandas as pd
import re
from datetime import datetime, timedelta
from pykrx import stock

st.title("세희의 첫 주식 대시보드 📈")

# --- 상위 그룹 계층 구조 ---
grouped_tickers = {
    "한국 증시 (KOSPI/KOSDAQ)": {
        "반도체": {
            "삼성전자 (005930)": "005930.KS",
            "SK하이닉스 (000660)": "000660.KS",
            "한미반도체 (042700)": "042700.KQ"
        },
        "에너지/전기전력": {
            "두산에너빌리티 (034020)": "034020.KS",
            "한국전력 (015760)": "015760.KS",
            "삼성전기 (009150)": "009150.KS",
            "LS ELECTRIC (010120)": "010120.KS",
            "HD현대일렉트릭 (267260)": "267260.KS"
        },
        "의료 AI": {
            "씨어스테크놀로지 (458870)": "458870.KQ",
            "뷰노 (338220)": "338220.KQ",
            "루닛 (328130)": "328130.KQ"
        },
        "바이오/헬스케어": {
            "셀트리온 (068270)": "068270.KS",
            "삼성바이오로직스 (207940)": "207940.KS",
            "SK바이오팜 (326030)": "326030.KS",
            "삼성에피스홀딩스 (373220)": "373220.KQ",  # 수정: .KS -> .KQ (코스닥)
            "SK바이오사이언스 (302440)": "302440.KS",
            "대웅제약 (069620)": "069620.KS"  # 대웅제약 추가
        },
        "자동차/로봇": {  # 신규 그룹 추가
            "현대자동차 (005380)": "005380.KS",
            "현대모비스 (012330)": "012330.KS",
            "기아 (000270)": "000270.KS"
        },
        "방산주": {
            "한화에어로스페이스 (012450)": "012450.KS",
            "LIG넥스원 (079550)": "079550.KS",
            "한국항공우주 (047810)": "047810.KS",
            "현대로템 (064350)": "064350.KS",
        },
        "ISA ETF (주요 거래가능)": {
            "KODEX 코스피200 (069500)": "069500.KS",
            "TIGER 미국S&P500 (360200)": "360200.KS",
            "TIGER 미국나스닥바이오 (195930)": "195930.KS",
            "TIGER 미국핵심전력인프라 (456460)": "456460.KS",
            "TIME 글로벌우주테크&방산 (462230)": "462230.KS"
        },
        "안전자산(ETF/현물)": {
            "KODEX 골드현물 (132030)": "132030.KS",
            "TIGER 미국채10년 (305080)": "305080.KS",
            "KODEX 단기채권 (153130)": "153130.KS",
            "KODEX 증권 (102110)": "102110.KS",
            "KODEX 미국달러 (261240)": "261240.KS"
        }
    },
    "미국 증시 (NASDAQ/NYSE/QQQ)": {
        "빅테크": {
            "엔비디아 (NVDA)": "NVDA",
            "애플 (AAPL)": "AAPL",
            "마이크로소프트 (MSFT)": "MSFT",
            "알파벳 C (GOOG)": "GOOG"
        }
        # 미국 ETF는 필요 시 미국 그룹에 추가할 수 있음
    }
}

# --- 업종 매핑도 계층적 키 연결 (불변, 기존대로) ---
industry_mapping = {
    "빅테크": ["NVDA", "AAPL", "MSFT", "GOOG"],
    "반도체": ["005930.KS", "000660.KS", "042700.KQ"],
    "에너지/전기전력": [
        "034020.KS",  # 두산에너빌리티
        "015760.KS",  # 한국전력
        "009150.KS",  # 삼성전기
        "010120.KS",  # LS ELECTRIC
        "267260.KS"   # HD현대일렉트릭
    ],
    "의료 AI": ["458870.KQ", "338220.KQ", "328130.KQ"],
    "바이오/헬스케어": ["068270.KS", "207940.KS", "326030.KS", "373220.KQ", "302440.KS", "069620.KS"],  # 대웅제약 추가
    "자동차/로봇": ["005380.KS", "012330.KS", "000270.KS"],
    "방산주": ["012450.KS", "079550.KS", "047810.KS", "064350.KS"],
}

# ---------- 계층별 드롭다운 ----------
st.sidebar.header("투자 시장/카테고리/종목 선택")

top_level = st.sidebar.selectbox("시장(나라/거래소) 선택", list(grouped_tickers.keys()))
categories = list(grouped_tickers[top_level].keys())
category = st.sidebar.selectbox("카테고리를 선택하세요", categories)
stock_names = list(grouped_tickers[top_level][category].keys())
selected_name = st.sidebar.selectbox("종목을 선택하세요", stock_names)
selected_ticker = grouped_tickers[top_level][category][selected_name]

# --- ETF 판별 로직 수정 ---
def check_is_etf(category, selected_name):
    is_etf = False
    if "ETF" in category or "ETF" in selected_name:
        is_etf = True
    elif ("KODEX" in selected_name) or ("TIGER" in selected_name):
        is_etf = True
    return is_etf
is_etf = check_is_etf(category, selected_name)

st.write(f"### {selected_name} 최근 6개월 주가 흐름")
ticker_obj = yf.Ticker(selected_ticker)
stock_data = ticker_obj.history(period="6mo")

# 실적 발표일(Earnings Date) 가져오기 (미국/해외 주식만 존재)
earnings_date_str = "예정일 정보 없음"
if not is_etf:
    try:
        cal = ticker_obj.get_calendar()
        if cal is not None and "Earnings Date" in cal.index:
            date_val = cal.loc["Earnings Date"].values[0]
            if hasattr(date_val, "strftime"):
                earnings_date_str = date_val.strftime("%Y-%m-%d")
            elif isinstance(date_val, str):
                earnings_date_str = date_val
            elif hasattr(date_val, "__getitem__"):
                dt = date_val[0]
                if hasattr(dt, "strftime"):
                    earnings_date_str = dt.strftime("%Y-%m-%d")
                elif isinstance(dt, str):
                    earnings_date_str = dt
                else:
                    earnings_date_str = "예정일 정보 없음"
        else:
            df = ticker_obj.get_earnings_dates(limit=1)
            if not df.empty:
                dt_val = df.iloc[0, 0]
                if hasattr(dt_val, "strftime"):
                    earnings_date_str = dt_val.strftime("%Y-%m-%d")
                elif isinstance(dt_val, str):
                    earnings_date_str = dt_val
    except Exception:
        earnings_date_str = "예정일 정보 없음"
    st.info(f"**다음 실적 발표 예정일:** {earnings_date_str}")

if not stock_data.empty:
    st.line_chart(stock_data['Close'])
else:
    st.error("데이터를 불러오지 못했습니다. 종목 코드나 인터넷 연결을 확인해주세요.")

# --------- 주요 재무 지표/ETF 운용보수 및 섹션 UI 분기 시작 ---------
if not is_etf:
    st.write("#### 주요 재무 지표 (가장 최근 영업일 기준)")

def is_korean_stock(ticker):
    return bool(re.match(r"^(\d{6})\.(KS|KQ)$", ticker))

def extract_kr_code(ticker):
    return ticker.split('.')[0] if '.' in ticker else ticker

def fetch_korean_fundamental_pykrx(code):
    today = datetime.now()
    past_days = today - timedelta(days=10)
    start_date = past_days.strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")
    
    indicators = {"PER": "N/A", "PBR": "N/A", "EPS": "N/A", "ROE (%)": "N/A"}
    
    try:
        df = stock.get_market_fundamental(start_date, end_date, code)
        if not df.empty:
            last_row = df.iloc[-1]
            per = float(last_row.get("PER", 0))
            pbr = float(last_row.get("PBR", 0))
            eps = float(last_row.get("EPS", 0))
            indicators["PER"] = round(per, 2) if per != 0 and not pd.isna(per) else "N/A"
            indicators["PBR"] = round(pbr, 2) if pbr != 0 and not pd.isna(pbr) else "N/A"
            indicators["EPS"] = int(eps) if eps != 0 and not pd.isna(eps) else "N/A"
            if indicators["PER"] != "N/A" and indicators["PBR"] != "N/A":
                indicators["ROE (%)"] = round((indicators["PBR"] / indicators["PER"]) * 100, 2)
    except Exception:
        pass
    return indicators

def fetch_us_fundamental_yf(ticker):
    indicators = {"ROE (%)": "N/A", "EPS": "N/A", "PER": "N/A", "PBR": "N/A"}
    try:
        tkr = yf.Ticker(ticker)
        info = tkr.info if hasattr(tkr, "info") else {}
        roe = info.get("returnOnEquity")
        eps = info.get("trailingEps")
        per = info.get("trailingPE")
        pbr = info.get("priceToBook")
        if roe is not None:
            indicators["ROE (%)"] = round(roe * 100, 2)
        if eps is not None:
            indicators["EPS"] = round(float(eps), 2)
        if per is not None:
            indicators["PER"] = round(float(per), 2)
        if pbr is not None:
            indicators["PBR"] = round(float(pbr), 2)
    except Exception:
        pass
    return indicators

def fetch_financial_indicators(ticker):
    if is_korean_stock(ticker):
        code = extract_kr_code(ticker)
        return fetch_korean_fundamental_pykrx(code)
    else:
        return fetch_us_fundamental_yf(ticker)

# ETF 운용보수 함수
def fetch_etf_expense_ratio(ticker_obj):
    try:
        info = ticker_obj.info if hasattr(ticker_obj, "info") else {}
        ratio = info.get("annualReportExpenseRatio")
        if ratio is not None:
            return f"{round(ratio*100, 2)} %"
    except Exception:
        pass
    return "정보 없음"

# ETF 운용사/구성 종목(Top 10) 함수
def fetch_etf_top_holdings(ticker_obj):
    """
    미국 ETF의 경우 yfinance holdings 정보 반환.
    한국 ETF는 None 반환.
    """
    try:
        holdings = getattr(ticker_obj, "fund_holdings", None)
        if holdings is not None and not holdings.empty:
            df = holdings
            top10_df = df.head(10)
            top10 = []
            for _, row in top10_df.iterrows():
                name = row.get("holdingName") or row.get("symbol")
                percent = row.get("holdingPercent", None)
                if percent is not None:
                    percent_str = f"{round(percent*100, 2)}%"
                else:
                    percent_str = ""
                if name:
                    item_str = f"{name} ({percent_str})" if percent_str else f"{name}"
                    top10.append(item_str)
            if len(top10) >= 1:
                return top10
        info = getattr(ticker_obj, "info", {})
        if "holdings" in info and isinstance(info["holdings"], dict):
            holdings = info["holdings"]
            top10 = []
            for name, percent in list(holdings.items())[:10]:
                percent_str = f"{round(percent*100, 2)}%"
                top10.append(f"{name} ({percent_str})")
            return top10
    except Exception:
        pass
    return None

# -------- 각 경우의 UI (일반주식/ETF) 분기 처리 --------
if not is_etf:
    indicators = fetch_financial_indicators(selected_ticker)
    metrics_order = ["ROE (%)", "EPS", "PER", "PBR"]
    indicators = {k: indicators.get(k, "N/A") for k in metrics_order}
    df_ind = pd.DataFrame.from_dict(indicators, orient='index', columns=["종목"])

    # 업종 평균 계산
    industry_avg = None
    if category in industry_mapping:
        ticker_list = industry_mapping[category]
        vals = {"ROE (%)": [], "EPS": [], "PER": [], "PBR": []}
        for t in ticker_list:
            ix = fetch_financial_indicators(t)
            for k in vals.keys():
                v = ix.get(k, None)
                if v != "N/A" and v is not None and not pd.isna(v):
                    vals[k].append(v)
        avg_dict = {}
        for k, v in vals.items():
            try:
                avg_dict[k] = round(sum(v) / len(v), 2) if v else "N/A"
            except Exception:
                avg_dict[k] = "N/A"
        df_ind["업종평균"] = pd.Series(avg_dict)
    else:
        df_ind["업종평균"] = None

    def get_conditional_emoji(per, roe):
        try:
            if per == "N/A" or roe == "N/A":
                return ""
            _per = float(per)
            _roe = float(roe)
            if pd.isna(_per) or pd.isna(_roe):
                return ""
            if _per <= 15 and _roe >= 10:
                return " 👑"
            elif _per >= 40:
                return " ⚠️"
            else:
                return ""
        except Exception:
            return ""

    emoji_for_name = get_conditional_emoji(df_ind.loc["PER", "종목"], df_ind.loc["ROE (%)", "종목"])
    display_name_with_emoji = f"{selected_name}{emoji_for_name}"

    st.write("##### 개별 종목 vs 업종 평균 비교")
    col_stock, col_industry = st.columns(2)

    with col_stock:
        st.markdown(f"**{display_name_with_emoji}**")
        single_df = df_ind[[df_ind.columns[0]]].copy()
        single_df = single_df.rename(columns={"종목": f"{display_name_with_emoji}"})
        st.dataframe(single_df.fillna("정보 없음"), use_container_width=True)

    with col_industry:
        st.markdown("**업종 평균**")
        if "업종평균" in df_ind.columns:
            ind_df = df_ind[["업종평균"]].copy()
            st.dataframe(ind_df.fillna("정보 없음"), use_container_width=True)
        else:
            st.info("업종 평균 정보가 없습니다.")

    bar_df = df_ind.copy()
    for col in bar_df.columns:
        bar_df[col] = bar_df[col].apply(lambda x: x if isinstance(x, (float, int)) else 0)
    bar_df_for_chart = bar_df.rename(columns={"종목": f"{display_name_with_emoji}", "업종평균": "업종평균"})
    st.write("##### (Bar Chart) 재무지표 시각 비교")
    st.bar_chart(bar_df_for_chart)

else:
    st.write("#### ETF 정보 및 운용 보수")
    col1, col2 = st.columns([1,2])
    with col1:
        st.markdown("**운용 보수 (%/연)**")
        ratio_str = fetch_etf_expense_ratio(ticker_obj)
        st.info(f"{ratio_str}")

    st.write("#### 주요 구성 종목 (Top 10)")
    is_korean_etf = (is_korean_stock(selected_ticker) or ".KS" in selected_ticker or ".KQ" in selected_ticker)
    kor_etf_possible = ("KODEX" in selected_name) or ("TIGER" in selected_name) or category.startswith("ISA ETF") or category.startswith("안전자산")
    holdings_list = fetch_etf_top_holdings(ticker_obj)
    if is_korean_etf or kor_etf_possible or holdings_list is None:
        st.markdown(
            """
            **상세 구성 종목은 운용사 홈페이지를 참고하거나 아래 메모장에 기록하세요**

            - [KODEX 공식](https://www.kodex.com/)
            - [TIGER 공식](https://www.tigeretf.com/)
            """
        )
        st.write("예시 Top10 (플레이스홀더)")
        placeholder_list = [
            "1. (구성 종목 이름 입력)", "2. (구성 종목 이름 입력)",
            "3. (구성 종목 이름 입력)", "4. (구성 종목 이름 입력)",
            "5. (구성 종목 이름 입력)", "6. (구성 종목 이름 입력)",
            "7. (구성 종목 이름 입력)", "8. (구성 종목 이름 입력)", 
            "9. (구성 종목 이름 입력)", "10. (구성 종목 이름 입력)"
        ]
        for item in placeholder_list:
            st.write(item)
    else:
        if holdings_list and isinstance(holdings_list, list):
            for idx, item in enumerate(holdings_list, 1):
                st.write(f"{idx}. {item}")
        else:
            st.info("상세 구성 종목 데이터를 찾을 수 없습니다.")

    # ----------- 네이버 증권 ETF 페이지 링크 버튼 추가 -----------
    def get_naver_kr_etf_url(ticker):
        # ticker: 069500.KS, 195930.KS, 132030.KS, etc.
        # 네이버는 https://finance.naver.com/item/main.naver?code=종목코드 (숫자 6자리)
        m = re.match(r"^(\d{6})\.(KS|KQ)", ticker)
        if m:
            code = m.group(1)
            return f"https://finance.naver.com/item/main.naver?code={code}"
        return None  # 외국 ETF의 경우 없음

    def get_naver_us_etf_url(ticker):
        return "https://finance.naver.com/sise/etf.naver"

    naver_url = None
    if is_korean_etf:
        naver_url = get_naver_kr_etf_url(selected_ticker)
    else:
        naver_url = get_naver_us_etf_url(selected_ticker)

    st.info("상세 구성 종목 및 정확한 보수는 [네이버 증권]에서 확인하세요")
    if naver_url is not None:
        st.link_button("네이버 증권에서 확인하기", naver_url)
# -------------------------------------------------------------

MEMO_FILE = "memos.json"
MARKET_MEMO_FILE = "market_memos.json"

def load_memos(filename=MEMO_FILE):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_memos(memos, filename=MEMO_FILE):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(memos, f, ensure_ascii=False, indent=2)

# 개별 종목 메모
memos = load_memos(MEMO_FILE)
memo_key = selected_ticker
default_text = memos.get(memo_key, "")

# 시장/카테고리 전체 메모 (한국 증시/미국 증시용, 모든 하위 그룹에서 공통으로 볼 수 있도록)
market_memos = load_memos(MARKET_MEMO_FILE)

st.write("---")
st.subheader("📒 종목 메모")
memo_text = st.text_area("이 종목에 대한 나의 메모", value=default_text, height=120)

col1, col2 = st.columns([1,3])
with col1:
    if st.button("저장"):
        memos[memo_key] = memo_text
        save_memos(memos, MEMO_FILE)
        st.success("메모가 저장되었습니다!")
with col2:
    st.caption("※ 종목을 바꿔도 이전에 메모한 내용이 자동으로 불러와집니다.")

st.write("---")
st.subheader("🌍 시장/카테고리 메모장 (한국/미국 증시 현황, 특징 등 기록)")
market_memo_key = top_level  # "한국 증시 (KOSPI/KOSDAQ)" 또는 "미국 증시 (NASDAQ/NYSE/QQQ)"
market_memo_val = market_memos.get(market_memo_key, "")

market_text = st.text_area(
    f"[{market_memo_key}] 전체 시장/카테고리 메모 (모든 하위 그룹에서 공통으로 표시)", 
    value=market_memo_val, height=120, key=f"marketmemo_{market_memo_key}"
)
if st.button(f"{market_memo_key} 메모 저장"):
    market_memos[market_memo_key] = market_text
    save_memos(market_memos, MARKET_MEMO_FILE)
    st.success("시장/카테고리 메모가 저장되었습니다!")