
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from playwright.sync_api import sync_playwright
import csv
import os
import time
import uuid

app = FastAPI()

USERNAME = "NCRDC4429"
PASSWORD = "Odinson1203"

def check_multiple_ids(id_list):
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.ncrdebthelp.co.za/")
        page.click("text='System LogIn'")
        page.fill("#cp_pagedata_f_login_username", USERNAME)
        page.fill("#cp_pagedata_f_login_password", PASSWORD)
        page.click("text='Proceed | LogIn'")
        page.wait_for_selector("a[href*='dhs_ManageRequestTransfers.aspx']", timeout=15000)
        page.click("a[href*='dhs_ManageRequestTransfers.aspx']")
        page.wait_for_selector("#cp_pagedata_lb_NewData", timeout=15000)
        page.click("#cp_pagedata_lb_NewData")

        for id_number in id_list:
            status = "NO DHS"
            dc_name = "NO DHS"

            try:
                page.fill("#cp_pagedata_f_RSAIDPass", id_number)
                time.sleep(1)
                page.click("#cp_pagedata_lb_ApplyDataFilter")

                row_selector = f"tr:has(td:text('{id_number}'))"

                try:
                    page.wait_for_selector(row_selector, timeout=6000)
                    status_selector = f"{row_selector} >> td:nth-child(6) >> div >> span"
                    status = page.locator(status_selector).inner_text().strip()

                    modal_trigger_selector = f"{row_selector} >> td:nth-child(8) >> div"
                    page.click(modal_trigger_selector)
                    page.wait_for_selector("iframe#IframePage", timeout=10000)
                    iframe = page.frame(name="IframePage")
                    if not iframe:
                        iframe = next(f for f in page.frames if "dhs_ViewDCDetails.aspx" in f.url)
                    iframe.wait_for_selector("#f_TradingName", timeout=10000)
                    dc_name = iframe.locator("#f_TradingName").inner_text().strip()
                    page.click("#cp_pagedata_btnHide")
                    time.sleep(1)

                except:
                    pass

            except:
                pass

            results.append({"id_number": id_number, "status": status, "debt_counsellor": dc_name})

        browser.close()
    return results

@app.post("/check_ids/")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    decoded = contents.decode("utf-8").splitlines()
    reader = csv.reader(decoded)
    next(reader, None)  # skip header
    id_list = [row[0].strip() for row in reader if row and row[0].strip()]
    result = check_multiple_ids(id_list)
    return JSONResponse(content={"results": result})
