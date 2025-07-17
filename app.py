from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
from io import StringIO, BytesIO
import csv
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'votre_cle_secrete_ici'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventaire.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ------------------ MODELES ------------------

class TypeMateriel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), unique=True, nullable=False)

class Materiel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    marque = db.Column(db.String(50), nullable=False)
    modele = db.Column(db.String(100))
    numero_serie = db.Column(db.String(100), unique=True)
    date_acquisition = db.Column(db.String(20))
    statut = db.Column(db.String(20), default='En stock')
    attribue_a = db.Column(db.String(200))
    matricule = db.Column(db.String(50))
    service = db.Column(db.String(100))
    date_attribution = db.Column(db.String(20))
    commentaires = db.Column(db.Text)

class Historique(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    materiel_id = db.Column(db.Integer, db.ForeignKey('materiel.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    date_action = db.Column(db.String(20), nullable=False)
    details = db.Column(db.Text)
    utilisateur = db.Column(db.String(100))

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# ------------------ BASE ------------------
with app.app_context():
    db.create_all()

# ------------------ UTIL ------------------

def get_stats():
    return {
        'total': Materiel.query.count(),
        'en_stock': Materiel.query.filter_by(statut='En stock').count(),
        'attribue': Materiel.query.filter_by(statut='Attribué').count(),
        'laptops': Materiel.query.filter_by(type='Laptop').count(),
        'telephones': Materiel.query.filter_by(type='Téléphone').count(),
        'box': Materiel.query.filter_by(type='Box').count(),
        'sim': Materiel.query.filter_by(type='SIM Flotte').count()
    }

# ------------------ ROUTES ------------------

@app.route('/')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    type_filtre = request.args.get('type')
    materiels = Materiel.query.filter_by(type=type_filtre).order_by(Materiel.modele).all() if type_filtre else Materiel.query.order_by(Materiel.type).all()
    types = [row[0] for row in db.session.query(Materiel.type).distinct().order_by(Materiel.type).all()]
    return render_template('index.html', materiels=materiels, stats=get_stats(), types=types, type_filtre=type_filtre)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == '1234':
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('Identifiants invalides')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Déconnexion réussie", "success")
    return redirect(url_for('login'))

@app.route('/ajouter', methods=['GET', 'POST'])
def ajouter():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            nouveau = Materiel(
                type=request.form.get('type'),
                marque=request.form.get('marque', '').strip() or None,
                modele=request.form.get('modele', '').strip() or None,
                numero_serie=request.form.get('numero_serie', '').strip() or None,
                date_acquisition=request.form.get('date_acquisition', ''),
                commentaires=request.form.get('commentaires', '')
            )
            db.session.add(nouveau)
            db.session.flush()

            hist = Historique(
                materiel_id=nouveau.id,
                action='Ajout',
                date_action=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                details=f"{nouveau.type} {nouveau.modele} (SN: {nouveau.numero_serie}) ajouté",
                utilisateur="Admin"
            )
            db.session.add(hist)
            db.session.commit()
            flash('Matériel ajouté avec succès!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'danger')
    return render_template('ajouter.html')

@app.route('/attribuer/<int:id>', methods=['GET', 'POST'])
def attribuer(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    materiel = Materiel.query.get_or_404(id)
    if request.method == 'POST':
        try:
            attribue_a = f"{request.form['matricule']} - {request.form['nom_personne']}"
            if request.form.get('service'):
                attribue_a += f" ({request.form['service']})"

            materiel.statut = 'Attribué'
            materiel.attribue_a = attribue_a
            materiel.matricule = request.form['matricule']
            materiel.service = request.form.get('service', '')
            materiel.date_attribution = request.form.get('date_attribution', datetime.now().strftime("%Y-%m-%d"))
            materiel.commentaires = request.form.get('commentaires', '')

            hist = Historique(
                materiel_id=materiel.id,
                action='Attribution',
                date_action=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                details=f"Attribué à {attribue_a}. Commentaire: {materiel.commentaires}",
                utilisateur="Admin"
            )
            db.session.add(hist)
            db.session.commit()
            flash('Matériel attribué avec succès!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'danger')

    return render_template('attribuer.html', materiel=materiel, date_aujourdhui=datetime.now().strftime("%Y-%m-%d"))

@app.route('/retourner/<int:id>')
def retourner(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    materiel = Materiel.query.get_or_404(id)
    if materiel.statut == 'Attribué':
        try:
            hist = Historique(
                materiel_id=materiel.id,
                action='Retour',
                date_action=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                details=f"Retour par {materiel.attribue_a}",
                utilisateur="Admin"
            )
            db.session.add(hist)

            materiel.statut = 'En stock'
            materiel.attribue_a = None
            materiel.matricule = None
            materiel.service = None
            materiel.date_attribution = None

            db.session.commit()
            flash('Matériel retourné avec succès!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors du retour: {e}', 'danger')
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Nom d’utilisateur déjà utilisé', 'danger')
            return redirect(url_for('signup'))

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Compte créé avec succès ! Vous pouvez vous connecter.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/supprimer/<int:id>')
def supprimer(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    materiel = Materiel.query.get_or_404(id)
    try:
        Historique.query.filter_by(materiel_id=id).delete()
        db.session.delete(materiel)
        db.session.commit()
        flash('Matériel supprimé avec succès!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {e}', 'danger')
    return redirect(url_for('index'))

@app.route("/ajouter-type", methods=["GET", "POST"])
def ajouter_type():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":
        nom = request.form.get("nom")
        if nom:
            if not TypeMateriel.query.filter_by(nom=nom).first():
                db.session.add(TypeMateriel(nom=nom))
                db.session.commit()
                flash("Type ajouté", "success")
        return redirect(url_for("ajouter_type"))

    types = TypeMateriel.query.order_by(TypeMateriel.nom).all()
    return render_template("ajouter_type.html", types=types)

@app.route('/utilisateurs')
def utilisateurs():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    users = User.query.order_by(User.username).all()
    return render_template('utilisateurs.html', users=users)

@app.route('/supprimer_utilisateur/<int:id>', methods=['POST'])
def supprimer_utilisateur(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    user = User.query.get_or_404(id)

    try:
        db.session.delete(user)
        db.session.commit()
        flash(f"Utilisateur '{user.username}' supprimé avec succès.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression : {str(e)}", 'danger')

    return redirect(url_for('utilisateurs'))


@app.route('/historique/<int:id>')
def historique(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    materiel = Materiel.query.get_or_404(id)
    historiques = Historique.query.filter_by(materiel_id=id).order_by(Historique.date_action.desc()).all()
    return render_template('historique.html', materiel=materiel, historiques=historiques, datetime=datetime)

@app.route('/export_csv')
def export_csv():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    try:
        output_text = StringIO()
        writer = csv.writer(output_text, delimiter=';')
        writer.writerow(['ID', 'Type', 'Marque', 'Modèle', 'Numéro de série', 'Statut', 'Matricule', 'Attribué à', 'Service', 'Date attribution', 'Commentaires'])

        for m in Materiel.query.all():
            writer.writerow([
                m.id, m.type, m.marque, m.modele, m.numero_serie, m.statut,
                m.matricule or '', m.attribue_a or '', m.service or '',
                m.date_attribution or '', m.commentaires or ''
            ])

        output = BytesIO()
        output.write(b'\xef\xbb\xbf')
        output.write(output_text.getvalue().encode('utf-8'))
        output.seek(0)

        return send_file(
            output,
            mimetype='text/csv; charset=utf-8',
            as_attachment=True,
            download_name=f'inventaire_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
        )
    except Exception as e:
        flash(f"Erreur lors de l'export : {str(e)}", 'danger')
        return redirect(url_for('index'))

# ------------------ DEMARRAGE ------------------

if __name__ == '__main__':
    app.run(debug=True)