from app.db.session import SessionLocal
from app.db.seed import seed


def main():
    db = SessionLocal()

    seed(db)

    db.close()


if __name__ == "__main__":
    main()