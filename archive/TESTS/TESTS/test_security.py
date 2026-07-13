import unittest
import sys

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.security import Encryption, TokenManager, KeyVault, SecretManager, SecurityAudit


class TestEncryption(unittest.TestCase):
    def setUp(self):
        self.key = b"0123456789abcdef0123456789abcdef"
        self.enc = Encryption(self.key)

    def test_encrypt_decrypt_roundtrip(self):
        original = "hello quantos"
        cipher = self.enc.encrypt(original)
        self.assertIsInstance(cipher, str)
        self.assertNotEqual(cipher, original)
        decrypted = self.enc.decrypt(cipher)
        self.assertEqual(decrypted, original)

    def test_encrypt_different_outputs(self):
        data = "same data"
        c1 = self.enc.encrypt(data)
        c2 = self.enc.encrypt(data)
        self.assertNotEqual(c1, c2)

    def test_decrypt_wrong_key_raises(self):
        original = "secret"
        cipher = self.enc.encrypt(original)
        other = Encryption(b"yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy")
        with self.assertRaises(Exception):
            other.decrypt(cipher)

    def test_rotate_key(self):
        new_key = b"ffffffffffffffffffffffffffffffff"
        self.enc.rotate_key(new_key)
        data = "after rotation"
        cipher = self.enc.encrypt(data)
        decrypted = self.enc.decrypt(cipher)
        self.assertEqual(decrypted, data)


class TestTokenManager(unittest.TestCase):
    def setUp(self):
        self.tm = TokenManager()

    def test_create_token_returns_string(self):
        token = self.tm.create("user1")
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 0)

    def test_validate_valid_token(self):
        token = self.tm.create("user1")
        self.assertTrue(self.tm.validate(token))

    def test_validate_invalid_token(self):
        self.assertFalse(self.tm.validate("invalid_token"))

    def test_revoke_removes_token(self):
        token = self.tm.create("user1")
        self.assertTrue(self.tm.validate(token))
        self.tm.revoke(token)
        self.assertFalse(self.tm.validate(token))

    def test_get_user_returns_user(self):
        token = self.tm.create("alice")
        self.assertEqual(self.tm.get_user(token), "alice")

    def test_get_user_none_for_unknown(self):
        self.assertIsNone(self.tm.get_user("unknown"))


class TestKeyVault(unittest.TestCase):
    def setUp(self):
        self.vault = KeyVault()

    def test_store_and_retrieve(self):
        self.vault.store("api_key", "sk-1234")
        self.assertEqual(self.vault.retrieve("api_key"), "sk-1234")

    def test_retrieve_unknown_returns_none(self):
        self.assertIsNone(self.vault.retrieve("unknown"))

    def test_delete_removes_key(self):
        self.vault.store("my_key", "my_value")
        self.vault.delete("my_key")
        self.assertIsNone(self.vault.retrieve("my_key"))

    def test_store_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.vault.store("", "value")


class TestSecretManager(unittest.TestCase):
    def setUp(self):
        self.sm = SecretManager()

    def test_set_and_get(self):
        self.sm.set("db_password", "p@ssw0rd")
        self.assertEqual(self.sm.get("db_password"), "p@ssw0rd")

    def test_get_unknown_returns_none(self):
        self.assertIsNone(self.sm.get("unknown"))

    def test_delete_removes_secret(self):
        self.sm.set("secret", "value")
        self.sm.delete("secret")
        self.assertIsNone(self.sm.get("secret"))

    def test_set_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.sm.set("", "value")


class TestSecurityAudit(unittest.TestCase):
    def setUp(self):
        self.audit = SecurityAudit()

    def test_log_events(self):
        self.audit.log("LOGIN", "User logged in")
        events = self.audit.get_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "LOGIN")
        self.assertEqual(events[0]["detail"], "User logged in")

    def test_log_multiple_events(self):
        self.audit.log("LOGIN", "first")
        self.audit.log("LOGOUT", "second")
        self.assertEqual(len(self.audit.get_events()), 2)

    def test_clear_removes_events(self):
        self.audit.log("TEST", "event")
        self.audit.clear()
        self.assertEqual(len(self.audit.get_events()), 0)

    def test_event_has_timestamp(self):
        self.audit.log("ACTION", "detail")
        self.assertIsNotNone(self.audit.get_events()[0].get("timestamp"))


if __name__ == "__main__":
    unittest.main()
