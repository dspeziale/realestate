# Copyright 2025 SILICONDEV SPA
# Filename: blueprints/properties.py
# Description: Properties management Blueprint

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_

from database import db
from models.property import Property
from models.user import User
from utils.decorators import admin_required

# Initialize Blueprint
properties_bp = Blueprint('properties', __name__, url_prefix='/properties')

@properties_bp.route('/')
@login_required
def index():
    """List properties"""
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    # Search and filters
    search = request.args.get('search', '').strip()
    property_type = request.args.get('property_type', '')
    status = request.args.get('status', '')
    city = request.args.get('city', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    
    query = Property.query
    
    # Apply filters based on user role
    if not current_user.is_admin:
        # Non-admin users see only their properties and those in auction
        query = query.filter(
            or_(
                Property.agent_id == current_user.id,
                Property.status.in_(['auction_scheduled', 'in_auction'])
            )
        )
    
    # Search filter
    if search:
        query = query.filter(
            or_(
                Property.title.contains(search),
                Property.description.contains(search),
                Property.address.contains(search),
                Property.city.contains(search)
            )
        )
    
    # Property type filter
    if property_type:
        query = query.filter(Property.property_type == property_type)
    
    # Status filter
    if status:
        query = query.filter(Property.status == status)
    
    # City filter
    if city:
        query = query.filter(Property.city.contains(city))
    
    # Price range filter
    if min_price:
        query = query.filter(Property.base_price >= min_price)
    if max_price:
        query = query.filter(Property.base_price <= max_price)
    
    # Order by creation date (newest first)
    query = query.order_by(Property.created_at.desc())
    
    properties = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    # Get filter options
    property_types = db.session.query(Property.property_type.distinct()).all()
    property_types = [pt[0] for pt in property_types if pt[0]]
    
    cities = db.session.query(Property.city.distinct()).order_by(Property.city).all()
    cities = [city[0] for city in cities if city[0]]
    
    statuses = [
        ('pre_auction', 'Pre-Asta'),
        ('auction_scheduled', 'Asta Programmata'),
        ('in_auction', 'In Asta'),
        ('sold', 'Venduto'),
        ('unsold', 'Invenduto'),
        ('withdrawn', 'Ritirato')
    ]
    
    return render_template('properties/index.html', 
                         properties=properties,
                         search=search,
                         filters={
                             'property_type': property_type,
                             'status': status,
                             'city': city,
                             'min_price': min_price,
                             'max_price': max_price
                         },
                         filter_options={
                             'property_types': property_types,
                             'cities': cities,
                             'statuses': statuses
                         })

@properties_bp.route('/<int:property_id>')
@login_required
def show(property_id):
    """Show property details"""
    property = Property.query.get_or_404(property_id)
    
    # Check if user can view this property
    if not current_user.is_admin and property.agent_id != current_user.id:
        # Allow viewing if property is in auction
        if property.status not in ['auction_scheduled', 'in_auction']:
            flash('Non hai i permessi per visualizzare questo immobile.', 'error')
            return redirect(url_for('properties.index'))
    
    return render_template('properties/show.html', property=property)

@properties_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new property"""
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        property_type = request.form.get('property_type', '').strip()
        condition = request.form.get('condition', '').strip()
        surface_area = request.form.get('surface_area', type=float)
        rooms = request.form.get('rooms', type=int)
        bathrooms = request.form.get('bathrooms', type=int)
        floor = request.form.get('floor', '').strip()
        year_built = request.form.get('year_built', type=int)
        
        # Location
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        province = request.form.get('province', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        region = request.form.get('region', '').strip()
        
        # Financial
        base_price = request.form.get('base_price', type=float)
        estimated_value = request.form.get('estimated_value', type=float)
        minimum_bid = request.form.get('minimum_bid', type=float)
        cadastral_income = request.form.get('cadastral_income', type=float)
        
        # Legal
        cadastral_data = request.form.get('cadastral_data', '').strip()
        court = request.form.get('court', '').strip()
        procedure_number = request.form.get('procedure_number', '').strip()
        judge = request.form.get('judge', '').strip()
        
        # Features
        has_garage = request.form.get('has_garage') == 'on'
        has_garden = request.form.get('has_garden') == 'on'
        has_terrace = request.form.get('has_terrace') == 'on'
        has_elevator = request.form.get('has_elevator') == 'on'
        energy_class = request.form.get('energy_class', '').strip()
        
        # Status and conditions
        is_occupied = request.form.get('is_occupied') == 'on'
        has_debts = request.form.get('has_debts') == 'on'
        debt_amount = request.form.get('debt_amount', type=float) if has_debts else None
        
        # Agent (admin can assign to different user)
        agent_id = current_user.id
        if current_user.is_admin:
            agent_id = request.form.get('agent_id', type=int) or current_user.id
        
        # Validation
        errors = []
        
        if not title:
            errors.append('Titolo è richiesto.')
        
        if not property_type:
            errors.append('Tipo immobile è richiesto.')
        
        if not address:
            errors.append('Indirizzo è richiesto.')
        
        if not city:
            errors.append('Città è richiesta.')
        
        if not province:
            errors.append('Provincia è richiesta.')
        
        if not base_price or base_price <= 0:
            errors.append('Prezzo base deve essere maggiore di zero.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            # Get agents for form
            agents = User.query.filter_by(is_active=True).order_by(User.first_name, User.last_name).all()
            return render_template('properties/create.html', agents=agents)
        
        # Create property
        try:
            property = Property(
                title=title,
                description=description,
                property_type=property_type,
                condition=condition,
                surface_area=surface_area,
                rooms=rooms,
                bathrooms=bathrooms,
                floor=floor,
                year_built=year_built,
                address=address,
                city=city,
                province=province,
                postal_code=postal_code,
                region=region,
                base_price=base_price,
                estimated_value=estimated_value,
                minimum_bid=minimum_bid,
                cadastral_income=cadastral_income,
                cadastral_data=cadastral_data,
                court=court,
                procedure_number=procedure_number,
                judge=judge,
                has_garage=has_garage,
                has_garden=has_garden,
                has_terrace=has_terrace,
                has_elevator=has_elevator,
                energy_class=energy_class,
                is_occupied=is_occupied,
                has_debts=has_debts,
                debt_amount=debt_amount,
                agent_id=agent_id
            )
            
            db.session.add(property)
            db.session.commit()
            
            flash(f'Immobile "{property.title}" creato con successo!', 'success')
            return redirect(url_for('properties.show', property_id=property.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Errore nella creazione dell\'immobile: {str(e)}', 'error')
    
    # Get agents for form (admin only)
    agents = User.query.filter_by(is_active=True).order_by(User.first_name, User.last_name).all() if current_user.is_admin else []
    
    return render_template('properties/create.html', agents=agents)

@properties_bp.route('/<int:property_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(property_id):
    """Edit property"""
    property = Property.query.get_or_404(property_id)
    
    # Check permissions
    if not property.can_edit(current_user):
        flash('Non hai i permessi per modificare questo immobile.', 'error')
        return redirect(url_for('properties.show', property_id=property.id))
    
    if request.method == 'POST':
        # Similar form processing as create() but updating existing property
        # ... (form processing code similar to create)
        
        try:
            # Update all fields
            property.title = request.form.get('title', '').strip()
            property.description = request.form.get('description', '').strip()
            property.property_type = request.form.get('property_type', '').strip()
            # ... (update other fields)
            
            property.updated_at = datetime.utcnow()
            db.session.commit()
            
            flash(f'Immobile "{property.title}" aggiornato con successo!', 'success')
            return redirect(url_for('properties.show', property_id=property.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Errore nell\'aggiornamento dell\'immobile: {str(e)}', 'error')
    
    # Get agents for form (admin only)
    agents = User.query.filter_by(is_active=True).order_by(User.first_name, User.last_name).all() if current_user.is_admin else []
    
    return render_template('properties/edit.html', property=property, agents=agents)

@properties_bp.route('/<int:property_id>/delete', methods=['POST'])
@login_required
def delete(property_id):
    """Delete property"""
    property = Property.query.get_or_404(property_id)
    
    # Check permissions
    if not property.can_edit(current_user):
        flash('Non hai i permessi per eliminare questo immobile.', 'error')
        return redirect(url_for('properties.show', property_id=property.id))
    
    # Check if property has auctions
    if property.auctions.count() > 0:
        flash('Impossibile eliminare un immobile con aste associate.', 'error')
        return redirect(url_for('properties.show', property_id=property.id))
    
    try:
        property_title = property.title
        db.session.delete(property)
        db.session.commit()
        
        flash(f'Immobile "{property_title}" eliminato con successo!', 'success')
        return redirect(url_for('properties.index'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nell\'eliminazione dell\'immobile: {str(e)}', 'error')
        return redirect(url_for('properties.show', property_id=property.id))

@properties_bp.route('/api/search')
@login_required
def api_search():
    """API endpoint for property search (AJAX)"""
    search = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)
    
    if not search or len(search) < 2:
        return jsonify([])
    
    query = Property.query
    
    # Apply user restrictions
    if not current_user.is_admin:
        query = query.filter(
            or_(
                Property.agent_id == current_user.id,
                Property.status.in_(['auction_scheduled', 'in_auction'])
            )
        )
    
    # Search
    properties = query.filter(
        or_(
            Property.title.contains(search),
            Property.address.contains(search),
            Property.city.contains(search)
        )
    ).limit(limit).all()
    
    return jsonify([{
        'id': p.id,
        'title': p.title,
        'address': p.full_address,
        'price': float(p.base_price),
        'status': p.status_label
    } for p in properties])