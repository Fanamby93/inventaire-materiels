from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from io import StringIO, BytesIO
import csv
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'votre_cle_secrete_ici'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventaire.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)



# Modèles de base de données

class TypeMateriel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), unique=True, nullable=False)

class Materiel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    marque = db.Column(db.String(50), nullable=False)
    modele = db.Column(db.String(100)) # Champ non obligatoire
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

# Créer la base si elle n’existe pas
with app.app_context():
    db.create_all()

# Statistiques
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

@app.route('/')
def index():
    type_filtre = request.args.get('type')
    if type_filtre:
        materiels = Materiel.query.filter_by(type=type_filtre).order_by(Materiel.modele).all()
    else:
        materiels = Materiel.query.order_by(Materiel.type).all()
    
    types = [row[0] for row in db.session.query(Materiel.type).distinct().order_by(Materiel.type).all()]
    return render_template('index.html', materiels=materiels, stats=get_stats(), types=types, type_filtre=type_filtre)

@app.route('/ajouter', methods=['GET', 'POST'])
def ajouter():
    if request.method == 'POST':
        try:
            nouveau = Materiel(
                type=request.form.get('type'),  # .get() au lieu de [] pour éviter KeyError
            marque=request.form.get('marque', '').strip() or None,  # Convertit "" en None
            modele=request.form.get('modele', '').strip() or None,
                numero_serie=request.form.get('numero_serie').strip() or None,
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
    materiel = Materiel.query.get_or_404(id)
    if request.method == 'POST':
        try:
            matricule = request.form['matricule']
            nom_personne = request.form['nom_personne']
            service = request.form.get('service', '')
            commentaires = request.form.get('commentaires', '')
            attribue_a = f"{matricule} - {nom_personne}"
            if service:
                attribue_a += f" ({service})"

            materiel.statut = 'Attribué'
            materiel.attribue_a = attribue_a
            materiel.matricule = matricule
            materiel.service = service
            materiel.date_attribution = request.form.get('date_attribution', datetime.now().strftime("%Y-%m-%d"))
            materiel.commentaires = commentaires

            hist = Historique(
                materiel_id=materiel.id,
                action='Attribution',
                date_action=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                details=f"Attribué à {attribue_a}. Commentaire: {commentaires}",
                utilisateur="Admin"
            )
            db.session.add(hist)
            db.session.commit()
            flash('Matériel attribué avec succès!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de l\'attribution: {e}', 'danger')
    date_aujourdhui = datetime.now().strftime("%Y-%m-%d")
    return render_template('attribuer.html', materiel=materiel, date_aujourdhui=date_aujourdhui)

@app.route('/retourner/<int:id>')
def retourner(id):
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

@app.route('/supprimer/<int:id>')
def supprimer(id):
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
    if request.method == "POST":
        nom = request.form.get("nom")
        if nom:
            existant = TypeMateriel.query.filter_by(nom=nom).first()
            if not existant:
                nouveau_type = TypeMateriel(nom=nom)
                db.session.add(nouveau_type)
                db.session.commit()
        return redirect(url_for("ajouter_type"))

    types = TypeMateriel.query.order_by(TypeMateriel.nom).all()
    return render_template("ajouter_type.html", types=types)



@app.route('/historique/<int:id>')
def historique(id):
    materiel = Materiel.query.get_or_404(id)
    historiques = Historique.query.filter_by(materiel_id=id).order_by(Historique.date_action.desc()).all()
    return render_template('historique.html', materiel=materiel, historiques=historiques, datetime=datetime)

@app.route('/export_csv')
def export_csv():
    try:
        # Étape 1 : Préparation des données en mémoire texte
        output_text = StringIO()
        writer = csv.writer(output_text, delimiter=';')
        
        # En-tête avec noms de colonnes
        writer.writerow([
            'ID', 'Type', 'Marque', 'Modèle', 'Numéro de série', 'Statut',
            'Matricule', 'Attribué à', 'Service', 'Date attribution', 'Commentaires'
        ])
        
        # Données
        materiels = Materiel.query.all()
        for m in materiels:
            writer.writerow([
                m.id, m.type, m.marque, m.modele, m.numero_serie, m.statut,
                m.matricule or '',
                m.attribue_a or '',
                m.service or '',
                m.date_attribution or '',
                m.commentaires or ''
            ])
        
        # Étape 2 : Conversion en binaire avec BOM UTF-8
        output = BytesIO()
        output.write(b'\xef\xbb\xbf')  # BOM UTF-8 (équivalent de '\ufeff'.encode('utf-8'))
        output.write(output_text.getvalue().encode('utf-8'))
        output.seek(0)
        
        # Étape 3 : Envoi du fichier
        return send_file(
            output,
            mimetype='text/csv; charset=utf-8',
            as_attachment=True,
            download_name=f'inventaire_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
        )
        
    except Exception as e:
        flash(f"Erreur lors de l'export : {str(e)}", 'danger')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
