from flask import Flask, render_template, request, jsonify
import yfinance as yf
import requests
import datetime

app = Flask(__name__, template_folder='templates')

# Quick name -> symbol mapping for common Korean stocks to avoid unreliable remote lookups
NAME_TO_CODE = {
    '삼성전자': '005930.KS',
    'SK하이닉스': '000660.KS',
    '네이버': '035420.KS',
    '카카오': '035720.KS',
    '현대자동차': '005380.KS',
    '알지노믹스': '476830.KQ',
}


def fetch_price(ticker: str):
    """입력값(종목번호나 종목명)을 지원해 가격과 종목명을 조회합니다.

    반환 형식: dict {
        'requested': 원래 입력,
        'resolved': yfinance에 사용된 실제 심볼(예: 005930.KS) 또는 None,
        'name': 종목명(가능하면),
        'price': float 또는 None,
        'currency': 통화 문자열(예: KRW) 또는 None,
        'error': 에러 메시지 또는 None
    }
    동작 순서:
    1) 입력을 그대로 심볼로 시도
    2) 숫자만 입력 시 .KS, .KQ 순으로 시도
    3) 입력이 문자(종목명)인 경우 Yahoo Search API로 심볼을 찾아 시도
    4) 마지막으로 .KS/.KQ를 덧붙여 시도
    """
    def _fetch_sym(sym: str):
        try:
            app.logger.debug(f"Fetching symbol: {sym}")
            t = yf.Ticker(sym)
            # fast_info 시도 (더 빠를 수 있음)
            price = None
            fi = getattr(t, 'fast_info', None) or {}
            if isinstance(fi, dict):
                price = fi.get('last_price') or fi.get('last_close')
            # info에서 시도
            info = {}
            try:
                info = t.info or {}
            except Exception:
                app.logger.debug(f"t.info failed for {sym}")
            if price is None:
                price = info.get('regularMarketPrice') or info.get('previousClose') or info.get('open')
            # history fallback (분단위가 없을 수 있으므로 기간을 넉넉히)
            if price is None:
                try:
                    hist = t.history(period='5d', interval='1m')
                    if not hist.empty:
                        price = hist['Close'].iloc[-1]
                except Exception:
                    try:
                        hist = t.history(period='5d')
                        if not hist.empty:
                            price = hist['Close'].iloc[-1]
                    except Exception:
                        app.logger.debug(f"history failed for {sym}")
            currency = info.get('currency')
            name = info.get('shortName') or info.get('longName')
            if currency is None and ('.KS' in sym.upper() or '.KQ' in sym.upper()):
                currency = 'KRW'
            app.logger.debug(f"Result for {sym}: price={price}, currency={currency}, name={name}")
            return price, currency, name
        except Exception as e:
            app.logger.error(f"Exception fetching {sym}: {e}")
            return None, None, None

    def resolve_by_name(query: str):
        try:
            app.logger.debug(f"Resolving by name: {query}")
            url = 'https://query1.finance.yahoo.com/v1/finance/search'
            params = {'q': query, 'quotesCount': 10, 'newsCount': 0}
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.get(url, params=params, headers=headers, timeout=5)
            # 안전성: JSON이 아닌 경우(차단 등)에는 Yahoo 대신 Naver로 폴백
            if resp.status_code == 200 and resp.headers.get('Content-Type', '').lower().find('application/json') != -1:
                try:
                    data = resp.json()
                except Exception as e:
                    app.logger.debug(f"Yahoo returned non-json for '{query}': {e}")
                    data = None
            else:
                app.logger.debug(f"Yahoo search not usable (status={resp.status_code}, content-type={resp.headers.get('Content-Type')}), falling back to Naver")
                data = None

            if data:
                for q in data.get('quotes', []):
                    sym = q.get('symbol')
                    if not sym:
                        continue
                    up = sym.upper()
                    if up.endswith('.KS') or up.endswith('.KQ'):
                        return up, q.get('shortname') or q.get('longname')
                if data.get('quotes'):
                    first = data['quotes'][0]
                    return first.get('symbol'), first.get('shortname') or first.get('longname')

            # Naver으로 폴백: autocomplete JSON을 사용해 종목코드를 찾는다
            try:
                ac_url = 'https://ac.search.naver.com/nx/ac'
                ac_params = {'q': query, 'q_enc': 'utf-8', 'where': 'finance', 'st': '100', 'frm': 'autocomplete', 'r_format': 'json'}
                nheaders = {'User-Agent': headers['User-Agent']}
                nac = requests.get(ac_url, params=ac_params, headers=nheaders, timeout=5)
                if nac.status_code == 200 and nac.text:
                    # Log preview for debugging when body is unexpectedly empty/invalid
                    preview = nac.text[:800].strip()
                    app.logger.debug(f"Naver autocomplete response (len={len(nac.text)}): {preview[:300]}")
                    # JSON 응답 파싱 시도
                    try:
                        j = nac.json()
                        # JSON 내부에 종목 코드가 포함된 항목을 문자열로 검색
                        import re
                        s = str(j)
                        m = re.search(r"'code':\s*'?(\d{6})'?", s) or re.search(r'code\":\\"(\d{6})', s) or re.search(r'\b(\d{6})\b', s)
                        if m:
                            code = m.group(1)
                            app.logger.debug(f"Found code in Naver JSON: {code}")
                            return code + '.KS', query
                    except Exception as e:
                        app.logger.debug(f"Naver ac JSON parse failed: {e}")
                    # HTML/text에서도 시도
                    m2 = re.search(r'/item/main.naver\?code=(\d{6})', nac.text)
                    if m2:
                        code = m2.group(1)
                        app.logger.debug(f"Found code in Naver HTML: {code}")
                        return code + '.KS', query
            except Exception as e:
                app.logger.debug(f"Naver autocomplete fallback failed for '{query}': {e}")

        except Exception as e:
            app.logger.error(f"Error resolving name '{query}': {e}")
            return None, None
        return None, None

    orig = (ticker or '').strip()
    if not orig:
        return {'requested': ticker, 'resolved': None, 'name': None, 'price': None, 'currency': None, 'error': 'empty ticker'}

    # Fast-path: if name matches our small mapping, use it immediately
    mapped = NAME_TO_CODE.get(orig)
    if mapped:
        app.logger.debug(f"Using mapping for '{orig}' -> {mapped}")
        price, currency, name = _fetch_sym(mapped)
        if price is not None:
            return {'requested': orig, 'resolved': mapped, 'name': name, 'price': float(price), 'currency': currency or 'KRW', 'error': None}

    up = orig.upper()
    # 1) 입력 그대로 시도
    price, currency, name = _fetch_sym(up)
    if price is not None:
        return {'requested': orig, 'resolved': up, 'name': name, 'price': float(price), 'currency': currency or ("KRW" if ('.KS' in up or '.KQ' in up) else None), 'error': None}

    # 2) 숫자만 입력된 경우 .KS, .KQ 시도
    if '.' not in up and up.replace('-', '').isdigit():
        for suf in ['.KS', '.KQ']:
            cand = up + suf
            price, currency, name = _fetch_sym(cand)
            if price is not None:
                return {'requested': orig, 'resolved': cand, 'name': name, 'price': float(price), 'currency': currency or 'KRW', 'error': None}

    # 3) 입력이 문자(종목명)인 경우 Yahoo 검색으로 심볼 해석 시도
    if any(c.isalpha() for c in orig):
        sym, found_name = resolve_by_name(orig)
        if sym:
            price, currency, name2 = _fetch_sym(sym)
            if price is not None:
                return {'requested': orig, 'resolved': sym, 'name': found_name or name2, 'price': float(price), 'currency': currency or ("KRW" if ('.KS' in sym.upper() or '.KQ' in sym.upper()) else None), 'error': None}
            else:
                # 심볼은 찾았지만 가격이 없을 때 상세 오류 반환
                return {'requested': orig, 'resolved': sym, 'name': found_name or name2, 'price': None, 'currency': currency or ("KRW" if ('.KS' in sym.upper() or '.KQ' in sym.upper()) else None), 'error': 'symbol found but price unavailable'}

    # 4) 최종 fallback: .KS/.KQ 시도
    for suf in ['.KS', '.KQ']:
        cand = up + suf
        price, currency, name = _fetch_sym(cand)
        if price is not None:
            return {'requested': orig, 'resolved': cand, 'name': name, 'price': float(price), 'currency': currency or 'KRW', 'error': None}

    return {'requested': orig, 'resolved': None, 'name': None, 'price': None, 'currency': None, 'error': 'not found'}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/prices')
def prices():
    ticks = request.args.get('tickers', '')
    tickers = [s.strip() for s in ticks.split(',') if s.strip()]
    results = {}
    for t in tickers:
        results[t] = fetch_price(t)
    return jsonify({'prices': results, 'ts': datetime.datetime.utcnow().isoformat()})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
