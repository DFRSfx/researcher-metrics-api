from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
import threading
import time
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

SCRAPER_KEY = "3a70ca2369ad3945c2e46ff97ec0b571"
SCRAPER_URL = "http://api.scraperapi.com"

SCOPUS_EMAIL = "a22307370@mail.islagaia.pt"
SCOPUS_PASSWORD = "DaSo22307370#"

_cache: dict = {}
_CACHE_TTL = 86400
_scholar_lock = threading.Lock()
_scopus_lock = threading.Lock()
_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        opts = webdriver.ChromeOptions()
        opts.binary_location = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        _driver = webdriver.Chrome(service=Service(ChromeDriverManager(driver_version="147.0.7727.102").install()), options=opts)
        _driver.maximize_window()
        log.info("Chrome driver started")
    return _driver


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: dict):
    _cache[key] = {"data": data, "ts": time.time()}


def _scrape_scholar(scholar_id: str) -> dict:
    log.info(f"Scraping Google Scholar: {scholar_id}")
    t0 = time.time()
    with _scholar_lock:
        resp = requests.get(
            SCRAPER_URL,
            params={
                "api_key": SCRAPER_KEY,
                "url": f"https://scholar.google.com/citations?user={scholar_id}&hl=en",
                "render": "false",
            },
            timeout=60,
        )
    log.info(f"Scholar scrape done in {time.time()-t0:.1f}s status={resp.status_code}")
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    name = soup.select_one("#gsc_prf_in")
    stats = soup.select("#gsc_rsb_st tbody tr")

    if not stats:
        raise ValueError("Could not parse Scholar page — possibly blocked")

    row_vals = [td.text for td in stats[0].select("td")]
    h_row = [td.text for td in stats[1].select("td")]
    i10_row = [td.text for td in stats[2].select("td")]

    return {
        "name": name.text if name else None,
        "h_index": int(h_row[1]) if h_row[1].isdigit() else None,
        "citations": int(row_vals[1]) if row_vals[1].isdigit() else None,
        "i10_index": int(i10_row[1]) if i10_row[1].isdigit() else None,
        "source": "google_scholar",
    }


def _scopus_login(driver):
    log.info("Logging into Scopus...")
    driver.get("https://www.scopus.com/home.uri")
    wait = WebDriverWait(driver, 20)

    # Dismiss cookie banner
    try:
        wait.until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler"))).click()
        log.info("Cookie banner dismissed")
        time.sleep(1)
    except Exception:
        log.info("No cookie banner found")

    # Click Sign in button
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='header-sign-in']"))).click()
    log.info("Clicked Sign in")

    # Dismiss cookie banner again if reappeared after sign in click
    try:
        cookie_btn = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler")))
        cookie_btn.click()
        log.info("Cookie banner dismissed (post sign-in)")
        time.sleep(1)
    except Exception:
        pass

    # Enter email on Elsevier ID page
    wait.until(EC.presence_of_element_located((By.ID, "bdd-email"))).send_keys(SCOPUS_EMAIL)
    driver.find_element(By.ID, "bdd-elsPrimaryBtn").click()
    log.info("Email submitted")

    # Dismiss cookie banner again if reappeared
    try:
        cookie_btn = driver.find_element(By.ID, "onetrust-reject-all-handler")
        if cookie_btn.is_displayed():
            cookie_btn.click()
            time.sleep(1)
    except Exception:
        pass

    # Enter password
    wait.until(EC.presence_of_element_located((By.ID, "bdd-password"))).send_keys(SCOPUS_PASSWORD)
    driver.find_element(By.ID, "bdd-elsPrimaryBtn").click()
    log.info("Password submitted")

    # Wait for redirect back to Scopus (any scopus page)
    wait.until(lambda d: "scopus.com" in d.current_url and "elsevier.com" not in d.current_url)
    log.info(f"Scopus login complete, at: {driver.current_url}")


_scopus_logged_in = False


def _scrape_scopus(scopus_id: str) -> dict:
    global _scopus_logged_in
    log.info(f"Scraping Scopus: {scopus_id}")
    t0 = time.time()

    with _scopus_lock:
        driver = _get_driver()
        wait = WebDriverWait(driver, 30)

        if not _scopus_logged_in:
            _scopus_login(driver)
            _scopus_logged_in = True

        driver.get(f"https://www.scopus.com/authid/detail.uri?authorId={scopus_id}")

        # Wait for h-index to appear
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='h-index-value'], .hindex-value")))
        except Exception:
            pass  # try parsing anyway

        soup = BeautifulSoup(driver.page_source, "html.parser")

    log.info(f"Scopus scrape done in {time.time()-t0:.1f}s")

    def _text(selector):
        el = soup.select_one(selector)
        return el.text.strip() if el else None

    def _int(selector):
        val = _text(selector)
        return int(val.replace(",", "")) if val and val.replace(",", "").isdigit() else None

    name = _text("[data-testid='author-profile-name']")
    h_index = _int("[data-testid='metrics-section-h-index'] [data-testid='unclickable-count']")
    citations = _int("[data-testid='metrics-section-citations-count'] [data-testid='unclickable-count']")
    documents = _int("[data-testid='metrics-section-document-count'] [data-testid='unclickable-count']")

    if h_index is None:
        with open("scopus_debug.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        raise ValueError("Could not parse Scopus page — check scopus_debug.html")

    return {
        "name": name,
        "h_index": h_index,
        "citations": citations,
        "documents": documents,
        "source": "scopus",
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("API ready")
    yield
    if _driver:
        _driver.quit()


app = FastAPI(lifespan=lifespan)


@app.get("/metrics")
def get_metrics(
    scholar_id: str = Query(None),
    scopus_id: str = Query(None)
):
    log.info(f"Request: scholar_id={scholar_id} scopus_id={scopus_id}")
    result = {}

    if scholar_id:
        cached = _cache_get(f"scholar:{scholar_id}")
        if cached:
            log.info(f"Cache hit: scholar:{scholar_id}")
            result["scholar"] = cached
        else:
            try:
                data = _scrape_scholar(scholar_id)
                _cache_set(f"scholar:{scholar_id}", data)
                result["scholar"] = data
            except Exception as e:
                log.error(f"Scholar error {scholar_id}: {e}")
                result["scholar"] = {"error": str(e)}

    if scopus_id:
        cached = _cache_get(f"scopus:{scopus_id}")
        if cached:
            log.info(f"Cache hit: scopus:{scopus_id}")
            result["scopus"] = cached
        else:
            try:
                data = _scrape_scopus(scopus_id)
                _cache_set(f"scopus:{scopus_id}", data)
                result["scopus"] = data
            except Exception as e:
                log.error(f"Scopus error {scopus_id}: {e}")
                result["scopus"] = {"error": str(e)}

    log.info(f"Response: {result}")
    return result
