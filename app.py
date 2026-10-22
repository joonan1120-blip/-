"""냉장고 식단 에이전트 - Streamlit (카카오톡 테마)."""
from __future__ import annotations

import html
import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from core import data as D
from core.agents import MainAgent, Settings
from core.tools import fmt_qty

load_dotenv(override=True)

st.set_page_config(page_title="냉장고 식단 봇", page_icon="🍳", layout="centered")

BOT_NAME = "냉장고 식단 봇"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
:root { --kk-bg:#ABC1D1; --kk-yellow:#FEE500; --kk-text:#191919; --kk-sub:#5F6B76; }
html, body, .stApp, .stApp p, .stApp span, .stApp div, .stApp button, .stApp input, .stApp textarea, .stApp label { font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif; }
[data-testid="stIconMaterial"], .material-symbols-rounded, [class*="material-icons"] { font-family: 'Material Symbols Rounded', 'Material Icons' !important; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: var(--kk-bg); }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 560px; padding: 2.6rem 1rem 7rem; }
[data-testid="stSidebar"] { display: none; }

/* 상단 바 */
.kk-top { display:flex; align-items:center; gap:10px; padding:4px 2px 10px; color:var(--kk-text); }
.kk-top .back { font-size:26px; line-height:1; margin-right:2px; }
.kk-top .title { font-size:17px; font-weight:700; }
.kk-top .count { font-size:15px; color:var(--kk-sub); font-weight:500; margin-left:2px; }
.kk-top .icons { margin-left:auto; display:flex; gap:16px; font-size:18px; opacity:.85; }
.kk-date { display:flex; justify-content:center; margin:6px 0 14px; }
.kk-date span { background:rgba(0,0,0,.18); color:#fff; font-size:12px; padding:5px 14px; border-radius:14px; }

/* 말풍선 */
.kk-row { display:flex; gap:8px; margin:6px 0; align-items:flex-start; }
.kk-row.me { justify-content:flex-end; }
.kk-ava { flex:0 0 42px; width:42px; height:42px; border-radius:16px; background:linear-gradient(145deg,#FFF3B0,#FEE500);
          display:flex; align-items:center; justify-content:center; font-size:23px; box-shadow:0 1px 2px rgba(0,0,0,.12); }
.kk-col { display:flex; flex-direction:column; min-width:0; max-width:82%; }
.kk-name { font-size:12px; color:var(--kk-text); margin:0 0 4px 2px; }
.kk-line { display:flex; align-items:flex-end; gap:5px; }
.kk-bubble { position:relative; padding:9px 12px; border-radius:12px; font-size:14.5px; line-height:1.5; color:var(--kk-text);
             word-break:break-word; max-width:100%; }
.kk-bubble.bot { background:#fff; border-top-left-radius:2px; }
.kk-bubble.bot::before { content:""; position:absolute; top:0; left:-7px; border-style:solid; border-width:0 8px 9px 0;
                         border-color:transparent #fff transparent transparent; }
.kk-bubble.me { background:var(--kk-yellow); border-top-right-radius:2px; }
.kk-bubble.me::after { content:""; position:absolute; top:0; right:-7px; border-style:solid; border-width:0 0 9px 8px;
                       border-color:transparent transparent transparent var(--kk-yellow); }
.kk-bubble.err { background:#FFE3DF; }
.kk-bubble.err::before { border-color:transparent #FFE3DF transparent transparent; }
.kk-time { font-size:11px; color:var(--kk-sub); white-space:nowrap; padding-bottom:1px; }
.kk-read { font-size:11px; color:#E2A900; font-weight:700; margin-right:2px; }

/* 입력 중 표시 */
.kk-typing span { display:inline-block; width:7px; height:7px; margin:0 2px; border-radius:50%; background:#9AA5AF;
                  animation:kkblink 1.2s infinite ease-in-out; }
.kk-typing span:nth-child(2){ animation-delay:.2s } .kk-typing span:nth-child(3){ animation-delay:.4s }
@keyframes kkblink { 0%,80%,100%{ opacity:.25; transform:translateY(0) } 40%{ opacity:1; transform:translateY(-3px) } }

/* 말풍선 아래 카드(표·후보·조리순서) */
[class*="st-key-kkcard"] { background:#fff; border-radius:14px; padding:12px 14px; margin:2px 0 8px 50px; width:calc(100% - 50px); box-sizing:border-box;
                           box-shadow:0 1px 2px rgba(0,0,0,.08); }
[class*="st-key-kkcard"] [data-testid="stExpander"] { background:#F7F8F9; border:1px solid #E5E8EB; border-radius:10px; }
.kk-note { font-size:12px; color:var(--kk-sub); }
.kk-cand { padding:6px 0; border-bottom:1px solid #F0F1F3; }
.kk-cand:last-child { border-bottom:none; }

/* 버튼 = 카카오 빠른 답장 칩 */
.stButton > button { background:#fff; color:var(--kk-text); border:1px solid #E1CF3A; border-radius:18px; font-weight:500;
                     padding:2px 14px; min-height:34px; }
.stButton > button:hover { background:var(--kk-yellow); border-color:var(--kk-yellow); color:var(--kk-text); }
.stButton > button:disabled { background:#EEF0F2; border-color:#DDE0E3; color:#999; }
[class*="st-key-kkchips"] { margin-left:50px; gap:.35rem; }
.block-container { overflow-x:hidden; }
[class*="st-key-kkchips"] .stButton > button { background:#fff; }

/* 하단 입력창 */
[data-testid="stBottom"], [data-testid="stBottom"] > div { background:var(--kk-bg); }
[data-testid="stChatInput"] { background:#fff; border-radius:24px; border:none; box-shadow:0 1px 3px rgba(0,0,0,.12); }
[data-testid="stChatInput"] textarea { font-size:14.5px; }
[data-testid="stChatInput"] button { background:var(--kk-yellow); color:var(--kk-text); border-radius:50%; }
[data-testid="stChatInput"] button:disabled { background:#EEF0F2; color:#B5BBC1; }

/* 탭 = 카카오 하단 탭처럼 */
.stTabs [data-baseweb="tab-list"] { background:rgba(255,255,255,.35); border-radius:12px; padding:3px; gap:2px; border:none; }
.stTabs [data-baseweb="tab"] { border-radius:9px; height:34px; padding:0 14px; color:var(--kk-text); }
.stTabs [aria-selected="true"] { background:#fff; font-weight:700; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none !important; height:0 !important; background:transparent !important; }
[data-testid="stExpander"] { background:#fff; border-radius:12px; border:none; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ 상태
def ss_init() -> None:
    s = st.session_state
    if "fridge" not in s:
        s.fridge = D.load_default_fridge()
        s.recipes = D.load_default_recipes()
        s.fridge_src = None
        s.recipes_src = None
        s.up_n = 0       # 업로더 초기화용 카운터
        s.edit_n = 0     # 편집기 초기화용 카운터
        s.messages = []
        s.history = []
        s.ctx = {}
        s.processing = False


ss_init()
S = st.session_state


def current_store() -> D.Store:
    return D.merge(S.fridge, S.recipes)


def kor_time(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return f'{"오전" if dt.hour < 12 else "오후"} {dt.hour % 12 or 12}:{dt.minute:02d}'


def add_msg(role: str, content: str, **extra) -> None:
    S.messages.append({"role": role, "content": content, "ts": kor_time(), **extra})


def new_chat() -> None:
    S.messages, S.history, S.ctx, S.processing = [], [], {}, False


def reset_defaults() -> None:
    S.fridge, S.recipes = D.load_default_fridge(), D.load_default_recipes()
    S.fridge_src = S.recipes_src = None
    S.up_n += 1
    S.edit_n += 1


def send(text: str) -> None:
    add_msg("user", text)
    S.processing = True
    st.rerun()


# ------------------------------------------------------------------ 설정(.env)
api_key = os.getenv("OPENAI_API_KEY", "").strip()
model = os.getenv("OPENAI_MODEL", "gpt-6.1-sol")
effort = os.getenv("MAIN_REASONING_EFFORT", "low")
timeout = float(os.getenv("REQUEST_TIMEOUT", "60"))
max_calls = int(os.getenv("MAX_TOOL_CALLS", "8"))
mock_fail = False

store = current_store()

# ------------------------------------------------------------------ 헤더 / 오류
st.markdown(f'<div class="kk-top"><span class="back">‹</span><span class="title">{BOT_NAME}</span>'
            '<span class="count">2</span></div>',
            unsafe_allow_html=True)
if not store.ok:
    st.error("데이터 파일에 오류가 있어 메뉴 판단·계산을 멈췄습니다. 오류를 고치거나 정상 파일로 바꿔 주세요.\n\n"
             + "\n".join(f"- {e}" for e in store.errors))

tab_chat, tab_fridge, tab_recipe = st.tabs(["💬 채팅", "🧊 냉장고", "📖 레시피"])


# ------------------------------------------------------------------ 표시 헬퍼
def md_html(text: str) -> str:
    """말풍선용 아주 작은 마크다운 변환(굵게·목록·줄바꿈). 먼저 이스케이프해 HTML 주입을 막는다."""
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?m)^\s*[-*] ", "• ", t)
    return t.replace("\n", "<br>")


def bubble(role: str, content: str, ts: str = "", error: bool = False) -> str:
    time_html = f'<span class="kk-time">{ts}</span>' if ts else ""
    if role == "user":
        return (f'<div class="kk-row me"><div class="kk-line">{time_html}'
                f'<div class="kk-bubble me">{md_html(content)}</div></div></div>')
    cls = "bot err" if error else "bot"
    return (f'<div class="kk-row"><div class="kk-ava">🍳</div><div class="kk-col"><div class="kk-name">{BOT_NAME}</div>'
            f'<div class="kk-line"><div class="kk-bubble {cls}">{md_html(content)}</div>{time_html}</div></div></div>')


def typing_bubble() -> str:
    return (f'<div class="kk-row"><div class="kk-ava">🍳</div><div class="kk-col"><div class="kk-name">{BOT_NAME}</div>'
            '<div class="kk-line"><div class="kk-bubble bot kk-typing"><span></span><span></span><span></span></div></div></div></div>')


def calc_df(c: dict) -> pd.DataFrame:
    rows = []
    for r in c["rows"]:
        have = fmt_qty(r["보유"]) + r.get("보유단위", r["단위"]) if r["보유"] is not None else "-"
        rows.append({"재료": r["이름"], "필요": f'{fmt_qty(r["필요"])}{r["단위"]}', "보유": have,
                     "부족": "보류" if r["부족"] is None else f'{fmt_qty(r["부족"])}{r["단위"]}', "비고": r["상태"]})
    return pd.DataFrame(rows)


def render_calc(c: dict, latest: bool) -> None:
    title = f'{c["recipe_name"]} · {c["servings"]}명 기준 (기준 {c["base_servings"]}명)'
    if latest:
        st.markdown(f"**📊 최신 결과 — {title}**")
        body = st.container()
    else:
        body = st.expander(f"이전 결과 — {title}")
    with body:
        st.dataframe(calc_df(c), hide_index=True, width="stretch")
        if c["shopping_list"]:
            st.markdown("🛒 **장보기:** " + ", ".join(f'{s["이름"]} {fmt_qty(s["수량"])}{s["단위"]}' for s in c["shopping_list"]))
        elif not c["held"]:
            st.markdown("✅ 추가로 필요한 재료가 없습니다.")
        if c["held"]:
            st.warning(f'단위가 달라 계산을 보류한 재료({", ".join(c["held"])})가 있어 장보기를 확정할 수 없습니다.')
        st.caption("현재 재고는 변경되지 않습니다.")


def render_candidates(res: dict, key: str) -> None:
    cond = f'{res["servings"]}명 · 제외: {", ".join(res["exclude"]) or "없음"}' + (" · 있는 재료만" if res["only_available"] else "")
    st.markdown(f"**🍽️ 메뉴 후보** ({cond})")
    if not res["candidates"]:
        st.info("조건에 맞는 후보가 없습니다.")
        return
    for i, c in enumerate(res["candidates"]):
        icon = {"가능": "🟢", "부족": "🟠"}.get(c["판정"], "⚪")
        extra = f' — 부족: {", ".join(c["부족재료"])}' if c["부족재료"] else ""
        extra += f' — 계산 보류: {", ".join(c["보류재료"])}' if c["보류재료"] else ""
        col1, col2 = st.columns([4, 1], vertical_alignment="center")
        col1.markdown(f'<div class="kk-cand">{icon} <b>{html.escape(c["이름"])}</b> ({c["인원"]}명) · {c["판정"]}{html.escape(extra)}<br>'
                      f'<span class="kk-note">{html.escape(" · ".join(c["재료"]))}</span></div>', unsafe_allow_html=True)
        if col2.button("선택", key=f"kkchip_{key}_pick{i}"):
            send(f'{c["이름"]}({c["레시피ID"]})으로 할게. {c["인원"]}명 분량으로 계산해줘.')


def render_recipe_steps(r: dict) -> None:
    st.markdown(f'**📖 {r["이름"]}** (기준 {r["기준인원"]}명) 조리 순서')
    for n, step in enumerate(r["조리순서"], 1):
        st.markdown(f"{n}. {step}")
    if r.get("출처"):
        st.caption(f'출처: {r["출처"]}')


def render_logs(logs: list[dict]) -> None:
    with st.expander(f"도구 실행 기록 ({len(logs)}건)"):
        for l in logs:
            icon = "✅" if l["status"] == "성공" else "❌"
            tag = " · 🧪 시험용 실패" if l["mock"] else ""
            st.markdown(f'{icon} **{l["tool"]}** · {l["agent"]} · {l["status"]}{tag}')
            st.code(f'인자: {l["args"]}\n반환 요약: {l["summary"]}', language=None)


def latest_calc_id() -> tuple[int, int] | None:
    found = None
    for mi, m in enumerate(S.messages):
        for li, l in enumerate(m.get("logs", [])):
            if l["tool"] == "calculate_requirements" and l["status"] == "성공":
                found = (mi, li)
    return found


def render_message(mi: int, m: dict, latest: tuple[int, int] | None) -> None:
    st.markdown(bubble(m["role"], m["content"], m.get("ts", ""), bool(m.get("error"))), unsafe_allow_html=True)
    logs = m.get("logs", [])
    if not logs and not m.get("error"):
        return
    with st.container(key=f"kkcard{mi}"):
        for li, l in enumerate(logs):
            if l["status"] != "성공":
                continue
            if l["tool"] == "search_menu_candidates":
                render_candidates(l["result"], key=f"m{mi}l{li}")
            elif l["tool"] == "calculate_requirements":
                render_calc(l["result"], latest == (mi, li))
            elif l["tool"] == "get_recipe":
                render_recipe_steps(l["result"]["recipe"])
        if logs:
            render_logs(logs)
        if m.get("error") and mi == len(S.messages) - 1:
            if st.button("🔄 다시 시도", key=f"kkchip_retry{mi}"):
                S.messages.pop()
                S.processing = True
                st.rerun()


def run_turn() -> None:
    last_user = next(m for m in reversed(S.messages) if m["role"] == "user")["content"]
    agent = MainAgent(Settings(api_key=api_key, model=model, reasoning_effort=effort, timeout=float(timeout),
                               max_tool_calls=int(max_calls), mock_tool_failure=mock_fail), current_store())
    st.markdown(typing_bubble(), unsafe_allow_html=True)
    res = agent.run(S.history, last_user, S.ctx)
    S.history, S.ctx = res.history, res.ctx
    add_msg("assistant", res.text, logs=res.logs, error=res.error)
    S.processing = False
    st.rerun()


QUICK = ["두 명이 먹을 저녁 메뉴 추천해줘. 달걀은 빼줘.", "냉장고에 뭐 있어?", "등록된 메뉴 알려줘"]

# ------------------------------------------------------------------ 채팅 탭
with tab_chat:
    today = datetime.now()
    wd = "월화수목금토일"[today.weekday()]
    st.markdown(f'<div class="kk-date"><span>{today.year}년 {today.month}월 {today.day}일 {wd}요일</span></div>',
                unsafe_allow_html=True)
    if not api_key:
        st.warning("OPENAI_API_KEY가 설정되지 않았습니다. 프로젝트 폴더의 `.env`에 키를 넣고 앱을 다시 시작해 주세요 "
                   "(`.env.example` 참고).")
    if not S.messages:
        st.markdown(bubble("bot", "안녕하세요! 냉장고 재료로 한 끼 메뉴를 찾아 드릴게요 🍳\n인원과 빼고 싶은 재료를 알려 주세요.",
                           kor_time()), unsafe_allow_html=True)
        with st.container(key="kkchips_quick"):
            for qi, q in enumerate(QUICK):
                if st.button(q, key=f"kkchip_quick{qi}", disabled=not (api_key and store.ok)):
                    send(q)
    latest = latest_calc_id()
    for mi, m in enumerate(S.messages):
        render_message(mi, m, latest)
    if S.processing:
        run_turn()
    if S.messages and st.button("🗑️ 새 대화", help="대화만 비웁니다. 재료·레시피 데이터는 그대로입니다."):
        new_chat()
        st.rerun()

can_chat = bool(api_key) and store.ok
placeholder = ("메시지를 입력하세요" if can_chat else
               "OPENAI_API_KEY를 설정해 주세요" if not api_key else "데이터 오류를 먼저 해결해 주세요")
if prompt := st.chat_input(placeholder, disabled=not can_chat):
    send(prompt)



# ------------------------------------------------------------------ 냉장고 탭
def fridge_df(rows):
    return pd.DataFrame(rows, columns=D.FRIDGE_COLUMNS)


with tab_fridge:
    up = st.file_uploader("냉장고 CSV 교체 (재료ID, 이름, 수량, 단위)", type=["csv"], key=f"up_fridge{S.up_n}")
    if up is not None and S.fridge_src != up.file_id:
        S.fridge, S.fridge_src = D.parse_fridge_csv(D.decode_bytes(up.getvalue())), up.file_id
        S.edit_n += 1
        st.rerun()
    if up is None and S.fridge_src is not None:
        S.fridge, S.fridge_src = D.load_default_fridge(), None
        S.edit_n += 1
        st.rerun()
    st.caption("사용 중: " + (f"업로드한 파일 ({up.name})" if up is not None else "data/냉장고.csv (기본)"))
    if S.fridge.inventory is None:
        st.error("냉장고 데이터 오류:\n\n" + "\n".join(f"- {e}" for e in S.fridge.fridge_errors))
    else:
        st.markdown(f"**보유 재료 {len(S.fridge.inventory)}종** — 표에서 직접 수정·추가·삭제할 수 있습니다.")
        edited = st.data_editor(
            fridge_df(S.fridge.inventory), num_rows="dynamic", hide_index=True, width="stretch",
            key=f"fridge_edit{S.edit_n}",
            column_config={"재료ID": st.column_config.TextColumn("재료ID (자동)", disabled=True),
                           "수량": st.column_config.NumberColumn("수량", min_value=0, step=0.5),
                           "단위": st.column_config.SelectboxColumn("단위", options=list(D.UNITS), required=True)})
        c1, c2 = st.columns(2)
        if c1.button("변경 적용", key="fridge_apply"):
            rows = edited.where(edited.notna(), None).to_dict("records")
            catalog = D.ingredient_catalog(S.fridge.inventory, S.recipes.recipes)
            rows = D.assign_ids([r for r in rows if str(r.get("이름") or "").strip() or r.get("수량") is not None], catalog)
            clean, errs = D.validate_inventory(rows, start_row=1)
            if errs:
                st.error("적용하지 않았습니다:\n\n" + "\n".join(f"- {e}" for e in errs))
            else:
                S.fridge = D.Store(inventory=clean)
                S.edit_n += 1
                st.rerun()
        with c2:
            ok_save = st.checkbox("data/냉장고.csv 원본 덮어쓰기 확인", key="fridge_confirm")
            if st.button("원본 파일에 저장", disabled=not ok_save, key="fridge_save"):
                D.save_inventory(S.fridge.inventory)
                st.success("저장했습니다.")
    st.caption("‘변경 적용’은 이 세션에만 반영됩니다. 원본 파일은 ‘원본 파일에 저장’을 누를 때만 바뀝니다.")
    if st.button("기본 파일로 되돌리기", key="reset_all_f"):
        reset_defaults()
        st.rerun()


# ------------------------------------------------------------------ 레시피 탭
NEW = "➕ 새 레시피"

with tab_recipe:
    up = st.file_uploader("레시피 JSON 교체", type=["json"], key=f"up_recipes{S.up_n}")
    if up is not None and S.recipes_src != up.file_id:
        S.recipes, S.recipes_src = D.parse_recipes_json(D.decode_bytes(up.getvalue())), up.file_id
        S.edit_n += 1
        st.rerun()
    if up is None and S.recipes_src is not None:
        S.recipes, S.recipes_src = D.load_default_recipes(), None
        S.edit_n += 1
        st.rerun()
    st.caption("사용 중: " + (f"업로드한 파일 ({up.name})" if up is not None else "data/레시피.json (기본)"))
    if S.recipes.recipes is None:
        st.error("레시피 데이터 오류:\n\n" + "\n".join(f"- {e}" for e in S.recipes.recipe_errors))
    else:
        recipes = S.recipes.recipes
        inv_ids = {r["재료ID"] for r in (S.fridge.inventory or [])}
        have_inv = S.fridge.inventory is not None
        st.markdown(f"**등록 메뉴 {len(recipes)}개**")
        for r in recipes:
            with st.expander(f'{r["레시피ID"]} {r["이름"]} · 기준 {r["기준인원"]}명'):
                df = pd.DataFrame([{
                    "재료": i["이름"], "수량": fmt_qty(i["수량"]), "단위": i["단위"],
                    "비고": "미등록, 보유 0으로 비교" if have_inv and i["재료ID"] not in inv_ids else ""}
                    for i in r["재료"]])
                st.dataframe(df, hide_index=True, width="stretch")
                for n, step in enumerate(r["조리순서"], 1):
                    st.markdown(f"{n}. {step}")

        st.divider()
        st.markdown("**✏️ 레시피 편집**")
        pick = st.selectbox("편집할 레시피", [NEW] + [f'{r["레시피ID"]} {r["이름"]}' for r in recipes],
                            key=f"rpick{S.edit_n}")
        idx = None if pick == NEW else [f'{r["레시피ID"]} {r["이름"]}' for r in recipes].index(pick)
        cur = recipes[idx] if idx is not None else {
            "레시피ID": f"R{max(int(r['레시피ID'][1:]) for r in recipes if r['레시피ID'][1:].isdigit()) + 1:02d}"
            if any(r["레시피ID"][1:].isdigit() for r in recipes) else "R01", "이름": "", "기준인원": 1,
            "재료": [], "조리순서": []}
        k = f"{S.edit_n}_{pick}"
        a, b, c = st.columns([1, 2, 1])
        rid = a.text_input("레시피ID (자동)", cur["레시피ID"], key=f"rid{k}", disabled=True)
        rname = b.text_input("이름", cur["이름"], key=f"rname{k}")
        rbase = c.number_input("기준인원", min_value=0, value=int(cur["기준인원"]), step=1, key=f"rbase{k}")

        catalog = D.ingredient_catalog(S.fridge.inventory, recipes)
        extra = S.setdefault("extra_names", [])
        n1, n2 = st.columns([3, 1], vertical_alignment="bottom")
        new_name = n1.text_input("새 재료 등록 (목록에 없는 재료만)", key=f"newing{S.edit_n}", placeholder="예: 돼지고기")
        if n2.button("재료 등록", key="add_ing"):
            nn = new_name.strip()
            if not nn:
                st.warning("재료 이름을 입력해 주세요.")
            elif nn in catalog or nn in extra:
                st.info(f"'{nn}'은(는) 이미 있는 재료입니다. 아래 표에서 선택하세요.")
            else:
                extra.append(nn)
                st.success(f"'{nn}' 등록. 아래 표에서 선택하세요. 재료ID는 적용할 때 자동 부여됩니다.")
        options = sorted(set(catalog) | set(extra))
        ing_edit = st.data_editor(
            pd.DataFrame(cur["재료"], columns=["이름", "수량", "단위"]), num_rows="dynamic", hide_index=True,
            width="stretch", key=f"ring{k}",
            column_config={"이름": st.column_config.SelectboxColumn("재료 (검색해서 선택)", options=options, required=True),
                           "수량": st.column_config.NumberColumn("수량", min_value=0, step=0.5),
                           "단위": st.column_config.SelectboxColumn("단위", options=list(D.UNITS), required=True)})
        steps_txt = st.text_area("조리순서 (한 줄에 한 단계)", "\n".join(cur["조리순서"]), key=f"rsteps{k}")
        b1, b2 = st.columns(2)
        if b1.button("레시피 적용", key="recipe_apply"):
            ings = ing_edit.where(ing_edit.notna(), None).to_dict("records")
            ings = D.assign_ids([i for i in ings if i.get("이름")], catalog)
            new = {"레시피ID": rid.strip(), "이름": rname.strip(), "기준인원": int(rbase),
                   "재료": ings, "조리순서": [s.strip() for s in steps_txt.splitlines() if s.strip()]}
            updated = list(recipes)
            if idx is None:
                updated.append(new)
            else:
                updated[idx] = new
            valid, errs = D.validate_recipes(updated)
            if errs:
                st.error("적용하지 않았습니다:\n\n" + "\n".join(f"- {e}" for e in errs))
            else:
                S.recipes = D.Store(recipes=valid)
                S.edit_n += 1
                st.rerun()
        if idx is not None and b2.button("이 레시피 삭제", key="recipe_del"):
            updated = [r for i, r in enumerate(recipes) if i != idx]
            valid, errs = D.validate_recipes(updated)
            if errs:
                st.error("삭제할 수 없습니다: " + "; ".join(errs))
            else:
                S.recipes = D.Store(recipes=valid)
                S.edit_n += 1
                st.rerun()
        ok_save = st.checkbox("data/레시피.json 원본 덮어쓰기 확인", key="recipe_confirm")
        if st.button("원본 파일에 저장", disabled=not ok_save, key="recipe_save"):
            D.save_recipes(S.recipes.recipes)
            st.success("저장했습니다.")
    st.caption("‘레시피 적용’은 이 세션에만 반영됩니다. 재료 제외는 선호 반영일 뿐 알레르기 안전을 보장하지 않으며, 조리 순서는 예시입니다.")
    if st.button("기본 파일로 되돌리기", key="reset_all_r"):
        reset_defaults()
        st.rerun()
