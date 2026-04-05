from app.db import engine, Base
import app.models  # important: loads all model classes into Base.metadata


def reset_database():
    print("⚠️  Resetting database...")
    print("Tables known to SQLAlchemy metadata:")
    print(list(Base.metadata.tables.keys()))

    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)

    print("Recreating tables from models...")
    Base.metadata.create_all(bind=engine)

    print("✅ Database reset complete.")


if __name__ == "__main__":
    confirm = input(
        "This will DROP ALL TABLES and recreate them. Type 'yes' to continue: "
    )

    if confirm.lower() != "yes":
        print("Aborted.")
        raise SystemExit(0)

    reset_database()
