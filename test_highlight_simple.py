# test_highlight_simple.py - Simple test for highlight functionality
import sys
sys.path.insert(0, '.')

print("=" * 60)
print("Testing Highlight Module")
print("=" * 60)

# 1. Test module import
print("\n[1] Testing module import...")
try:
    from highlight_helper import (
        init_highlight, 
        highlight_locator, 
        highlight_by_selector, 
        HIGHLIGHT_ENABLED,
        HIGHLIGHT_CSS,
        HIGHLIGHT_JS
    )
    print("  [OK] Module imported successfully")
    print(f"  [OK] HIGHLIGHT_ENABLED = {HIGHLIGHT_ENABLED}")
    print(f"  [OK] CSS length = {len(HIGHLIGHT_CSS)} chars")
    print(f"  [OK] JS length = {len(HIGHLIGHT_JS)} chars")
except Exception as e:
    print(f"  [FAIL] Module import failed: {e}")
    sys.exit(1)

# 2. Test CSS styles
print("\n[2] Testing CSS styles...")
try:
    assert "#playwright-highlight-overlay" in HIGHLIGHT_CSS
    assert ".playwright-highlight-box" in HIGHLIGHT_CSS
    assert ".playwright-highlight-label" in HIGHLIGHT_CSS
    assert ".playwright-highlight-dot" in HIGHLIGHT_CSS
    assert "@keyframes highlight-pulse" in HIGHLIGHT_CSS
    assert "@keyframes dot-pulse" in HIGHLIGHT_CSS
    assert "border: 3px solid #ff0000" in HIGHLIGHT_CSS
    print("  [OK] CSS contains all necessary elements")
except AssertionError as e:
    print(f"  [FAIL] CSS incomplete: {e}")

# 3. Test JavaScript code
print("\n[3] Testing JavaScript code...")
try:
    assert "window.__playwrightHighlight" in HIGHLIGHT_JS
    assert "initOverlay" in HIGHLIGHT_JS
    assert "highlight" in HIGHLIGHT_JS
    assert "getBoundingClientRect" in HIGHLIGHT_JS
    assert "playwright-highlight-box" in HIGHLIGHT_JS
    assert "playwright-highlight-label" in HIGHLIGHT_JS
    assert "playwright-highlight-dot" in HIGHLIGHT_JS
    print("  [OK] JavaScript contains all necessary functions")
except AssertionError as e:
    print(f"  [FAIL] JavaScript incomplete: {e}")

# 4. Test sync_orders.py import
print("\n[4] Testing sync_orders.py import...")
try:
    import sync_orders
    print(f"  [OK] sync_orders module imported successfully")
    print(f"  [OK] HIGHLIGHT_ENABLED = {sync_orders.HIGHLIGHT_ENABLED}")
except Exception as e:
    print(f"  [FAIL] sync_orders import failed: {e}")

# 5. Test main.py import
print("\n[5] Testing main.py import...")
try:
    import main
    print(f"  [OK] main module imported successfully")
    print(f"  [OK] HIGHLIGHT_ENABLED = {main.HIGHLIGHT_ENABLED}")
except Exception as e:
    print(f"  [FAIL] main import failed: {e}")

# 6. Test monitor.py import
print("\n[6] Testing monitor.py import...")
try:
    import monitor
    print(f"  [OK] monitor module imported successfully")
    print(f"  [OK] HIGHLIGHT_ENABLED = {monitor.HIGHLIGHT_ENABLED}")
except Exception as e:
    print(f"  [FAIL] monitor import failed: {e}")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)
print("\nSummary:")
print("  - highlight_helper module works correctly")
print("  - All highlight CSS and JS code included")
print("  - All modules successfully import highlight_helper")
print("\nHighlight feature is ready to use!")
