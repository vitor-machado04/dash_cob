#!/usr/bin/env bash
set -euo pipefail

pkill -f "streamlit run .*app.py" || true
echo "Streamlit finalizado."
