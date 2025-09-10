# Copyright 2025 SILICONDEV SPA
# Filename: blueprints/users.py
# Description: Users management Blueprint

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_

from database import db
from models.user import User
from utils.decorators import admin_required

# Initialize Blueprint
users_bp = Blueprint('users', __name__, url_prefix='/admin/users')

@users_bp.route('/')
@login_required
@admin_required
def index():
    """List all users"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Search functionality
    search = request.args.get('search', '').strip()
    
    query = User.query
    
    if search:
        query = query.filter(
            or_(
                User.first_name.contains(search),
                User.last_name.contains(search),
                User.email.contains(search),
                User.username.contains(search),
                User.company_name.contains(search)
            )
        )
    
    # Order by creation date (newest first)
    query = query.order_by(User.created_at.desc())
    
    users = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    return render_template('users/index.html', 
                         users=users, 
                         search=search)

@users_bp.route('/<int:user_id>')
@login_required
@admin_required
def show(user_id):
    """Show user details"""
    user = User.query.get_or_404(user_id)
    return render_template('users/show.html', user=user)

@users_bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(user_id):
    """Edit user"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        # Get form data
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        country = request.form.get('country', '').strip()
        company_name = request.form.get('company_name', '').strip()
        license_number = request.form.get('license_number', '').strip()
        vat_number = request.form.get('vat_number', '').strip()
        is_active = request.form.get('is_active') == 'on'
        is_verified = request.form.get('is_verified') == 'on'
        is_admin = request.form.get('is_admin') == 'on'
        
        # Validation
        errors = []
        
        if not first_name:
            errors.append('Nome è richiesto.')
        
        if not last_name:
            errors.append('Cognome è richiesto.')
        
        if not email:
            errors.append('Email è richiesta.')
        elif email != user.email and User.query.filter_by(email=email).first():
            errors.append('Email già utilizzata da un altro utente.')
        
        if username and username != user.username:
            if User.query.filter_by(username=username).first():
                errors.append('Username già utilizzato.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('users/edit.html', user=user)
        
        # Prevent admin from removing their own admin status
        if user.id == current_user.id and not is_admin:
            flash('Non puoi rimuovere i tuoi privilegi di amministratore.', 'warning')
            is_admin = True
        
        # Update user
        try:
            user.first_name = first_name
            user.last_name = last_name
            user.username = username or None
            user.email = email
            user.phone = phone or None
            user.address = address or None
            user.city = city or None
            user.postal_code = postal_code or None
            user.country = country or 'Italia'
            user.company_name = company_name or None
            user.license_number = license_number or None
            user.vat_number = vat_number or None
            user.is_active = is_active
            user.is_verified = is_verified
            user.is_admin = is_admin
            user.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash(f'Utente {user.full_name} aggiornato con successo!', 'success')
            return redirect(url_for('users.show', user_id=user.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Errore nell\'aggiornamento dell\'utente: {str(e)}', 'error')
    
    return render_template('users/edit.html', user=user)

@users_bp.route('/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_status(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deactivating themselves
    if user.id == current_user.id:
        flash('Non puoi disattivare il tuo stesso account.', 'warning')
        return redirect(url_for('users.show', user_id=user.id))
    
    try:
        user.is_active = not user.is_active
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        status = 'attivato' if user.is_active else 'disattivato'
        flash(f'Utente {user.full_name} {status} con successo!', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nel cambio stato utente: {str(e)}', 'error')
    
    return redirect(url_for('users.show', user_id=user.id))

@users_bp.route('/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(user_id):
    """Delete user"""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        flash('Non puoi eliminare il tuo stesso account.', 'warning')
        return redirect(url_for('users.show', user_id=user.id))
    
    try:
        user_name = user.full_name
        db.session.delete(user)
        db.session.commit()
        
        flash(f'Utente {user_name} eliminato con successo!', 'success')
        return redirect(url_for('users.index'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nell\'eliminazione dell\'utente: {str(e)}', 'error')
        return redirect(url_for('users.show', user_id=user.id))

@users_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    """Create new user"""
    if request.method == 'POST':
        # Get form data
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        country = request.form.get('country', '').strip()
        company_name = request.form.get('company_name', '').strip()
        license_number = request.form.get('license_number', '').strip()
        vat_number = request.form.get('vat_number', '').strip()
        is_active = request.form.get('is_active') == 'on'
        is_verified = request.form.get('is_verified') == 'on'
        is_admin = request.form.get('is_admin') == 'on'
        
        # Validation
        errors = []
        
        if not first_name:
            errors.append('Nome è richiesto.')
        
        if not last_name:
            errors.append('Cognome è richiesto.')
        
        if not email:
            errors.append('Email è richiesta.')
        elif User.query.filter_by(email=email).first():
            errors.append('Email già utilizzata.')
        
        if username and User.query.filter_by(username=username).first():
            errors.append('Username già utilizzato.')
        
        if not password:
            errors.append('Password è richiesta.')
        elif len(password) < 6:
            errors.append('Password deve essere almeno 6 caratteri.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('users/create.html')
        
        # Create user
        try:
            user = User(
                first_name=first_name,
                last_name=last_name,
                username=username or None,
                email=email,
                phone=phone or None,
                address=address or None,
                city=city or None,
                postal_code=postal_code or None,
                country=country or 'Italia',
                company_name=company_name or None,
                license_number=license_number or None,
                vat_number=vat_number or None,
                is_active=is_active,
                is_verified=is_verified,
                is_admin=is_admin
            )
            
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            flash(f'Utente {user.full_name} creato con successo!', 'success')
            return redirect(url_for('users.show', user_id=user.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Errore nella creazione dell\'utente: {str(e)}', 'error')
    
    return render_template('users/create.html')

@users_bp.route('/stats')
@login_required
@admin_required
def stats():
    """Show user statistics"""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    verified_users = User.query.filter_by(is_verified=True).count()
    admin_users = User.query.filter_by(is_admin=True).count()
    google_users = User.query.filter(User.google_id.isnot(None)).count()
    
    # Recent registrations (last 30 days)
    from datetime import timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_registrations = User.query.filter(User.created_at >= thirty_days_ago).count()
    
    # Users by month (last 12 months)
    from sqlalchemy import func, extract
    monthly_stats = db.session.query(
        extract('year', User.created_at).label('year'),
        extract('month', User.created_at).label('month'),
        func.count(User.id).label('count')
    ).filter(
        User.created_at >= datetime.utcnow() - timedelta(days=365)
    ).group_by(
        extract('year', User.created_at),
        extract('month', User.created_at)
    ).order_by('year', 'month').all()
    
    stats_data = {
        'total_users': total_users,
        'active_users': active_users,
        'verified_users': verified_users,
        'admin_users': admin_users,
        'google_users': google_users,
        'recent_registrations': recent_registrations,
        'monthly_stats': monthly_stats
    }
    
    return render_template('users/stats.html', stats=stats_data)

@users_bp.route('/export')
@login_required
@admin_required
def export():
    """Export users to CSV"""
    import csv
    from io import StringIO
    from flask import Response
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'Nome', 'Cognome', 'Email', 'Username', 'Telefono',
        'Azienda', 'Numero Albo', 'P.IVA', 'Attivo', 'Verificato', 
        'Admin', 'Data Registrazione', 'Ultimo Login'
    ])
    
    # Write data
    users = User.query.order_by(User.created_at.desc()).all()
    for user in users:
        writer.writerow([
            user.id,
            user.first_name,
            user.last_name,
            user.email,
            user.username or '',
            user.phone or '',
            user.company_name or '',
            user.license_number or '',
            user.vat_number or '',
            'Sì' if user.is_active else 'No',
            'Sì' if user.is_verified else 'No',
            'Sì' if user.is_admin else 'No',
            user.created_at.strftime('%d/%m/%Y %H:%M') if user.created_at else '',
            user.last_login.strftime('%d/%m/%Y %H:%M') if user.last_login else ''
        ])
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=utenti_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    )