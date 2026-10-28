# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx[http2]",
#     "tqdm",
# ]
# ///

import asyncio
import csv
import httpx
from tqdm.asyncio import tqdm
import sys
from urllib.parse import urlsplit

TIMEOUT = 10.0
MAX_CONCURRENT = 50
SUCCESS_STATUS_CODES = frozenset((401, 403, 405, 406, 429))

async def check_url(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, original_url: str, idx: int) -> tuple[int, str, str, str]:
    if not original_url:
        return idx, original_url, "none", ""

    url = original_url.strip()
    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    parsed = urlsplit(url)
    domain_part = parsed.netloc + parsed.path
    if parsed.query:
        domain_part += "?" + parsed.query
    if parsed.fragment:
        domain_part += "#" + parsed.fragment

    https_url = "https://" + domain_part
    http_url = "http://" + domain_part

    def is_success(status_code):
        # We consider 401 and 403 as success because the server is responding (likely a bot challenge).
        # We consider 405 (Method Not Allowed) as partial success and retry with GET.
        return status_code < 400 or status_code in SUCCESS_STATUS_CODES

    async def fetch(target_url):
        try:
            resp = await client.head(target_url, follow_redirects=True)
            if is_success(resp.status_code):
                return resp.status_code, None

            # If head fails or is not allowed, try GET
            resp = await client.get(target_url, follow_redirects=True)
            if is_success(resp.status_code):
                return resp.status_code, None
            return resp.status_code, f"Status {resp.status_code}"
        except Exception as e:
            return None, type(e).__name__

    async with semaphore:
        # 1. Try HTTPS
        https_status, https_error = await fetch(https_url)
        if https_error is None:
            return idx, https_url, "success", ""

        # 2. Try HTTP
        http_status, http_error = await fetch(http_url)
        if http_error is None:
            return idx, http_url, "success", ""

        # 3. Both failed
        # We log detailed errors for failed_urls.csv
        error_msg = f"HTTPS: {https_error} | HTTP: {http_error}"
        return idx, original_url, "failed", error_msg

async def main():
    csv.field_size_limit(sys.maxsize)

    with open('airports.csv', mode='r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    print(f"Loaded {len(rows)} airports.")

    url_idx = 6 # url column

    timeout = httpx.Timeout(TIMEOUT)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    # Dictionary to keep track of updated rows
    updated_rows = rows.copy()
    failed_entries = []

    # Identify rows that have URLs
    rows_to_check = [(i, row[url_idx]) for i, row in enumerate(rows) if row[url_idx].strip()]
    print(f"Found {len(rows_to_check)} airports with URLs.")

    limits = httpx.Limits(max_connections=None, max_keepalive_connections=None)
    async with httpx.AsyncClient(http2=True, timeout=timeout, verify=False, limits=limits) as client:
        # Use a real-world user agent
        client.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})

        tasks = [check_url(client, semaphore, url, idx) for idx, url in rows_to_check]

        for f in tqdm.as_completed(tasks, total=len(tasks)):
            idx, final_url, status, error_msg = await f

            if status == "success":
                updated_rows[idx][url_idx] = final_url
            elif status == "failed":
                failed_entries.append({
                    "airport_code": rows[idx][0],
                    "name": rows[idx][2],
                    "original_url": rows[idx][url_idx],
                    "error": error_msg
                })

    # Write updated airports.csv
    with open('airports.csv', mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(header)
        writer.writerows(updated_rows)

    print(f"Updated airports.csv successfully.")

    # Write failed URLs to failed_urls.csv
    if failed_entries:
        with open('failed_urls.csv', mode='w', encoding='utf-8', newline='') as f:
            fieldnames = ["airport_code", "name", "original_url", "error"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for entry in failed_entries:
                writer.writerow(entry)
        print(f"Logged {len(failed_entries)} failed URLs to failed_urls.csv.")
    else:
        print("No URLs failed!")

if __name__ == "__main__":
    asyncio.run(main())