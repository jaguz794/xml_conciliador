import unittest

from backend.app.services.auth_service import hash_password, verify_password


class AuthServiceTests(unittest.TestCase):
    def test_hash_password_and_verify(self) -> None:
        password_hash, password_salt = hash_password("Segura123!")

        self.assertTrue(verify_password("Segura123!", password_hash, password_salt))
        self.assertFalse(verify_password("OtraClave123!", password_hash, password_salt))

    def test_rejects_short_passwords(self) -> None:
        with self.assertRaises(ValueError):
            hash_password("1234567")

    def test_allows_temporary_password_with_six_characters(self) -> None:
        password_hash, password_salt = hash_password("123456", allow_temporary_short_password=True)

        self.assertTrue(verify_password("123456", password_hash, password_salt))

    def test_rejects_temporary_passwords_shorter_than_six_characters(self) -> None:
        with self.assertRaises(ValueError):
            hash_password("12345", allow_temporary_short_password=True)


if __name__ == "__main__":
    unittest.main()
