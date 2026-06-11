from flask import Flask
from flask_cors import CORS

from .config import Config
from .extensions import db
from .routes import register_blueprints
from .seed import seed_data


def migrate_sqlite_columns():
    inspector = db.inspect(db.engine)
    existing_columns = {col["name"] for col in inspector.get_columns("appointments")}
    new_columns = [
        ("rule_allow_weekend", "BOOLEAN"),
        ("rule_max_daily_slots", "INTEGER"),
        ("rule_min_interval_days", "INTEGER"),
    ]
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            db.session.execute(
                db.text(f"ALTER TABLE appointments ADD COLUMN {col_name} {col_type}")
            )
    db.session.commit()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)

    with app.app_context():
        db.create_all()
        migrate_sqlite_columns()
        seed_data()

    register_blueprints(app)

    @app.get("/api/health")
    def health_check():
        return {"status": "ok", "service": "driving-exam-booking"}

    return app
