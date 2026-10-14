"""Read monthly costs from the Azure Pricing Calculator with Playwright.

The calculator has no public API, so this script drives the web page: it adds one product per
scenario, fills the form fields (located by their ``name`` attribute) and reads the monthly total.
Every number is a *list price in USD, pay-as-you-go, no agreement discount*.

Run:  python scripts/azure_cost_estimate.py [--shots outputs/azure-cost] [--only aoai_]
      python scripts/azure_cost_estimate.py --export outputs/azure-cost/ExportedEstimate.xlsx
The second form puts the whole stack into ONE estimate and downloads the calculator's own
"Export" workbook, the file attached to Azure resource-request tickets.
Needs: pip install -e ".[test]" and python -m playwright install chromium

The scenarios mirror docs/research/azure-cost-estimate.md. If the calculator changes its form,
a field that cannot be set is reported under "failed" instead of silently producing a wrong total.
Prices of individual meters can be cross-checked with the public Azure Retail Prices API
(https://prices.azure.com/api/retail/prices), which needs no login.
"""
import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://azure.microsoft.com/en-us/pricing/calculator/"
SEA, JPE = "Southeast Asia", "Japan East"

# Token counts are in thousands (the calculator field is "x1,000 tokens").
# 6,000 runs, 70 % on the fast model and 30 % on the strong model, see the cost document.
FAST_IN, FAST_OUT = 151_200, 6_300      # 4,200 runs x 36k in / 1.5k out
STRONG_IN, STRONG_OUT = 64_800, 3_600   # 1,800 runs x 36k in / 2k out


def aoai(model, prompt, completion):
    return {"product": "Azure OpenAI", "set": {
        "region": JPE, "modelForLanguage": model, "pricingStrategy": "Standard (On-Demand)",
        "deploymentType": "Global", "prompt": prompt, "completion": completion}}


SCENARIOS = {
    # Container Apps, Consumption plan, 0.5 vCPU / 1 GiB. The calculator models only *active* time
    # (requests x execution time); it has no field for an idle always-on replica.
    "aca_light_traffic": {"product": "Container Apps", "set": {
        "region": SEA, "planType": "Consumption", "requestsInMillions": 0.05,
        "activeUsageConcurrentRequests": 20, "activeUsageExecutionMsPerRequest": 2000,
        "vCpuCount": "0.5", "memorySize": "1 GiB"}},
    "aca_always_active_31d": {"product": "Container Apps", "set": {
        "region": SEA, "planType": "Consumption", "requestsInMillions": 2.6784,
        "activeUsageConcurrentRequests": 1, "activeUsageExecutionMsPerRequest": 1000,
        "vCpuCount": "0.5", "memorySize": "1 GiB"}},
    # The calculator has no idle model. This case is sized so that its total equals what one replica
    # costs while idle for 26 days (0.5 vCPU + 1 GiB at 0.000004 USD/s each = 13.5 USD): about 1.003
    # million "active" seconds, after the monthly free grant the calculator applies.
    "aca_idle_equivalent_26d": {"product": "Container Apps", "set": {
        "region": SEA, "planType": "Consumption", "requestsInMillions": 1.0029,
        "activeUsageConcurrentRequests": 1, "activeUsageExecutionMsPerRequest": 1000,
        "vCpuCount": "0.5", "memorySize": "1 GiB"}},
    "acr_basic_30d": {"product": "Container Registry", "set": {
        "region": SEA, "tier": "Basic", "registry": 1, "days": 30, "storageUnits": 0, "cpus": 1, "buildUnits": 0}},
    # 30 USD plan: about 2,800 runs, all on gpt-6-luna (36k tokens in, 1.5k out per run)
    "aoai_plan30_gpt6_luna": aoai("GPT-6 Luna (short context)", 100_800, 4_200),
    "aoai_fast_gpt6_luna": aoai("GPT-6 Luna (short context)", FAST_IN, FAST_OUT),
    "aoai_strong_gpt6_sol": aoai("GPT-6 Sol (short context)", STRONG_IN, STRONG_OUT),
    "aoai_fast_gpt54_mini": aoai("GPT-5.4 mini", FAST_IN, FAST_OUT),
    "aoai_strong_gpt54": aoai("GPT-5.4 (<272k context length)", STRONG_IN, STRONG_OUT),
}


def read_totals(page):
    text = page.evaluate("document.body.innerText")
    out = {}
    for key, label in (("monthly_usd", "Estimated monthly cost"), ("upfront_usd", "Estimated upfront cost")):
        m = re.search(r"\$\s*([\d,]+\.\d\d)\s*\n?\s*/?\s*" + label, text)
        out[key] = float(m.group(1).replace(",", "")) if m else None
    return out


def add_product(page, scenario, region_first=False):
    """Add one product to the open estimate and fill its form.

    Products are appended in order, so the controls of the product just added are the *last* ones
    with that name, except for ``region`` of the first product when it has several region selects.
    """
    page.get_by_placeholder("Search products").fill(scenario["product"])
    page.wait_for_timeout(2500)
    page.get_by_role("button", name="Add to estimate").first.click()
    page.wait_for_timeout(4000)
    failed = {}
    for field, value in scenario["set"].items():
        group = page.locator(f"[name={field}]")
        control = group.first if (region_first and field == "region") else group.last
        try:
            if isinstance(value, str):
                control.select_option(label=value)
            else:
                control.fill(str(value))
                control.press("Tab")
        except Exception as exc:  # report, never guess
            failed[field] = str(exc).splitlines()[0][:100]
        page.wait_for_timeout(700)
    return failed


def open_calculator(browser):
    page = browser.new_context(viewport={"width": 1500, "height": 1200}, locale="en-US",
                               accept_downloads=True).new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(6000)
    return page


def run_scenario(pw, name, scenario, shots):
    browser = pw.chromium.launch(headless=True)
    try:
        page = open_calculator(browser)
        failed = add_product(page, scenario, region_first=True)
        page.wait_for_timeout(3500)
        result = {"scenario": name, **read_totals(page), "failed": failed}
        if shots:
            shots.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shots / f"{name}.png"), full_page=True)
        return result
    finally:
        browser.close()


# One estimate for the whole stack, in the order the products must be added (ACR first, because it
# has extra region selects). This is the 30 USD plan: one idle replica for 26 days plus ~2,800 runs.
EXPORT_ORDER = ["acr_basic_30d", "aca_idle_equivalent_26d", "aoai_plan30_gpt6_luna"]


def export_estimate(pw, target):
    browser = pw.chromium.launch(headless=True)
    try:
        page = open_calculator(browser)
        failed = {}
        for i, name in enumerate(EXPORT_ORDER):
            failed.update({f"{name}.{k}": v for k, v in add_product(page, SCENARIOS[name], region_first=(i == 0)).items()})
        page.wait_for_timeout(3500)
        totals = read_totals(page)
        target.parent.mkdir(parents=True, exist_ok=True)
        with page.expect_download(timeout=30_000) as download:
            page.get_by_role("button", name="Export").first.click()
        download.value.save_as(str(target))
        return {"export": str(target), "products": EXPORT_ORDER, **totals, "failed": failed}
    finally:
        browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shots", type=Path, help="folder for full-page screenshots (optional)")
    parser.add_argument("--only", default="", help="run only scenarios whose name contains this text")
    parser.add_argument("--days", type=int, help="length of the period in days for the Container Registry and the always-active Container Apps case (default 30/31)")
    parser.add_argument("--export", type=Path, help="build one estimate with the whole stack and save the calculator's Excel export here")
    args = parser.parse_args()
    if args.days:
        SCENARIOS["acr_basic_30d"]["set"]["days"] = args.days
        SCENARIOS["aca_always_active_31d"]["set"]["requestsInMillions"] = round(args.days * 86_400 / 1_000_000, 4)
        # active seconds S whose calculator price equals one idle replica for N days, after the free grant:
        # S * (0.5 * 0.000034 + 1 * 0.000004) - 7.56 = N * 86400 * 1.5 * 0.000004
        idle_usd = args.days * 86_400 * 1.5 * 0.000004
        SCENARIOS["aca_idle_equivalent_26d"]["set"]["requestsInMillions"] = round((idle_usd + 7.56) / 0.000021 / 1_000_000, 4)
    with sync_playwright() as pw:
        if args.export:
            results = [export_estimate(pw, args.export)]
        else:
            chosen = {n: s for n, s in SCENARIOS.items() if args.only in n}
            results = [run_scenario(pw, n, s, args.shots) for n, s in chosen.items()]
    print(json.dumps(results, indent=1))
    return 1 if any(r["failed"] or r["monthly_usd"] is None for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
