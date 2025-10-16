from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///agriturismo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Models
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(300))
    tagline = db.Column(db.Text)
    location = db.Column(db.String(200))
    surface_ha = db.Column(db.Float)
    apartments = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    investments = db.relationship('Investment', backref='project', lazy=True, cascade='all, delete-orphan')
    revenues = db.relationship('Revenue', backref='project', lazy=True, cascade='all, delete-orphan')
    costs = db.relationship('Cost', backref='project', lazy=True, cascade='all, delete-orphan')
    activities = db.relationship('Activity', backref='project', lazy=True, cascade='all, delete-orphan')


class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)


class Revenue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)


class Cost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    detail = db.Column(db.Text)
    amount = db.Column(db.Float, nullable=False)


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)


# Routes
@app.route('/')
def index():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('index.html', projects=projects)


@app.route('/project/new', methods=['GET', 'POST'])
def new_project():
    if request.method == 'POST':
        project = Project(
            name=request.form['name'],
            subtitle=request.form.get('subtitle', ''),
            tagline=request.form.get('tagline', ''),
            location=request.form.get('location', ''),
            surface_ha=float(request.form.get('surface_ha', 0)),
            apartments=int(request.form.get('apartments', 0))
        )
        db.session.add(project)
        db.session.commit()
        flash('Progetto creato con successo!', 'success')
        return redirect(url_for('edit_project', project_id=project.id))
    return render_template('new_project.html')


@app.route('/project/<int:project_id>/edit')
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    return render_template('edit_project.html', project=project)


@app.route('/project/<int:project_id>/update', methods=['POST'])
def update_project(project_id):
    project = Project.query.get_or_404(project_id)
    project.name = request.form['name']
    project.subtitle = request.form.get('subtitle', '')
    project.tagline = request.form.get('tagline', '')
    project.location = request.form.get('location', '')
    project.surface_ha = float(request.form.get('surface_ha', 0))
    project.apartments = int(request.form.get('apartments', 0))
    db.session.commit()
    flash('Progetto aggiornato!', 'success')
    return redirect(url_for('edit_project', project_id=project_id))


@app.route('/project/<int:project_id>/delete', methods=['POST'])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash('Progetto eliminato!', 'info')
    return redirect(url_for('index'))


@app.route('/project/<int:project_id>/investment/add', methods=['POST'])
def add_investment(project_id):
    investment = Investment(
        project_id=project_id,
        name=request.form['name'],
        amount=float(request.form['amount'])
    )
    db.session.add(investment)
    db.session.commit()
    flash('Investimento aggiunto!', 'success')
    return redirect(url_for('edit_project', project_id=project_id))


@app.route('/investment/<int:inv_id>/delete', methods=['POST'])
def delete_investment(inv_id):
    investment = Investment.query.get_or_404(inv_id)
    project_id = investment.project_id
    db.session.delete(investment)
    db.session.commit()
    flash('Investimento eliminato!', 'info')
    return redirect(url_for('edit_project', project_id=project_id))


@app.route('/project/<int:project_id>/revenue/add', methods=['POST'])
def add_revenue(project_id):
    revenue = Revenue(
        project_id=project_id,
        name=request.form['name'],
        amount=float(request.form['amount'])
    )
    db.session.add(revenue)
    db.session.commit()
    flash('Ricavo aggiunto!', 'success')
    return redirect(url_for('edit_project', project_id=project_id))


@app.route('/revenue/<int:rev_id>/delete', methods=['POST'])
def delete_revenue(rev_id):
    revenue = Revenue.query.get_or_404(rev_id)
    project_id = revenue.project_id
    db.session.delete(revenue)
    db.session.commit()
    flash('Ricavo eliminato!', 'info')
    return redirect(url_for('edit_project', project_id=project_id))


@app.route('/project/<int:project_id>/cost/add', methods=['POST'])
def add_cost(project_id):
    cost = Cost(
        project_id=project_id,
        category=request.form['category'],
        name=request.form['name'],
        detail=request.form.get('detail', ''),
        amount=float(request.form['amount'])
    )
    db.session.add(cost)
    db.session.commit()
    flash('Costo aggiunto!', 'success')
    return redirect(url_for('edit_project', project_id=project_id))


@app.route('/cost/<int:cost_id>/delete', methods=['POST'])
def delete_cost(cost_id):
    cost = Cost.query.get_or_404(cost_id)
    project_id = cost.project_id
    db.session.delete(cost)
    db.session.commit()
    flash('Costo eliminato!', 'info')
    return redirect(url_for('edit_project', project_id=project_id))


@app.route('/project/<int:project_id>/activity/add', methods=['POST'])
def add_activity(project_id):
    activity = Activity(
        project_id=project_id,
        category=request.form['category'],
        name=request.form['name'],
        description=request.form.get('description', '')
    )
    db.session.add(activity)
    db.session.commit()
    flash('Attività aggiunta!', 'success')
    return redirect(url_for('edit_project', project_id=project_id))


@app.route('/activity/<int:activity_id>/delete', methods=['POST'])
def delete_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    project_id = activity.project_id
    db.session.delete(activity)
    db.session.commit()
    flash('Attività eliminata!', 'info')
    return redirect(url_for('edit_project', project_id=project_id))


@app.route('/project/<int:project_id>/report')
def view_report(project_id):
    project = Project.query.get_or_404(project_id)

    # Calcoli
    total_investment = sum(inv.amount for inv in project.investments)
    total_revenue = sum(rev.amount for rev in project.revenues)

    costs_by_category = {}
    for cost in project.costs:
        if cost.category not in costs_by_category:
            costs_by_category[cost.category] = []
        costs_by_category[cost.category].append(cost)

    total_costs = sum(cost.amount for cost in project.costs)
    ebitda = total_revenue - total_costs
    ebitda_percent = (ebitda / total_revenue * 100) if total_revenue > 0 else 0

    activities_by_category = {}
    for activity in project.activities:
        if activity.category not in activities_by_category:
            activities_by_category[activity.category] = []
        activities_by_category[activity.category].append(activity)

    return render_template('report.html',
                           project=project,
                           total_investment=total_investment,
                           total_revenue=total_revenue,
                           costs_by_category=costs_by_category,
                           total_costs=total_costs,
                           ebitda=ebitda,
                           ebitda_percent=ebitda_percent,
                           activities_by_category=activities_by_category)


def init_db():
    """Initialize database with sample data"""
    with app.app_context():
        db.create_all()

        # Check if sample project exists
        if Project.query.first() is None:
            # Create Colle Benedetto project
            project = Project(
                name="COLLE BENEDETTO",
                subtitle="Agriturismo Multifunzionale di Eccellenza",
                tagline="Un'esperienza rigenerativa che unisce ospitalità premium, produzione a ciclo chiuso e tradizione enogastronomica del Lazio",
                location="Riano (RM) - 15 minuti dal GRA",
                surface_ha=21,
                apartments=12
            )
            db.session.add(project)
            db.session.flush()

            # Add investments
            investments_data = [
                ("Acquisto Proprietà", 900000),
                ("Ristrutturazione Appartamenti (12 unità)", 100000),
                ("Sistemazioni Agrosilvopastorali", 40000),
                ("Acquisto Bestiame e Attrezzature", 30000),
                ("Costi Amministrativi e Pratiche", 50000)
            ]
            for name, amount in investments_data:
                db.session.add(Investment(project_id=project.id, name=name, amount=amount))

            # Add revenues
            revenues_data = [
                ("Ospitalità (12 appartamenti)", 300000),
                ("Pascolo Razionale Bovini (20 capi)", 50000),
                ("Area Ricettiva Eventi/Ristorante", 80000),
                ("Coltivazione Specializzata", 30000),
                ("Vendita Diretta (Farm Shop)", 40000),
                ("Attività Didattiche e Ricreative", 35000)
            ]
            for name, amount in revenues_data:
                db.session.add(Revenue(project_id=project.id, name=name, amount=amount))

            # Add sample costs
            costs_data = [
                ("Personale", "Responsabile Aziendale/Imprenditore", "RAL + contributi", 45000),
                ("Personale", "Responsabile Ospitalità e Ristorazione", "RAL + contributi", 35000),
                ("Personale", "Addetto Produzione Agricola (n.2)", "RAL + contributi x2", 56000),
                ("Utilities", "Energia Elettrica", "60.000 kWh/anno", 18000),
                ("Utilities", "Acqua e Fognature", "8.000 m³/anno", 12000),
                ("Marketing", "Pubblicità Online", "Google Ads, Meta", 6000),
            ]
            for category, name, detail, amount in costs_data:
                db.session.add(Cost(project_id=project.id, category=category, name=name, detail=detail, amount=amount))

            db.session.commit()
            print("Database inizializzato con dati di esempio!")


if __name__ == '__main__':
    # Create instance directory if it doesn't exist
    os.makedirs('instance', exist_ok=True)
    init_db()
    app.run(debug=True)