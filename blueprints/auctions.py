# Copyright 2025 SILICONDEV SPA
# Filename: blueprints/auctions.py
# Description: Auctions management Blueprint

from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, and_

from database import db
from models.auction import Auction, Bid
from models.property import Property
from models.user import User
from utils.decorators import admin_required

# Initialize Blueprint
auctions_bp = Blueprint('auctions', __name__, url_prefix='/auctions')


@auctions_bp.route('/')
@login_required
def index():
    """List auctions"""
    page = request.args.get('page', 1, type=int)
    per_page = 12

    # Filters
    status = request.args.get('status', '')
    auction_type = request.args.get('auction_type', '')
    search = request.args.get('search', '').strip()

    query = Auction.query.join(Property)

    # Apply filters based on user role
    if not current_user.is_admin:
        # Non-admin users see all public auctions and their own properties' auctions
        query = query.filter(
            or_(
                Property.agent_id == current_user.id,
                Auction.status.in_(['scheduled', 'active'])
            )
        )

    # Status filter
    if status:
        query = query.filter(Auction.status == status)

    # Auction type filter
    if auction_type:
        query = query.filter(Auction.auction_type == auction_type)

    # Search filter
    if search:
        query = query.filter(
            or_(
                Auction.title.contains(search),
                Auction.auction_number.contains(search),
                Property.title.contains(search),
                Property.city.contains(search)
            )
        )

    # Order by start date (upcoming first, then by creation date)
    query = query.order_by(Auction.start_date.desc(), Auction.created_at.desc())

    auctions = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    # Filter options
    statuses = [
        ('scheduled', 'Programmata'),
        ('active', 'In corso'),
        ('ended', 'Terminata'),
        ('cancelled', 'Annullata'),
        ('sold', 'Venduta'),
        ('unsold', 'Invenduta')
    ]

    auction_types = [
        ('synchronous', 'Sincrona'),
        ('asynchronous', 'Asincrona'),
        ('telematic', 'Telematica')
    ]

    return render_template('auctions/index.html',
                           auctions=auctions,
                           search=search,
                           filters={
                               'status': status,
                               'auction_type': auction_type
                           },
                           filter_options={
                               'statuses': statuses,
                               'auction_types': auction_types
                           })


@auctions_bp.route('/<int:auction_id>')
@login_required
def show(auction_id):
    """Show auction details"""
    auction = Auction.query.get_or_404(auction_id)

    # Check if user can view this auction
    if not current_user.is_admin and auction.property.agent_id != current_user.id:
        # Allow viewing if auction is public (scheduled or active)
        if auction.status not in ['scheduled', 'active']:
            flash('Non hai i permessi per visualizzare questa asta.', 'error')
            return redirect(url_for('auctions.index'))

    # Get recent bids
    recent_bids = auction.bids.order_by(Bid.created_at.desc()).limit(10).all()

    # Check if user can bid
    can_bid = auction.can_bid(current_user)

    return render_template('auctions/show.html',
                           auction=auction,
                           recent_bids=recent_bids,
                           can_bid=can_bid)


@auctions_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new auction"""
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        property_id = request.form.get('property_id', type=int)
        auction_type = request.form.get('auction_type', '').strip()
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        registration_deadline = request.form.get('registration_deadline')
        starting_price = request.form.get('starting_price', type=float)
        minimum_bid_increment = request.form.get('minimum_bid_increment', type=float)
        deposit_percentage = request.form.get('deposit_percentage', type=float)
        court = request.form.get('court', '').strip()
        procedure_number = request.form.get('procedure_number', '').strip()
        professional_delegate = request.form.get('professional_delegate', '').strip()
        special_conditions = request.form.get('special_conditions', '').strip()
        viewing_schedule = request.form.get('viewing_schedule', '').strip()
        requires_registration = request.form.get('requires_registration') == 'on'
        allows_remote_bidding = request.form.get('allows_remote_bidding') == 'on'

        # Validation
        errors = []

        if not title:
            errors.append('Titolo è richiesto.')

        if not property_id:
            errors.append('Immobile è richiesto.')

        # Check if property exists and user has permission
        property = Property.query.get(property_id)
        if not property:
            errors.append('Immobile non trovato.')
        elif not current_user.is_admin and property.agent_id != current_user.id:
            errors.append('Non hai i permessi per questo immobile.')

        if not auction_type:
            errors.append('Tipo asta è richiesto.')

        if not start_date:
            errors.append('Data inizio è richiesta.')
        else:
            try:
                start_date = datetime.fromisoformat(start_date.replace('T', ' '))
                if start_date <= datetime.utcnow():
                    errors.append('Data inizio deve essere futura.')
            except ValueError:
                errors.append('Formato data inizio non valido.')

        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date.replace('T', ' '))
                if end_date <= start_date:
                    errors.append('Data fine deve essere successiva alla data inizio.')
            except ValueError:
                errors.append('Formato data fine non valido.')

        if registration_deadline:
            try:
                registration_deadline = datetime.fromisoformat(registration_deadline.replace('T', ' '))
                if registration_deadline >= start_date:
                    errors.append('Scadenza registrazione deve essere prima dell\'inizio asta.')
            except ValueError:
                errors.append('Formato scadenza registrazione non valido.')

        if not starting_price or starting_price <= 0:
            errors.append('Prezzo di partenza deve essere maggiore di zero.')

        if not minimum_bid_increment or minimum_bid_increment <= 0:
            errors.append('Incremento minimo deve essere maggiore di zero.')

        if not deposit_percentage or deposit_percentage <= 0 or deposit_percentage > 100:
            errors.append('Percentuale cauzione deve essere tra 1 e 100.')

        if errors:
            for error in errors:
                flash(error, 'error')
            # Get properties for form
            if current_user.is_admin:
                properties = Property.query.filter_by(status='pre_auction').order_by(Property.title).all()
            else:
                properties = Property.query.filter_by(
                    agent_id=current_user.id,
                    status='pre_auction'
                ).order_by(Property.title).all()
            return render_template('auctions/create.html', properties=properties)

        # Generate auction number
        auction_number = f"AST{datetime.now().strftime('%Y%m%d')}{Auction.query.count() + 1:04d}"

        # Calculate deposit amount
        deposit_amount = starting_price * (deposit_percentage / 100)

        # Create auction
        try:
            auction = Auction(
                title=title,
                description=description,
                property_id=property_id,
                auction_number=auction_number,
                auction_type=auction_type,
                start_date=start_date,
                end_date=end_date,
                registration_deadline=registration_deadline,
                starting_price=starting_price,
                minimum_bid_increment=minimum_bid_increment,
                deposit_amount=deposit_amount,
                deposit_percentage=deposit_percentage,
                court=court,
                procedure_number=procedure_number,
                professional_delegate=professional_delegate,
                special_conditions=special_conditions,
                viewing_schedule=viewing_schedule,
                requires_registration=requires_registration,
                allows_remote_bidding=allows_remote_bidding
            )

            db.session.add(auction)

            # Update property status
            property.status = 'auction_scheduled'

            db.session.commit()

            flash(f'Asta "{auction.title}" creata con successo!', 'success')
            return redirect(url_for('auctions.show', auction_id=auction.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Errore nella creazione dell\'asta: {str(e)}', 'error')

    # Get available properties for auction
    if current_user.is_admin:
        properties = Property.query.filter_by(status='pre_auction').order_by(Property.title).all()
    else:
        properties = Property.query.filter_by(
            agent_id=current_user.id,
            status='pre_auction'
        ).order_by(Property.title).all()

    return render_template('auctions/create.html', properties=properties)


@auctions_bp.route('/<int:auction_id>/bid', methods=['POST'])
@login_required
def place_bid(auction_id):
    """Place a bid on auction"""
    auction = Auction.query.get_or_404(auction_id)

    # Check if user can bid
    if not auction.can_bid(current_user):
        return jsonify({
            'success': False,
            'message': 'Non puoi fare offerte su questa asta.'
        }), 400

    bid_amount = request.json.get('amount', type=float)

    if not bid_amount or bid_amount <= 0:
        return jsonify({
            'success': False,
            'message': 'Importo offerta non valido.'
        }), 400

    # Validate bid amount
    current_price = auction.current_price or auction.starting_price
    minimum_next_bid = current_price + auction.minimum_bid_increment

    if bid_amount < minimum_next_bid:
        return jsonify({
            'success': False,
            'message': f'Offerta minima: €{minimum_next_bid:,.2f}'
        }), 400

    try:
        # Create bid
        bid = Bid(
            auction_id=auction.id,
            bidder_id=current_user.id,
            amount=bid_amount
        )

        db.session.add(bid)

        # Update auction current price and reset winning bids
        Bid.query.filter_by(auction_id=auction.id, is_winning=True).update({'is_winning': False})
        bid.is_winning = True

        auction.update_current_price()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Offerta registrata con successo!',
            'new_price': float(bid_amount),
            'total_bids': auction.total_bids
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Errore nella registrazione dell\'offerta: {str(e)}'
        }), 500


@auctions_bp.route('/my-bids')
@login_required
def my_bids():
    """Show user's bids"""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    bids = Bid.query.filter_by(bidder_id=current_user.id) \
        .join(Auction) \
        .order_by(Bid.created_at.desc()) \
        .paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template('auctions/my_bids.html', bids=bids)


@auctions_bp.route('/active')
@login_required
def active():
    """Show active auctions"""
    active_auctions = Auction.query.filter_by(status='active') \
        .order_by(Auction.end_date.asc()) \
        .all()

    return render_template('auctions/active.html', auctions=active_auctions)


@auctions_bp.route('/<int:auction_id>/start', methods=['POST'])
@login_required
@admin_required
def start_auction(auction_id):
    """Start an auction (admin only)"""
    auction = Auction.query.get_or_404(auction_id)

    if auction.status != 'scheduled':
        flash('Solo le aste programmate possono essere avviate.', 'error')
        return redirect(url_for('auctions.show', auction_id=auction.id))

    try:
        auction.status = 'active'
        auction.property.status = 'in_auction'
        db.session.commit()

        flash(f'Asta "{auction.title}" avviata con successo!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Errore nell\'avvio dell\'asta: {str(e)}', 'error')

    return redirect(url_for('auctions.show', auction_id=auction.id))


@auctions_bp.route('/<int:auction_id>/end', methods=['POST'])
@login_required
@admin_required
def end_auction(auction_id):
    """End an auction (admin only)"""
    auction = Auction.query.get_or_404(auction_id)

    if auction.status != 'active':
        flash('Solo le aste attive possono essere terminate.', 'error')
        return redirect(url_for('auctions.show', auction_id=auction.id))

    try:
        winning_bid = auction.get_winning_bid()

        if winning_bid:
            auction.status = 'sold'
            auction.property.status = 'sold'
        else:
            auction.status = 'unsold'
            auction.property.status = 'unsold'

        db.session.commit()

        result = 'venduta' if winning_bid else 'non venduta'
        flash(f'Asta "{auction.title}" terminata - {result}.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Errore nella chiusura dell\'asta: {str(e)}', 'error')

    return redirect(url_for('auctions.show', auction_id=auction.id))


@auctions_bp.route('/<int:auction_id>/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_auction(auction_id):
    """Cancel an auction (admin only)"""
    auction = Auction.query.get_or_404(auction_id)

    if auction.status not in ['scheduled', 'active']:
        flash('Solo le aste programmate o attive possono essere annullate.', 'error')
        return redirect(url_for('auctions.show', auction_id=auction.id))

    try:
        auction.status = 'cancelled'
        auction.property.status = 'pre_auction'
        db.session.commit()

        flash(f'Asta "{auction.title}" annullata con successo!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Errore nell\'annullamento dell\'asta: {str(e)}', 'error')

    return redirect(url_for('auctions.show', auction_id=auction.id))


@auctions_bp.route('/api/<int:auction_id>/status')
@login_required
def api_auction_status(auction_id):
    """API endpoint for auction status (AJAX polling)"""
    auction = Auction.query.get_or_404(auction_id)

    return jsonify({
        'status': auction.status,
        'current_price': float(auction.current_price or auction.starting_price),
        'highest_bid': float(auction.highest_bid) if auction.highest_bid else None,
        'total_bids': auction.total_bids,
        'time_remaining': auction.time_remaining.total_seconds() if auction.time_remaining else None,
        'is_active': auction.is_active,
        'winning_bidder': auction.get_winning_bid().bidder.full_name if auction.get_winning_bid() else None
    })