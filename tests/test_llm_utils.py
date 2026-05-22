import unittest

from llm_utils import build_model_routing_plan, choose_model_for_task


class ModelRoutingTests(unittest.TestCase):
    def test_routes_openai_tasks_to_current_cost_tier_models(self):
        available = ["gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-4.1"]
        routing = build_model_routing_plan("gpt-4.1", True, available)

        self.assertEqual(routing["query_refinement"], "gpt-5.4-mini")
        self.assertEqual(routing["query_expansion"], "gpt-5.4-mini")
        self.assertEqual(routing["result_triage"], "gpt-5.4-nano")
        self.assertEqual(routing["final_report"], "gpt-5.4")

    def test_disabled_routing_preserves_selected_model(self):
        routing = build_model_routing_plan("claude-sonnet-4-5", False, ["gpt-5.4"])

        self.assertFalse(routing["enabled"])
        self.assertEqual(routing["final_report"], "claude-sonnet-4-5")

    def test_routing_falls_back_when_preferred_models_unavailable(self):
        self.assertEqual(
            choose_model_for_task("final_report", "gemini-2.5-pro", ["gemini-2.5-pro"]),
            "gemini-2.5-pro",
        )


if __name__ == "__main__":
    unittest.main()
