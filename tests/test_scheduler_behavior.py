from datetime import datetime, timedelta, timezone

from models.database import db, Subject, Task, StudySession, User
from models.scheduler import StudyScheduler


def _create_subject(user, name, priority=3, difficulty=3, workload=4):
    subject = Subject(
        user_id=user.id,
        name=name,
        priority=priority,
        difficulty=difficulty,
        workload=workload,
        color="#3498db"
    )
    db.session.add(subject)
    db.session.flush()
    return subject


def _create_task(user, subject, title, deadline, estimated_minutes, priority=5):
    task = Task(
        user_id=user.id,
        subject_id=subject.id,
        title=title,
        deadline=deadline,
        estimated_time=estimated_minutes,
        priority=priority,
        completed=False
    )
    db.session.add(task)
    db.session.flush()
    return task


def test_deadline_tasks_take_priority(app, sample_user):
    user_id, _ = sample_user
    with app.app_context():
        user = User.query.get(user_id)
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        urgent_subject = _create_subject(user, 'Capstone', priority=2)
        regular_subject = _create_subject(user, 'History', priority=5)

        urgent_task = _create_task(
            user,
            urgent_subject,
            'Urgent project',
            deadline=now,
            estimated_minutes=120,
            priority=5
        )
        _create_task(
            user,
            regular_subject,
            'Reading',
            deadline=now + timedelta(days=3),
            estimated_minutes=60,
            priority=2
        )

        db.session.commit()

        scheduler = StudyScheduler(
            user=user,
            subjects=[urgent_subject, regular_subject],
            start_date=now,
            end_date=now + timedelta(days=1)
        )

        schedule = scheduler.generate_schedule()

        assert schedule, "Scheduler should create sessions"
        first_session_subject = schedule[0]['subject_id']
        assert first_session_subject == urgent_subject.id, (
            "First session should target the subject with the due-today task"
        )

        scheduler.save_schedule_to_db(schedule, db)
        linked_sessions = StudySession.query.filter_by(
            user_id=user.id,
            subject_id=urgent_subject.id,
            task_id=urgent_task.id
        ).count()
        assert linked_sessions > 0, "Urgent task should be linked to generated sessions"


def test_insufficient_hours_warns_user(app, sample_user):
    user_id, _ = sample_user
    with app.app_context():
        user = User.query.get(user_id)
        user.study_hours_per_week = 3  # ~0.4 hours/day
        db.session.commit()

        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        urgent_subject = _create_subject(user, 'Math', priority=3)

        _create_task(
            user,
            urgent_subject,
            'Exam prep',
            deadline=now,
            estimated_minutes=240,  # four hours, more than available today
            priority=5
        )
        db.session.commit()

        scheduler = StudyScheduler(
            user=user,
            subjects=[urgent_subject],
            start_date=now,
            end_date=now + timedelta(days=1)
        )

        check = scheduler.check_urgent_task_coverage()
        assert check['warnings'], "Expected an insufficient-hours warning"
        assert check['warnings'][0]['type'] == 'insufficient_hours'

