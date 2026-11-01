# Tech Deals

A small local web app for discovering technology listings and following sale changes on Amazon, Flipkart, Blinkit and Walmart. It uses TinyFish Search, Fetch, Agent, Research, Monitor and Browser APIs.

## Run it on Windows

Open PowerShell in this folder and run:

```powershell
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
notepad .env
```

Replace `put_your_tinyfish_api_key_here` with your key and save. Then start the app:

```powershell
python deals.py
```

Open <http://127.0.0.1:8000>. Keep the terminal open while using the app. Press Ctrl+C in the terminal to stop it.

If the virtual environment is missing, create it and install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Features

- **Search:** Query selected retailer domains, localize the search region, and view live source links and snippets.
- **Fetch:** Extract the current content of a product page URL.
- **Agent:** Inspect a URL entered in the Agent card or a search result, returning product details, displayed price, original price, discount if shown, seller and availability.
- **Research:** Request a source-backed research report about a category or sale question.
- **Monitor:** Schedule a daily or six-hour page monitor for a known product listing.
- **Browser:** Create a remote browser session and show its connection details for direct CDP/Playwright use.
- **Shortlist:** Save recent search terms in browser local storage.

## Project files

- `deals.py` — local HTTP server, input validation and API routes.
- `tinyfish.py` — import-safe TinyFish API client.
- `web/index.html` — frontend structure.
- `web/styles.css` — responsive styling and interaction states.
- `web/app.js` — frontend behavior and API calls.
- `tests/test_app.py` — local smoke tests.

The API key is read by Python and stays on the server. Do not place the key in frontend JavaScript or commit your `.env` file.

## Notes

- Search results help discover listings; their snippets are not guaranteed to contain reliable, comparable prices. Use **Check displayed offer with Agent** on a result and verify the final checkout price on the retailer site.
- Pages and prices can differ by country, seller, inventory and time. Amazon India is used for India searches; Amazon US is used for US searches. The other store domains are searched as selected.
- Monitors recur on their TinyFish schedule and may consume usage. Manage or remove them through TinyFish's Monitor dashboard/API.
- Browser creates a remote session. This frontend displays the returned session data; connect to `cdp_url` from your own Playwright code for direct browser control.
- A TinyFish API key and network access are needed for live web calls. UI, health endpoint and request validation still run without a key.

## Test

Run the local tests without making TinyFish API calls. The integration test uses a fake client to confirm that every UI-backed API route reaches the matching TinyFish client method:

```powershell
python -m unittest discover -s tests -v
```

For official API details, see [TinyFish docs](https://docs.tinyfish.ai/).
