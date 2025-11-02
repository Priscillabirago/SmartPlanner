from datetime import datetime, timedelta, timezone

from models.database import db, Subject, Task, StudySession, User
from models.scheduler import StudyScheduler


def _seed_schedule(user):
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    subject = Subject(
        user_id=user.id,
        name='Capstone',
        priority=4,
        difficulty=3,
        workload=5
    )
    db.session.add(subject)
    db.session.flush()

    Task(
        user_id=user.id,
        subject_id=subject.id,
        title='Final project',
        deadline=now,
        estimated_time=90,
        priority=5
    )
    db.session.commit()

    scheduler = StudyScheduler(
        user=user,
        subjects=[subject],
        start_date=now,
        end_date=now + timedelta(days=1)
    )
    schedule = scheduler.generate_schedule()
    scheduler.save_schedule_to_db(schedule, db)


def test_dashboard_and_calendar_render(app, client, sample_user):
    user_id, password = sample_user
    with app.app_context():
        user = User.query.get(user_id)
        _seed_schedule(user)
        email = user.email

    response = client.post('/login', data={
        'email': email,
        'password': password
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Today's Schedule" in response.data

    dashboard = client.get('/dashboard')
    assert dashboard.status_code == 200
    assert b'Capstone' in dashboard.data

    calendar = client.get('/calendar')
    assert calendar.status_code == 200
    assert b'Study Calendar' in calendar.data

