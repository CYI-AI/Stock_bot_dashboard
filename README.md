# AI 한국주식 포트폴리오 대시보드

가치 + 모멘텀 전략으로 운영되는 한국 주식 자동매매 포트폴리오의 실시간 대시보드.

## 페이지

- 💰 **자산 현황** — 평가금액, 운영 시작 대비 누적 수익률 곡선, 자산 분포
- 📦 **보유 종목** — 종목별 매수 근거와 매도 기준 (목표가·손절가·추격손절)
- 🎯 **AI 판단** — 오늘의 매매 계획, 보유 종목 점검, 매수 후보 선별 과정

## 구조

```
[봇 머신] (private)
  봇 운영 + KIS API 키
   │
   │ 10분마다 push (snapshot JSON만)
   ▼
[이 레포] (public)
  대시보드 코드 + data/dashboard_snapshot.json
   │
   ▼
[Streamlit Cloud]
  https://your-app.streamlit.app
```

## 보안

- 이 레포는 대시보드 코드와 정제된 스냅샷 데이터만 포함
- KIS API 키, 매매 권한, 봇 로직은 별도 private 레포에 격리
- 대시보드 서버가 침투당해도 봇 머신에 절대 접근 불가
- 단방향 데이터 흐름 (봇 → 대시보드)

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run dashboard/longid_dashboard.py
```
