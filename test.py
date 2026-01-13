import requests, re
url = "https://ac.search.naver.com/nx/ac"
params = {'q':'삼성전자','where':'finance','r_format':'json'}
headers = {'User-Agent':'Mozilla/5.0'}
r = requests.get(url, params=params, headers=headers, timeout=5)
print("status:", r.status_code)
print("content-type:", r.headers.get('Content-Type'))
print("body preview:", r.text[:800])
m = re.search(r'\\b(\\d{6})\\b', r.text)
print("found code:", m.group(1) if m else "not found")
# JSON 파싱 시도
try:
    j = r.json()
    print("json keys:", list(j.keys())[:10])
except Exception as e:
    print("json parse failed:", e)
