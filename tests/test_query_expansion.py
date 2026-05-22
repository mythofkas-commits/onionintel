import unittest

from query_expansion import (
    CONSERVATIVE_LIMIT,
    EXPLORATORY_LIMIT,
    EXPLORATORY_INITIAL_LIMIT,
    annotate_result_quality,
    build_expansion_context,
    classify_search_intent,
    filter_qualified_results,
    generate_query_plan,
    parse_query_plan_output,
    run_expanded_search,
    search_query_entries,
)


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, content):
        self.content = content

    def invoke(self, prompt):
        if isinstance(self.content, Exception):
            raise self.content
        return FakeResponse(self.content)


class QueryExpansionTests(unittest.TestCase):
    def test_classifies_common_search_intents(self):
        self.assertEqual(classify_search_intent("Caitlyn Helber")["intent"], "person_name")
        self.assertEqual(classify_search_intent("@caitlyn")["intent"], "handle")
        self.assertEqual(classify_search_intent("caitlyn_flower")["intent"], "handle")
        self.assertEqual(classify_search_intent("name@example.com")["intent"], "email_or_domain")
        self.assertEqual(classify_search_intent("example.com")["intent"], "email_or_domain")
        self.assertEqual(classify_search_intent("CVE-2026-12345")["intent"], "technical_ioc")
        self.assertEqual(classify_search_intent("Acme", build_expansion_context(organization="Acme Inc"))["intent"], "org_or_brand")

    def test_parse_query_plan_output_accepts_fenced_json(self):
        raw = """
```json
{"queries":[{"query":"Michael Owens PGP","query_type":"ai_probe","reason":"Probe PGP mentions."}]}
```
"""
        parsed = parse_query_plan_output(raw)

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["query"], "Michael Owens PGP")
        self.assertEqual(parsed[0]["query_type"], "ai_probe")

    def test_generate_query_plan_falls_back_on_invalid_llm_output(self):
        plan = generate_query_plan(
            FakeLLM("not json"),
            base_query="Michael Owens",
            refined_query="Michael Owens",
            context=build_expansion_context(aliases="Mike Owens"),
            mode="conservative",
        )

        self.assertEqual(plan["mode"], "conservative")
        self.assertLessEqual(len(plan["queries"]), CONSERVATIVE_LIMIT)
        self.assertTrue(plan["warnings"])
        self.assertIn('"Michael Owens"', [item["query"] for item in plan["queries"]])
        self.assertIn('"Mike Owens"', [item["query"] for item in plan["queries"]])

    def test_query_budget_limits_are_mode_specific(self):
        many_queries = {
            "queries": [
                {"query": f"probe {idx}", "query_type": "ai_probe", "reason": "fixture"}
                for idx in range(50)
            ]
        }
        conservative = generate_query_plan(FakeLLM(__import__("json").dumps(many_queries)), "base", "refined", mode="conservative")
        exploratory = generate_query_plan(FakeLLM(__import__("json").dumps(many_queries)), "base", "refined", mode="exploratory")

        self.assertLessEqual(len(conservative["queries"]), CONSERVATIVE_LIMIT)
        self.assertLessEqual(len(exploratory["queries"]), EXPLORATORY_INITIAL_LIMIT)

    def test_conservative_person_name_suppresses_sensitive_probes(self):
        plan = generate_query_plan(
            FakeLLM(
                '{"queries":[{"query":"\\"Caitlyn Helber\\" \\"SSN\\"","query_type":"sensitive_probe","reason":"fixture"}]}'
            ),
            "Caitlyn Helber",
            "Caitlyn Helber",
            mode="conservative",
            search_intent="person_name",
        )

        queries = [item["query"].lower() for item in plan["queries"]]
        self.assertFalse(any("ssn" in query for query in queries))
        self.assertGreater(plan["sensitive_probes_suppressed"], 0)

    def test_exploratory_person_name_allows_limited_sensitive_probes(self):
        plan = generate_query_plan(
            FakeLLM('{"queries":[]}'),
            "Caitlyn Helber",
            "Caitlyn Helber",
            mode="exploratory",
            search_intent="person_name",
        )

        self.assertTrue(any(item["query_type"] == "sensitive_probe" for item in plan["queries"]))
        self.assertLessEqual(len(plan["queries"]), EXPLORATORY_INITIAL_LIMIT)
        self.assertEqual(plan["artifact_pivot_reserve"], 6)

    def test_search_query_entries_merges_duplicate_result_provenance(self):
        def fake_search(query, max_workers=1):
            source = "SourceA" if query == "first" else "SourceB"
            return {
                "results": [{"title": "Hit", "link": "http://targetabcdefghijklmnop.onion/path", "source": source}],
                "sources": [{"name": source, "status": "success", "result_count": 1}],
            }

        payload = search_query_entries(
            [
                {"query": "first", "query_type": "exact", "reason": "first", "phase": "initial"},
                {"query": "second", "query_type": "ai_probe", "reason": "second", "phase": "initial"},
            ],
            search_fn=fake_search,
        )

        self.assertEqual(len(payload["results"]), 1)
        result = payload["results"][0]
        self.assertEqual(result["matched_query"], "first")
        self.assertEqual(result["found_by_sources"], ["SourceA", "SourceB"])
        self.assertEqual([item["query"] for item in result["matched_queries"]], ["first", "second"])

    def test_result_quality_marks_direct_and_infrastructure_only(self):
        direct = annotate_result_quality(
            {"title": "Caitlyn Helber paste", "link": "http://targetabcdefghijklmnop.onion", "source": "Fixture"},
            "Caitlyn Helber",
            {},
            "person_name",
        )
        generic = annotate_result_quality(
            {"title": "Dark leak Market", "link": "http://marketabcdefghijklmnop.onion", "source": "Fixture"},
            "Caitlyn Helber",
            {},
            "person_name",
        )

        self.assertTrue(direct["quality"]["direct_mention"])
        self.assertFalse(direct["quality"]["infrastructure_only"])
        self.assertTrue(generic["quality"]["infrastructure_only"])
        self.assertTrue(generic["quality"]["no_direct_mention"])

    def test_handle_quality_requires_exact_identifier_not_split_tokens(self):
        generic_flower = annotate_result_quality(
            {"title": "Farrah Flower profile", "link": "http://targetabcdefghijklmnop.onion", "source": "Fixture"},
            "caitlyn_flower",
            {},
            "handle",
        )
        exact_handle = annotate_result_quality(
            {"title": "caitlyn_flower paste", "link": "http://targetabcdefghijklmnop.onion", "source": "Fixture"},
            "caitlyn_flower",
            {},
            "handle",
        )

        self.assertFalse(generic_flower["quality"]["direct_mention"])
        self.assertTrue(generic_flower["quality"]["no_direct_mention"])
        self.assertTrue(exact_handle["quality"]["direct_mention"])

    def test_handle_policy_suppresses_underscore_to_space_ai_alias(self):
        plan = generate_query_plan(
            FakeLLM(
                '{"queries":[{"query":"caitlyn flower","query_type":"alias","reason":"bad split alias"},'
                '{"query":"caitlyn_flower telegram","query_type":"ai_probe","reason":"exact handle probe"}]}'
            ),
            "caitlyn_flower",
            "caitlyn_flower",
            mode="conservative",
            search_intent="handle",
        )

        queries = [item["query"] for item in plan["queries"]]
        self.assertNotIn("caitlyn flower", queries)
        self.assertIn("caitlyn_flower telegram", queries)
        self.assertTrue(any("weak handle" in warning.lower() for warning in plan["warnings"]))

    def test_identifier_quality_filter_drops_generic_non_direct_results(self):
        generic = annotate_result_quality(
            {"title": "Flowers", "link": "http://genericabcdefghijklmnop.onion", "source": "Fixture"},
            "caitlyn_flower",
            {},
            "handle",
        )
        direct = annotate_result_quality(
            {"title": "caitlyn_flower", "link": "http://directabcdefghijklmnop.onion", "source": "Fixture"},
            "caitlyn_flower",
            {},
            "handle",
        )

        qualified = filter_qualified_results([generic, direct], "handle")

        self.assertEqual([item["link"] for item in qualified], ["http://directabcdefghijklmnop.onion"])

    def test_off_mode_runs_single_refined_query(self):
        seen = []

        def fake_search(query, max_workers=1):
            seen.append(query)
            return {"results": [], "sources": []}

        payload = run_expanded_search(
            FakeLLM("{}"),
            base_query="base",
            refined_query="refined",
            mode="off",
            search_fn=fake_search,
        )

        self.assertEqual(seen, ["refined"])
        self.assertEqual(payload["query_expansion_mode"], "off")

    def test_exploratory_mode_runs_artifact_pivots(self):
        seen = []

        def fake_search(query, max_workers=1):
            seen.append(query)
            if "admin@example.com" in query:
                return {"results": [], "sources": [{"name": "Fixture", "status": "zero_results", "result_count": 0}]}
            return {
                "results": [
                    {
                        "title": "Contact admin@example.com",
                        "link": "http://targetabcdefghijklmnop.onion",
                        "source": "Fixture",
                    }
                ],
                "sources": [{"name": "Fixture", "status": "success", "result_count": 1}],
            }

        payload = run_expanded_search(
            FakeLLM('{"queries":[]}'),
            base_query="example",
            refined_query="example",
            mode="exploratory",
            search_fn=fake_search,
        )

        self.assertTrue(any("admin@example.com" in query for query in seen))
        self.assertTrue(any(run["phase"] == "artifact_pivot" for run in payload["query_runs"]))


if __name__ == "__main__":
    unittest.main()
