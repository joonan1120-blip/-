"""모의 시험: 가짜 모델 응답으로 호출 상한·도구 실패·시간 초과 흐름을 확인한다(실제 LLM 아님)."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openai  # noqa: E402

from core import data as D  # noqa: E402
from core.agents import MainAgent, Settings  # noqa: E402


def _item(d):
    return NS(**d, model_dump=lambda exclude_none=True: d)


def tool_resp(name, args="{}", cid="c1"):
    call = _item({"type": "function_call", "call_id": cid, "name": name, "arguments": args})
    return NS(output=[call], output_text="")


def text_resp(t):
    return NS(output=[_item({"type": "message", "content": t})], output_text=t)


def make(responses, **kw):
    agent = MainAgent(Settings(api_key="sk-test", **kw), D.load_default())
    it = iter(responses)

    def fake(_system, _msgs):
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r
    agent._call = fake
    return agent


class AgentMock(unittest.TestCase):
    def test_lookup_one_tool(self):
        a = make([tool_resp("get_inventory", '{"names":["쌀"]}'), text_resp("쌀은 150g입니다.")])
        r = a.run([], "냉장고에 쌀 얼마나 있어?", {})
        self.assertIsNone(r.error)
        self.assertEqual([l["tool"] for l in r.logs], ["get_inventory"])
        self.assertIn("150g", r.logs[0]["summary"])

    def test_calc_updates_ctx(self):
        a = make([tool_resp("calculate_requirements", '{"recipe":"R01","servings":2}'), text_resp("ok")])
        r = a.run([], "당근밥 2명", {})
        self.assertEqual(r.ctx["servings"], 2)
        self.assertIn("R01", r.ctx["recipe"])

    def test_call_limit(self):
        calls = [tool_resp("get_inventory", cid=f"c{i}") for i in range(10)]
        a = make(calls, max_tool_calls=3)
        r = a.run([], "x", {})
        self.assertEqual(r.error, "limit")
        self.assertEqual(sum(1 for l in r.logs if l["tool"] == "get_inventory"), 3)
        self.assertEqual(r.history, [])  # 실패한 턴은 대화 기록에 남기지 않는다

    def test_tool_failure_recorded(self):
        a = make([tool_resp("get_inventory"), text_resp("도구가 실패했습니다.")], mock_tool_failure=True)
        r = a.run([], "x", {})
        self.assertIsNone(r.error)
        self.assertEqual(r.logs[0]["status"], "실패")
        self.assertTrue(r.logs[0]["mock"])
        self.assertIsNone(r.logs[0]["result"])

    def test_timeout(self):
        err = openai.APITimeoutError(request=NS(method="POST", url="https://x"))
        a = make([err], timeout=0.01)
        r = a.run([], "x", {})
        self.assertEqual(r.error, "timeout")
        self.assertIn("시험용 실패", r.logs[-1]["summary"])
        self.assertEqual(r.history, [])

    def test_unknown_calc_target_fails(self):
        a = make([tool_resp("calculate_requirements", '{"recipe":"없는메뉴","servings":2}'), text_resp("없음")])
        r = a.run([], "x", {})
        self.assertEqual(r.logs[0]["status"], "실패")


if __name__ == "__main__":
    unittest.main()
