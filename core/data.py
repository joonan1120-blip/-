"""냉장고 CSV / 레시피 JSON 읽기·검증·저장."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_FRIDGE = DATA_DIR / "냉장고.csv"
DEFAULT_RECIPES = DATA_DIR / "레시피.json"

UNITS = ("g", "개")
FRIDGE_COLUMNS = ["재료ID", "이름", "수량", "단위"]


@dataclass
class Store:
    """검증을 통과한 작업용 데이터. 오류가 있으면 inventory/recipes는 None."""

    inventory: list[dict] | None = None
    recipes: list[dict] | None = None
    fridge_errors: list[str] = field(default_factory=list)
    recipe_errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.fridge_errors and not self.recipe_errors

    @property
    def errors(self) -> list[str]:
        return self.fridge_errors + self.recipe_errors


def _num(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return None if value != value or abs(value) == float("inf") else value
    try:
        text = str(value).strip().replace(",", "")
        n = float(text)
    except (TypeError, ValueError):
        return None
    if n != n or n in (float("inf"), float("-inf")):
        return None
    return int(n) if n.is_integer() and "." not in text else n


def decode_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- 냉장고
def validate_inventory(rows: list[dict], start_row: int = 2) -> tuple[list[dict], list[str]]:
    """rows: 재료ID/이름/수량/단위 dict 목록. 반환: (정규화된 행, 오류 목록)."""
    errors: list[str] = []
    clean: list[dict] = []
    seen: dict[str, int] = {}
    for i, row in enumerate(rows, start=start_row):
        rid = str(row.get("재료ID", "") or "").strip()
        name = str(row.get("이름", "") or "").strip()
        unit = str(row.get("단위", "") or "").strip()
        qty = _num(row.get("수량"))
        if not rid:
            errors.append(f"냉장고 {i}행: 재료ID가 비어 있습니다.")
        elif rid in seen:
            errors.append(f"냉장고 {i}행: 재료ID {rid}가 중복되었습니다({seen[rid]}행과 {i}행).")
        else:
            seen[rid] = i
        if not name:
            errors.append(f"냉장고 {i}행({rid or '?'}): 이름이 비어 있습니다.")
        if qty is None:
            errors.append(f"냉장고 {i}행({name or rid}): 수량 '{row.get('수량')}'은(는) 숫자가 아닙니다.")
        elif qty < 0:
            errors.append(f"냉장고 {i}행({name or rid}): 수량이 음수입니다({qty}).")
        if unit not in UNITS:
            errors.append(f"냉장고 {i}행({name or rid}): 단위 '{unit}'은(는) g 또는 개여야 합니다.")
        clean.append({"재료ID": rid, "이름": name, "수량": qty, "단위": unit})
    return clean, errors


def parse_fridge_csv(text: str) -> Store:
    store = Store()
    try:
        reader = csv.DictReader(io.StringIO(text))
        header = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in FRIDGE_COLUMNS if c not in header]
        if missing:
            store.fridge_errors = [f"냉장고 CSV 1행(헤더): 필수 열이 없습니다 → {', '.join(missing)}"]
            return store
        rows = [{k.strip(): v for k, v in r.items() if k} for r in reader]
    except csv.Error as e:
        store.fridge_errors = [f"냉장고 CSV를 읽을 수 없습니다: {e}"]
        return store
    if not rows:
        store.fridge_errors = ["냉장고 CSV에 재료 행이 없습니다."]
        return store
    clean, errors = validate_inventory(rows)
    store.fridge_errors = errors
    store.inventory = None if errors else clean
    return store


# ---------------------------------------------------------------- 레시피
def validate_recipes(data) -> tuple[list[dict] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(data, list):
        return None, ["레시피 JSON 최상위는 레시피 목록(배열)이어야 합니다."]
    if not data:
        return None, ["레시피 JSON에 레시피가 없습니다."]
    seen: set[str] = set()
    for n, rec in enumerate(data, start=1):
        if not isinstance(rec, dict):
            errors.append(f"레시피 {n}번째 항목이 객체가 아닙니다.")
            continue
        rid = str(rec.get("레시피ID", "")).strip()
        label = f"레시피 {rid or f'{n}번째'} {rec.get('이름', '')}".strip()
        if not rid:
            errors.append(f"레시피 {n}번째: 레시피ID가 없습니다.")
        elif rid in seen:
            errors.append(f"{label}: 레시피ID {rid}가 중복되었습니다.")
        seen.add(rid)
        if not str(rec.get("이름", "")).strip():
            errors.append(f"{label}: 이름이 없습니다.")
        base = rec.get("기준인원")
        if isinstance(base, bool) or not isinstance(base, int) or base < 1:
            errors.append(f"{label}: 기준인원이 1 이상의 정수가 아닙니다(값: {base!r}).")
        ings = rec.get("재료")
        if not isinstance(ings, list) or not ings:
            errors.append(f"{label}: 재료 목록이 비어 있거나 형식이 다릅니다.")
        else:
            ids: set[str] = set()
            for j, ing in enumerate(ings, start=1):
                if not isinstance(ing, dict):
                    errors.append(f"{label} 재료 {j}번째: 객체가 아닙니다.")
                    continue
                iid = str(ing.get("재료ID", "")).strip()
                q = _num(ing.get("수량"))
                if not iid:
                    errors.append(f"{label} 재료 {j}번째: 재료ID가 없습니다.")
                elif iid in ids:
                    errors.append(f"{label} 재료 {j}번째: 재료ID {iid}가 중복되었습니다.")
                ids.add(iid)
                if not str(ing.get("이름", "")).strip():
                    errors.append(f"{label} 재료 {j}번째({iid}): 이름이 없습니다.")
                if q is None or isinstance(ing.get("수량"), bool) or q < 0:
                    errors.append(f"{label} 재료 {j}번째({iid}): 수량이 0 이상 숫자가 아닙니다(값: {ing.get('수량')!r}).")
                if ing.get("단위") not in UNITS:
                    errors.append(f"{label} 재료 {j}번째({iid}): 단위가 g 또는 개가 아닙니다(값: {ing.get('단위')!r}).")
        steps = rec.get("조리순서")
        if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
            errors.append(f"{label}: 조리순서가 문자열 목록이 아닙니다.")
    return (None if errors else data), errors


def parse_recipes_json(text: str) -> Store:
    store = Store()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        store.recipe_errors = [f"레시피 JSON을 읽을 수 없습니다(JSON 형식 손상): {e.lineno}행 {e.colno}열 - {e.msg}"]
        return store
    recipes, errors = validate_recipes(data)
    store.recipe_errors = errors
    store.recipes = recipes
    return store


# ---------------------------------------------------------------- 재료ID 자동 할당
def ingredient_catalog(inventory: list[dict] | None, recipes: list[dict] | None) -> dict[str, str]:
    """알려진 재료 이름 -> 재료ID (냉장고 우선, 레시피 재료 포함)."""
    cat: dict[str, str] = {}
    for r in inventory or []:
        cat.setdefault(r["이름"], r["재료ID"])
    for rec in recipes or []:
        for i in rec["재료"]:
            cat.setdefault(i["이름"], i["재료ID"])
    return cat


def assign_ids(rows: list[dict], catalog: dict[str, str]) -> list[dict]:
    """이름으로 기존 재료ID를 찾고, 새 재료면 다음 번호(I13, ...)를 자동 부여한다.

    이미 ID가 있는 행(기존 재료)은 ID를 유지한다. catalog 는 새로 부여한 ID로 갱신된다.
    """
    used = set(catalog.values()) | {r.get("재료ID") for r in rows if r.get("재료ID")}
    top = max((int(i[1:]) for i in used if i[:1] == "I" and i[1:].isdigit()), default=0)
    out = []
    for r in rows:
        name = str(r.get("이름") or "").strip()
        rid = str(r.get("재료ID") or "").strip() or catalog.get(name, "")
        if name and not rid:
            top += 1
            rid = f"I{top:02d}"
        if name:
            catalog.setdefault(name, rid)
        out.append({**r, "이름": name, "재료ID": rid})
    return out


# ---------------------------------------------------------------- 로드/저장
def load_default_fridge(path: Path = DEFAULT_FRIDGE) -> Store:
    try:
        return parse_fridge_csv(decode_bytes(path.read_bytes()))
    except OSError as e:
        return Store(fridge_errors=[f"{path.name} 파일을 열 수 없습니다: {e}"])


def load_default_recipes(path: Path = DEFAULT_RECIPES) -> Store:
    try:
        return parse_recipes_json(decode_bytes(path.read_bytes()))
    except OSError as e:
        return Store(recipe_errors=[f"{path.name} 파일을 열 수 없습니다: {e}"])


def load_default() -> Store:
    return merge(load_default_fridge(), load_default_recipes())


def merge(fridge: Store, recipes: Store) -> Store:
    return Store(
        inventory=fridge.inventory,
        recipes=recipes.recipes,
        fridge_errors=fridge.fridge_errors,
        recipe_errors=recipes.recipe_errors,
    )


def inventory_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FRIDGE_COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r[c] for c in FRIDGE_COLUMNS})
    return buf.getvalue()


def save_inventory(rows: list[dict], path: Path = DEFAULT_FRIDGE) -> None:
    path.write_text(inventory_to_csv(rows), encoding="utf-8-sig")


def save_recipes(recipes: list[dict], path: Path = DEFAULT_RECIPES) -> None:
    path.write_text(json.dumps(recipes, ensure_ascii=False, indent=1), encoding="utf-8")
