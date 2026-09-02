import os
import unittest
from unittest.mock import MagicMock, patch

import server


class GeminiFallbackTests(unittest.TestCase):
    def test_quota_switches_to_configured_fallback_credential_once(self) -> None:
        primary_client = MagicMock()
        primary_error = Exception("429 Too Many Requests")
        primary_error.code = 429
        primary_client.models.generate_content.side_effect = primary_error

        fallback_client = MagicMock()
        fallback_response = MagicMock()
        fallback_response.text = '{"status": "ok", "result": {"summary": "fallback"}}'
        fallback_client.models.generate_content.return_value = fallback_response

        original_model = server.GEMINI_MODEL
        try:
            server.GEMINI_MODEL = "primary-model"
            with patch.dict(os.environ, {"GEMINI_API_KEY": "primary", "GEMINI_API_KEY_FALLBACK": "fallback"}, clear=False):
                async def run_test() -> None:
                    with patch.object(server.genai, "Client", side_effect=[primary_client, fallback_client]):
                        payload = await server._call_gemini([("a.jpg", "image/jpeg", b"abc")])
                    self.assertEqual(payload["result"]["summary"], "fallback")
                    self.assertEqual(primary_client.models.generate_content.call_count, 1)
                    self.assertEqual(fallback_client.models.generate_content.call_count, 1)
                    self.assertEqual(fallback_client.models.generate_content.call_args.kwargs["model"], "primary-model")

                import asyncio
                asyncio.run(run_test())
        finally:
            server.GEMINI_MODEL = original_model

    def test_transient_gemini_503_retries_three_times(self) -> None:
        original_primary = server.GEMINI_MODEL
        server.GEMINI_MODEL = "gemini-3.6-flash"

        try:
            client = MagicMock()

            def fake_generate_content(model: str, contents):
                if client.models.generate_content.call_count < 3:
                    error = Exception("503 Service Unavailable")
                    error.code = 503
                    raise error
                response = MagicMock()
                response.text = '{"status": "ok", "result": {"summary": "tested"}}'
                return response

            client.models.generate_content.side_effect = fake_generate_content

            async def run_test() -> None:
                with patch.object(server.genai, "Client", return_value=client):
                    with patch.object(server.asyncio, "sleep", return_value=None) as sleep:
                        payload = await server._call_gemini([("a.jpg", "image/jpeg", b"abc")])
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(client.models.generate_content.call_count, 3)
                self.assertEqual(sleep.call_args_list[0].args, (2,))
                self.assertEqual(sleep.call_args_list[1].args, (5,))
                self.assertTrue(all(call.kwargs["model"] == "gemini-3.6-flash" for call in client.models.generate_content.call_args_list))

            import asyncio
            asyncio.run(run_test())
        finally:
            server.GEMINI_MODEL = original_primary

    def test_three_failed_gemini_attempts_return_clean_503(self) -> None:
        client = MagicMock()

        def fail_generate_content(model: str, contents):
            error = Exception("503 Service Unavailable")
            error.code = 503
            raise error

        client.models.generate_content.side_effect = fail_generate_content

        async def run_test() -> None:
            with patch.object(server.genai, "Client", return_value=client):
                with patch.object(server.asyncio, "sleep", return_value=None):
                    with self.assertRaises(server.HTTPException) as context:
                        await server._call_gemini([("a.jpg", "image/jpeg", b"abc")])
            self.assertEqual(context.exception.status_code, 503)
            self.assertEqual(context.exception.detail, "AI analysis service is temporarily unavailable. Please try again.")
            self.assertEqual(client.models.generate_content.call_count, 3)

        import asyncio
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
