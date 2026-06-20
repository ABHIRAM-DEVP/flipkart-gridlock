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

# Wait for PostgreSQL to be ready using Python
echo "Waiting for PostgreSQL to be ready..."
python -c "
import time
import psycopg
import os

host = os.getenv('POSTGRES_HOST', 'postgres')
port = int(os.getenv('POSTGRES_PORT', '5432'))
user = os.getenv('POSTGRES_USER', 'postgres')
password = os.getenv('POSTGRES_PASSWORD', 'data45Dada')
db = os.getenv('POSTGRES_DB', 'astram')

for i in range(30):
    try:
        conn = psycopg.connect(
            host=host, port=port, user=user, password=password, dbname=db
        )
        conn.close()
        print('PostgreSQL is ready!')
        break
    except Exception:
        if i < 29:
            print(f'PostgreSQL not ready yet, waiting... ({i+1}/30)')
            time.sleep(1)
        else:
            print('PostgreSQL failed to start after 30 seconds')
            exit(1)
"

echo "Initializing database..."
python src/seed_db.py

exec python app.py
