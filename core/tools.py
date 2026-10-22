"""도구 구현. 수량 계산은 모두 여기(코드)에서 하고, 모델이 만든 숫자는 쓰지 않는다."""
from __future__ import annotations

from fractions import Fraction

from .data import Store


class ToolError(Exception):
    """도구가 처리할 수 없는 요청(잘못된 인자 등)."""


def _frac(x) -> Fraction:
    return Fraction(str(x))


def _out(x: Fraction):
    """정수면 int, 아니면 반올림 없이 float."""
    return int(x) if x.denominator == 1 else float(x)


def fmt_qty(x) -> str:
    return f"{x:g}" if isinstance(x, float) else str(x)


def _inv_by_id(store: Store) -> dict[str, dict]:
    return {r["재료ID"]: r for r in store.inventory}


def _find_recipe(store: Store, key) -> dict:
    key = str(key or "").strip()
    for r in store.recipes:
        if r["레시피ID"].lower() == key.lower() or r["이름"] == key:
            return r
    raise ToolError(f"등록되지 않은 레시피입니다: '{key}' (등록 메뉴: {', '.join(r['이름'] for r in store.recipes)})")


# ---------------------------------------------------------------- 조회
def get_inventory(store: Store, names: list[str] | None = None) -> dict:
    items = store.inventory
    if names:
        wanted = [n.strip() for n in names if n and n.strip()]
        found = [r for r in items if r["이름"] in wanted or r["재료ID"] in wanted]
        missing = [n for n in wanted if not any(r["이름"] == n or r["재료ID"] == n for r in items)]
        return {"items": found, "not_found": missing}
    return {"items": list(items), "not_found": []}


def list_menus(store: Store) -> dict:
    inv = _inv_by_id(store)
    menus = []
    for r in store.recipes:  # 메뉴가 많아도 컨텍스트가 커지지 않도록 재료는 한 줄 문자열로 요약
        menus.append({
            "레시피ID": r["레시피ID"], "이름": r["이름"], "기준인원": r["기준인원"],
            "재료": [f'{i["이름"]} {fmt_qty(i["수량"])}{i["단위"]}' for i in r["재료"]],
            "미등록재료": [i["이름"] for i in r["재료"] if i["재료ID"] not in inv],
        })
    return {"menus": menus}


def get_recipe(store: Store, recipe: str) -> dict:
    r = _find_recipe(store, recipe)
    inv = _inv_by_id(store)
    return {"recipe": {**r, "재료": [{**i, "미등록": i["재료ID"] not in inv} for i in r["재료"]]}}


# ---------------------------------------------------------------- 계산
def calculate_requirements(store: Store, recipe: str, servings) -> dict:
    if isinstance(servings, bool) or not isinstance(servings, (int, float)) or servings != int(servings) or servings < 1:
        raise ToolError(f"인원은 1 이상의 정수여야 합니다(받은 값: {servings!r}).")
    servings = int(servings)
    r = _find_recipe(store, recipe)
    inv = _inv_by_id(store)
    rows, shopping, held = [], [], []
    for ing in r["재료"]:
        need = _frac(ing["수량"]) * servings / r["기준인원"]
        have_row = inv.get(ing["재료ID"])
        row = {"재료ID": ing["재료ID"], "이름": ing["이름"], "단위": ing["단위"], "필요": _out(need)}
        if have_row is None:
            row.update(보유=0, 부족=_out(need), 상태="미등록, 보유 0으로 비교")
        elif have_row["단위"] != ing["단위"]:
            row.update(보유=have_row["수량"], 보유단위=have_row["단위"], 부족=None,
                       상태=f"계산 보류(단위 불일치: 냉장고 {have_row['단위']} ≠ 레시피 {ing['단위']})")
            held.append(ing["이름"])
        else:
            short = max(need - _frac(have_row["수량"]), Fraction(0))
            row.update(보유=have_row["수량"], 부족=_out(short), 상태="부족" if short > 0 else "충분")
        rows.append(row)
        if row["부족"]:
            shopping.append({"이름": row["이름"], "수량": row["부족"], "단위": row["단위"]})
    return {
        "recipe_id": r["레시피ID"], "recipe_name": r["이름"], "servings": servings,
        "base_servings": r["기준인원"], "rows": rows, "shopping_list": shopping,
        "held": held, "feasible": not shopping and not held,
        "inventory_changed": False,
    }


def search_menu_candidates(store: Store, servings, exclude_ingredients: list[str] | None = None,
                           only_available: bool = False, limit: int = 3) -> dict:
    exclude = [e.strip() for e in (exclude_ingredients or []) if e and e.strip()]
    if isinstance(servings, bool) or not isinstance(servings, (int, float)) or servings != int(servings) or servings < 1:
        raise ToolError(f"인원은 1 이상의 정수여야 합니다(받은 값: {servings!r}).")
    excluded_recipes, cands = [], []
    for r in store.recipes:
        hit = [i["이름"] for i in r["재료"] if i["이름"] in exclude or i["재료ID"] in exclude]
        if hit:
            excluded_recipes.append({"이름": r["이름"], "제외사유": hit})
            continue
        c = calculate_requirements(store, r["레시피ID"], servings)
        short = [f'{x["이름"]} {fmt_qty(x["부족"])}{x["단위"]}' for x in c["rows"] if x["부족"]]
        verdict = "가능" if c["feasible"] else ("계산 보류 재료 있음" if c["held"] and not short else "부족")
        cands.append({
            "레시피ID": r["레시피ID"], "이름": r["이름"], "인원": int(servings),
            "재료": [f'{i["이름"]} {fmt_qty(i["수량"])}{i["단위"]}' for i in r["재료"]],
            "판정": verdict, "부족재료": short, "보류재료": c["held"],
            "_rank": (0 if c["feasible"] else 1, len(short) + len(c["held"])),
        })
    if only_available:
        cands = [c for c in cands if c["판정"] == "가능"]
    cands.sort(key=lambda c: c["_rank"])
    for c in cands:
        del c["_rank"]
    return {
        "servings": int(servings), "exclude": exclude, "only_available": bool(only_available),
        "candidates": cands[:limit], "total_matching": len(cands), "excluded_recipes": excluded_recipes,
    }


# ---------------------------------------------------------------- 스키마 / 요약
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_inventory",
        "description": "냉장고 보유 재료 조회. names를 주면 해당 재료만, 생략하면 전체.",
        "parameters": {"type": "object", "properties": {
            "names": {"type": "array", "items": {"type": "string"}, "description": "조회할 재료 이름(예: ['쌀'])"}}}}},
    {"type": "function", "function": {
        "name": "list_menus",
        "description": "등록된 모든 메뉴(레시피)의 이름·기준인원·재료 목록 조회.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_recipe",
        "description": "레시피 한 개의 재료와 조리 순서 원문 조회.",
        "parameters": {"type": "object", "properties": {
            "recipe": {"type": "string", "description": "레시피ID(R01) 또는 메뉴 이름"}}, "required": ["recipe"]}}},
    {"type": "function", "function": {
        "name": "search_menu_candidates",
        "description": "인원·제외 재료·있는 재료만 여부로 등록 레시피에서 후보(최대 3개)를 찾고 후보별 가능/부족을 코드로 판정.",
        "parameters": {"type": "object", "properties": {
            "servings": {"type": "integer", "description": "먹는 인원(1 이상)"},
            "exclude_ingredients": {"type": "array", "items": {"type": "string"},
                                    "description": "빼고 싶은 재료 이름. 누적된 제외 조건 전체를 넣는다."},
            "only_available": {"type": "boolean", "description": "'있는 재료만'(부족량 0)일 때 true"}},
            "required": ["servings"]}}},
    {"type": "function", "function": {
        "name": "calculate_requirements",
        "description": "레시피와 인원으로 재료별 필요/보유/부족과 장보기 목록을 코드로 계산. 수량은 직접 넘기지 않는다.",
        "parameters": {"type": "object", "properties": {
            "recipe": {"type": "string", "description": "레시피ID(R01) 또는 메뉴 이름"},
            "servings": {"type": "integer", "description": "인원(1 이상)"}},
            "required": ["recipe", "servings"]}}},
]


def summarize(tool: str, result: dict) -> str:
    if tool == "get_inventory":
        s = ", ".join(f'{r["이름"]} {fmt_qty(r["수량"])}{r["단위"]}' for r in result["items"]) or "해당 재료 없음"
        if result["not_found"]:
            s += f" / 미등록: {', '.join(result['not_found'])}"
        return s
    if tool == "list_menus":
        return f'메뉴 {len(result["menus"])}개: ' + ", ".join(m["이름"] for m in result["menus"])
    if tool == "get_recipe":
        r = result["recipe"]
        return f'{r["이름"]}({r["레시피ID"]}) 기준 {r["기준인원"]}명, 조리 {len(r["조리순서"])}단계'
    if tool == "search_menu_candidates":
        names = ", ".join(f'{c["이름"]}({c["판정"]})' for c in result["candidates"]) or "후보 없음"
        return f'{result["servings"]}명, 제외 {result["exclude"] or "없음"}, 있는 재료만={result["only_available"]} → {names}'
    if tool == "calculate_requirements":
        short = ", ".join(f'{s["이름"]} {fmt_qty(s["수량"])}{s["단위"]}' for s in result["shopping_list"]) or "없음"
        held = f' / 계산 보류: {", ".join(result["held"])}' if result["held"] else ""
        return f'{result["recipe_name"]} {result["servings"]}명 · 장보기: {short}{held}'
    return ""
