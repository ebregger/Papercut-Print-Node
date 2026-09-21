"""Test script to verify double-sided printing functionality."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ipp_util import (
    SIDES_ONE_SIDED,
    SIDES_TWO_SIDED_LONG_EDGE,
    SIDES_TWO_SIDED_SHORT_EDGE,
    extract_sides_from_request,
    normalize_sides
)

# Test data for simulating IPP requests
class MockIPPRequest:
    def __init__(self, sides_value=None):
        self.sides_value = sides_value
    
    def lookup(self, section, attribute, tag):
        if attribute == b"sides" and self.sides_value:
            return [self.sides_value.encode('utf-8')]
        raise KeyError("Attribute not found")

def test_sides_normalization():
    """Test that sides values are properly normalized."""
    print("Testing sides normalization...")
    
    # Test valid values
    assert normalize_sides(SIDES_ONE_SIDED) == SIDES_ONE_SIDED
    assert normalize_sides(SIDES_TWO_SIDED_LONG_EDGE) == SIDES_TWO_SIDED_LONG_EDGE
    assert normalize_sides(SIDES_TWO_SIDED_SHORT_EDGE) == SIDES_TWO_SIDED_SHORT_EDGE
    
    # Test invalid values fallback to default
    assert normalize_sides("invalid-value") == SIDES_ONE_SIDED
    assert normalize_sides(None) == SIDES_ONE_SIDED
    
    print("✓ Sides normalization tests passed")

def test_extract_sides():
    """Test extracting sides from IPP requests."""
    print("Testing sides extraction...")
    
    # Test with one-sided
    request = MockIPPRequest(SIDES_ONE_SIDED)
    result = extract_sides_from_request(request)
    assert result == SIDES_ONE_SIDED
    print("✓ One-sided extraction works")
    
    # Test with two-sided long edge
    request = MockIPPRequest(SIDES_TWO_SIDED_LONG_EDGE)
    result = extract_sides_from_request(request)
    assert result == SIDES_TWO_SIDED_LONG_EDGE
    print("✓ Two-sided long edge extraction works")
    
    # Test with two-sided short edge
    request = MockIPPRequest(SIDES_TWO_SIDED_SHORT_EDGE)
    result = extract_sides_from_request(request)
    assert result == SIDES_TWO_SIDED_SHORT_EDGE
    print("✓ Two-sided short edge extraction works")
    
    # Test with invalid value fallback
    request = MockIPPRequest("invalid-value")
    result = extract_sides_from_request(request)
    assert result == SIDES_ONE_SIDED  # Should fallback to default
    print("✓ Invalid value fallback works")
    
    # Test with no value
    request = MockIPPRequest(None)
    result = extract_sides_from_request(request)
    assert result == SIDES_ONE_SIDED  # Should fallback to default
    print("✓ No value fallback works")
    
    print("✓ All sides extraction tests passed")

if __name__ == "__main__":
    test_sides_normalization()
    test_extract_sides()
    print("All tests passed! Double-sided printing support is working correctly.")
