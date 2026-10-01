"""Tests for per-launch terms/key activation and persistent one-use keys."""

import json
import os
import tempfile
import unittest

from core.activation import (
    ActivationManager,
    ActivationStateError,
    InvalidActivationKey,
    _hash_key,
)


TEST_KEY = "ABCD-EF01-2345-6789-ABCD-EF01"
TEST_KEY_HASH = _hash_key(TEST_KEY.replace("-", ""))


class TestActivationManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = os.path.join(self.temp_dir.name, "activation.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_manager(self):
        return ActivationManager(
            key_hashes=[TEST_KEY_HASH],
            state_path=self.state_path,
        )

    def test_key_is_reserved_then_consumed_once_on_close(self):
        manager = self.create_manager()
        self.assertEqual(manager.remaining_count, 1)

        manager.reserve_key(TEST_KEY.lower())
        self.assertEqual(manager.used_count, 0)
        self.assertEqual(manager.remaining_count, 0)
        self.assertTrue(manager.consume_active_key())
        self.assertEqual(manager.used_count, 1)
        self.assertFalse(manager.consume_active_key())

        reopened = self.create_manager()
        self.assertEqual(reopened.remaining_count, 0)
        with self.assertRaisesRegex(InvalidActivationKey, "đã được sử dụng"):
            reopened.reserve_key(TEST_KEY)

    def test_interrupted_session_consumes_stale_reservation_on_next_launch(self):
        first_launch = self.create_manager()
        first_launch.reserve_key(TEST_KEY)

        reopened = self.create_manager()
        self.assertEqual(reopened.used_count, 1)
        self.assertEqual(reopened.remaining_count, 0)
        with self.assertRaisesRegex(InvalidActivationKey, "đã được sử dụng"):
            reopened.reserve_key(TEST_KEY)

    def test_unknown_key_is_rejected_without_consuming_a_slot(self):
        manager = self.create_manager()
        with self.assertRaisesRegex(InvalidActivationKey, "không hợp lệ"):
            manager.reserve_key("FFFF-FFFF-FFFF-FFFF-FFFF-FFFF")
        self.assertEqual(manager.remaining_count, 1)
        self.assertFalse(os.path.exists(self.state_path))

    def test_malformed_state_fails_closed(self):
        with open(self.state_path, "w", encoding="utf-8") as state_file:
            json.dump({"version": 1, "used": ["not-a-hash"], "active": None}, state_file)

        with self.assertRaises(ActivationStateError):
            self.create_manager()

    @unittest.skipIf(os.name == "nt", "POSIX file permission check")
    def test_state_file_is_private_to_current_user(self):
        manager = self.create_manager()
        manager.reserve_key(TEST_KEY)
        self.assertEqual(os.stat(self.state_path).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
