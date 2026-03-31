"""
fetch_data.py
GitHub Actions가 5분마다 실행 → data.json 갱신
"""

import yfinance as yf
import json
import datetime
import pytz

KST = pytz.timezone("Asia/Seoul")

def fmt(v, d=2):
    try:
        return round(float(v), d)
    except:
        return None

def get_quote(symbol):
    """현재가·당일 OHLCV 반환"""
    try:
        tk = yf.Ticker(symbol)
        info = tk.info
        hist = tk.history(period="1d", interval="1m")

        price  = fmt(info.get("regularMarketPrice") or info.get("currentPrice"))
        prev   = fmt(info.get("regularMarketPreviousClose"))
        open_  = fmt(info.get("regularMarketOpen"))
        high   = fmt(info.get("regularMarketDayHigh"))
        low    = fmt(info.get("regularMarketDayLow"))
        vol    = int(info.get("regularMarketVolume") or 0)
        chg    = fmt((price - prev) if price and prev else None)
        pct    = fmt(((price - prev) / prev * 100) if price and prev else None)

        # 인트라데이 1분봉 → 차트용 포인트
        chart = []
        if not hist.empty:
            for ts, row in hist.iterrows():
                t_kst = ts.astimezone(KST)
                chart.append({
                    "t": t_kst.strftime("%H:%M"),
                    "o": fmt(row["Open"]),
                    "h": fmt(row["High"]),
                    "l": fmt(row["Low"]),
                    "c": fmt(row["Close"]),
                    "v": int(row["Volume"]),
                })

        return {
            "price": price, "prev": prev, "open": open_,
            "high": high,   "low": low,   "vol": vol,
            "chg": chg,     "pct": pct,   "chart": chart,
            "ok": price is not None,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "chart": []}


def get_index(symbol, name):
    try:
        info = yf.Ticker(symbol).info
        price = fmt(info.get("regularMarketPrice") or info.get("currentPrice"))
        prev  = fmt(info.get("regularMarketPreviousClose"))
        chg   = fmt((price - prev) if price and prev else None)
        pct   = fmt(((price - prev) / prev * 100) if price and prev else None)
        return {"name": name, "price": price, "chg": chg, "pct": pct, "ok": price is not None}
    except:
        return {"name": name, "ok": False}


def main():
    now_kst = datetime.datetime.now(KST)
    updated = now_kst.strftime("%Y-%m-%d %H:%M KST")

    print(f"[{updated}] 데이터 수집 시작...")

    # ── 주간 선물: ^KS200 (KOSPI200 지수로 대체, 선물 직접 심볼 없음)
    # Yahoo Finance에서 KOSPI200 선물 근월물은 ^KS200 으로 조회
    day   = get_quote("^KS200")          # KOSPI200 지수 (주간 대표)
    night = get_quote("^KS200")          # 야간은 별도 심볼 없어 동일 기준가 사용
    kospi = get_quote("^KS11")           # KOSPI 지수

    # 야간은 주간 종가 기준으로 약간 변동 (야간전용 심볼 미지원)
    night["session"] = "night"
    night["note"] = "야간선물 별도 심볼 미제공 (KOSPI200 기준가)"

    # ── 글로벌 지수
    indices_raw = [
        ("^KS11",    "KOSPI"),
        ("^KS200",   "KOSPI200"),
        ("^KQ11",    "KOSDAQ"),
        ("ES=F",     "S&P500 선물"),
        ("NQ=F",     "나스닥 선물"),
        ("^N225",    "닛케이225"),
        ("USDKRW=X", "달러/원"),
        ("GC=F",     "금 (Gold)"),
        ("CL=F",     "WTI 원유"),
        ("^VIX",     "VIX"),
    ]
    indices = [get_index(sym, name) for sym, name in indices_raw]

    # ── 뉴스 (yfinance news)
    news_items = []
    try:
        tk = yf.Ticker("^KS200")
        raw_news = tk.news or []
        for n in raw_news[:10]:
            ct = n.get("content", {})
            title = ct.get("title") or n.get("title", "")
            link  = ct.get("canonicalUrl", {}).get("url") or n.get("link", "#")
            pub   = ct.get("pubDate") or n.get("providerPublishTime")
            ago   = ""
            if pub:
                try:
                    if isinstance(pub, int):
                        pub_dt = datetime.datetime.fromtimestamp(pub, tz=KST)
                    else:
                        pub_dt = datetime.datetime.fromisoformat(pub).astimezone(KST)
                    diff = int((now_kst - pub_dt).total_seconds() / 60)
                    ago = "방금 전" if diff < 1 else f"{diff}분 전" if diff < 60 else f"{diff//60}시간 전"
                except:
                    ago = ""
            if title:
                news_items.append({"title": title, "link": link, "ago": ago})
    except Exception as e:
        print(f"뉴스 수집 오류: {e}")

    data = {
        "updated": updated,
        "day":     day,
        "night":   night,
        "kospi":   kospi,
        "indices": indices,
        "news":    news_items,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[{updated}] data.json 저장 완료 ✓")
    print(f"  KOSPI200: {day.get('price')} ({day.get('pct')}%)")
    print(f"  KOSPI:    {kospi.get('price')}")
    print(f"  뉴스:     {len(news_items)}건")


if __name__ == "__main__":
    main()
