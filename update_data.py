import json
import urllib.request
from datetime import datetime, timedelta, timezone

def fetch_eastmoney(report_name, columns="ALL", page_size=5, sort_Columns="REPORT_DATE", sort_Types="-1"):
    url = (
        f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
        f"reportName={report_name}&columns={columns}&pageNumber=1&pageSize={page_size}"
        f"&sortColumns={sort_Columns}&sortTypes={sort_Types}&source=WEB&client=WEB"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("result", {}).get("data", [])

def main():
    tz_cn = timezone(timedelta(hours=8))
    data = {
        "updated_at": datetime.now(tz_cn).strftime("%Y-%m-%d %H:%M (北京时间)"),
        "trade_balance": 850.0,
        "trade_date": "最新一期",
        "cpi_yoy": 0.5,
        "cpi_date": "最新一期",
        "fx_reserve": 3.25,
        "fx_date": "最新一期"
    }

    # 1. 获取海关进出口贸易顺差 (当月出口 EXIT_BASE - 当月进口 IMPORT_BASE)
    try:
        rows = fetch_eastmoney("RPT_ECONOMY_CUSTOMS")
        for row in rows:
            exp_val = row.get("EXIT_BASE")
            imp_val = row.get("IMPORT_BASE")
            if exp_val is not None and imp_val is not None:
                raw_balance = float(exp_val) - float(imp_val)
                # 海关原始单位为“千美元”，若绝对值大于 100万，则除以 100000 换算为“亿美元”
                if abs(raw_balance) > 1000000:
                    balance_billion_usd = raw_balance / 100000.0
                else:
                    balance_billion_usd = raw_balance
                data["trade_balance"] = round(balance_billion_usd, 1)
                data["trade_date"] = str(row.get("REPORT_DATE", ""))[:7]
                break
    except Exception as e:
        print("Trade fetch error:", e)

    # 2. 获取中国 CPI 同比 (RPT_ECONOMY_CPI)
    try:
        rows = fetch_eastmoney("RPT_ECONOMY_CPI")
        for row in rows:
            val = row.get("NATIONAL_SAME")
            if val is not None:
                data["cpi_yoy"] = round(float(val), 2)
                data["cpi_date"] = str(row.get("REPORT_DATE", ""))[:7]
                break
    except Exception as e:
        print("CPI fetch error:", e)

    # 3. 获取国家外汇储备 (RPT_ECONOMY_GOLD_CURRENCY)
    try:
        rows = fetch_eastmoney("RPT_ECONOMY_GOLD_CURRENCY")
        for row in rows:
            val = row.get("FOREX")
            if val is not None:
                fx_val = float(val)
                # 东方财富外储单位为“亿美元”，除以 10000 换算为“万亿美元”
                if fx_val > 1000:
                    fx_val = fx_val / 10000.0
                data["fx_reserve"] = round(fx_val, 3)
                data["fx_date"] = str(row.get("REPORT_DATE", ""))[:7]
                break
    except Exception as e:
        print("FX fetch error:", e)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Saved data.json:", data)

if __name__ == "__main__":
    main()
