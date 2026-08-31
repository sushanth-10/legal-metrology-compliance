import unittest

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


if __name__ == "__main__":
    unittest.main()
