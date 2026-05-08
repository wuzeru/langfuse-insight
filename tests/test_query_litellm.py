import unittest
import importlib.util
from datetime import date
from pathlib import Path

QUERY_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "langfuse-insight"
    / "scripts"
    / "query.py"
)
QUERY_SPEC = importlib.util.spec_from_file_location("query", QUERY_PATH)
query = importlib.util.module_from_spec(QUERY_SPEC)
assert QUERY_SPEC.loader is not None
QUERY_SPEC.loader.exec_module(query)


class LiteLLMLogMappingTest(unittest.TestCase):
    def test_maps_spend_log_to_trace_and_generation_observation(self):
        log = {
            "request_id": "req-123",
            "call_type": "acompletion",
            "model": "MiniMax-M2.7",
            "model_group": "MiniMax-M2.7",
            "status": "success",
            "startTime": "2026-05-07T00:14:12.872+00:00",
            "endTime": "2026-05-07T00:14:16.159+00:00",
            "completionStartTime": "2026-05-07T00:14:13.000+00:00",
            "request_duration_ms": 3287,
            "spend": 0.0189546,
            "total_tokens": 8525,
            "prompt_tokens": 8358,
            "completion_tokens": 167,
            "user": "user-from-request",
            "end_user": "",
            "session_id": "session-1",
            "request_tags": ["h-agent"],
            "metadata": {
                "user_api_key_alias": "wanghui",
                "user_api_key_user_id": "user-from-key",
                "error_information": None,
            },
        }

        trace = query.litellm_log_to_trace(log, project_id="litellm", target_date=date(2026, 5, 7))
        observation = query.litellm_log_to_observation(log)

        self.assertEqual(trace["id"], "req-123")
        self.assertEqual(trace["name"], "acompletion: MiniMax-M2.7")
        self.assertEqual(trace["project_id"], "litellm")
        self.assertEqual(trace["user_id"], "user-from-request")
        self.assertEqual(trace["session_id"], "session-1")
        self.assertEqual(trace["timestamp"], "2026-05-07T00:14:12.872+00:00")
        self.assertEqual(trace["tags"], ["h-agent"])
        self.assertEqual(trace["metadata"]["source"], "litellm")
        self.assertEqual(trace["metadata"]["api_key_alias"], "wanghui")

        self.assertEqual(observation["id"], "req-123:generation")
        self.assertEqual(observation["trace_id"], "req-123")
        self.assertEqual(observation["type"], "generation")
        self.assertEqual(observation["level"], "DEFAULT")
        self.assertEqual(observation["model"], "MiniMax-M2.7")
        self.assertEqual(observation["start_time"], "2026-05-07T00:14:12.872+00:00")
        self.assertEqual(observation["end_time"], "2026-05-07T00:14:16.159+00:00")
        self.assertEqual(observation["metadata"]["spend"], 0.0189546)
        self.assertEqual(observation["metadata"]["total_tokens"], 8525)

    def test_marks_failed_spend_log_as_error_observation(self):
        log = {
            "request_id": "req-failed",
            "call_type": "acompletion",
            "model": "gpt-4o",
            "status": "failure",
            "startTime": "2026-05-07T01:00:00+00:00",
            "endTime": "2026-05-07T01:00:01+00:00",
            "metadata": {
                "error_information": {
                    "error_code": "429",
                    "error_message": "rate limit",
                },
            },
        }

        observation = query.litellm_log_to_observation(log)

        self.assertEqual(observation["level"], "ERROR")
        self.assertEqual(observation["metadata"]["error_code"], "429")
        self.assertEqual(observation["metadata"]["error_message"], "rate limit")


if __name__ == "__main__":
    unittest.main()
