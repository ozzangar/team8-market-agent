"""
Verify query_data reproduces the EXACT numbers in the 15 public reference answers.
Each check prints PASS/FAIL with the computed value vs the reference fact.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from agent.query_data import query_data, coverage

P = 0
F = 0
def check(label, got, expected):
    global P, F
    ok = got == expected
    if ok: P += 1
    else:  F += 1
    print(f"{'PASS' if ok else 'FAIL'} | {label}")
    if not ok:
        print(f"      got:      {got}")
        print(f"      expected: {expected}")

def approx(label, got, expected, tol):
    global P, F
    ok = got is not None and abs(got - expected) <= tol
    if ok: P += 1
    else:  F += 1
    print(f"{'PASS' if ok else 'FAIL'} | {label}  (got {got}, exp {expected} +/-{tol})")

print("="*70)
print("MHQ001 — RBA changes: 41 total, 20 inc, 21 dec (of 175)")
r = query_data("rba", "count_changes")
check("  total_records=175", r["total_records"], 175)
check("  changes=41", r["changes"], 41)
check("  increases=20", r["increases"], 20)
check("  decreases=21", r["decreases"], 21)

print("="*70)
print("MHQ035 — 2011-2013 easing: 8 cuts (2/4/2), -2.25pp, 4.75->2.50")
r = query_data("rba", "period_summary", start_year=2011, end_year=2013)
check("  n_cuts=8", r["n_cuts"], 8)
check("  by_year 2011=2", r["by_year"].get(2011), 2)
check("  by_year 2012=4", r["by_year"].get(2012), 4)
check("  by_year 2013=2", r["by_year"].get(2013), 2)
check("  cumulative=-2.25", r["cumulative_change"], -2.25)
check("  rate_before=4.75", r["rate_before"], 4.75)
check("  rate_after=2.50", r["rate_after"], 2.50)

print("="*70)
print("MHQ040 — ASX dims: 18 files, 1774 rows, 2015-01-02..2021-12-30")
r = query_data("asx", "dimensions")
check("  n_tickers=18", r["n_tickers"], 18)
check("  rows=1774", r["rows_per_ticker"], 1774)
check("  start=2015-01-02", r["start_date"], "2015-01-02")
check("  end=2021-12-30", r["end_date"], "2021-12-30")

print("="*70)
print("MHQ045 — 2018 best/worst ex-Tabcorp: BHP +22.17, AMP -50.04")
r = query_data("asx", "rank_annual_returns", year=2018, exclude_tabcorp=True)
check("  best ticker BHP.AX", r["best"]["ticker"], "BHP.AX")
approx("  best +22.17", r["best"]["return_pct"], 22.17, 0.02)
check("  worst ticker AMP.AX", r["worst"]["ticker"], "AMP.AX")
approx("  worst -50.04", r["worst"]["return_pct"], -50.04, 0.02)

print("="*70)
print("MHQ049 — highest avg volume ex-Tabcorp: AMP.AX 11,635,671.71")
r = query_data("asx", "avg_volume", exclude_tabcorp=True)
check("  highest AMP.AX", r["highest"]["ticker"], "AMP.AX")
approx("  avg_vol 11635671.71", r["highest"]["avg_volume"], 11635671.71, 1.0)

print("="*70)
print("MHQ055 — worst 3 drawdowns ex-Tabcorp")
r = query_data("asx", "max_drawdown", exclude_tabcorp=True, top=3)
w = r["worst"]
check("  #1 AMP.AX", w[0]["ticker"], "AMP.AX")
approx("  #1 -82.45", w[0]["drawdown_pct"], -82.45, 0.02)
check("  #1 peak 20 Mar 2015", w[0]["peak_date"], "20 Mar 2015")
check("  #1 trough 17 Dec 2021", w[0]["trough_date"], "17 Dec 2021")
check("  #2 AGL.AX", w[1]["ticker"], "AGL.AX")
approx("  #2 -76.24", w[1]["drawdown_pct"], -76.24, 0.02)
check("  #3 QAN.AX", w[2]["ticker"], "QAN.AX")
approx("  #3 -71.08", w[2]["drawdown_pct"], -71.08, 0.02)

print("="*70)
print("MHQ058 — rate in force 23 Feb 2021 = 0.10%")
r = query_data("rba", "lookup_rate", date="2021-02-23")
check("  rate=0.10", r["rate"], 0.10)

print("="*70)
print("MHQ061 — 'unemployment' peak year 2020=1452, peak month May2020=218")
r = query_data("afr", "peak_year_and_month", pattern=r"\bunemployment\b")
check("  peak_year=2020", r["peak_year"], "2020")
check("  peak_year_count=1452", r["peak_year_count"], 1452)
check("  peak_month=202005", r["peak_month"], "202005")
check("  peak_month_count=218", r["peak_month_count"], 218)

print("="*70)
print("MHQ067 — rate in force 25 Nov 2021 = 0.10%")
r = query_data("rba", "lookup_rate", date="2021-11-25")
check("  rate=0.10", r["rate"], 0.10)

print("="*70)
print("MHQ072 — after 5 Jun 2019 cut: target 1.25; basket & 5 tickers 5->12 Jun")
r = query_data("rba", "lookup_rate", date="2019-06-05")
check("  RBA rate 1.25", r["rate"], 1.25)
r = query_data("asx", "basket_window_return", start="2019-06-05", end="2019-06-12", exclude_tabcorp=True)
approx("  basket +2.88", r["basket_return_pct"], 2.88, 0.02)
approx("  CBA +0.60", r["constituents"].get("CBA.AX"), 0.60, 0.02)
approx("  NAB +1.39", r["constituents"].get("NAB.AX"), 1.39, 0.02)
approx("  ANZ +0.89", r["constituents"].get("ANZ.AX"), 0.89, 0.02)
approx("  BHP +5.89", r["constituents"].get("BHP.AX"), 5.89, 0.02)
approx("  RIO +2.91", r["constituents"].get("RIO.AX"), 2.91, 0.02)

print("="*70)
print("MHQ074 — three 2019 cuts one-week basket returns")
for (d0, d1, exp) in [("2019-06-05","2019-06-12",2.88),("2019-07-03","2019-07-10",0.24),("2019-10-02","2019-10-09",-2.17)]:
    r = query_data("asx", "basket_window_return", start=d0, end=d1, exclude_tabcorp=True)
    approx(f"  {d0}->{d1} {exp}", r["basket_return_pct"], exp, 0.02)

print("="*70)
print("MHQ076 — 2021 whole-word QBE count=369; QBE.AX 2021 return +35.57")
r = query_data("afr", "count_year", pattern=r"\bQBE\b", year=2021)
check("  QBE count 369", r["count"], 369)
r = query_data("asx", "annual_return", ticker="QBE.AX", year=2021)
approx("  QBE.AX +35.57", r["return_pct"], 35.57, 0.02)

print("="*70)
print("MHQ080 — basket 30 Nov->7 Dec 2020 = +2.37; rate 0.10")
r = query_data("rba", "lookup_rate", date="2020-11-28")
check("  rate=0.10", r["rate"], 0.10)
r = query_data("asx", "basket_window_return", start="2020-11-30", end="2020-12-07", exclude_tabcorp=True)
approx("  basket +2.37", r["basket_return_pct"], 2.37, 0.02)

print("="*70)
print("MHQ084 — 2019: 3 cuts -0.75 ->0.75; AFR pattern 3181; basket avg +20.11")
r = query_data("rba", "period_summary", start_year=2019, end_year=2019)
check("  n_cuts=3", r["n_cuts"], 3)
check("  cumulative=-0.75", r["cumulative_change"], -0.75)
check("  rate_after=0.75", r["rate_after"], 0.75)
r = query_data("afr", "count_year", pattern=r"interest rates?|cash rate|rate cut|rate hike|\bRBA\b", year=2019)
check("  AFR pattern 3181", r["count"], 3181)
# basket avg annual 2019 return = mean of 17 non-Tabcorp annual returns
rk = query_data("asx", "rank_annual_returns", year=2019, exclude_tabcorp=True)
avg = sum(x["return_pct"] for x in rk["ranking"]) / len(rk["ranking"])
approx("  basket avg +20.11", round(avg,2), 20.11, 0.05)

print("="*70)
print("MHQ090 — coverage: AFR/ASX end 2021, RBA to 2026 -> unsupported")
c = coverage()
print("  coverage:", c)

print("="*70)
print(f"RESULT: {P} passed, {F} failed")
sys.exit(1 if F else 0)
