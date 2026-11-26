"""Regression tests for the build preflight."""
import unittest
from types import SimpleNamespace

from v6.storage import GIB, RESERVE, require_space, stage_budgets


class StorageTests(unittest.TestCase):
    def test_reserve_at_exact_boundary(self):
        growth = 3 * GIB
        disk = lambda _: SimpleNamespace(free=RESERVE + growth)
        self.assertEqual(require_space(".", growth, disk), RESERVE + growth)

    def test_refuses_to_cross_reserve(self):
        growth = 3 * GIB
        disk = lambda _: SimpleNamespace(free=RESERVE + growth - 1)
        with self.assertRaisesRegex(ValueError, "Espaço insuficiente"):
            require_space(".", growth, disk)

    def test_budget_counts_retained_stage_outputs(self):
        source = 4 * GIB
        self.assertEqual(sum(stage_budgets(source).values()), 23 * GIB)


if __name__ == "__main__":
    unittest.main()
