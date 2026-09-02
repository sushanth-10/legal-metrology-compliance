import unittest

import server
from server import _build_supabase_storage_key, _slugify_storage_object_name


class SupabaseStoragePathTests(unittest.TestCase):
    def test_storage_key_uses_secure_user_and_scan_namespace(self) -> None:
        key = _build_supabase_storage_key("user-abc", "scan-123", "IMG_01.png")
        self.assertTrue(key.startswith("scan-images/user-abc/scan-123/"))
        self.assertTrue(key.endswith("IMG_01.png"))

    def test_storage_object_name_is_safe_and_unique(self) -> None:
        slug = _slugify_storage_object_name("IMG 01 (final).png")
        self.assertTrue(slug.endswith(".png"))
        self.assertNotIn(" ", slug)
        self.assertNotIn("(", slug)
        self.assertNotIn(")", slug)
        self.assertNotEqual(slug, "IMG 01 (final).png")

    def test_signed_urls_are_cached_for_repeated_lookups(self) -> None:
        storage_ref = "scan-images/user-abc/scan-123/IMG_01.png"
        calls = {"count": 0}

        class DummyStorage:
            def from_(self, _bucket_name):
                return self

            def create_signed_url(self, object_key, expires_in):
                calls["count"] += 1
                self.object_key = object_key
                self.expires_in = expires_in
                return type("Response", (), {"data": {"signedUrl": f"https://example.com/{object_key}?exp={expires_in}"}})()

        class DummyClient:
            storage = DummyStorage()

        original = server._supabase_storage_client
        try:
            server._supabase_storage_client = lambda: DummyClient()
            first = server._supabase_storage_signed_url(storage_ref)
            second = server._supabase_storage_signed_url(storage_ref)
        finally:
            server._supabase_storage_client = original

        self.assertEqual(first, second)
        self.assertEqual(calls["count"], 1)


if __name__ == "__main__":
    unittest.main()
