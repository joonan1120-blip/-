"""메인 에이전트(LLM, 추론 수준 낮음)와 서브 에이전트(LLM 없이 도구만 실행).

메인 에이전트가 tool-calling 으로 필요한 도구를 고르면, 해당 도구를 소유한 서브 에이전트가
실행하고 기록을 남긴다. 서브 에이전트는 판단하지 않고 도구만 불러온다.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field

import openai
from openai import OpenAI

from . import tools as T
from .data import Store


@dataclass
class Settings:
    api_key: str
    model: str = "gpt-6.1-sol"
    reasoning_effort: str = "low"
    timeout: float = 60.0
    max_tool_calls: int = 8
    mock_tool_failure: bool = False


@dataclass
class TurnResult:
    text: str
    logs: list[dict] = field(default_factory=list)
    error: str | None = None  # None | timeout | model | limit
    history: list[dict] = field(default_factory=list)
    ctx: dict = field(default_factory=dict)


# ------------------------------------------------------------ 서브 에이전트
class SubAgent:
    name = ""
    tools: dict = {}

    def run(self, tool: str, args: dict, store: Store, mock_fail: bool) -> dict:
        """도구를 실행하고 실행 기록 1건을 돌려준다."""
        log = {"agent": self.name, "tool": tool, "args": args, "status": "성공",
               "summary": "", "mock": False, "result": None}
        try:
            if mock_fail:
                log["mock"] = True
                raise T.ToolError("시험용 실패: 도구 실패 모의 시험이 켜져 있습니다.")
            result = self.tools[tool](store, **args)
            log["result"] = result
            log["summary"] = T.summarize(tool, result)
        except T.ToolError as e:
            log.update(status="실패", summary=str(e))
        except TypeError as e:  # 모델이 잘못된 인자를 넘긴 경우
            log.update(status="실패", summary=f"인자 오류: {e}")
        except Exception as e:  # noqa: BLE001 - 도구 실패는 기록하고 모델에 알린다
            log.update(status="실패", summary=f"도구 오류: {type(e).__name__}: {e}")
        return log


class InventoryAgent(SubAgent):
    name = "재고 에이전트"
    tools = {"get_inventory": T.get_inventory}


class RecipeAgent(SubAgent):
    name = "레시피 에이전트"
    tools = {"list_menus": T.list_menus, "get_recipe": T.get_recipe}


class PlannerAgent(SubAgent):
    name = "식단 에이전트"
    tools = {"search_menu_candidates": T.search_menu_candidates,
             "calculate_requirements": T.calculate_requirements}


SUB_AGENTS = [InventoryAgent(), RecipeAgent(), PlannerAgent()]
TOOL_OWNER = {t: a for a in SUB_AGENTS for t in a.tools}


# ------------------------------------------------------------ 메인 에이전트
SYSTEM_PROMPT = """너는 냉장고 재료로 한 끼 메뉴를 찾아 주는 식단 도우미(메인 에이전트)다. 한국어로 짧게 답한다.
도구는 서브 에이전트가 실행하며, 질문에 꼭 필요한 도구만 호출한다.

규칙
- 재고·메뉴·레시피·수량은 반드시 도구 결과를 근거로 말한다. 기억이나 추측으로 답하지 않는다.
- 재고나 메뉴 조회만 묻는 질문에는 해당 조회 도구만 호출하고 인원을 묻거나 식단 계산을 덧붙이지 않는다.
- 메뉴 추천 요청에 인원이 없으면 도구 호출 없이 먼저 몇 명이 먹는지 묻는다. 제외 재료는 선택 사항이라 묻지 않는다.
- 후보는 search_menu_candidates, 필요량·부족량은 calculate_requirements 로만 얻는다. 숫자를 직접 계산하거나 도구에 수량을 넘기지 않는다.
- 도구로 계산하기 전에는 '보유 재료만으로 가능'이라고 단정하지 않는다.
- '있는 재료만'이면 only_available=true. 후보가 없으면 없다고 알리고 조건을 바꿀지 묻는다.
- 화면에 후보 표와 계산 표(필요/보유/부족, 장보기)가 이미 표시되므로 표의 숫자를 다시 길게 나열하거나 바꾸지 말고 핵심만 한두 문장으로 요약한다.
- 계산 결과에는 '현재 재고는 변경되지 않습니다'를 짧게 덧붙인다.
- 인원만 바뀌면(예: '세 명으로') [현재 대화 맥락]의 선택 메뉴를 유지한 채 calculate_requirements 를 다시 호출한다.
- 제외 조건이 늘면(예: '당근도 빼줘') 기존 제외 조건에 합쳐 search_menu_candidates 를 다시 호출한다. 제외 재료가 든 메뉴를 재료만 빼서 제시하지 않는다.
- '그걸', '아까 그 메뉴'처럼 대상이 맥락에 없으면 도구 호출 없이 어떤 메뉴인지 묻는다.
- 조리 순서는 get_recipe 로 읽은 원문 그대로만 말한다. 임의로 바꾸거나 지어내지 않는다.
- 도구가 실패하면 실패했다고 알리고 숫자를 지어내지 않는다.
- 재료 제외는 선호 반영일 뿐 알레르기 안전을 보장하지 않는다.
"""


def _context_block(ctx: dict) -> str:
    if not ctx:
        return "[현재 대화 맥락]\n없음 (아직 선택한 메뉴·인원·제외 조건이 없다)"
    lines = ["[현재 대화 맥락]"]
    if ctx.get("recipe"):
        lines.append(f'- 선택한 메뉴: {ctx["recipe"]}')
    if ctx.get("servings"):
        lines.append(f'- 인원: {ctx["servings"]}명')
    if ctx.get("exclude"):
        lines.append(f'- 제외 재료: {", ".join(ctx["exclude"])}')
    return "\n".join(lines)


def _update_ctx(ctx: dict, log: dict) -> None:
    if log["status"] != "성공":
        return
    res = log["result"]
    if log["tool"] == "search_menu_candidates":
        ctx["servings"] = res["servings"]
        ctx["exclude"] = res["exclude"]
        ctx.pop("recipe", None)  # 새 검색 후에는 사용자가 다시 메뉴를 고른다
    elif log["tool"] == "calculate_requirements":
        ctx["recipe"] = f'{res["recipe_name"]}({res["recipe_id"]})'
        ctx["servings"] = res["servings"]


# Responses API 는 Chat Completions 와 달리 function 정의를 평평하게 받는다.
RESPONSES_TOOLS = [{"type": "function", **t["function"]} for t in T.TOOL_SCHEMAS]


def _dump(item) -> dict:
    return item.model_dump(exclude_none=True)


class MainAgent:
    def __init__(self, settings: Settings, store: Store):
        self.s = settings
        self.store = store
        self.client = OpenAI(api_key=settings.api_key, timeout=settings.timeout, max_retries=0)

    def _call(self, instructions: str, items: list[dict]):
        """Responses API 호출(함수 도구 + reasoning 은 /v1/responses 에서만 지원)."""
        kwargs = dict(model=self.s.model, instructions=instructions, input=items, tools=RESPONSES_TOOLS)
        if self.s.reasoning_effort:
            kwargs["reasoning"] = {"effort": self.s.reasoning_effort}
        try:
            return self.client.responses.create(**kwargs)
        except openai.BadRequestError as e:
            if "reasoning" in str(e) and "reasoning" in kwargs:  # 추론 수준 옵션을 받지 않는 모델
                kwargs.pop("reasoning")
                return self.client.responses.create(**kwargs)
            raise

    def run(self, history: list[dict], user_text: str, ctx: dict) -> TurnResult:
        ctx = copy.deepcopy(ctx)
        start = list(history)
        msgs = start + [{"role": "user", "content": user_text}]
        logs: list[dict] = []
        calls = 0
        system = SYSTEM_PROMPT + "\n" + _context_block(ctx)

        def fail(kind: str, text: str, detail: str, mock: bool = False) -> TurnResult:
            logs.append({"agent": "메인 에이전트", "tool": "LLM 호출", "args": {"model": self.s.model},
                         "status": "실패", "summary": detail, "mock": mock, "result": None})
            return TurnResult(text=text, logs=logs, error=kind, history=start, ctx=ctx_before)

        ctx_before = copy.deepcopy(ctx)
        # 모델이 도구를 계속 부르는 경우를 막기 위한 안전 장치(호출 상한과 별개)
        for _ in range(self.s.max_tool_calls + 2):
            try:
                resp = self._call(system, msgs)
            except openai.APITimeoutError:
                mock = self.s.timeout < 1
                return fail("timeout", f"모델 응답이 제한 시간({self.s.timeout:g}초)을 넘었습니다. 다시 시도해 주세요.",
                            f"시간 초과({self.s.timeout:g}초)" + (" · 시험용 실패" if mock else ""), mock)
            except openai.AuthenticationError:
                return fail("model", "API 키가 올바르지 않습니다. .env의 OPENAI_API_KEY를 확인해 주세요.", "인증 실패")
            except openai.APIError as e:
                return fail("model", "모델 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.",
                            f"{type(e).__name__}: {str(e)[:200]}")
            msgs.extend(_dump(it) for it in resp.output)
            fcalls = [it for it in resp.output if it.type == "function_call"]
            if not fcalls:
                return TurnResult(text=resp.output_text or "", logs=logs, history=msgs, ctx=ctx)
            for c in fcalls:
                if calls >= self.s.max_tool_calls:
                    return fail("limit", f"도구 호출 상한({self.s.max_tool_calls}회)에 도달해 중단했습니다. "
                                "질문을 나누어 다시 시도해 주세요.", f"호출 상한 {self.s.max_tool_calls}회 도달")
                calls += 1
                name = c.name
                try:
                    args = json.loads(c.arguments or "{}")
                    if not isinstance(args, dict):
                        raise ValueError
                except ValueError:
                    log = {"agent": "-", "tool": name, "args": {}, "status": "실패",
                           "summary": "인자 JSON 오류", "mock": False, "result": None}
                else:
                    owner = TOOL_OWNER.get(name)
                    if owner is None:
                        log = {"agent": "-", "tool": name, "args": args, "status": "실패",
                               "summary": "등록되지 않은 도구", "mock": False, "result": None}
                    else:
                        log = owner.run(name, args, self.store, self.s.mock_tool_failure)
                logs.append(log)
                _update_ctx(ctx, log)
                payload = ({"ok": True, **log["result"]} if log["status"] == "성공"
                           else {"ok": False, "error": log["summary"]})
                msgs.append({"type": "function_call_output", "call_id": c.call_id,
                             "output": json.dumps(payload, ensure_ascii=False)})
        return fail("limit", "도구 호출이 반복되어 중단했습니다. 다시 시도해 주세요.", "반복 호출 중단")
