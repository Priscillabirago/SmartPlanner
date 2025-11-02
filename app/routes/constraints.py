from datetime import datetime, time
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models.database import db, UserConstraint, ClassBlock

constraints = Blueprint('constraints', __name__, url_prefix='/constraints')

PROFILE_ROUTE = 'auth.profile'
DASHBOARD_ROUTE = 'main.dashboard'
INDEX_ROUTE = 'constraints.index'

@constraints.route('/')
@login_required
def index():
    """View all constraints and class blocks."""
    user_constraints = UserConstraint.query.filter_by(
        user_id=current_user.id).order_by(UserConstraint.day_of_week, UserConstraint.start_time).all()
    
    class_blocks = ClassBlock.query.filter_by(
        user_id=current_user.id).order_by(ClassBlock.day_of_week, ClassBlock.start_time).all()
    
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    return render_template(
        'constraints/index.html',
        user_constraints=user_constraints,
        class_blocks=class_blocks,
        days=days
    )


@constraints.route('/constraint/add', methods=['POST'])
@login_required
def add_constraint():
    """Add a new user constraint (busy time)."""
    try:
        title = request.form.get('title')
        day_of_week = int(request.form.get('day_of_week'))
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        is_hard = request.form.get('is_hard') == 'true'
        
        # Validate inputs
        if not title:
            flash('Title is required.', 'danger')
            return redirect(url_for(INDEX_ROUTE))
        
        if day_of_week < 0 or day_of_week > 6:
            flash('Invalid day of week.', 'danger')
            return redirect(url_for(INDEX_ROUTE))
        
        # Parse times
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        
        if start_time >= end_time:
            flash('End time must be after start time.', 'danger')
            return redirect(url_for(INDEX_ROUTE))
        
        # Create constraint
        constraint = UserConstraint(
            user_id=current_user.id,
            title=title,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            is_hard=is_hard
        )
        
        db.session.add(constraint)
        db.session.commit()
        
        flash(f'Busy time "{title}" added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding busy time: {str(e)}', 'danger')
    
    return redirect(url_for(INDEX_ROUTE))


@constraints.route('/constraint/delete/<int:constraint_id>', methods=['POST'])
@login_required
def delete_constraint(constraint_id):
    """Delete a user constraint."""
    constraint = UserConstraint.query.get_or_404(constraint_id)
    
    # Security check
    if constraint.user_id != current_user.id:
        flash('You do not have permission to delete this constraint.', 'danger')
        return redirect(url_for(INDEX_ROUTE))
    
    title = constraint.title
    db.session.delete(constraint)
    db.session.commit()
    
    flash(f'Busy time "{title}" deleted successfully!', 'success')
    return redirect(url_for(INDEX_ROUTE))


@constraints.route('/class/add', methods=['POST'])
@login_required
def add_class():
    """Add a new class block."""
    try:
        title = request.form.get('title')
        day_of_week = int(request.form.get('day_of_week'))
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        location = request.form.get('location', '')
        color = request.form.get('color', '#6c757d')
        
        # Validate inputs
        if not title:
            flash('Class name is required.', 'danger')
            return redirect(url_for(INDEX_ROUTE))
        
        if day_of_week < 0 or day_of_week > 6:
            flash('Invalid day of week.', 'danger')
            return redirect(url_for(INDEX_ROUTE))
        
        # Parse times
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        
        if start_time >= end_time:
            flash('End time must be after start time.', 'danger')
            return redirect(url_for(INDEX_ROUTE))
        
        # Create class block
        class_block = ClassBlock(
            user_id=current_user.id,
            title=title,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            location=location,
            color=color
        )
        
        db.session.add(class_block)
        db.session.commit()
        
        flash(f'Class "{title}" added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding class: {str(e)}', 'danger')
    
    return redirect(url_for(INDEX_ROUTE))


@constraints.route('/class/delete/<int:class_id>', methods=['POST'])
@login_required
def delete_class(class_id):
    """Delete a class block."""
    class_block = ClassBlock.query.get_or_404(class_id)
    
    # Security check
    if class_block.user_id != current_user.id:
        flash('You do not have permission to delete this class.', 'danger')
        return redirect(url_for(INDEX_ROUTE))
    
    title = class_block.title
    db.session.delete(class_block)
    db.session.commit()
    
    flash(f'Class "{title}" deleted successfully!', 'success')
    return redirect(url_for(INDEX_ROUTE))

