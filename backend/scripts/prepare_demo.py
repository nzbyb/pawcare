"""Prepare a separate, persistent SQLite demo database; never clear existing data."""
import os
from pathlib import Path
import secrets
import sys

BACKEND = Path(__file__).resolve().parents[1]
DEMO = BACKEND / 'demo-data'
DEMO.mkdir(exist_ok=True)
DATABASE = DEMO / 'pawcare.sqlite3'

os.environ['DATABASE_URL'] = f'sqlite:///{DATABASE.as_posix()}'
os.environ['JWT_SECRET_KEY'] = secrets.token_urlsafe(48)
os.environ['PAYMENT_PROVIDER'] = 'mock'
os.environ['PAYMENT_MOCK_BASE_URL'] = 'http://localhost:5174'
os.environ['PUBLIC_BASE_URL'] = 'http://127.0.0.1:8001'
os.environ['UPLOAD_DIR'] = str(DEMO / 'uploads')
os.environ['SCHEDULER_ENABLED'] = 'false'
os.environ['RAG_ENABLED'] = 'false'
os.environ['SMTP_HOST'] = ''
os.environ['SMTP_USER'] = ''
os.environ['SMTP_PASSWORD'] = ''
os.environ['LLM_API_KEY'] = ''
sys.path.insert(0, str(BACKEND))


def main():
    # seed.py is additive and keyed by username / kennel / seed-demo marker.
    # Existing demo activity is kept on restart. There is deliberately no reset flag.
    from seed import main as seed_main
    seed_main()
    from app.database import SessionLocal
    from review_business_data import review
    with SessionLocal() as db:
        result = review(db)
    print(f'Demo database: {DATABASE}')
    print(f"Data review: {result['orders_checked']} orders, {len(result['issues'])} issues")
    if result['issues']:
        print('Existing activity was preserved; inspect with review_business_data.py before presenting.')


if __name__ == '__main__':
    main()
