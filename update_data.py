import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone

def fetch_eastmoney(report_name, page_size=6):
    url = (
        f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
        f"reportName={report_name}&columns=ALL&pageNumber=1&pageSize={page_size}"
        f"&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("result", {}).get("data", [])

def fetch_live_usdcny():
    # 获取实时美元兑人民币汇率
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return round(float(res["rates"]["CNY"]), 4)
    except Exception:
        return 6.6800

def call_github_ai(prompt_data):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None

    system_prompt = (
        "你是一位顶尖的宏观经济与外汇资产配置首席分析师。"
        "请根据用户提供的中国最新6个月宏观数据序列（贸易顺差、CPI同比、外汇储备）及实时汇率，"
        "结合环比变化趋势、连续升跌态势、以及‘人民币理财(1.5%) vs 美元理财(3.0%，扣除0.4%换汇点差后净利差仅1.1%)’的真实算账逻辑，"
        "生成深入、具体、不套话的动态分析。必须严格输出为合法的 JSON 对象，包含以下 6 个字段（每个字段 60~110 字，可使用 <b> 标签加粗关键数字和结论）：\n"
        "{\n"
        '  "insight_trade": "针对当月贸易顺差及近半年环比趋势的具体解读",\n'
        '  "insight_cpi": "针对当月CPI及近半年物价趋势对购买力影响的具体解读",\n'
        '  "insight_fx": "针对最新外汇储备规模及近半年增减变化的具体解读",\n'
        '  "sum_macro": "底部总结1：结合近半年三大数据真实变化，剖析当前财政内债与通缩顺差的宏观传导现状",\n'
        '  "sum_trend": "底部总结2：基于最新数据边际变化，研判未来1-3个月人民币汇率的支撑与潜在风险点",\n'
        '  "sum_action": "底部总结3：结合当前实时汇率，精确算出换美元的盈亏平衡汇率点位，给出手头人民币怎么存的具体实操建议"\n'
        "}"
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(prompt_data, ensure_ascii=False)}
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"}
    }

    req = urllib.request.Request(
        "https://models.inference.ai.azure.com/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=35) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"]
        return json.loads(content)

def main():
    tz_cn = timezone(timedelta(hours=8))
    usdcny = fetch_live_usdcny()
    # 存美元(3%)比存人民币(1.5%)扣除0.4%换汇磨损后只多赚1.1%，计算1年后不亏本的汇率临界点
    breakeven_rate = round(usdcny * (1 - 0.011), 4)

    trade_history, cpi_history, fx_history = [], [], []

    # 1. 抓取近6个月贸易顺差序列
    try:
        for row in fetch_eastmoney("RPT_ECONOMY_CUSTOMS", 6):
            exp_val, imp_val = row.get("EXIT_BASE"), row.get("IMPORT_BASE")
            if exp_val is not None and imp_val is not None:
                raw = float(exp_val) - float(imp_val)
                val = round(raw / 100000.0 if abs(raw) > 1000000 else raw, 1)
                trade_history.append({"date": str(row.get("REPORT_DATE", ""))[:7], "val": val})
    except Exception as e:
        print("Trade error:", e)

    # 2. 抓取近6个月CPI序列
    try:
        for row in fetch_eastmoney("RPT_ECONOMY_CPI", 6):
            val = row.get("NATIONAL_SAME")
            if val is not None:
                cpi_history.append({"date": str(row.get("REPORT_DATE", ""))[:7], "val": round(float(val), 2)})
    except Exception as e:
        print("CPI error:", e)

    # 3. 抓取近6个月外汇储备序列
    try:
        for row in fetch_eastmoney("RPT_ECONOMY_GOLD_CURRENCY", 6):
            val = row.get("FOREX")
            if val is not None:
                fx_v = float(val)
                fx_v = round(fx_v / 10000.0 if fx_v > 1000 else fx_v, 3)
                fx_history.append({"date": str(row.get("REPORT_DATE", ""))[:7], "val": fx_v})
    except Exception as e:
        print("FX error:", e)

    latest_trade = trade_history[0]["val"] if trade_history else 850.0
    prev_trade = trade_history[1]["val"] if len(trade_history) > 1 else latest_trade
    trade_diff = round(latest_trade - prev_trade, 1)

    latest_cpi = cpi_history[0]["val"] if cpi_history else 0.5
    prev_cpi = cpi_history[1]["val"] if len(cpi_history) > 1 else latest_cpi
    cpi_diff = round(latest_cpi - prev_cpi, 2)

    latest_fx = fx_history[0]["val"] if fx_history else 3.25
    prev_fx = fx_history[1]["val"] if len(fx_history) > 1 else latest_fx
    fx_diff_billion = round((latest_fx - prev_fx) * 10000, 1)

    # 构建动态量化分析兜底（含真实环比增减与盈亏平衡点计算）
    ai_insights = {
        "insight_trade": f"当月顺差 <b>{latest_trade} 亿美元</b>（较上月环比 <b>{'+' if trade_diff>=0 else ''}{trade_diff} 亿美元</b>）。近半年顺差序列为 {[x['val'] for x in trade_history[:4]]} 亿，外贸结汇底盘依然稳固。",
        "insight_cpi": f"当月 CPI 同比 <b>{latest_cpi}%</b>（较上月变动 <b>{'+' if cpi_diff>=0 else ''}{cpi_diff}%</b>）。近半年物价走势 {[x['val'] for x in cpi_history[:4]]}%，未出现印钞型恶性通胀，真实购买力坚挺。",
        "insight_fx": f"最新外储 <b>{latest_fx} 万亿美元</b>（较上月变动 <b>{'+' if fx_diff_billion>=0 else ''}{fx_diff_billion} 亿美元</b>），高出 3.0 万亿警戒线 <b>{round((latest_fx-3.0)*10000, 0)} 亿美元</b>。",
        "sum_macro": f"综合近半年走势：贸易顺差最新为 <b>{latest_trade}亿美元</b>（环比{'增加' if trade_diff>=0 else '减少'} {abs(trade_diff)}亿），CPI 处于 <b>{latest_cpi}%</b>。国内虽财政承压、利率极低，但内债靠低息展期消化，并未触发高通胀，巨额顺差持续提供硬通货支撑。",
        "sum_trend": f"当前外储达 <b>{latest_fx}万亿美元</b>（单月变动 {'+' if fx_diff_billion>=0 else ''}{fx_diff_billion}亿美元），叠加资本管制防线，空头难以撼动汇率。除非未来顺差连续跌破200亿且CPI冲破3.5%，否则人民币仍将保持强势韧性。",
        "sum_action": f"按当前实时汇率 <b>{usdcny}</b> 测算：3%美元理财扣除0.4%换汇磨损后仅比1.5%人民币理财多赚 <b>1.1%</b>。意味着1年后只要人民币升值突破 <b>{breakeven_rate}</b>，换美元就会倒亏本金！建议日常资金继续持有人民币稳健理财。"
    }

    # 调用 GitHub Models (GPT-4o-mini) 生成真 AI 深度分析
    try:
        prompt_payload = {
            "current_usdcny_rate": usdcny,
            "usd_breakeven_rate_1yr": breakeven_rate,
            "trade_balance_6m_billion_usd": trade_history,
            "cpi_yoy_6m_percent": cpi_history,
            "fx_reserve_6m_trillion_usd": fx_history
        }
        ai_res = call_github_ai(prompt_payload)
        if ai_res and "sum_macro" in ai_res:
            ai_insights.update(ai_res)
            ai_mode = "🤖 AI 大模型 (GPT-4o-mini) 结合近 6 个月趋势实时生成"
        else:
            ai_mode = "📐 量化趋势引擎动态计算"
    except Exception as e:
        print("AI call fallback:", e)
        ai_mode = "📐 量化趋势引擎动态计算"

    data = {
        "updated_at": datetime.now(tz_cn).strftime("%Y-%m-%d %H:%M") + f" · {ai_mode}",
        "usdcny": usdcny,
        "trade_balance": latest_trade,
        "trade_date": trade_history[0]["date"] if trade_history else "最新",
        "cpi_yoy": latest_cpi,
        "cpi_date": cpi_history[0]["date"] if cpi_history else "最新",
        "fx_reserve": latest_fx,
        "fx_date": fx_history[0]["date"] if fx_history else "最新",
        "ai_insights": ai_insights
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Successfully generated data.json with AI insights!")

if __name__ == "__main__":
    main()
