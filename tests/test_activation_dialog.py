"""Qt-level checks for the launch consent and activation gate."""

import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog

from core.activation import ActivationManager, _hash_key
from ui.activation_dialog import ActivationDialog


TEST_KEY = "ABCD-EF01-2345-6789-ABCD-EF01"


class TestActivationDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = ActivationManager(
            key_hashes=[_hash_key(TEST_KEY.replace("-", ""))],
            state_path=os.path.join(self.temp_dir.name, "activation.json"),
        )
        self.dialog = ActivationDialog(self.manager)

    def tearDown(self):
        self.dialog.close()
        self.temp_dir.cleanup()

    def test_terms_must_be_checked_before_key_can_activate(self):
        self.assertFalse(self.dialog.accept_terms.isChecked())
        self.assertFalse(self.dialog.activate_button.isEnabled())

        self.dialog.key_input.setText(TEST_KEY)
        self.assertFalse(self.dialog.activate_button.isEnabled())

        self.dialog.accept_terms.setChecked(True)
        self.assertTrue(self.dialog.activate_button.isEnabled())
        self.dialog.activate_button.click()

        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(self.manager.remaining_count, 0)

    def test_invalid_key_keeps_dialog_open(self):
        self.dialog.accept_terms.setChecked(True)
        self.dialog.key_input.setText("FFFF-FFFF-FFFF-FFFF-FFFF-FFFF")
        self.dialog.activate_button.click()

        self.assertEqual(self.dialog.result(), 0)
        self.assertFalse(self.dialog.error.isHidden())
        self.assertEqual(self.manager.remaining_count, 1)


if __name__ == "__main__":
    unittest.main()
