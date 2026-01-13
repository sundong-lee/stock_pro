from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio
import json
import datetime
import yfinance as yf

app = FastAPI()
# 정적 파일(프론트)를 /static에 마운트 (WebSocket 경로와 충돌 방지)
app.mount("/static", StaticFiles(directory="web/static"), name="static")

@app.get("/")
async def root():
    return FileResponse("web/index.html")


def fetch_sync(ticker: str):
    """yfinance를 사용해 최근 종가(근사 실시간)를 조회합니다."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1d", interval="1m")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        # fallback
        info = t.info
        price = info.get('regularMarketPrice')
        if price is not None:
            return float(price)
    except Exception:
        return None
    return None


async def fetch_loop(ws: WebSocket, state: dict):
    """연결된 클라이언트별로 주기적으로 가격을 조회해 전송합니다."""
    try:
        loop = asyncio.get_event_loop()
        while True:
            tickers = state.get('tickers', [])
            interval = state.get('interval', 5)
            if not tickers:
                await asyncio.sleep(1)
                continue
            results = {}
            tasks = [loop.run_in_executor(None, fetch_sync, t) for t in tickers]
            res = await asyncio.gather(*tasks)
            for t, p in zip(tickers, res):
                results[t] = p
            payload = {
                'prices': results,
                'ts': datetime.datetime.utcnow().isoformat()
            }
            await ws.send_text(json.dumps(payload))
            await asyncio.sleep(max(1, interval))
    except asyncio.CancelledError:
        return


@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state = {'tickers': [], 'interval': 5}
    fetch_task = None
    try:
        while True:
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
            except Exception:
                # 단순 텍스트는 무시
                continue
            # 예: {"tickers":["AAPL","TSLA"], "interval":2}
            if 'tickers' in data:
                state['tickers'] = [s.strip().upper() for s in data['tickers'] if s.strip()]
            if 'interval' in data:
                try:
                    state['interval'] = int(data['interval'])
                except Exception:
                    pass
            # fetch 루프 시작
            if fetch_task is None:
                fetch_task = asyncio.create_task(fetch_loop(ws, state))
    except WebSocketDisconnect:
        if fetch_task:
            fetch_task.cancel()
        return
    except Exception:
        if fetch_task:
            fetch_task.cancel()
        return


if __name__ == "__main__":
    # 편의상 `python app.py` 로도 uvicorn 서버를 실행할 수 있게 합니다.
    # 디폴트 포트는 8000입니다.
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)