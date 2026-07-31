#!/usr/bin/env python
"""
Test runner script for prefix-file-sort.
"""
import unittest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Discover and run tests
loader = unittest.TestLoader()
start_dir = 'tests'
suite = loader.discover(start_dir, pattern='test_*.py')

# Run tests
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

# Exit with error code if tests failed
sys.exit(0 if result.wasSuccessful() else 1)
