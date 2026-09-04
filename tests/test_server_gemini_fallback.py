import os
import unittest
from unittest.mock import MagicMock, patch

import server


class GeminiFallbackTests(unittest.TestCase):
    def test_gemini_credentials_support_fallback_and_delimited_key_list(self) -> None:
        original_primary = server.GEMINI_MODEL
        original_fallback = server.GEMINI_FALLBACK_MODEL
        try:
            server.GEMINI_MODEL = "primary-model"
            server.GEMINI_FALLBACK_MODEL = "fallback-model"
            with patch.dict(os.environ, {
                "GEMINI_API_KEY": "primary-key",
                "GEMINI_API_KEY_FALLBACK": "fallback-key",
                "GEMINI_API_KEYS": "third-key; fourth-key,third-key",
            }, clear=False):
                self.assertEqual(server._configured_gemini_credentials(), [
                    ("primary-key", "primary-model"),
                    ("fallback-key", "fallback-model"),
                    ("third-key", "fallback-model"),
                    ("fourth-key", "fallback-model"),
                ])
        finally:
            server.GEMINI_MODEL = original_primary
            server.GEMINI_FALLBACK_MODEL = original_fallback

    def test_gemini_error_categories_distinguish_quota_rate_limit_and_auth(self) -> None:
        quota = Exception("429 RESOURCE_EXHAUSTED: quota exhausted")
        quota.code = 429
        rate = Exception("429 Too Many Requests")
        rate.code = 429
        auth = Exception("401 UNAUTHENTICATED: invalid API key")
        auth.code = 401
        self.assertEqual(server._gemini_error_category(quota), "quota_exhausted")
        self.assertEqual(server._gemini_error_category(rate), "rate_limited")
        self.assertEqual(server._gemini_error_category(auth), "authentication")

    def test_json_parser_recovers_first_object_when_gemini_appends_text(self) -> None:
        payload = server._json_from_response('{"fields": {"mrp": {}}}\nThis trailing text is ignored.')
        self.assertEqual(payload, {"fields": {"mrp": {}}})

    def test_json_parser_prefers_extraction_object_over_unrelated_wrapper(self) -> None:
        payload = server._json_from_response(
            '{"status":"ok"}\n{"fields":{"mrp":{"status":"VISIBLE","value":"MRP Rs. 20/- (INCL. OF ALL TAXES)"}}}'
        )
        self.assertIn("fields", payload)
        self.assertEqual(payload["fields"]["mrp"]["status"], "VISIBLE")

    def test_extractor_unwraps_known_response_envelope(self) -> None:
        package = server._extract_package({
            "result": {
                "fields": {
                    "mrp": {
                        "status": "VISIBLE",
                        "value": "MRP Rs. 20/- (INCL. OF ALL TAXES)",
                        "evidence": "MRP Rs. 20/- (INCL. OF ALL TAXES)",
                    },
                },
                "context": {"inspected_relevant_label_surfaces": True},
            },
        })
        self.assertEqual(package.mrp.value, "MRP Rs. 20/- (INCL. OF ALL TAXES)")

    def test_primary_success_does_not_call_fallback(self) -> None:
        primary_client = MagicMock()
        primary_response = MagicMock()
        primary_response.text = '{"status": "ok", "result": {"summary": "primary"}}'
        primary_client.models.generate_content.return_value = primary_response
        fallback_client = MagicMock()

        original_model = server.GEMINI_MODEL
        original_fallback = server.GEMINI_FALLBACK_MODEL
        try:
            server.GEMINI_MODEL = "primary-model"
            server.GEMINI_FALLBACK_MODEL = "fallback-model"
            with patch.dict(os.environ, {"GEMINI_API_KEY": "primary", "GEMINI_API_KEY_FALLBACK": "fallback", "GEMINI_API_KEYS": ""}, clear=False):
                async def run_test() -> None:
                    with patch.object(server.genai, "Client", return_value=primary_client):
                        payload = await server._call_gemini([
                            ("front.jpg", "image/jpeg", b"front"),
                            ("back.jpg", "image/jpeg", b"back"),
                        ])
                    self.assertEqual(payload["result"]["summary"], "primary")
                    self.assertEqual(primary_client.models.generate_content.call_count, 1)
                    contents = primary_client.models.generate_content.call_args.kwargs["contents"]
                    self.assertEqual(contents[1], "Inspect the complete package image named front.jpg, including all readable label panels.")
                    self.assertEqual(contents[3], "Inspect the complete package image named back.jpg, including all readable label panels.")
                    self.assertEqual(fallback_client.models.generate_content.call_count, 0)

                import asyncio
                asyncio.run(run_test())
        finally:
            server.GEMINI_MODEL = original_model
            server.GEMINI_FALLBACK_MODEL = original_fallback

    def test_quota_switches_to_configured_fallback_model_once(self) -> None:
        primary_client = MagicMock()
        primary_error = Exception("429 Too Many Requests")
        primary_error.code = 429
        primary_client.models.generate_content.side_effect = primary_error

        fallback_client = MagicMock()
        fallback_response = MagicMock()
        fallback_response.text = '{"status": "ok", "result": {"summary": "fallback"}}'
        fallback_client.models.generate_content.return_value = fallback_response

        original_model = server.GEMINI_MODEL
        original_fallback = server.GEMINI_FALLBACK_MODEL
        try:
            server.GEMINI_MODEL = "primary-model"
            server.GEMINI_FALLBACK_MODEL = "fallback-model"
            with patch.dict(os.environ, {"GEMINI_API_KEY": "primary", "GEMINI_API_KEY_FALLBACK": "fallback", "GEMINI_API_KEYS": ""}, clear=False):
                async def run_test() -> None:
                    with patch.object(server.genai, "Client", side_effect=[primary_client, fallback_client]):
                        payload = await server._call_gemini([("a.jpg", "image/jpeg", b"abc")])
                    self.assertEqual(payload["result"]["summary"], "fallback")
                    self.assertEqual(primary_client.models.generate_content.call_count, 1)
                    self.assertEqual(fallback_client.models.generate_content.call_count, 1)
                    self.assertEqual(fallback_client.models.generate_content.call_args.kwargs["model"], "fallback-model")

                import asyncio
                asyncio.run(run_test())
        finally:
            server.GEMINI_MODEL = original_model
            server.GEMINI_FALLBACK_MODEL = original_fallback

    def test_transient_gemini_503_switches_to_fallback_once(self) -> None:
        original_primary = server.GEMINI_MODEL
        original_fallback = server.GEMINI_FALLBACK_MODEL
        server.GEMINI_MODEL = "gemini-3.6-flash"
        server.GEMINI_FALLBACK_MODEL = "gemini-3.5-flash"

        try:
            primary_client = MagicMock()
            primary_error = Exception("503 Service Unavailable")
            primary_error.code = 503
            primary_client.models.generate_content.side_effect = primary_error
            fallback_client = MagicMock()
            fallback_response = MagicMock()
            fallback_response.text = '{"status": "ok", "result": {"summary": "tested"}}'
            fallback_client.models.generate_content.return_value = fallback_response

            async def run_test() -> None:
                with patch.dict(os.environ, {"GEMINI_API_KEY": "primary", "GEMINI_API_KEY_FALLBACK": "fallback", "GEMINI_API_KEYS": ""}, clear=False):
                    with patch.object(server.genai, "Client", side_effect=[primary_client, fallback_client]):
                        payload = await server._call_gemini([("a.jpg", "image/jpeg", b"abc")])
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(primary_client.models.generate_content.call_count, 1)
                self.assertEqual(fallback_client.models.generate_content.call_count, 1)
                self.assertEqual(fallback_client.models.generate_content.call_args.kwargs["model"], "gemini-3.5-flash")

            import asyncio
            asyncio.run(run_test())
        finally:
            server.GEMINI_MODEL = original_primary
            server.GEMINI_FALLBACK_MODEL = original_fallback

    def test_timeout_switches_to_fallback(self) -> None:
        primary_client = MagicMock()
        primary_client.models.generate_content.side_effect = TimeoutError("request timed out")
        fallback_client = MagicMock()
        fallback_response = MagicMock()
        fallback_response.text = '{"status": "ok", "result": {"summary": "timeout fallback"}}'
        fallback_client.models.generate_content.return_value = fallback_response

        original_primary = server.GEMINI_MODEL
        original_fallback = server.GEMINI_FALLBACK_MODEL
        try:
            server.GEMINI_MODEL = "primary-model"
            server.GEMINI_FALLBACK_MODEL = "fallback-model"
            async def run_test() -> None:
                with patch.dict(os.environ, {"GEMINI_API_KEY": "primary", "GEMINI_API_KEY_FALLBACK": "fallback", "GEMINI_API_KEYS": ""}, clear=False):
                    with patch.object(server.genai, "Client", side_effect=[primary_client, fallback_client]):
                        payload = await server._call_gemini([("a.jpg", "image/jpeg", b"abc")])
                self.assertEqual(payload["result"]["summary"], "timeout fallback")
                self.assertEqual(primary_client.models.generate_content.call_count, 1)
                self.assertEqual(fallback_client.models.generate_content.call_count, 1)

            import asyncio
            asyncio.run(run_test())
        finally:
            server.GEMINI_MODEL = original_primary
            server.GEMINI_FALLBACK_MODEL = original_fallback

    def test_transient_failure_does_not_retry_the_same_model(self) -> None:
        primary_client = MagicMock()
        primary_error = Exception("503 Service Unavailable")
        primary_error.code = 503
        primary_client.models.generate_content.side_effect = primary_error
        fallback_client = MagicMock()

        original_primary = server.GEMINI_MODEL
        original_fallback = server.GEMINI_FALLBACK_MODEL
        try:
            server.GEMINI_MODEL = "gemini-3.5-flash"
            server.GEMINI_FALLBACK_MODEL = "gemini-3.5-flash"

            async def run_test() -> None:
                with patch.dict(os.environ, {"GEMINI_API_KEY": "primary", "GEMINI_API_KEY_FALLBACK": "primary", "GEMINI_API_KEYS": ""}, clear=False):
                    with patch.object(server.genai, "Client", side_effect=[primary_client, fallback_client]):
                        with self.assertRaises(server.HTTPException) as context:
                            await server._call_gemini([("a.jpg", "image/jpeg", b"abc")])
                self.assertEqual(context.exception.status_code, 503)
                self.assertEqual(primary_client.models.generate_content.call_count, 1)
                self.assertEqual(fallback_client.models.generate_content.call_count, 0)

            import asyncio
            asyncio.run(run_test())
        finally:
            server.GEMINI_MODEL = original_primary
            server.GEMINI_FALLBACK_MODEL = original_fallback

    def test_quota_failure_does_not_retry_same_credential_and_model(self) -> None:
        primary_client = MagicMock()
        quota_error = Exception("429 RESOURCE_EXHAUSTED: quota exhausted")
        quota_error.code = 429
        primary_client.models.generate_content.side_effect = quota_error
        fallback_client = MagicMock()

        original_primary = server.GEMINI_MODEL
        original_fallback = server.GEMINI_FALLBACK_MODEL
        try:
            server.GEMINI_MODEL = "gemini-3.5-flash"
            server.GEMINI_FALLBACK_MODEL = "gemini-3.5-flash"

            async def run_test() -> None:
                with patch.dict(os.environ, {"GEMINI_API_KEY": "primary", "GEMINI_API_KEY_FALLBACK": "primary", "GEMINI_API_KEYS": ""}, clear=False):
                    with patch.object(server.genai, "Client", side_effect=[primary_client, fallback_client]):
                        with self.assertRaises(server.HTTPException) as context:
                            await server._call_gemini([("a.jpg", "image/jpeg", b"abc")])
                self.assertEqual(context.exception.status_code, 429)
                self.assertIn("quota is currently unavailable", context.exception.detail)
                self.assertEqual(primary_client.models.generate_content.call_count, 1)
                self.assertEqual(fallback_client.models.generate_content.call_count, 0)

            import asyncio
            asyncio.run(run_test())
        finally:
            server.GEMINI_MODEL = original_primary
            server.GEMINI_FALLBACK_MODEL = original_fallback

    def test_quota_fallback_reaches_third_distinct_configured_credential(self) -> None:
        primary_client = MagicMock()
        second_client = MagicMock()
        third_client = MagicMock()
        for client in (primary_client, second_client):
            quota_error = Exception("429 RESOURCE_EXHAUSTED: quota exhausted")
            quota_error.code = 429
            client.models.generate_content.side_effect = quota_error
        third_response = MagicMock()
        third_response.text = '{"status": "ok", "result": {"summary": "third credential"}}'
        third_client.models.generate_content.return_value = third_response

        original_primary = server.GEMINI_MODEL
        original_fallback = server.GEMINI_FALLBACK_MODEL
        try:
            server.GEMINI_MODEL = "primary-model"
            server.GEMINI_FALLBACK_MODEL = "fallback-model"

            async def run_test() -> None:
                with patch.dict(os.environ, {
                    "GEMINI_API_KEY": "primary-key",
                    "GEMINI_API_KEY_FALLBACK": "second-key",
                    "GEMINI_API_KEYS": "third-key",
                }, clear=False):
                    with patch.object(server.genai, "Client", side_effect=[primary_client, second_client, third_client]) as client_factory:
                        payload = await server._call_gemini([("a.jpg", "image/jpeg", b"abc")])
                self.assertEqual(payload["result"]["summary"], "third credential")
                self.assertEqual(client_factory.call_count, 3)
                self.assertEqual(third_client.models.generate_content.call_args.kwargs["model"], "fallback-model")

            import asyncio
            asyncio.run(run_test())
        finally:
            server.GEMINI_MODEL = original_primary
            server.GEMINI_FALLBACK_MODEL = original_fallback

    def test_primary_and_fallback_fail_return_clean_503(self) -> None:
        client = MagicMock()

        def fail_generate_content(model: str, contents):
            error = Exception("503 Service Unavailable")
            error.code = 503
            raise error

        client.models.generate_content.side_effect = fail_generate_content

        original_fallback = server.GEMINI_FALLBACK_MODEL
        server.GEMINI_FALLBACK_MODEL = "fallback-model"
        async def run_test() -> None:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "primary", "GEMINI_API_KEY_FALLBACK": "", "GEMINI_API_KEYS": ""}, clear=False):
                with patch.object(server.genai, "Client", return_value=client):
                    with self.assertRaises(server.HTTPException) as context:
                        await server._call_gemini([("a.jpg", "image/jpeg", b"abc")])
            self.assertEqual(context.exception.status_code, 503)
            self.assertEqual(context.exception.detail, "AI analysis service is temporarily unavailable. Please try again.")
            self.assertEqual(client.models.generate_content.call_count, 2)

        import asyncio
        try:
            asyncio.run(run_test())
        finally:
            server.GEMINI_FALLBACK_MODEL = original_fallback


if __name__ == "__main__":
    unittest.main()
