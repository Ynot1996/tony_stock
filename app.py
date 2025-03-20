import requests
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, render_template, request
import mplfinance as mpf
import os

app = Flask(__name__)

# 確保有一個 static 資料夾來儲存圖片
if not os.path.exists("static"):
    os.makedirs("static")

# 定義函數來獲取個股指定日期區間的交易資料
def get_stock_data(stock_code, start_date, end_date):
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    current_date = start_date
    dfs = []

    while current_date <= end_date:
        params = {
            "response": "json",
            "date": current_date.strftime("%Y%m%d"),
            "stockNo": stock_code
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()

            if data["stat"] != "OK":
                print(f"無法獲取股票 {stock_code} 的資料（{current_date.strftime('%Y%m')}）：{data['stat']}")
                current_date = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)
                continue

            columns = data["fields"]
            raw_data = data["data"]
            df = pd.DataFrame(raw_data, columns=columns)

            df = df[["日期", "開盤價", "最高價", "最低價", "收盤價"]]
            df["日期"] = df["日期"].apply(lambda x: str(int(x.split("/")[0]) + 1911) + "-" + x.split("/")[1] + "-" + x.split("/")[2])
            df["日期"] = pd.to_datetime(df["日期"])

            for col in ["開盤價", "最高價", "最低價", "收盤價"]:
                df[col] = df[col].str.replace(",", "")
                df[col] = df[col].str.replace("X", "")
                df[col] = pd.to_numeric(df[col], errors="coerce")

            dfs.append(df)

        except Exception as e:
            print(f"發生錯誤（{current_date.strftime('%Y%m')}）：{e}")

        current_date = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)

    if not dfs:
        return None
    df = pd.concat(dfs, ignore_index=True)
    df = df[(df["日期"] >= start_date) & (df["日期"] <= end_date)]

    for col in ["開盤價", "最高價", "最低價", "收盤價"]:
        df[col] = df[col].apply(lambda x: round(x, 2) if pd.notnull(x) else "N/A")

    return df

# 首頁路由：顯示表單和結果
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        stock_code = request.form["stock_code"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]

        try:
            start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
            df = get_stock_data(stock_code, start_date_dt, end_date_dt)

            if df is not None and not df.empty:
                # 將 DataFrame 轉為 HTML 表格
                table_html = df.to_html(index=False, classes="table table-striped", justify="center")

                # 繪製 K 線圖並儲存為圖片
                df.set_index("日期", inplace=True)
                df.rename(columns={
                    "開盤價": "Open",
                    "最高價": "High",
                    "最低價": "Low",
                    "收盤價": "Close"
                }, inplace=True)

                chart_path = f"static/{stock_code}_kline.png"
                mpf.plot(df, type="candle", style="charles", title=f"{stock_code} K線圖 ({start_date} 至 {end_date})", 
                         ylabel="價格 (TWD)", figsize=(12, 6), savefig=chart_path)

                return render_template("index.html", table=table_html, stock_code=stock_code, 
                                     start_date=start_date, end_date=end_date, chart_path=chart_path)

            else:
                error = "無法獲取資料，請檢查股票代碼或日期是否正確。"
                return render_template("index.html", error=error)

        except Exception as e:
            error = f"發生錯誤：{str(e)}"
            return render_template("index.html", error=error)

    return render_template("index.html")

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5000))  # Render 會提供 PORT 環境變數，預設為 5000
    app.run(host="0.0.0.0", port=port)
