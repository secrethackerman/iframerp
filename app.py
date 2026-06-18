from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright
import asyncio

app = FastAPI(title="Iframe DOM Extractor")

async def extract_iframes(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            await browser.close()
            return {"error": f"navigation failed: {e}"}

        # Wait for network to settle so the iframe has a chance to load
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Wait for the Cloudflare Turnstile callback to redirect the iframe.
        # The script appends '?_rcp=<32-char-token>' to the URL and reloads it.
        print("Waiting for Turnstile verification and redirect...")
        start_time = asyncio.get_event_loop().time()
        timeout_sec = 25
        
        while asyncio.get_event_loop().time() - start_time < timeout_sec:
            # Check if any frame's URL now contains the '_rcp' parameter
            if any("_rcp" in frame.url for frame in page.frames):
                print("Redirect detected! Waiting for DOM to render...")
                break
            await asyncio.sleep(0.5)
        else:
            print("Timeout waiting for _rcp. Extracting current DOM...")

        # Give the redirected iframe a moment to render its final DOM
        await asyncio.sleep(2)

        frames_out = []
        main = page.main_frame
        for frame in page.frames:
            if frame == main:
                continue
            entry = {"url": frame.url, "name": frame.name or None}
            try:
                html = await frame.content()
                entry["dom"] = html
                try:
                    title = await frame.title()
                    entry["title"] = title
                except Exception:
                    entry["title"] = None
            except Exception as e:
                entry["error"] = str(e)
                entry["dom"] = None
            frames_out.append(entry)

        await browser.close()
        return frames_out


@app.get("/")
async def root(url: str = Query(..., description="x.com URL that embeds y.com")):
    try:
        iframes = await extract_iframes(url)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    return JSONResponse(
        {
            "source_url": url,
            "iframe_count": len(iframes) if isinstance(iframes, list) else 0,
            "iframes": iframes,
        }
    )

@app.get("/healthz")
async def healthz():
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
