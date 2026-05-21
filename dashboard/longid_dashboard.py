"""AI 한국주식 포트폴리오 대시보드 (Streamlit)

스타일: Toss/Robinhood 톤 — Pretendard + 퍼플 액센트 + 오프화이트
실행:
  streamlit run dashboard/longid_dashboard.py --server.address 0.0.0.0 --server.port 8501

페이지:
  💰 자산 현황   — 평가금액 + 누적 수익률 곡선 + 자산 분포
  📦 보유 종목   — 종목별 매수/매도 기준 + 매매 이력
  🎯 AI 판단    — 오늘 계획 + 보유 점검 + 종목 선별 사유
"""

from __future__ import annotations

import html
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

import streamlit as st
import pandas as pd


def esc(s) -> str:
    """외부 데이터(LLM/KIS 응답)를 HTML에 박기 전 escape — XSS 방어."""
    if s is None:
        return ""
    return html.escape(str(s), quote=True)

# 프로젝트 루트
_THIS = Path(__file__).resolve()
ROOT = _THIS.parent.parent
sys.path.insert(0, str(ROOT))

# ── Streamlit 설정 ────────────────────────────────────────────────

st.set_page_config(
    page_title="AI 한국주식 포트폴리오",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ── 디자인 토큰 (Style C — Toss/Robinhood) ──────────────────────

THEME = {
    "bg": "#fafafa",
    "card": "#ffffff",
    "text": "#1a1a1a",
    "text_muted": "#6b7280",
    "border": "#e5e7eb",
    "accent": "#8b5cf6",   # 퍼플
    "accent_soft": "#ede9fe",
    "up": "#10b981",       # 민트
    "down": "#ef4444",     # 레드
    "flat": "#9ca3af",
}


def inject_global_css() -> None:
    """전역 CSS — Pretendard 웹폰트 + Style C 시스템."""
    css = f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

    html, body, [class*="css"] {{
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif !important;
        font-feature-settings: 'tnum';
    }}

    .stApp {{
        background: {THEME['bg']};
        color: {THEME['text']};
    }}

    /* 모든 텍스트 요소 명시적으로 다크 컬러 (다크모드 OS 대응) */
    .stApp, .stApp p, .stApp span, .stApp div, .stApp li,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stMarkdown, .stMarkdown p, .stText, .stCaption,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stText"],
    .stRadio label, .stRadio div,
    .stSelectbox label, .stTextInput label,
    .stDataFrame, .stTable,
    [data-testid="stWidgetLabel"] {{
        color: {THEME['text']};
    }}

    /* Streamlit 위젯 라벨 — 더 옅게 */
    [data-testid="stWidgetLabel"] p {{
        color: {THEME['text_muted']};
    }}

    /* 탭 텍스트 */
    button[data-baseweb="tab"] {{
        color: {THEME['text_muted']} !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {THEME['accent']} !important;
    }}

    /* dataframe / table */
    .stDataFrame table, .stDataFrame thead, .stDataFrame tbody, .stDataFrame tr, .stDataFrame td, .stDataFrame th {{
        color: {THEME['text']} !important;
    }}

    /* expander 헤더 */
    [data-testid="stExpander"] summary {{
        color: {THEME['text']} !important;
    }}

    /* input/select 박스 */
    .stTextInput input, .stSelectbox div[role="combobox"] {{
        color: {THEME['text']} !important;
        background: {THEME['card']} !important;
    }}

    /* alert/info/warning */
    .stAlert, [data-testid="stAlert"] {{
        color: {THEME['text']};
    }}

    /* Streamlit 기본 헤더/푸터 숨김 */
    header[data-testid="stHeader"] {{ background: transparent; }}
    footer {{ visibility: hidden; }}
    #MainMenu {{ visibility: hidden; }}

    /* 본문 폭 약간 좁게 — 모바일에서도 보기 좋게 */
    .block-container {{
        max-width: 1100px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }}

    /* 사이드바 */
    section[data-testid="stSidebar"] {{
        background: #ffffff;
        border-right: 1px solid {THEME['border']};
    }}

    /* 카드 — Toss 스타일 */
    .card {{
        background: {THEME['card']};
        border-radius: 16px;
        padding: 24px;
        border: 1px solid {THEME['border']};
        margin-bottom: 16px;
    }}
    .card-tight {{
        background: {THEME['card']};
        border-radius: 14px;
        padding: 16px 20px;
        border: 1px solid {THEME['border']};
        margin-bottom: 12px;
    }}

    /* Hero 평가금액 */
    .hero-label {{
        color: {THEME['text_muted']};
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 8px;
    }}
    .hero-value {{
        color: {THEME['text']};
        font-size: 44px;
        font-weight: 700;
        line-height: 1.1;
        letter-spacing: -1px;
    }}
    .hero-delta {{
        font-size: 16px;
        font-weight: 600;
        margin-top: 8px;
    }}
    .delta-up {{ color: {THEME['up']}; }}
    .delta-down {{ color: {THEME['down']}; }}
    .delta-flat {{ color: {THEME['flat']}; }}

    /* KPI 미니 카드 */
    .kpi-label {{
        color: {THEME['text_muted']};
        font-size: 13px;
        font-weight: 500;
        margin-bottom: 4px;
    }}
    .kpi-value {{
        color: {THEME['text']};
        font-size: 22px;
        font-weight: 700;
    }}
    .kpi-sub {{
        color: {THEME['text_muted']};
        font-size: 12px;
        margin-top: 4px;
    }}

    /* 페이지 타이틀 */
    .page-title {{
        font-size: 28px;
        font-weight: 700;
        color: {THEME['text']};
        margin: 0 0 4px 0;
        letter-spacing: -0.5px;
    }}
    .page-sub {{
        color: {THEME['text_muted']};
        font-size: 14px;
        margin-bottom: 24px;
    }}

    /* 종목 카드 */
    .stock-card {{
        background: {THEME['card']};
        border-radius: 16px;
        padding: 20px;
        border: 1px solid {THEME['border']};
        margin-bottom: 12px;
        transition: border-color 0.15s;
    }}
    .stock-name {{
        font-size: 17px;
        font-weight: 700;
        color: {THEME['text']};
    }}
    .stock-code {{
        font-size: 12px;
        color: {THEME['text_muted']};
        margin-left: 6px;
    }}
    .stock-sector {{
        display: inline-block;
        background: {THEME['accent_soft']};
        color: {THEME['accent']};
        font-size: 11px;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 20px;
        margin-left: 8px;
    }}

    /* 배지 — 결과 표시 */
    .badge {{
        display: inline-block;
        font-size: 11px;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 20px;
        letter-spacing: 0.3px;
    }}
    .badge-pass {{ background: #dcfce7; color: #15803d; }}
    .badge-warning {{ background: #fef3c7; color: #b45309; }}
    .badge-reject {{ background: #fee2e2; color: #b91c1c; }}
    .badge-skip {{ background: #f3f4f6; color: #4b5563; }}
    .badge-purple {{ background: {THEME['accent_soft']}; color: {THEME['accent']}; }}

    /* st.container(border=True) — Toss 카드와 톤 통일 */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: {THEME['card']};
        border-radius: 16px !important;
        padding: 20px !important;
        border: 1px solid {THEME['border']} !important;
        margin-bottom: 16px;
    }}

    /* Streamlit metric 비활성화 (직접 카드 사용) */
    [data-testid="stMetric"] {{
        background: {THEME['card']};
        border-radius: 14px;
        padding: 16px 20px;
        border: 1px solid {THEME['border']};
    }}
    [data-testid="stMetricLabel"] {{
        color: {THEME['text_muted']};
        font-size: 13px;
    }}
    [data-testid="stMetricValue"] {{
        color: {THEME['text']};
        font-size: 22px;
        font-weight: 700;
    }}

    /* expander */
    .streamlit-expanderHeader {{
        background: transparent;
        border-radius: 12px;
    }}

    /* 라디오 (사이드바) */
    div[role="radiogroup"] label {{
        padding: 8px 12px;
        border-radius: 10px;
    }}

    /* 마진/패딩 미세 조정 */
    .small-gap {{ margin-bottom: 8px; }}
    hr {{
        border: none;
        border-top: 1px solid {THEME['border']};
        margin: 24px 0;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# ── 데이터 로더 ──────────────────────────────────────────────────


# 통합 snapshot 단일 출처. refresh_dashboard_data.py가 10분마다 모든 데이터 통합.
# 대시보드는 이 파일 하나만 읽음 (KIS 호출 0회, .env/DB 접근 0회).


@st.cache_data(ttl=30)
def load_snapshot() -> dict:
    p = ROOT / "data" / "dashboard_snapshot.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_error": f"snapshot 로드 실패: {e}"}


def load_balance() -> dict:
    snap = load_snapshot()
    if snap.get("_error"):
        return {"_error": snap["_error"]}
    bal = snap.get("balance", {})
    if not bal:
        return {"_error": "스냅샷에 잔고 없음 — refresh 스크립트 미실행"}
    return bal


def load_pnl_history() -> dict:
    snap = load_snapshot()
    if snap.get("_error"):
        return {"ok": False, "error": snap["_error"], "items": [], "summary": {}}
    return snap.get("pnl_history", {"ok": False, "items": [], "summary": {}})


def load_portfolio() -> dict:
    return load_snapshot().get("portfolio", {}) or {}


def load_history() -> list:
    return load_snapshot().get("history", []) or []


def load_reviews() -> list:
    return load_snapshot().get("reviews", []) or []


def load_daily_plan() -> dict:
    return load_snapshot().get("daily_plan", {}) or {}


def load_decision_log_latest() -> dict:
    return load_snapshot().get("decision_log_latest", {}) or {}


def load_filter_stage1_summary() -> dict:
    return load_snapshot().get("filter_stage1_summary", {}) or {}


def load_filter_stage1_rejected() -> list:
    return load_snapshot().get("filter_stage1_rejected", []) or []


def load_filter_stage3() -> dict:
    return load_snapshot().get("filter_stage3", {}) or {}


def load_asset_history() -> list:
    return load_snapshot().get("asset_history", []) or []


def get_refresh_time() -> str:
    return load_snapshot().get("refreshed_at", "")


def get_operation_start() -> str:
    return load_snapshot().get("operation_start", "2026-04-15")


# ── 헬퍼 ────────────────────────────────────────────────────────


def fmt_won(amount, sign: bool = False) -> str:
    try:
        v = int(amount)
        if sign:
            return f"{v:+,}원"
        return f"{v:,}원"
    except (ValueError, TypeError):
        return "—"


def fmt_pct(value, decimals: int = 2, sign: bool = True) -> str:
    try:
        v = float(value)
        if sign:
            return f"{v:+.{decimals}f}%"
        return f"{v:.{decimals}f}%"
    except (ValueError, TypeError):
        return "—"


def color_class(value) -> str:
    try:
        v = float(value)
        if v > 0:
            return "delta-up"
        if v < 0:
            return "delta-down"
        return "delta-flat"
    except (ValueError, TypeError):
        return "delta-flat"


def parse_date(s: str):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def hero_block(label: str, value: str, delta: str = "", delta_class: str = "") -> str:
    """Hero 메인 숫자 — 페이지 1 상단용."""
    delta_html = f'<div class="hero-delta {delta_class}">{delta}</div>' if delta else ""
    return f"""
    <div class="card">
      <div class="hero-label">{label}</div>
      <div class="hero-value">{value}</div>
      {delta_html}
    </div>
    """


def kpi_block(label: str, value: str, sub: str = "") -> str:
    """KPI 미니 카드 — 4-column 그리드용."""
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="card-tight">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      {sub_html}
    </div>
    """


# ── Plotly 차트 (Style C 톤) ───────────────────────────────────


def plot_return_pct(series: list) -> "go.Figure":
    """운영 시작 대비 누적 수익률 곡선 — 일별 평가액 시계열 기반."""
    import plotly.graph_objects as go

    if not series:
        return go.Figure().add_annotation(
            text="데이터 없음", showarrow=False,
            xref="paper", yref="paper", x=0.5, y=0.5,
        )

    df = pd.DataFrame(series)
    df["date"] = pd.to_datetime(df["date"])

    # 양수/음수에 따라 fill 색상 변경
    last_pct = df["return_pct"].iloc[-1]
    line_color = THEME["up"] if last_pct >= 0 else THEME["down"]
    fill_color = "rgba(16, 185, 129, 0.08)" if last_pct >= 0 else "rgba(239, 68, 68, 0.08)"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["return_pct"],
        mode="lines",
        line=dict(color=line_color, width=2.5, shape="spline"),
        fill="tozeroy",
        fillcolor=fill_color,
        name="수익률",
        customdata=df["eval_amt"],
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>수익률 %{y:+.2f}%<br>평가액 %{customdata:,.0f}원<extra></extra>",
    ))
    fig.add_hline(y=0, line=dict(color=THEME["border"], width=1, dash="dot"))

    fig.update_layout(
        height=340,
        margin=dict(l=20, r=20, t=10, b=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Pretendard", color=THEME["text"], size=12),
        xaxis=dict(showgrid=False, showline=False, ticks="", tickformat="%m/%d"),
        yaxis=dict(
            showgrid=True, gridcolor=THEME["border"], gridwidth=1,
            zeroline=False, ticks="",
            ticksuffix="%",
        ),
        hovermode="x unified",
    )
    return fig


def plot_portfolio_donut(positions: list) -> "go.Figure":
    """포트폴리오 종목별 비중 도넛."""
    import plotly.graph_objects as go

    if not positions:
        return go.Figure()

    labels = [p.get("name", p.get("code", "?")) for p in positions]
    values = [p.get("evlu_amt", 0) for p in positions]
    if sum(values) == 0:
        return go.Figure()

    # 퍼플 그라데이션 톤
    palette = ["#8b5cf6", "#a78bfa", "#c4b5fd", "#ddd6fe", "#ede9fe",
               "#7c3aed", "#6d28d9", "#5b21b6"]
    colors = (palette * 10)[:len(labels)]

    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=labels,
        values=values,
        hole=0.65,
        marker=dict(colors=colors, line=dict(color="#ffffff", width=2)),
        textposition="outside",
        texttemplate="%{label}<br>%{percent}",
        hovertemplate="<b>%{label}</b><br>%{value:,}원<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(family="Pretendard", size=12),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ═════════════════════════════════════════════════════════════════
# Page 1: 자산 현황
# ═════════════════════════════════════════════════════════════════


def page_assets():
    st.markdown('<div class="page-title">💰 자산 현황</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">가치 + 모멘텀 전략 · 2026-04-15 운영 시작 · 정규장 종가 기준</div>', unsafe_allow_html=True)

    balance = load_balance()
    pnl_raw = load_pnl_history()
    asset_hist = load_asset_history()

    # 운영 시작일 — snapshot에서 가져옴 (단일 출처)
    OPERATION_START = get_operation_start()
    pnl_items_filtered = [it for it in pnl_raw.get("items", []) if it.get("date", "") >= OPERATION_START]
    pnl_filtered_summary = {
        "total_realized_pnl": sum(it.get("rlzt_pfls", 0) for it in pnl_items_filtered),
        "total_fee": sum(it.get("fee", 0) for it in pnl_items_filtered),
        "total_tax": sum(it.get("tl_tax", 0) for it in pnl_items_filtered),
        "total_buy": sum(it.get("buy_amt", 0) for it in pnl_items_filtered),
        "total_sell": sum(it.get("sll_amt", 0) for it in pnl_items_filtered),
    }
    pnl = {"ok": pnl_raw.get("ok", False), "items": pnl_items_filtered, "summary": pnl_filtered_summary}

    # ── Hero: 평가금액 ────────────────────────────────────
    if balance and not balance.get("_error"):
        total = balance.get("total_eval", 0)
        daily_chg = balance.get("daily_change", 0)
        daily_pct = balance.get("daily_change_rate", 0)

        delta_text = f"{fmt_won(daily_chg, sign=True)} · {fmt_pct(daily_pct)} (전일 대비)"
        st.markdown(
            hero_block("총 평가금액", fmt_won(total), delta_text, color_class(daily_chg)),
            unsafe_allow_html=True,
        )
    else:
        err = balance.get("_error", "잔고 조회 실패")
        st.markdown(hero_block("총 평가금액", "—", f"잔고 조회 실패: {err}", "delta-flat"), unsafe_allow_html=True)

    # ── KPI 4종 ──────────────────────────────────────────
    summary = pnl.get("summary", {}) if pnl.get("ok") else {}
    total_realized = summary.get("total_realized_pnl", 0)
    total_fee = summary.get("total_fee", 0)
    total_tax = summary.get("total_tax", 0)

    cash_t0 = balance.get("cash_t0", 0) if balance and not balance.get("_error") else 0
    cash_t2 = balance.get("cash_t2", 0) if balance and not balance.get("_error") else 0
    stocks_eval = balance.get("stocks_eval", 0) if balance and not balance.get("_error") else 0
    holdings_n = len(balance.get("positions", []) or []) if balance and not balance.get("_error") else 0
    current_total = balance.get("total_eval", 0) if balance and not balance.get("_error") else 0
    current_unrealized = balance.get("total_pnl", 0) if balance and not balance.get("_error") else 0

    # 운영 시작 자본 추정 → 누적 수익률 계산
    total_return_amt = total_realized + current_unrealized  # 실현 + 미실현
    start_capital = current_total - total_return_amt if current_total > 0 else 0
    cumulative_return_pct = (total_return_amt / start_capital * 100) if start_capital > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        # 메인 KPI — 운영 시작 대비 누적 수익률
        st.markdown(kpi_block("누적 수익률",
                              fmt_pct(cumulative_return_pct),
                              f"운영 시작 대비 {fmt_won(total_return_amt, sign=True)}"), unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_block("실현 손익", fmt_won(total_realized, sign=True),
                              f"수수료 {fmt_won(total_fee)} · 거래세 {fmt_won(total_tax)}"), unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_block("미실현 손익", fmt_won(current_unrealized, sign=True),
                              f"{holdings_n}종목 보유 · 평가 {fmt_won(stocks_eval)}"), unsafe_allow_html=True)
    with c4:
        # 예수금 (당일) + D+2 (실제 매수가능)
        st.markdown(kpi_block("예수금", fmt_won(cash_t0),
                              f"매수가능 {fmt_won(cash_t2)} (D+2)"), unsafe_allow_html=True)

    st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)

    # ── 일별 평가액 + 운영 시작 대비 수익률 시계열 ─────
    def _build_return_series(pnl_data: dict, current_eval: int, current_pnl: int) -> tuple:
        """
        일별 평가액 시계열 + 누적 수익률 % 시계열 구축.

        시작 평가액 추정:
          시작 자본 = 현재 총평가 - 누적 실현손익
          (= 매매 없었다면 오늘 갖고 있을 자본; 추가 입출금 없다고 가정)

        일별 평가액 추정:
          그날 평가액 ≈ 시작 자본 + 그날까지 누적 실현손익
          (미실현 변동은 일별로 알 수 없어 점프 없이 누적 실현만 반영)

        마지막 점은 실제 현재 평가액 (미실현 포함) — KPI와 정확히 일치.
        """
        items = pnl_data.get("items", []) if pnl_data.get("ok") else []
        if not items or current_eval <= 0:
            return [], 0

        start_eval = current_eval - current_pnl  # 시작 자본 추정
        if start_eval <= 0:
            return [], 0

        # 시작점 (운영 시작 전날 = 거래일 이전)
        from datetime import datetime as _dt, timedelta as _td
        first_trade_date = items[0].get("date", "")
        try:
            start_date = (_dt.fromisoformat(first_trade_date) - _td(days=1)).strftime("%Y-%m-%d")
        except Exception:
            start_date = first_trade_date

        series = [{"date": start_date, "eval_amt": start_eval, "return_pct": 0.0}]
        running_realized = 0
        for it in items:
            running_realized += it.get("rlzt_pfls", 0)
            eval_estimate = start_eval + running_realized
            series.append({
                "date": it.get("date"),
                "eval_amt": eval_estimate,
                "return_pct": (eval_estimate / start_eval - 1) * 100,
            })
        # 마지막 점은 실제 현재 평가액 (미실현 포함)
        from datetime import date as _date
        today = _date.today().strftime("%Y-%m-%d")
        last_in_series = series[-1]["date"]
        if today != last_in_series:
            series.append({
                "date": today,
                "eval_amt": current_eval,
                "return_pct": (current_eval / start_eval - 1) * 100,
            })
        else:
            # 마지막 점을 실제값으로 교체 (미실현 포함)
            series[-1]["eval_amt"] = current_eval
            series[-1]["return_pct"] = (current_eval / start_eval - 1) * 100

        return series, start_eval

    # ── 운영 시작 대비 수익률 차트 ────────────────────────
    return_series, _start_eval = _build_return_series(pnl, current_total, total_return_amt)

    with st.container(border=True):
        st.markdown('<div class="hero-label">운영 시작 대비 누적 수익률</div>', unsafe_allow_html=True)
        if return_series:
            final_pct = return_series[-1]["return_pct"]
            cls = color_class(final_pct)
            arrow = "▲" if final_pct > 0 else ("▼" if final_pct < 0 else "—")
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:baseline; margin:8px 0 16px;">
              <div class="{cls}" style="font-size:32px; font-weight:700;">
                {arrow} {fmt_pct(final_pct)}
              </div>
              <div style="color:{THEME['text_muted']}; font-size:13px;">
                시작 자본 추정 {fmt_won(_start_eval)} → 현재 {fmt_won(current_total)}
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.plotly_chart(plot_return_pct(return_series), use_container_width=True,
                            config={"displayModeBar": False})
            st.caption("ℹ️ 일중 평가 변동은 일별 스냅샷에 반영 — 매매가 없던 날의 평가 변동은 마지막 점에서 합산되어 보입니다. 추가 입금/출금이 없었다고 가정.")
        else:
            st.info("아직 거래 이력 없음")

    # ── 자산 분포 도넛 + 상위 종목 ───────────────────────
    if balance and not balance.get("_error") and balance.get("positions"):
        positions = balance.get("positions", [])
        c1, c2 = st.columns([1, 1])
        with c1:
            with st.container(border=True):
                st.markdown('<div class="hero-label">포트폴리오 구성</div>', unsafe_allow_html=True)
                st.plotly_chart(plot_portfolio_donut(positions), use_container_width=True,
                                config={"displayModeBar": False})

        with c2:
            with st.container(border=True):
                st.markdown('<div class="hero-label">보유 종목 손익</div>', unsafe_allow_html=True)
                st.markdown('<div style="height: 8px;"></div>', unsafe_allow_html=True)
                for p in sorted(positions, key=lambda x: x.get("evlu_pfls_rt", 0), reverse=True):
                    name = p.get("name", "?")
                    rt = p.get("evlu_pfls_rt", 0)
                    amt = p.get("evlu_pfls_amt", 0)
                    cls = color_class(rt)
                    arrow = "▲" if rt > 0 else ("▼" if rt < 0 else "—")
                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid {THEME['border']};">
                      <div><span style="font-weight:600;">{name}</span></div>
                      <div class="{cls}" style="font-weight:600;">{arrow} {fmt_pct(rt)} <span style="color:{THEME['text_muted']}; font-size:12px;">{fmt_won(amt, sign=True)}</span></div>
                    </div>
                    """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════
# Page 2: 보유 종목 매수/매도 로직
# ═════════════════════════════════════════════════════════════════


def page_holdings():
    st.markdown('<div class="page-title">📦 보유 종목</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">종목별 매수 논거와 매도 기준 (목표가 · 손절가 · 추격손절)</div>', unsafe_allow_html=True)

    portfolio = load_portfolio()
    history = load_history()
    balance = load_balance()
    kis_positions = {p["code"]: p for p in (balance.get("positions") or [])} if balance and not balance.get("_error") else {}

    if not portfolio:
        st.info("보유 종목 없음")
        return

    for code, pos in portfolio.items():
        name = pos.get("name", code)
        sector = pos.get("sector", "—")
        entry_price = pos.get("entry_price", 0)
        qty = pos.get("qty", 0)
        target = pos.get("target_price", 0)
        stop = pos.get("stop_loss_price", 0)
        high_price = pos.get("high_price", entry_price)

        kis = kis_positions.get(code, {})
        cur = kis.get("cur_price", 0)
        pnl_pct = kis.get("evlu_pfls_rt", 0)
        pnl_amt = kis.get("evlu_pfls_amt", 0)
        eval_amt = kis.get("evlu_amt", qty * entry_price)

        # 헤더
        cls = color_class(pnl_pct)
        arrow = "▲" if pnl_pct > 0 else ("▼" if pnl_pct < 0 else "—")

        st.markdown(f"""
        <div class="stock-card">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
            <div>
              <span class="stock-name">{esc(name)}</span>
              <span class="stock-code">{esc(code)}</span>
              <span class="stock-sector">{esc(sector)}</span>
            </div>
            <div class="{cls}" style="font-size:20px; font-weight:700;">
              {arrow} {fmt_pct(pnl_pct)}
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander(f"📋 {name} 상세", expanded=False):
            # 가격 정보 3-grid
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(kpi_block("매수가", fmt_won(entry_price), f"{qty}주"), unsafe_allow_html=True)
            with c2:
                st.markdown(kpi_block("현재가", fmt_won(cur) if cur else "—",
                                      fmt_pct(pnl_pct) if pnl_pct else None), unsafe_allow_html=True)
            with c3:
                st.markdown(kpi_block("평가금액", fmt_won(eval_amt),
                                      fmt_won(pnl_amt, sign=True)), unsafe_allow_html=True)

            # 매도 기준
            st.markdown('<div style="margin-top:16px; margin-bottom:8px; font-weight:700; color:#1a1a1a;">언제 매도하나요?</div>',
                        unsafe_allow_html=True)

            logic_rows = []
            if target > 0:
                dist = (target / cur - 1) * 100 if cur else None
                logic_rows.append(("🎯 목표가 도달 시", fmt_won(target),
                                   f"지금보다 {dist:+.1f}% 오르면" if dist is not None else ""))
            else:
                logic_rows.append(("🔄 추격 손절 모드", "일부 익절 완료 — 남은 수량은 최고가 대비 일정 % 하락 시 자동 매도", ""))

            if stop > 0:
                dist = (cur / stop - 1) * 100 if cur else None
                logic_rows.append(("🛑 손절가 도달 시", fmt_won(stop),
                                   f"지금보다 {dist:.1f}% 하락하면" if dist is not None else ""))

            if high_price and high_price > entry_price:
                trail_dist = (high_price / cur - 1) * 100 if cur else None
                logic_rows.append(("📈 보유 중 최고가", fmt_won(high_price),
                                   f"현재가 대비 {trail_dist:.1f}% 아래" if trail_dist is not None else ""))

            for label, value, sub in logic_rows:
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid {THEME['border']};">
                  <div style="color:{THEME['text_muted']}; font-weight:500;">{label}</div>
                  <div style="text-align:right;">
                    <div style="font-weight:700;">{value}</div>
                    <div style="color:{THEME['text_muted']}; font-size:12px;">{sub}</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            # 매수일
            entry_date = parse_date(pos.get("entry_date", ""))
            if entry_date:
                hold_days = (date.today() - entry_date).days
                st.markdown(f'<div style="margin-top:14px; color:{THEME["text_muted"]}; font-size:13px;">📅 매수: {entry_date} · {hold_days}일 보유 중</div>',
                            unsafe_allow_html=True)

            # 매수 근거 / 리스크 (st.write는 markdown 처리는 하지만 raw HTML은 escape함 — 안전)
            thesis = pos.get("thesis", "")
            risk = pos.get("risk", "")
            if thesis:
                st.markdown('<div style="margin-top:16px; font-weight:700;">💭 매수한 이유</div>', unsafe_allow_html=True)
                st.write(thesis)
            if risk:
                st.markdown('<div style="margin-top:8px; font-weight:700;">⚠️ 주의할 점</div>', unsafe_allow_html=True)
                st.write(risk)

            if not thesis and not risk:
                st.markdown(f'<div style="margin-top:12px; color:{THEME["text_muted"]}; font-size:13px; font-style:italic;">매수 근거 미기록 (이전 보유 종목)</div>',
                            unsafe_allow_html=True)

            # 매매 이력
            trades = [h for h in history if h.get("code") == code]
            if trades:
                st.markdown('<div style="margin-top:16px; font-weight:700;">📜 매매 이력</div>', unsafe_allow_html=True)
                df = pd.DataFrame(trades)
                if "recorded_at" in df.columns:
                    df["일시"] = df["recorded_at"].str[:19]
                # 컬럼명 한글로 매핑
                rename_map = {"type": "구분", "qty": "수량", "price": "가격", "reason": "사유", "pnl": "손익"}
                df = df.rename(columns=rename_map)
                # type 값도 한글로
                if "구분" in df.columns:
                    df["구분"] = df["구분"].replace({"buy": "매수", "sell": "매도"})
                df_show = df[[c for c in ["일시", "구분", "수량", "가격", "사유", "손익"] if c in df.columns]]
                st.dataframe(df_show, use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════
# Page 3: 모든 종목 판단 근거 (PASS/REJECT)
# ═════════════════════════════════════════════════════════════════


def page_decisions():
    st.markdown('<div class="page-title">🎯 AI의 판단 과정</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">매수·매도·보류 결정 근거와 종목 선별 과정을 모두 공개합니다</div>', unsafe_allow_html=True)

    plan = load_daily_plan()
    latest_review = load_decision_log_latest()
    stage1_summary = load_filter_stage1_summary()
    stage1_rejected = load_filter_stage1_rejected()
    stage3 = load_filter_stage3()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 오늘의 매매 계획", "🔍 보유 종목 점검", "✅ 매수 후보 종목", "❌ 제외된 종목"
    ])

    # ── 탭 1: 오늘 매매 계획 ────────────────────────────
    with tab1:
        if not plan:
            st.info("오늘 매매 계획 데이터 없음")
        else:
            status_kr = {"executed": "실행 완료", "pending": "대기 중", "failed": "실행 실패"}.get(
                plan.get("status", ""), plan.get("status", "—"))
            st.markdown(f'<div style="color:{THEME["text_muted"]};">계획 날짜: <b>{plan.get("date","—")}</b> · 진행 상태: <b>{status_kr}</b></div>',
                        unsafe_allow_html=True)
            st.markdown("<hr/>", unsafe_allow_html=True)

            buy_queue = plan.get("buy_queue", []) or []
            sell_queue = plan.get("sell_queue", []) or []

            st.markdown(f'<div style="font-weight:700; font-size:16px; margin:12px 0 8px;">🛒 매수하려고 했던 종목 ({len(buy_queue)})</div>',
                        unsafe_allow_html=True)
            if not buy_queue:
                st.markdown(f'<div style="color:{THEME["text_muted"]}; font-style:italic;">오늘은 매수 후보 없음</div>',
                            unsafe_allow_html=True)
            else:
                for b in buy_queue:
                    status = b.get("status", "?")
                    badge = {
                        "executed": '<span class="badge badge-pass">매수 완료</span>',
                        "skipped": '<span class="badge badge-skip">매수 보류</span>',
                        "pending": '<span class="badge badge-warning">대기 중</span>',
                        "failed": '<span class="badge badge-reject">매수 실패</span>',
                    }.get(status, f'<span class="badge badge-skip">{status}</span>')

                    skip_reason = b.get("skip_reason", "")
                    skip_html = f'<div style="color:{THEME["text_muted"]}; font-size:13px; margin-top:6px;">↳ 보류 사유: {esc(skip_reason)}</div>' if skip_reason else ""

                    confidence_kr = {"high": "높음", "medium": "보통", "low": "낮음"}.get(b.get("confidence", ""), b.get("confidence", ""))

                    st.markdown(f"""
                    <div class="card-tight">
                      <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                          <b>{esc(b.get("name","?"))}</b>
                          <span class="stock-code">{esc(b.get("code",""))}</span>
                          {badge}
                        </div>
                        <div style="color:{THEME["text_muted"]}; font-size:13px;">
                          편입 비중 {b.get("position_size", 0)*100:.0f}% · 확신도 {esc(confidence_kr)}
                        </div>
                      </div>
                      <div style="margin-top:8px; color:{THEME["text"]};">💭 {esc(b.get("thesis",""))}</div>
                      <div style="margin-top:6px; color:{THEME["text_muted"]}; font-size:13px;">
                        🎯 목표가 {fmt_won(b.get("target_price",0))} · 🛑 손절가 {fmt_won(b.get("stop_loss_price",0))}
                      </div>
                      {skip_html}
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown(f'<div style="font-weight:700; font-size:16px; margin:20px 0 8px;">💸 매도하려고 했던 종목 ({len(sell_queue)})</div>',
                        unsafe_allow_html=True)
            if not sell_queue:
                st.markdown(f'<div style="color:{THEME["text_muted"]}; font-style:italic;">오늘은 매도 후보 없음</div>',
                            unsafe_allow_html=True)
            else:
                for s in sell_queue:
                    st.markdown(f"""
                    <div class="card-tight">
                      <b>{esc(s.get("name","?"))}</b>
                      <span class="stock-code">{esc(s.get("code",""))}</span>
                      <div style="margin-top:6px;">{esc(s.get("reason",""))}</div>
                    </div>
                    """, unsafe_allow_html=True)

    # ── 탭 2: 보유 종목 점검 ─────────────────────────────
    with tab2:
        if not latest_review or not latest_review.get("reviews"):
            st.info("보유 종목 점검 이력 없음")
        else:
            st.markdown(f'<div style="color:{THEME["text_muted"]};">마지막 점검: <b>{esc(latest_review.get("logged_at","")[:19])}</b></div>',
                        unsafe_allow_html=True)
            st.markdown(f'<div style="color:{THEME["text_muted"]}; font-size:13px; margin-top:4px;">AI가 매일 보유 중인 종목의 매수 근거가 여전히 유효한지 다시 평가합니다.</div>',
                        unsafe_allow_html=True)
            st.markdown("<hr/>", unsafe_allow_html=True)

            for r in latest_review.get("reviews", []):
                status = r.get("thesis_status", "?")
                status_badge = {
                    "strengthen": '<span class="badge badge-pass">근거 더 강해짐</span>',
                    "maintain": '<span class="badge badge-purple">근거 유지</span>',
                    "weaken": '<span class="badge badge-warning">근거 약해짐</span>',
                    "damaged": '<span class="badge badge-reject">근거 무너짐</span>',
                }.get(status, f'<span class="badge badge-skip">{esc(status)}</span>')

                action_kr = {"hold": "계속 보유", "adjust": "목표가/손절가 조정", "sell": "매도"}.get(
                    r.get("action", ""), r.get("action", "?"))
                conf_kr = {"high": "높음", "medium": "보통", "low": "낮음"}.get(
                    r.get("confidence", ""), r.get("confidence", "?"))

                st.markdown(f"""
                <div class="card-tight">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                      <b>{esc(r.get("code","?"))}</b>
                      {status_badge}
                    </div>
                    <div style="color:{THEME["text_muted"]}; font-size:13px;">
                      판단: <b>{esc(action_kr)}</b> · 확신도 {esc(conf_kr)}
                    </div>
                  </div>
                  <div style="margin-top:8px; color:{THEME["text"]};">{esc(r.get("reason",""))}</div>
                  <div style="margin-top:6px; color:{THEME["text_muted"]}; font-size:13px;">
                    조정 목표가: {fmt_won(r.get("adjusted_target_price",0)) if r.get("adjusted_target_price") else "변경 없음"} ·
                    조정 손절가: {fmt_won(r.get("adjusted_stop_loss_price",0)) if r.get("adjusted_stop_loss_price") else "변경 없음"}
                  </div>
                </div>
                """, unsafe_allow_html=True)

    # ── 탭 3: 매수 후보 종목 (선별 완료) ─────────────────
    with tab3:
        if not stage3 or not stage3.get("selected"):
            st.info("선별 결과 데이터 없음")
        else:
            completed = stage3.get("completed_at", "")
            stale_warning = ""
            try:
                completed_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                age_days = (datetime.now() - completed_dt.replace(tzinfo=None)).days
                if age_days > 7:
                    stale_warning = f'<span class="badge badge-warning">⚠️ {age_days}일 전 데이터</span>'
            except Exception:
                pass

            st.markdown(f'<div style="color:{THEME["text_muted"]};">선별 완료: <b>{completed[:19]}</b> · 검토 {stage3.get("input_count","?")}종목 → 선정 {stage3.get("selected_count","?")}종목 {stale_warning}</div>',
                        unsafe_allow_html=True)
            st.markdown(f'<div style="color:{THEME["text_muted"]}; font-size:13px; margin-top:4px;">AI가 코스피·코스닥 전체에서 매수 가치가 있다고 판단한 종목들입니다.</div>',
                        unsafe_allow_html=True)
            st.markdown("<hr/>", unsafe_allow_html=True)

            selected = stage3.get("selected", [])
            df = pd.DataFrame(selected)
            # 영문 코드값을 한글로 변환
            if "position" in df.columns:
                df["position"] = df["position"].replace({
                    "CORE": "핵심 보유", "BUY": "매수 대상", "HOLD": "관망"
                })
            if "valuation_grade" in df.columns:
                df["valuation_grade"] = df["valuation_grade"].replace({
                    "ATTRACTIVE": "저평가", "FAIR": "적정", "EXPENSIVE": "고평가"
                })
            if "sector_grade" in df.columns:
                df["sector_grade"] = df["sector_grade"].replace({
                    "OW": "강세 섹터", "N": "중립 섹터", "UW": "약세 섹터"
                })
            display_cols = {
                "name": "종목명", "code": "코드", "sector": "업종",
                "position": "분류", "weight": "비중 %",
                "total_score": "종합 점수", "upside_pct": "상승 여력 %",
                "valuation_grade": "밸류에이션", "sector_grade": "업종 강도",
                "roe": "ROE %", "per": "PER", "op_yoy": "영업이익 성장 %",
            }
            df_show = df[[c for c in display_cols if c in df.columns]].rename(columns=display_cols)
            st.dataframe(df_show, use_container_width=True, hide_index=True)

    # ── 탭 4: 제외된 종목 ───────────────────────────────
    with tab4:
        if not stage1_summary:
            st.info("검토 결과 데이터 없음")
        else:
            completed = stage1_summary.get("completed_at", "")
            stale_warning = ""
            try:
                completed_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                age_days = (datetime.now() - completed_dt.replace(tzinfo=None)).days
                if age_days > 7:
                    stale_warning = f'<span class="badge badge-warning">⚠️ {age_days}일 전 데이터</span>'
            except Exception:
                pass

            st.markdown(f'<div style="color:{THEME["text_muted"]};">검토 완료: <b>{esc(completed[:19])}</b> · '
                        f'통과 {stage1_summary.get("pass_count","?")}종목 · 보류 {stage1_summary.get("warning_count","?")}종목 · '
                        f'제외 {stage1_summary.get("reject_count","?")}종목 {stale_warning}</div>',
                        unsafe_allow_html=True)
            st.markdown(f'<div style="color:{THEME["text_muted"]}; font-size:13px; margin-top:4px;">AI가 검토했지만 매수 대상에서 제외한 종목 — 왜 제외했는지 사유를 모두 공개합니다.</div>',
                        unsafe_allow_html=True)
            st.markdown("<hr/>", unsafe_allow_html=True)

            # snapshot에서 이미 정제된 형태로 옴 (code, name, sector, reasons[])
            rejected = [{
                "코드": r.get("code"),
                "종목명": r.get("name"),
                "섹터": r.get("sector", "—"),
                "제외 사유": " · ".join(r.get("reasons", [])[:3]) if r.get("reasons") else "—",
            } for r in stage1_rejected]

            if not rejected:
                st.info("제외된 종목 없음")
            else:
                st.markdown(f'<div style="margin-bottom:12px; color:{THEME["text_muted"]};">총 <b>{len(rejected)}</b>개 종목 제외됨</div>',
                            unsafe_allow_html=True)
                search = st.text_input("종목명 검색", "", placeholder="예: 삼성전자")
                df_rej = pd.DataFrame(rejected)
                if search:
                    # regex=False 로 ReDoS 방어 (정규식 메타문자 그대로 검색됨)
                    df_rej = df_rej[df_rej["종목명"].str.contains(search, case=False, na=False, regex=False)]
                st.dataframe(df_rej, use_container_width=True, hide_index=True, height=500)


# ═════════════════════════════════════════════════════════════════
# 메인
# ═════════════════════════════════════════════════════════════════


PAGES = {
    "💰 자산 현황": page_assets,
    "📦 보유 종목": page_holdings,
    "🎯 AI 판단": page_decisions,
}


def main():
    inject_global_css()

    # 사이드바
    st.sidebar.markdown(
        f'<div style="font-size:18px; font-weight:700; color:{THEME["accent"]}; margin-bottom:4px; line-height:1.3;">AI 한국주식<br/>포트폴리오</div>'
        f'<div style="color:{THEME["text_muted"]}; font-size:12px; margin-bottom:24px;">가치 + 모멘텀 전략</div>',
        unsafe_allow_html=True,
    )

    page = st.sidebar.radio("페이지", list(PAGES.keys()), label_visibility="collapsed")
    st.sidebar.markdown("<hr/>", unsafe_allow_html=True)

    # 갱신 정보 (디스크 스냅샷 시각)
    refreshed = get_refresh_time()
    if refreshed:
        try:
            dt = datetime.fromisoformat(refreshed.replace("Z", "+00:00")).replace(tzinfo=None)
            age_min = int((datetime.now() - dt).total_seconds() / 60)
            age_str = f"{age_min}분 전" if age_min < 60 else f"{age_min // 60}시간 {age_min % 60}분 전"
            st.sidebar.markdown(
                f'<div style="color:{THEME["text_muted"]}; font-size:11px; margin-bottom:8px;">'
                f'📡 마지막 갱신<br/>'
                f'<b style="color:{THEME["text"]};">{dt:%H:%M:%S}</b> ({age_str})'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            st.sidebar.caption(f"갱신: {refreshed[:19]}")
    else:
        st.sidebar.warning("스냅샷 없음 — refresh 스크립트 첫 실행 대기")

    if st.sidebar.button("🔄 캐시 비우기"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown(
        f'<div style="color:{THEME["text_muted"]}; font-size:11px; margin-top:24px;">'
        f'데이터는 10분마다 자동 갱신<br/>'
        f'(refresh_dashboard_data.py · launchd)'
        f'</div>',
        unsafe_allow_html=True,
    )

    PAGES[page]()


if __name__ == "__main__":
    main()
