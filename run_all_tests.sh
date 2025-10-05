#!/bin/bash
# Run all tests for the AI Token Manager

echo "════════════════════════════════════════════════════════════════════"
echo "🧪 AI Token Manager - Complete Test Suite"
echo "════════════════════════════════════════════════════════════════════"
echo ""

# Activate virtual environment
source venv/bin/activate

# Run unit tests
echo "1️⃣  Running Unit Tests..."
echo "───────────────────────────────────────────────────────────────────"
python test_token_manager.py
UNIT_RESULT=$?
echo ""

# Run smoke test
echo "2️⃣  Running Smoke Test..."
echo "───────────────────────────────────────────────────────────────────"
python smoke_test.py
SMOKE_RESULT=$?
echo ""

# Run enum fix test
echo "3️⃣  Running Enum Fix Test..."
echo "───────────────────────────────────────────────────────────────────"
python test_enum_fix.py
ENUM_RESULT=$?
echo ""

# Run diagnostics
echo "4️⃣  Running Diagnostic Test..."
echo "───────────────────────────────────────────────────────────────────"
python diagnose.py
DIAG_RESULT=$?
echo ""

# Summary
echo "════════════════════════════════════════════════════════════════════"
echo "📊 Test Suite Summary"
echo "════════════════════════════════════════════════════════════════════"

if [ $UNIT_RESULT -eq 0 ]; then
    echo "✅ Unit Tests: PASSED"
else
    echo "❌ Unit Tests: FAILED"
fi

if [ $SMOKE_RESULT -eq 0 ]; then
    echo "✅ Smoke Test: PASSED"
else
    echo "❌ Smoke Test: FAILED"
fi

if [ $ENUM_RESULT -eq 0 ]; then
    echo "✅ Enum Fix Test: PASSED"
else
    echo "❌ Enum Fix Test: FAILED"
fi

if [ $DIAG_RESULT -eq 0 ]; then
    echo "✅ Diagnostics: PASSED"
else
    echo "❌ Diagnostics: FAILED (warnings only)"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════"

# Overall result
if [ $UNIT_RESULT -eq 0 ] && [ $SMOKE_RESULT -eq 0 ] && [ $ENUM_RESULT -eq 0 ] && [ $DIAG_RESULT -eq 0 ]; then
    echo "✅ ALL TESTS PASSED - System is ready!"
    echo ""
    echo "🚀 To run the application:"
    echo "   streamlit run enhanced_multi_provider_manager.py"
    exit 0
else
    echo "⚠️  Some tests had issues - check output above"
    exit 1
fi
