from datetime import datetime
from flask import Blueprint, render_template, request, redirect
from flask import url_for, flash, jsonify
from flask_login import login_required, current_user

from models.database import db, Subject, StudySession, Task

subjects = Blueprint('subjects', __name__, url_prefix='/subjects')


@subjects.route('/')
@login_required
def index():
    """List all subjects for the current user."""
    user_subjects = Subject.query.filter_by(
        user_id=current_user.id).order_by(Subject.priority.desc()).all()
    
    return render_template('subjects/index.html', subjects=user_subjects)


@subjects.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add a new subject."""
    if request.method == 'POST':
        name = request.form.get('name')
        workload = request.form.get('workload', type=int)
        priority = request.form.get('priority', type=int)
        difficulty = request.form.get('difficulty', type=int)
        color = request.form.get('color', '#3498db')
        notes = request.form.get('notes', '')
        
        # Parse exam date if provided
        exam_date_str = request.form.get('exam_date')
        exam_date = None
        if exam_date_str:
            try:
                exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d')
            except ValueError:
                flash('Invalid exam date format. Please use YYYY-MM-DD.', 'danger')
                return redirect(url_for('subjects.add'))
        
        # Validate required fields
        if not name:
            flash('Subject name is required.', 'danger')
            return redirect(url_for('subjects.add'))
        
        if not workload or workload < 1:
            flash('Workload must be at least 1 hour per week.', 'danger')
            return redirect(url_for('subjects.add'))
        
        if not priority or priority < 1 or priority > 5:
            flash('Priority must be between 1 and 5.', 'danger')
            return redirect(url_for('subjects.add'))
        
        # Create new subject
        new_subject = Subject(
            user_id=current_user.id,
            name=name,
            workload=workload,
            priority=priority,
            difficulty=difficulty,
            exam_date=exam_date,
            color=color,
            notes=notes
        )
        
        db.session.add(new_subject)
        db.session.commit()
        
        flash(f'Subject "{name}" added successfully!', 'success')
        return redirect(url_for('subjects.index'))
    
    return render_template('subjects/add.html')


@subjects.route('/edit/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def edit(subject_id):
    """Edit an existing subject."""
    subject = Subject.query.get_or_404(subject_id)
    
    # Security check: ensure the subject belongs to the current user
    if subject.user_id != current_user.id:
        flash('You do not have permission to edit this subject.', 'danger')
        return redirect(url_for('subjects.index'))
    
    if request.method == 'POST':
        subject.name = request.form.get('name')
        subject.workload = request.form.get('workload', type=int)
        subject.priority = request.form.get('priority', type=int)
        subject.difficulty = request.form.get('difficulty', type=int)
        subject.color = request.form.get('color', '#3498db')
        subject.notes = request.form.get('notes', '')
        
        # Parse exam date if provided
        exam_date_str = request.form.get('exam_date')
        if exam_date_str:
            try:
                subject.exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d')
            except ValueError:
                flash('Invalid exam date format. Please use YYYY-MM-DD.', 'danger')
                return redirect(url_for('subjects.edit', subject_id=subject.id))
        else:
            subject.exam_date = None
        
        # Validate required fields
        if not subject.name:
            flash('Subject name is required.', 'danger')
            return redirect(url_for('subjects.edit', subject_id=subject.id))
        
        if not subject.workload or subject.workload < 1:
            flash('Workload must be at least 1 hour per week.', 'danger')
            return redirect(url_for('subjects.edit', subject_id=subject.id))
        
        if not subject.priority or subject.priority < 1 or subject.priority > 5:
            flash('Priority must be between 1 and 5.', 'danger')
            return redirect(url_for('subjects.edit', subject_id=subject.id))
        
        db.session.commit()
        
        flash(f'Subject "{subject.name}" updated successfully!', 'success')
        return redirect(url_for('subjects.index'))
    
    return render_template('subjects/edit.html', subject=subject)


@subjects.route('/delete/<int:subject_id>', methods=['POST'])
@login_required
def delete(subject_id):
    """Delete a subject."""
    subject = Subject.query.get_or_404(subject_id)
    
    # Security check: ensure the subject belongs to the current user
    if subject.user_id != current_user.id:
        flash('You do not have permission to delete this subject.', 'danger')
        return redirect(url_for('subjects.index'))
    
    subject_name = subject.name
    
    # Delete all associated study sessions
    StudySession.query.filter_by(subject_id=subject_id).delete()
    
    # Delete all associated tasks
    Task.query.filter_by(subject_id=subject_id).delete()
    
    # Delete the subject
    db.session.delete(subject)
    db.session.commit()
    
    flash(f'Subject "{subject_name}" deleted successfully!', 'success')
    return redirect(url_for('subjects.index'))


@subjects.route('/tasks/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def tasks(subject_id):
    """View and manage tasks for a subject."""
    subject = Subject.query.get_or_404(subject_id)
    
    # Security check: ensure the subject belongs to the current user
    if subject.user_id != current_user.id:
        flash('You do not have permission to view this subject.', 'danger')
        return redirect(url_for('subjects.index'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description', '')
        deadline_str = request.form.get('deadline')
        estimated_time = request.form.get('estimated_time', type=int)
        priority = request.form.get('priority', type=int, default=3)
        
        # Validate required fields
        if not title:
            flash('Task title is required.', 'danger')
            return redirect(url_for('subjects.tasks', subject_id=subject.id))
        
        # Parse deadline if provided
        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
            except ValueError:
                flash('Invalid deadline format. Please use YYYY-MM-DD.', 'danger')
                return redirect(url_for('subjects.tasks', subject_id=subject.id))
        
        # Create new task
        task = Task(
            user_id=current_user.id,
            subject_id=subject.id,
            title=title,
            description=description,
            deadline=deadline,
            estimated_time=estimated_time,
            priority=priority
        )
        
        db.session.add(task)
        db.session.commit()
        
        flash('Task added successfully!', 'success')
        return redirect(url_for('subjects.tasks', subject_id=subject.id))
    
    # Get existing tasks for this subject
    tasks = Task.query.filter_by(
        user_id=current_user.id, 
        subject_id=subject.id
    ).order_by(Task.deadline, Task.priority.desc()).all()
    
    return render_template('subjects/tasks.html', subject=subject, tasks=tasks)


@subjects.route('/task/complete/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    """Mark a task as completed."""
    task = Task.query.get_or_404(task_id)
    
    # Security check: ensure the task belongs to the current user
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    task.completed = True
    db.session.commit()
    
    return jsonify({'success': True})


@subjects.route('/task/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    """Delete a task."""
    task = Task.query.get_or_404(task_id)
    
    # Security check: ensure the task belongs to the current user
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    subject_id = task.subject_id
    db.session.delete(task)
    db.session.commit()
    
    flash('Task deleted successfully!', 'success')
    return redirect(url_for('subjects.tasks', subject_id=subject_id)) 