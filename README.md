# 실시간 주식 가격(간단한 예제)

간단한 FastAPI + WebSocket 기반 예제입니다. 클라이언트가 종목(티커)을 보내면 서버가 yfinance로 주기적으로 조회해 가격을 전송합니다.

## 설치

1. 가상환경 생성 (권장)
   - python -m venv .venv
   - .venv\Scripts\activate
2. 의존성 설치
   - pip install -r requirements.txt

## 실행

- 개발서버 실행 (FastAPI):
  - uvicorn app:app --reload
  - 브라우저에서 http://localhost:8000 에 접속

- 개발서버 실행 (Flask, 간단 버전):
  - python flask_app.py
  - 브라우저에서 http://localhost:5000 에 접속

## 사용법
- 종목을 콤마(,)로 구분해 입력하고 갱신 간격(초)을 설정한 뒤 "구독 시작" 클릭
- 서버가 yfinance로 근사 실시간(분 단위) 가격을 주기적으로 조회해 실시간으로 업데이트합니다.

### 한국(코스피/코스닥) 티커 사용 예
- 티커로 숫자만 입력(예: `005930`, `035420`)하면 서버가 자동으로 `.KS`(코스피) 및 `.KQ`(코스닥)를 순서대로 시도해 조회합니다.
- `.KS` 또는 `.KQ`를 명시(예: `005930.KS`)하면 해당 심볼로 바로 조회합니다.

## 주의
- yfinance는 무료이며 진정한 실시간(틱 단위) 피드를 제공하지 않습니다. 거래소 수준의 실시간 데이터가 필요하면 유료 API(Finnhub, IEX, Alpaca 등)의 WebSocket/REST를 사용하세요.
