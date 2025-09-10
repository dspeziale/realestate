from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///immobiliare.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Modelli del database
class Immobile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(200), nullable=False)
    descrizione = db.Column(db.Text)
    prezzo = db.Column(db.Float, nullable=False)
    superficie = db.Column(db.Integer, nullable=False)  # metri quadri
    locali = db.Column(db.Integer, nullable=False)
    bagni = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(50), nullable=False)  # appartamento, villa, ufficio
    contratto = db.Column(db.String(20), nullable=False)  # vendita, affitto
    citta = db.Column(db.String(100), nullable=False)
    indirizzo = db.Column(db.String(200))
    data_inserimento = db.Column(db.DateTime, default=datetime.utcnow)
    disponibile = db.Column(db.Boolean, default=True)


class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefono = db.Column(db.String(20))
    data_registrazione = db.Column(db.DateTime, default=datetime.utcnow)


class Richiesta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    immobile_id = db.Column(db.Integer, db.ForeignKey('immobile.id'), nullable=False)
    messaggio = db.Column(db.Text)
    data_richiesta = db.Column(db.DateTime, default=datetime.utcnow)
    stato = db.Column(db.String(20), default='in_attesa')  # in_attesa, processata, chiusa


# Form WTF
class ImmobileForm(FlaskForm):
    titolo = StringField('Titolo', validators=[DataRequired()])
    descrizione = TextAreaField('Descrizione')
    prezzo = FloatField('Prezzo (€)', validators=[DataRequired(), NumberRange(min=0)])
    superficie = IntegerField('Superficie (mq)', validators=[DataRequired(), NumberRange(min=1)])
    locali = IntegerField('Numero Locali', validators=[DataRequired(), NumberRange(min=1)])
    bagni = IntegerField('Numero Bagni', validators=[DataRequired(), NumberRange(min=1)])
    tipo = SelectField('Tipo', choices=[
        ('appartamento', 'Appartamento'),
        ('villa', 'Villa'),
        ('ufficio', 'Ufficio'),
        ('negozio', 'Negozio'),
        ('garage', 'Garage')
    ], validators=[DataRequired()])
    contratto = SelectField('Contratto', choices=[
        ('vendita', 'Vendita'),
        ('affitto', 'Affitto')
    ], validators=[DataRequired()])
    citta = StringField('Città', validators=[DataRequired()])
    indirizzo = StringField('Indirizzo')
    submit = SubmitField('Salva Immobile')


class ClienteForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired()])
    cognome = StringField('Cognome', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    telefono = StringField('Telefono')
    submit = SubmitField('Registra Cliente')


class RichiestaForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired()])
    cognome = StringField('Cognome', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    telefono = StringField('Telefono')
    messaggio = TextAreaField('Messaggio')
    submit = SubmitField('Invia Richiesta')


# Route principali
@app.route('/')
def index():
    # Ultimi immobili inseriti
    immobili_recenti = Immobile.query.filter_by(disponibile=True).order_by(
        Immobile.data_inserimento.desc()).limit(6).all()
    return render_template('index.html', immobili=immobili_recenti)


@app.route('/immobili')
def lista_immobili():
    page = request.args.get('page', 1, type=int)
    tipo = request.args.get('tipo', '')
    contratto = request.args.get('contratto', '')
    citta = request.args.get('citta', '')
    prezzo_min = request.args.get('prezzo_min', type=float)
    prezzo_max = request.args.get('prezzo_max', type=float)

    query = Immobile.query.filter_by(disponibile=True)

    if tipo:
        query = query.filter(Immobile.tipo == tipo)
    if contratto:
        query = query.filter(Immobile.contratto == contratto)
    if citta:
        query = query.filter(Immobile.citta.ilike(f'%{citta}%'))
    if prezzo_min:
        query = query.filter(Immobile.prezzo >= prezzo_min)
    if prezzo_max:
        query = query.filter(Immobile.prezzo <= prezzo_max)

    immobili = query.order_by(Immobile.data_inserimento.desc()).paginate(
        page=page, per_page=9, error_out=False)

    return render_template('immobili.html', immobili=immobili,
                           filtri={'tipo': tipo, 'contratto': contratto,
                                   'citta': citta, 'prezzo_min': prezzo_min,
                                   'prezzo_max': prezzo_max})


@app.route('/immobile/<int:id>')
def dettaglio_immobile(id):
    immobile = Immobile.query.get_or_404(id)
    form = RichiestaForm()
    return render_template('dettaglio_immobile.html', immobile=immobile, form=form)


@app.route('/richiesta/<int:immobile_id>', methods=['POST'])
def invia_richiesta(immobile_id):
    form = RichiestaForm()
    if form.validate_on_submit():
        # Cerca o crea il cliente
        cliente = Cliente.query.filter_by(email=form.email.data).first()
        if not cliente:
            cliente = Cliente(
                nome=form.nome.data,
                cognome=form.cognome.data,
                email=form.email.data,
                telefono=form.telefono.data
            )
            db.session.add(cliente)
            db.session.flush()

        # Crea la richiesta
        richiesta = Richiesta(
            cliente_id=cliente.id,
            immobile_id=immobile_id,
            messaggio=form.messaggio.data
        )
        db.session.add(richiesta)
        db.session.commit()

        flash('Richiesta inviata con successo! Ti contatteremo presto.', 'success')
        return redirect(url_for('dettaglio_immobile', id=immobile_id))

    immobile = Immobile.query.get_or_404(immobile_id)
    return render_template('dettaglio_immobile.html', immobile=immobile, form=form)


# Route amministrazione
@app.route('/admin')
def admin_dashboard():
    totale_immobili = Immobile.query.count()
    immobili_disponibili = Immobile.query.filter_by(disponibile=True).count()
    totale_clienti = Cliente.query.count()
    richieste_pending = Richiesta.query.filter_by(stato='in_attesa').count()

    stats = {
        'totale_immobili': totale_immobili,
        'immobili_disponibili': immobili_disponibili,
        'totale_clienti': totale_clienti,
        'richieste_pending': richieste_pending
    }

    return render_template('admin/dashboard.html', stats=stats)


@app.route('/admin/immobili')
def admin_immobili():
    immobili = Immobile.query.order_by(Immobile.data_inserimento.desc()).all()
    return render_template('admin/immobili.html', immobili=immobili)


@app.route('/admin/immobile/nuovo', methods=['GET', 'POST'])
def nuovo_immobile():
    form = ImmobileForm()
    if form.validate_on_submit():
        immobile = Immobile(
            titolo=form.titolo.data,
            descrizione=form.descrizione.data,
            prezzo=form.prezzo.data,
            superficie=form.superficie.data,
            locali=form.locali.data,
            bagni=form.bagni.data,
            tipo=form.tipo.data,
            contratto=form.contratto.data,
            citta=form.citta.data,
            indirizzo=form.indirizzo.data
        )
        db.session.add(immobile)
        db.session.commit()
        flash('Immobile aggiunto con successo!', 'success')
        return redirect(url_for('admin_immobili'))

    return render_template('admin/form_immobile.html', form=form, title='Nuovo Immobile')


@app.route('/admin/immobile/<int:id>/modifica', methods=['GET', 'POST'])
def modifica_immobile(id):
    immobile = Immobile.query.get_or_404(id)
    form = ImmobileForm(obj=immobile)

    if form.validate_on_submit():
        form.populate_obj(immobile)
        db.session.commit()
        flash('Immobile modificato con successo!', 'success')
        return redirect(url_for('admin_immobili'))

    return render_template('admin/form_immobile.html', form=form,
                           title='Modifica Immobile', immobile=immobile)


@app.route('/admin/immobile/<int:id>/elimina', methods=['POST'])
def elimina_immobile(id):
    immobile = Immobile.query.get_or_404(id)
    db.session.delete(immobile)
    db.session.commit()
    flash('Immobile eliminato con successo!', 'success')
    return redirect(url_for('admin_immobili'))


@app.route('/admin/clienti')
def admin_clienti():
    clienti = Cliente.query.order_by(Cliente.data_registrazione.desc()).all()
    return render_template('admin/clienti.html', clienti=clienti)


@app.route('/admin/richieste')
def admin_richieste():
    richieste = db.session.query(Richiesta, Cliente, Immobile).join(
        Cliente, Richiesta.cliente_id == Cliente.id).join(
        Immobile, Richiesta.immobile_id == Immobile.id).order_by(
        Richiesta.data_richiesta.desc()).all()

    return render_template('admin/richieste.html', richieste=richieste)


@app.route('/admin/richiesta/<int:id>/stato', methods=['POST'])
def cambia_stato_richiesta(id):
    richiesta = Richiesta.query.get_or_404(id)
    nuovo_stato = request.json.get('stato')
    if nuovo_stato in ['in_attesa', 'processata', 'chiusa']:
        richiesta.stato = nuovo_stato
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})


# API per ricerche AJAX
@app.route('/api/citta')
def api_citta():
    citta = db.session.query(Immobile.citta).filter_by(disponibile=True).distinct().all()
    return jsonify([c[0] for c in citta])


if __name__ == '__main__':
    # Inizializzazione database
    with app.app_context():
        db.create_all()

        # Dati di esempio (opzionale)
        if Immobile.query.count() == 0:
            immobili_esempio = [
                Immobile(
                    titolo="Appartamento Centro Storico",
                    descrizione="Bellissimo appartamento nel cuore della città",
                    prezzo=250000,
                    superficie=85,
                    locali=3,
                    bagni=2,
                    tipo="appartamento",
                    contratto="vendita",
                    citta="Milano",
                    indirizzo="Via Roma 15"
                ),
                Immobile(
                    titolo="Villa con Giardino",
                    descrizione="Elegante villa bifamiliare con ampio giardino",
                    prezzo=450000,
                    superficie=180,
                    locali=6,
                    bagni=3,
                    tipo="villa",
                    contratto="vendita",
                    citta="Roma",
                    indirizzo="Via dei Colli 8"
                ),
                Immobile(
                    titolo="Ufficio Zona Business",
                    descrizione="Moderno ufficio in zona commerciale",
                    prezzo=1200,
                    superficie=60,
                    locali=3,
                    bagni=1,
                    tipo="ufficio",
                    contratto="affitto",
                    citta="Milano",
                    indirizzo="Via Torino 45"
                )
            ]

            for immobile in immobili_esempio:
                db.session.add(immobile)
            db.session.commit()
            print("Dati di esempio creati!")

    app.run(debug=True)