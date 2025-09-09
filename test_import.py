#!/usr/bin/env python3
"""Simple test script to check if the integration can be imported."""

import sys
import os

# Add the integration to the path
integration_path = os.path.join(os.path.dirname(__file__), "custom_components", "nest_yale")
sys.path.insert(0, integration_path)

try:
    print("Testing basic imports...")
    
    # Test const import
    from const import DOMAIN
    print(f"✓ DOMAIN imported successfully: {DOMAIN}")
    
    # Test if we can import the config flow class
    import importlib
    config_flow_module = importlib.import_module('config_flow')
    print("✓ config_flow module imported successfully")
    
    print("✓ All basic imports successful!")
    
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
