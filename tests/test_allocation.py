"""
Unit tests for the hour allocation algorithm.

Tests the Largest Remainder (Hamilton) method to ensure:
- Allocated hours sum exactly to target
- Distribution is proportional to weights
- Caps are respected
- Edge cases are handled correctly
"""

import unittest
import sys
import os

# Add parent directory to path to import scheduler module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.scheduler import allocate_hours


class TestAllocateHours(unittest.TestCase):
    """Test suite for allocate_hours function."""
    
    def test_exact_sum_equal_weights(self):
        """Test that allocation sums exactly to total with equal weights."""
        weights = {1: 10, 2: 10, 3: 10}
        total_hours = 10
        
        result = allocate_hours(weights, total_hours)
        
        # Should sum to exactly 10
        self.assertEqual(sum(result.values()), 10)
        
        # With equal weights, expect distribution like [4, 3, 3] or [3, 4, 3]
        sorted_allocation = sorted(result.values(), reverse=True)
        self.assertEqual(sorted_allocation, [4, 3, 3])
    
    def test_exact_sum_unequal_weights(self):
        """Test allocation with unequal weights sums exactly."""
        weights = {1: 20, 2: 15, 3: 10}
        total_hours = 10
        
        result = allocate_hours(weights, total_hours)
        
        # Must sum to exactly 10
        self.assertEqual(sum(result.values()), 10)
        
        # Higher weight should get more hours
        self.assertGreater(result[1], result[3])
        self.assertGreater(result[2], result[3])
    
    def test_proportional_distribution(self):
        """Test that allocation is proportional to weights."""
        weights = {1: 50, 2: 30, 3: 20}  # 50%, 30%, 20%
        total_hours = 20
        
        result = allocate_hours(weights, total_hours)
        
        # Should sum to exactly 20
        self.assertEqual(sum(result.values()), 20)
        
        # Expected: 10, 6, 4 (exact proportions)
        self.assertEqual(result[1], 10)
        self.assertEqual(result[2], 6)
        self.assertEqual(result[3], 4)
    
    def test_with_caps(self):
        """Test that caps limit allocation correctly."""
        weights = {1: 10, 2: 10, 3: 10}
        total_hours = 10
        caps = {1: 2}  # Subject 1 capped at 2 hours
        
        result = allocate_hours(weights, total_hours, caps)
        
        # Subject 1 should not exceed cap
        self.assertLessEqual(result[1], 2)
        
        # Total may be less than 10 if caps prevent full allocation
        # This is intentional - we don't over-allocate beyond available work
        self.assertLessEqual(sum(result.values()), 10)
        
        # Other subjects should get the remaining hours
        self.assertGreaterEqual(result[2] + result[3], 8)
    
    def test_single_subject(self):
        """Test allocation with single subject."""
        weights = {1: 10}
        total_hours = 5
        
        result = allocate_hours(weights, total_hours)
        
        self.assertEqual(result[1], 5)
        self.assertEqual(sum(result.values()), 5)
    
    def test_zero_total_hours(self):
        """Test with zero total hours."""
        weights = {1: 10, 2: 10}
        total_hours = 0
        
        result = allocate_hours(weights, total_hours)
        
        # Should return empty or all zeros
        self.assertEqual(result, {})
    
    def test_empty_weights(self):
        """Test with empty weights dict."""
        weights = {}
        total_hours = 10
        
        result = allocate_hours(weights, total_hours)
        
        self.assertEqual(result, {})
    
    def test_zero_weights(self):
        """Test with all zero weights."""
        weights = {1: 0, 2: 0, 3: 0}
        total_hours = 9
        
        result = allocate_hours(weights, total_hours)
        
        # Should distribute equally when all weights are zero
        self.assertEqual(sum(result.values()), 9)
        # Each should get 3 hours (9 / 3)
        for hours in result.values():
            self.assertEqual(hours, 3)
    
    def test_large_numbers(self):
        """Test with larger numbers to ensure no overflow."""
        weights = {i: 100 * i for i in range(1, 11)}  # 10 subjects
        total_hours = 100
        
        result = allocate_hours(weights, total_hours)
        
        # Must sum exactly
        self.assertEqual(sum(result.values()), 100)
        
        # Higher IDs (higher weights) should get more hours
        self.assertGreater(result[10], result[1])
    
    def test_fractional_remainders(self):
        """Test case specifically designed to test remainder distribution."""
        # This should create fractional remainders that need distribution
        weights = {1: 7, 2: 7, 3: 7, 4: 7}
        total_hours = 10
        
        result = allocate_hours(weights, total_hours)
        
        # Should sum exactly
        self.assertEqual(sum(result.values()), 10)
        
        # Each subject should get either 2 or 3 hours
        # (7/28 * 10 = 2.5 each)
        for hours in result.values():
            self.assertIn(hours, [2, 3])
    
    def test_multiple_caps(self):
        """Test with multiple subjects capped."""
        weights = {1: 10, 2: 10, 3: 10, 4: 10}
        total_hours = 20
        caps = {1: 2, 2: 3}  # Cap subjects 1 and 2
        
        result = allocate_hours(weights, total_hours, caps)
        
        # Capped subjects should not exceed caps
        self.assertLessEqual(result[1], 2)
        self.assertLessEqual(result[2], 3)
        
        # Total may be less if caps limit work
        # Remaining hours go to uncapped subjects
        self.assertLessEqual(sum(result.values()), 20)
        
        # Uncapped subjects should get more hours
        self.assertGreater(result[3] + result[4], 10)
    
    def test_real_world_scenario(self):
        """Test realistic scenario with priorities and exam dates."""
        # Simulate: Math (priority 5, exam soon), History (priority 3), Science (priority 4)
        weights = {
            1: 10 + 5 + 10,  # Math: priority*2 + difficulty + exam_bonus = 25
            2: 6 + 3 + 0,    # History: 9
            3: 8 + 4 + 5     # Science: 17
        }
        total_hours = 15
        
        result = allocate_hours(weights, total_hours)
        
        # Should sum exactly
        self.assertEqual(sum(result.values()), 15)
        
        # Math should get most hours (highest weight)
        self.assertEqual(max(result.values()), result[1])
        
        # History should get least hours (lowest weight)
        self.assertEqual(min(result.values()), result[2])
    
    def test_no_negative_allocations(self):
        """Ensure no subject gets negative hours."""
        weights = {1: 5, 2: 10, 3: 1}
        total_hours = 8
        
        result = allocate_hours(weights, total_hours)
        
        # All allocations should be non-negative
        for hours in result.values():
            self.assertGreaterEqual(hours, 0)
    
    def test_consistency(self):
        """Test that same input gives same output (deterministic)."""
        weights = {1: 7, 2: 11, 3: 13}
        total_hours = 12
        
        result1 = allocate_hours(weights, total_hours)
        result2 = allocate_hours(weights, total_hours)
        
        # Should be identical
        self.assertEqual(result1, result2)


class TestAllocationEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def test_total_hours_equals_subjects(self):
        """Test when total hours equals number of subjects."""
        weights = {1: 10, 2: 20, 3: 30}
        total_hours = 3
        
        result = allocate_hours(weights, total_hours)
        
        self.assertEqual(sum(result.values()), 3)
    
    def test_total_hours_less_than_subjects(self):
        """Test when total hours is less than number of subjects."""
        weights = {1: 10, 2: 20, 3: 30, 4: 40}
        total_hours = 2
        
        result = allocate_hours(weights, total_hours)
        
        self.assertEqual(sum(result.values()), 2)
        
        # Highest weight subjects should get the hours
        self.assertGreater(result[4], 0)
        self.assertGreater(result[3], 0)
    
    def test_cap_less_than_fair_share(self):
        """Test cap that's less than what would be allocated."""
        weights = {1: 100, 2: 10}
        total_hours = 10
        caps = {1: 5}  # Cap at 5 even though it would get ~9
        
        result = allocate_hours(weights, total_hours, caps)
        
        self.assertLessEqual(result[1], 5)
        # Subject 2 should get remaining hours (at least 5)
        self.assertGreaterEqual(result[2], 5)
        # Total may be less than 10 if caps prevent full allocation
        self.assertLessEqual(sum(result.values()), 10)


if __name__ == '__main__':
    unittest.main()

