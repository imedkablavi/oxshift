import unittest

from voxshift.realtime_preflight import choose_safe_blocksize_from_ratios


class RealtimePreflightDecisionTests(unittest.TestCase):
    def test_keeps_current_block_when_headroom_is_safe(self):
        self.assertEqual(
            choose_safe_blocksize_from_ratios(256, {256: 0.25, 512: 0.20}),
            256,
        )

    def test_moves_up_to_first_safe_block(self):
        self.assertEqual(
            choose_safe_blocksize_from_ratios(256, {256: 1.20, 512: 0.65, 1024: 0.30}),
            512,
        )

    def test_never_recommends_smaller_than_user_selection(self):
        self.assertEqual(
            choose_safe_blocksize_from_ratios(512, {128: 0.10, 256: 0.10, 512: 0.90, 1024: 0.40}),
            1024,
        )

    def test_returns_none_when_no_candidate_has_headroom(self):
        self.assertIsNone(
            choose_safe_blocksize_from_ratios(256, {256: 1.1, 512: 1.0, 1024: 0.95}),
        )


if __name__ == "__main__":
    unittest.main()
