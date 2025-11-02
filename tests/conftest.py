import os
import sys

import pytest
from sqlalchemy.pool import StaticPool

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models.database import db, User, StudyPreference


@pytest.fixture()
def app():
    test_app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'poolclass': StaticPool,
            'connect_args': {'check_same_thread': False}
        },
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost'
    })

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def sample_user(app):
    """Create a user with preferences and return (user, password)."""
    with app.app_context():
        user = User(
            username='tester',
            email='tester@example.com',
            timezone='Asia/Shanghai',
            study_hours_per_week=14
        )
        user.set_password('password123')
        user.set_preferred_times({
            "morning": True,
            "afternoon": True,
            "evening": False,
            "night": False
        })
        db.session.add(user)
        db.session.flush()

        pref = StudyPreference(
            user_id=user.id,
            max_consecutive_hours=2,
            break_duration=10,
            preferred_session_length=60,
            weekend_study=True
        )
        db.session.add(pref)
        db.session.commit()

        return user.id, 'password123'

