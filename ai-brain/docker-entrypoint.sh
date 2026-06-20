#!/bin/sh
set -eu

cd /app

if [ ! -f artifacts/bundle.pkl ] || [ ! -f artifacts/dur_model.pkl ] || [ ! -f artifacts/encoder.pkl ]; then
  CSV_PATH=""
  for candidate in /app/dataset/*.csv /app/src/dataset/*.csv; do
    if [ -f "$candidate" ]; then
      CSV_PATH="$candidate"
      break
    fi
  done

  if [ -z "$CSV_PATH" ]; then
    echo "No training CSV found in dataset/"
    exit 1
  fi

  echo "Artifacts missing. Training model bundle from $CSV_PATH"
  python src/train.py --csv "$CSV_PATH" --outdir artifacts
fi

echo "Initializing SQLite database..."
python src/seed_db.py

exec python app.py
