"""API 키 없이 돌리는 코드 계산·검증 테스트: python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import data as D  # noqa: E402
from core import tools as T  # noqa: E402

ERR = ROOT / "data" / "오류"
FIX = ROOT / "tests" / "fixtures"  # 과제 원본 데이터(레시피 8개). 배포 데이터가 바뀌어도 테스트가 흔들리지 않게 고정


def load(fridge=None, recipes=None):
    f = D.load_default_fridge(fridge or FIX / "냉장고.csv")
    r = D.load_default_recipes(recipes or FIX / "레시피.json")
    return D.merge(f, r)


def rows(res):
    return {r["이름"]: (r["필요"], r["보유"], r["부족"]) for r in res["rows"]}


class Core(unittest.TestCase):
    def setUp(self):
        self.s = load()

    def test_load(self):
        self.assertTrue(self.s.ok)
        self.assertEqual((len(self.s.inventory), len(self.s.recipes)), (12, 8))

    def test_unregistered(self):
        m = {x["이름"]: x for x in T.list_menus(self.s)["menus"]}
        self.assertIn("돼지고기 150g", m["김치찌개"]["재료"])
        self.assertEqual(m["김치찌개"]["미등록재료"], ["돼지고기"])
        self.assertEqual(T.get_recipe(self.s, "김치찌개")["recipe"]["재료"][2]["미등록"], True)

    def test_carrot_rice_2(self):
        r = T.calculate_requirements(self.s, "R01", 2)
        self.assertEqual(rows(r), {"쌀": (200, 150, 50), "당근": (100, 120, 0), "물": (300, 1000, 0)})
        self.assertEqual(r["shopping_list"], [{"이름": "쌀", "수량": 50, "단위": "g"}])

    def test_carrot_rice_1_and_3(self):
        r = T.calculate_requirements(self.s, "당근밥", 1)
        self.assertEqual(rows(r), {"쌀": (100, 150, 0), "당근": (50, 120, 0), "물": (150, 1000, 0)})
        self.assertEqual(r["shopping_list"], [])
        r = T.calculate_requirements(self.s, "R01", 3)
        self.assertEqual(rows(r), {"쌀": (300, 150, 150), "당근": (150, 120, 30), "물": (450, 1000, 0)})

    def test_no_rounding(self):
        r = T.calculate_requirements(self.s, "감자전", 3)
        self.assertEqual(rows(r)["감자"], (4.5, 2, 2.5))

    @unittest.skipUnless(ERR.exists(), "data/오류 폴더 없음(배포본)")
    def test_unit_mismatch(self):
        s = load(fridge=ERR / "냉장고_단위불일치.csv")
        r = T.calculate_requirements(s, "R01", 2)
        self.assertIsNone(rows(r)["쌀"][2])
        self.assertEqual(rows(r)["당근"], (100, 120, 0))
        self.assertEqual(r["held"], ["쌀"])
        self.assertFalse(r["feasible"])

    def test_search_exclude_egg(self):
        r = T.search_menu_candidates(self.s, 2, ["달걀"])
        names = {c["이름"] for c in r["candidates"]}
        self.assertLessEqual(len(names), 3)
        self.assertFalse(names & {"달걀볶음밥", "두부부침", "양파달걀국"})
        v = {c["이름"]: c["판정"] for c in r["candidates"]}
        self.assertEqual(v["감자조림"], "가능")

    def test_only_available(self):
        r = T.search_menu_candidates(self.s, 2, ["달걀"], True)
        self.assertEqual({c["이름"] for c in r["candidates"]}, {"감자조림", "채소죽"})

    def test_none_available(self):
        r = T.search_menu_candidates(self.s, 1, ["달걀", "감자", "쌀"], True)
        self.assertEqual(r["candidates"], [])

    def test_exclude_carrot_3(self):
        r = T.search_menu_candidates(self.s, 3, ["달걀", "당근"])
        self.assertEqual({c["이름"] for c in r["candidates"]}, {"감자조림", "김치찌개", "감자전"})

    def test_inventory_lookup(self):
        self.assertEqual(T.get_inventory(self.s, ["쌀"])["items"][0]["수량"], 150)

    @unittest.skipUnless(ERR.exists(), "data/오류 폴더 없음(배포본)")
    def test_errors(self):
        cases = [
            ("냉장고_음수.csv", "fridge_errors", "쌀"),
            ("냉장고_중복ID.csv", "fridge_errors", "I02"),
        ]
        for name, attr, word in cases:
            st = D.load_default_fridge(ERR / name)
            self.assertIsNone(st.inventory)
            self.assertIn(word, "".join(getattr(st, attr)))
        st = D.load_default_recipes(ERR / "레시피_손상.json")
        self.assertIsNone(st.recipes)
        self.assertIn("JSON", "".join(st.recipe_errors))
        st = D.load_default_recipes(ERR / "레시피_기준인원오류.json")
        self.assertIsNone(st.recipes)
        self.assertIn("R01", "".join(st.recipe_errors))
        self.assertIn("기준인원", "".join(st.recipe_errors))

    def test_assign_ids(self):
        cat = D.ingredient_catalog(self.s.inventory, self.s.recipes)
        rows = D.assign_ids([{"이름": "쌀"}, {"이름": "돼지고기"}, {"이름": "마늘"}, {"이름": "마늘"}], cat)
        self.assertEqual([r["재료ID"] for r in rows], ["I01", "I13", "I14", "I14"])

    def test_bad_servings(self):
        with self.assertRaises(T.ToolError):
            T.calculate_requirements(self.s, "R01", 0)


if __name__ == "__main__":
    unittest.main()
