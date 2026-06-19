from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from patchright.async_api import async_playwright
import asyncio
import random

app = FastAPI(title="Iframe DOM Extractor")

async def extract_iframes(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,  # Patchright handles headless stealth natively
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process"
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        
        await context.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
        })

        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            await browser.close()
            return {"error": f"navigation failed: {e}"}

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        print("Attempting to trigger Cloudflare Turnstile...")
        
        # 1. Simulate human mouse movements on the main page
        for _ in range(3):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.2, 0.5))

        # 2. Try to click the Cloudflare checkbox if it appears
        try:
            cf_frame = page.frame_locator("iframe[src*='challenges.cloudflare.com']")
            # Wait for the checkbox to be ready (it might take a second to render)
            await cf_frame.locator("input[type='checkbox']").wait_for(timeout=5000)
            await cf_frame.locator("input[type='checkbox']").click()
            print("Clicked Cloudflare checkbox successfully!")
        except Exception as e:
            print(f"Checkbox click failed or not found: {e}")
            # Fallback: Click the coordinates of the Turnstile widget
            try:
                # The turnstile iframe is usually wrapped in a div with class 'cf-turnstile'
                widget = page.locator("div.cf-turnstile")
                box = await widget.bounding_box()
                if box:
                    # The checkbox is typically around x=30, y=height/2 relative to the widget
                    click_x = box['x'] + 30
                    click_y = box['y'] + (box['height'] / 2)
                    await page.mouse.move(click_x, click_y)
                    await asyncio.sleep(0.5)
                    await page.mouse.click(click_x, click_y)
                    print("Clicked Turnstile widget via coordinates.")
            except Exception as e2:
                print(f"Coordinate click also failed: {e2}")

        # 3. Wait for the Cloudflare Turnstile callback to redirect the iframe.
        print("Waiting for Turnstile verification and redirect...")
        start_time = asyncio.get_event_loop().time()
        timeout_sec = 20
        
        while asyncio.get_event_loop().time() - start_time < timeout_sec:
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
            if "challenges.cloudflare.com" in frame.url:
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
async def root(url: str = Query(None, description="x.com URL that embeds y.com")):
    if not url:
        return JSONResponse({"status": "ok", "message": "Service is running. Pass ?url=<site> to extract iframes."})

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
