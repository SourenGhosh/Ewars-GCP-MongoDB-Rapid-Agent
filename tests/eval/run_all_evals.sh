#!/bin/bash
set -e

echo "========================================"
echo " EWARS Phase 6 — Full Evaluation Suite"
echo "========================================"

echo ""; echo "Step 1: Lint..."
agents-cli lint
echo "PASS: Lint clean"

echo ""; echo "Step 2: Unit tests..."
pytest tests/unit/ -v --tb=short
echo "PASS: Unit tests"

echo ""; echo "Step 3: ADK eval — basic smoke..."
adk eval app/ tests/eval/evalsets/basic.evalset.json \
  --eval_config_file_path tests/eval/eval_config.json
echo "PASS"

echo ""; echo "Step 4: ADK eval — Week 1 WATCH..."
adk eval app/ tests/eval/evalsets/sars_week1_watch.evalset.json \
  --eval_config_file_path tests/eval/eval_config.json
echo "PASS"

echo ""; echo "Step 5: ADK eval — Week 4 ALERT..."
adk eval app/ tests/eval/evalsets/sars_week4_alert.evalset.json \
  --eval_config_file_path tests/eval/eval_config.json
echo "PASS"

echo ""; echo "Step 6: ADK eval — Week 8 EMERGENCY..."
adk eval app/ tests/eval/evalsets/sars_week8_emergency.evalset.json \
  --eval_config_file_path tests/eval/eval_config.json
echo "PASS"

echo ""; echo "Step 7: Integration tests..."
pytest tests/integration/ -v --tb=short
echo "PASS"

echo ""
echo "========================================"
echo " ALL EVALS PASSED — READY FOR DEMO"
echo "========================================"
