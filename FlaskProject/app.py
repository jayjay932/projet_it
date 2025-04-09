from flask import Flask, render_template, redirect, url_for, request, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import requests  # Import pour effectuer des requêtes HTTP
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuration pour MySQL avec XAMPP
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/elearning'
app.config['SECRET_KEY'] = 'secret_key'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

YOUTUBE_API_KEY = 'AIzaSyDi7ofCdfO43n9gCeircDoQfBI2UgAdKjg'  # Remplacez par votre clé API YouTube

# Configuration pour le téléchargement de fichiers
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')  # Dossier pour stocker les fichiers téléchargés
ALLOWED_EXTENSIONS = {'pdf', 'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'webm'}  # Extensions autorisées
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)  # Crée le dossier s'il n'existe pas

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='apprenant')  # Rôle par défaut : apprenant

class Formation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    domain = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Enum('video', 'pdf'), nullable=False)
    link = db.Column(db.String(500), nullable=False)
    duree = db.Column(db.Integer, nullable=True)
    taille_raw = db.Column("taille", db.String(50), nullable=True)  # Stockage brut en base
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    @property
    def taille(self):
        """Convertit la taille brute en float si possible."""
        try:
            return float(self.taille_raw.replace('Mo', '').strip())
        except (ValueError, AttributeError):
            return None

    @taille.setter
    def taille(self, value):
        """Stocke la taille en tant que chaîne avec 'Mo'."""
        if isinstance(value, (float, int)):
            self.taille_raw = f"{value} Mo"
        else:
            self.taille_raw = value

class UserFormation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    formation_id = db.Column(db.Integer, db.ForeignKey('formation.id'), nullable=False)
    selected_at = db.Column(db.DateTime, default=db.func.current_timestamp())

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/index')
def index():
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        role = request.form.get('role', 'admin')  # Récupère le rôle ou utilise 'apprenant' par défaut
        user = User(name=name, email=email, password=password, role=role)
        db.session.add(user)
        db.session.commit()
        flash('Inscription réussie, connecte-toi !', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            # Redirection basée sur le rôle
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'apprenant':
                return redirect(url_for('dashboard'))  # Corrected URL
            else:
                flash('Rôle inconnu, contactez l\'administrateur.', 'danger')
                return redirect(url_for('login'))
        flash('Échec de la connexion, vérifie tes identifiants.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    formations = Formation.query.all()
    apprenants_count = User.query.filter_by(role='apprenant').count()  # Compte les apprenants
    return render_template('index.html', name=current_user.name, formations=formations, apprenants_count=apprenants_count)

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Accès refusé : Vous n\'êtes pas administrateur.', 'danger')
        return redirect(url_for('dashboard'))
    formations = Formation.query.all()  # Récupère toutes les formations
    return render_template('admin_dashboard.html', name=current_user.name, formations=formations)

@app.route('/admin/dashboard', methods=['GET'])
@login_required
def admin_dashboard_view():
    if current_user.role != 'admin':
        flash("Accès refusé : Vous n'êtes pas administrateur.", "danger")
        return redirect(url_for('dashboard'))

    # Récupérer les filtres
    domain_filter = request.args.get('domain', '').strip()
    type_filter = request.args.get('type', '').strip()

    # Filtrer les formations
    query = Formation.query
    if domain_filter:
        query = query.filter(Formation.domain == domain_filter)
    if type_filter:
        query = query.filter(Formation.type == type_filter)
    formations = query.all()

    # Passer les filtres actuels au modèle pour les conserver dans le formulaire
    return render_template(
        'admin_dashboard.html',
        formations=formations,
        selected_domain=domain_filter,
        selected_type=type_filter,
        name=current_user.name
    )

def extract_metadata(file_path, file_type):
    """
    Extrait les métadonnées du fichier.
    - Pour les vidéos : retourne la durée en minutes.
    - Pour les PDF : retourne la taille en Mo.
    """
    metadata = {"duration": None, "size": None}
    if file_type == "video":
        try:
            from moviepy.editor import VideoFileClip
            clip = VideoFileClip(file_path)
            metadata["duration"] = int(clip.duration // 60)  # Durée en minutes
            clip.close()
        except Exception as e:
            print(f"Erreur lors de l'extraction de la durée : {e}")
    elif file_type == "pdf":
        try:
            metadata["size"] = round(os.path.getsize(file_path) / (1024 * 1024), 2)  # Taille en Mo
        except Exception as e:
            print(f"Erreur lors de l'extraction de la taille : {e}")
    return metadata

@app.route('/admin/add_formation', methods=['POST'])
@login_required
def add_formation():
    if current_user.role != 'admin':
        flash("Accès refusé : Vous n'êtes pas administrateur.", "danger")
        return redirect(url_for('dashboard'))

    # Récupérer les données du formulaire
    domain = request.form.get('domain')
    file = request.files.get('file')  # Récupérer le fichier téléchargé
    link = request.form.get('link')  # Récupérer le lien si fourni manuellement

    # Vérifier si tous les champs nécessaires sont remplis
    if not domain or (not file and not link):
        flash("Tous les champs obligatoires doivent être remplis.", "danger")
        return redirect(url_for('add_formation_page'))

    # Si un fichier est téléchargé
    if file and allowed_file(file.filename):
        try:
            # Vérifier si le dossier 'uploads' existe, sinon le créer
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            # Sécuriser le nom du fichier et enregistrer le fichier
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)  # Chemin relatif
            file.save(file_path)

            # Vérifier si le fichier a bien été enregistré
            if not os.path.exists(file_path):
                flash("Erreur : le fichier n'a pas été enregistré.", "danger")
                return redirect(url_for('add_formation_page'))

            # Déterminer le type de fichier automatiquement
            file_extension = file.filename.rsplit('.', 1)[1].lower()
            file_type = "video" if file_extension in {'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'webm'} else "pdf"

            # Extraire les métadonnées
            metadata = extract_metadata(file_path, file_type)

            # Générer automatiquement le titre et la description
            title = os.path.splitext(filename)[0]  # Nom du fichier sans extension
            description = f"Formation ajoutée automatiquement pour le fichier {filename}."

            # Ajouter la formation avec le chemin du fichier
            new_formation = Formation(
                title=title,
                description=description,
                domain=domain,
                type=file_type,
                link=file_path,  # Enregistrer le chemin relatif du fichier
                duree=metadata["duration"] if file_type == "video" else None,
                taille=metadata["size"] if file_type == "pdf" else None
            )
            db.session.add(new_formation)
            db.session.commit()

            flash("Formation ajoutée avec succès.", "success")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            print(f"Erreur lors de l'enregistrement du fichier : {e}")
            flash("Erreur lors de l'enregistrement du fichier.", "danger")
            return redirect(url_for('add_formation_page'))

    # Si un lien est fourni manuellement
    elif link:
        # Déterminer le type de fichier à partir du champ "type"
        file_type = request.form.get('type')
        title = request.form.get('title', 'Formation sans titre')
        description = request.form.get('description', 'Description non fournie.')

        # Ajouter la formation avec le lien
        new_formation = Formation(
            title=title,
            description=description,
            domain=domain,
            type=file_type,
            link=link,  # Enregistrer le lien
            duree=None,  # La durée peut être calculée plus tard si nécessaire
            taille=None
        )
        db.session.add(new_formation)
        db.session.commit()

        flash("Formation ajoutée avec succès.", "success")
        return redirect(url_for('admin_dashboard'))

    flash("Erreur lors de l'ajout de la formation.", "danger")
    return redirect(url_for('add_formation_page'))

@app.route('/download/<int:formation_id>')
@login_required
def download_file(formation_id):
    formation = Formation.query.get_or_404(formation_id)
    if not os.path.exists(formation.link):
        flash("Le fichier demandé n'existe pas sur le serveur.", "danger")
        return redirect(url_for('dashboard'))
    return send_from_directory(directory=os.path.dirname(formation.link), 
                               path=os.path.basename(formation.link), 
                               as_attachment=True)

@app.route('/admin/add_formation_page', methods=['GET'])
@login_required
def add_formation_page():
    if current_user.role != 'admin':
        flash('Accès refusé : Vous n\'êtes pas administrateur.', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('add_formation.html')

@app.route('/formations/<string:domain>')
@login_required
def formations_by_domain(domain):
    # Récupérer les formations correspondant au domaine
    formations = Formation.query.filter_by(domain=domain).all()
    if not formations:
        flash(f"Aucune formation trouvée pour le domaine : {domain}", "warning")
        return redirect(url_for('dashboard'))
    return render_template('formations_by_domain.html', domain=domain, formations=formations)

@app.route('/formation/<int:formation_id>')
@login_required
def formation_detail(formation_id):
    formation = Formation.query.get_or_404(formation_id)
    return render_template('formation_details.html', formation=formation)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Déconnexion réussie.', 'info')
    return redirect(url_for('login'))

@app.route('/set_session')
def set_session():
    session['key'] = 'valeur'
    return 'Session définie !'

@app.route('/get_session')
def get_session():
    valeur = session.get('key', 'Aucune valeur définie')
    return f'Valeur de la session : {valeur}'

@app.route('/clear_session')
def clear_session():
    session.pop('key', None)
    return 'Session supprimée !'

@app.route('/cours', methods=['GET', 'POST'])
@login_required
def cours():
    domain = request.args.get('domain')  # Récupère le domaine depuis les paramètres de requête
    type_ = request.args.get('type')  # Récupère le type depuis les paramètres de requête

    # Si une formation est sélectionnée
    if request.method == 'POST':
        formation_id = request.form.get('formation_id')
        if formation_id:
            # Vérifier si la formation est déjà sélectionnée
            existing_selection = UserFormation.query.filter_by(user_id=current_user.id, formation_id=formation_id).first()
            if not existing_selection:
                new_selection = UserFormation(user_id=current_user.id, formation_id=formation_id)
                db.session.add(new_selection)
                db.session.commit()
                flash("Formation sélectionnée avec succès.", "success")
            else:
                flash("Vous avez déjà sélectionné cette formation.", "info")

    # Filtrer les formations selon le domaine et le type
    query = Formation.query
    if domain and domain.strip():  # Vérifie si le domaine est défini et non vide
        query = query.filter(Formation.domain.ilike(f"%{domain}%"))  # Utilise ilike pour une correspondance insensible à la casse
    if type_ and type_.strip():  # Vérifie si le type est défini et non vide
        query = query.filter(Formation.type == type_)

    # Exclure les formations PDF ou vidéo déjà sélectionnées par l'utilisateur
    selected_formation_ids = db.session.query(UserFormation.formation_id).filter_by(user_id=current_user.id).subquery()
    formations = query.filter(~Formation.id.in_(selected_formation_ids)).filter(Formation.type.in_(['pdf', 'video'])).all()

    return render_template('cours.html', name=current_user.name, formations=formations, selected_domain=domain, selected_type=type_)

def get_youtube_video_duration(video_url):
    try:
        # Extraire l'ID de la vidéo YouTube
        video_id = video_url.split('v=')[-1].split('&')[0]
        # URL de l'API YouTube Data
        api_url = f'https://www.googleapis.com/youtube/v3/videos?id={video_id}&part=contentDetails&key={YOUTUBE_API_KEY}'
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        # Extraire la durée au format ISO 8601
        duration_iso = data['items'][0]['contentDetails']['duration']
        # Convertir la durée en minutes
        duration_minutes = parse_iso8601_duration(duration_iso)
        return duration_minutes
    except Exception as e:
        print(f"Erreur lors de la récupération de la durée : {e}")
        return None

def parse_iso8601_duration(duration):
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    # Retourne une chaîne lisible
    return f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"

@app.route('/admin/update_youtube_video_duration', methods=['POST'])
@login_required
def update_youtube_video_duration():
    if current_user.role != 'admin':
        flash("Accès refusé : Vous n'êtes pas administrateur.", "danger")
        return redirect(url_for('dashboard'))

    formations = Formation.query.filter_by(type='video').all()
    for formation in formations:
        if 'youtube.com' in formation.link or 'youtu.be' in formation.link:
            duration = get_youtube_video_duration(formation.link)
            if duration is not None:
                formation.duree = duration
                db.session.commit()
            else:
                flash(f"Impossible de récupérer la durée pour la vidéo : {formation.title}", "warning")

    flash("Durée des vidéos YouTube mise à jour avec succès.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_formation/<int:formation_id>', methods=['GET', 'POST'])
@login_required
def edit_formation(formation_id):
    if current_user.role != 'admin':
        flash("Accès refusé : Vous n'êtes pas administrateur.", "danger")
        return redirect(url_for('dashboard'))

    formation = Formation.query.get_or_404(formation_id)

    if request.method == 'POST':
        formation.title = request.form.get('title')
        formation.description = request.form.get('description')
        formation.domain = request.form.get('domain')
        formation.type = request.form.get('type')
        db.session.commit()
        flash("Formation modifiée avec succès.", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_formation.html', formation=formation)

@app.route('/admin/delete_formation/<int:formation_id>', methods=['POST'])
@login_required
def delete_formation(formation_id):
    if current_user.role != 'admin':
        flash("Accès refusé : Vous n'êtes pas administrateur.", "danger")
        return redirect(url_for('dashboard'))

    formation = Formation.query.get_or_404(formation_id)
    try:
        # Supprimer le fichier associé si c'est un fichier local
        if os.path.exists(formation.link):
            os.remove(formation.link)
        db.session.delete(formation)
        db.session.commit()
        flash("Formation supprimée avec succès.", "success")
    except Exception as e:
        print(f"Erreur lors de la suppression : {e}")
        flash("Erreur lors de la suppression de la formation.", "danger")

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/users', methods=['GET'])
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash("Accès refusé : Vous n'êtes pas administrateur.", "danger")
        return redirect(url_for('dashboard'))

    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'admin':
        flash("Accès refusé : Vous n'êtes pas administrateur.", "danger")
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.name = request.form.get('name')
        user.email = request.form.get('email')
        user.role = request.form.get('role')
        db.session.commit()
        flash("Utilisateur modifié avec succès.", "success")
        return redirect(url_for('admin_users'))

    return render_template('edit_user.html', user=user)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        flash("Accès refusé : Vous n'êtes pas administrateur.", "danger")
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "danger")
        return redirect(url_for('admin_users'))

    db.session.delete(user)
    db.session.commit()
    flash("Utilisateur supprimé avec succès.", "success")
    return redirect(url_for('admin_users'))

@app.route('/admin/add_user_page', methods=['GET'])
@login_required
def add_user_page():
    if current_user.role != 'admin':
        flash("Accès refusé : Vous n'êtes pas administrateur.", "danger")
        return redirect(url_for('dashboard'))
    return render_template('add_user.html')

@app.route('/admin/add_user', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        flash("Accès refusé : Vous n'êtes pas administrateur.", "danger")
        return redirect(url_for('dashboard'))

    name = request.form.get('name')
    email = request.form.get('email')
    password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
    role = request.form.get('role')

    if not name or not email or not password or not role:
        flash("Tous les champs sont obligatoires.", "danger")
        return redirect(url_for('add_user_page'))

    if User.query.filter_by(email=email).first():
        flash("Un utilisateur avec cet email existe déjà.", "danger")
        return redirect(url_for('add_user_page'))

    new_user = User(name=name, email=email, password=password, role=role)
    db.session.add(new_user)
    db.session.commit()

    flash("Utilisateur ajouté avec succès.", "success")
    return redirect(url_for('admin_users'))

@app.route('/download_formation/<int:formation_id>')
@login_required
def download_formation(formation_id):
    formation = Formation.query.get_or_404(formation_id)
    # Vérifie si l'utilisateur est apprenant
    if current_user.role != 'apprenant':
        flash("Accès refusé : Vous n'êtes pas autorisé à télécharger cette formation.", "danger")
        return redirect(url_for('dashboard'))
    # Vérifie si le fichier existe
    if not os.path.exists(formation.link):
        flash("Le fichier demandé n'existe pas sur le serveur.", "danger")
        return redirect(url_for('dashboard'))
    return send_from_directory(directory=os.path.dirname(formation.link), 
                               path=os.path.basename(formation.link), 
                               as_attachment=True)

@app.route('/add_formation', methods=['GET', 'POST'])
@login_required
def apprenant_add_formation():  # Renommé pour éviter le conflit
    if current_user.role != 'apprenant':
        flash("Accès refusé : Seuls les apprenants peuvent ajouter des formations.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        domain = request.form.get('domain')
        link = request.form.get('link')
        file_type = request.form.get('type')

        if not title or not description or not domain or not link or not file_type:
            flash("Tous les champs sont obligatoires.", "danger")
            return redirect(url_for('apprenant_add_formation'))

        new_formation = Formation(
            title=title,
            description=description,
            domain=domain,
            type=file_type,
            link=link,
            user_id=current_user.id  # Associe la formation à l'utilisateur connecté
        )
        db.session.add(new_formation)
        db.session.commit()
        flash("Formation ajoutée avec succès.", "success")
        return redirect(url_for('mes_formations'))

    return render_template('add_formation_apprenant.html')

@app.route('/mes_formations')
@login_required
def mes_formations():
    if current_user.role != 'apprenant':
        flash("Accès refusé : Seuls les apprenants peuvent voir leurs formations.", "danger")
        return redirect(url_for('dashboard'))

    # Récupérer les formations sélectionnées par l'utilisateur
    selected_formations = db.session.query(Formation).join(UserFormation).filter(UserFormation.user_id == current_user.id).all()
    return render_template('mes_formations.html', formations=selected_formations)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/team')
def team():
    return render_template('team.html')

@app.route('/testimonial')
def testimonial():
    return render_template('testimonial.html')

@app.route('/not_found_page')
def not_found_page():
    return render_template('404.html'), 404

@app.route('/join')
def join():
    return render_template('join.html')  # Assurez-vous que le fichier `join.html` existe.

def parse_size_to_float(size_str):
    """
    Convertit une chaîne de taille (ex: '1.2 Mo') en float.
    Si la conversion échoue, retourne None.
    """
    try:
        return float(size_str.replace('Mo', '').strip())
    except ValueError:
        return None

@app.route('/select_formation/<int:formation_id>', methods=['POST'])
@login_required
def select_formation(formation_id):
    if current_user.role != 'apprenant':
        flash("Accès refusé : Seuls les apprenants peuvent sélectionner des formations.", "danger")
        return redirect(url_for('dashboard'))

    # Vérifier si la formation existe
    formation = Formation.query.get_or_404(formation_id)

    # Vérifier si la formation est déjà sélectionnée
    existing_selection = UserFormation.query.filter_by(user_id=current_user.id, formation_id=formation_id).first()
    if existing_selection:
        flash(f"Vous avez déjà sélectionné la formation : {formation.title}.", "info")
    else:
        # Ajouter la formation à la table `user_formation`
        new_selection = UserFormation(user_id=current_user.id, formation_id=formation_id)
        db.session.add(new_selection)
        db.session.commit()
        flash(f"Formation sélectionnée avec succès : {formation.title}.", "success")

    # Exemple d'utilisation de parse_size_to_float
    if formation.type == 'pdf' and formation.taille:
        formation.taille = parse_size_to_float(formation.taille)

    return redirect(url_for('mes_formations'))





from flask import request, jsonify


@app.route('/chat', methods=['POST'])
def chatbot():
    user_input = request.json.get("message", "").strip().lower()

    # Initialisation d'une session de type "arbre de décision"
    if 'chat_state' not in session:
        session['chat_state'] = 'initial'

    state = session['chat_state']

    # Point de départ : on propose deux options
    if state == 'initial':
        session['chat_state'] = 'waiting_choice'
        return jsonify({
            "response": "Bienvenue ! 👋\nSouhaitez-vous :<br>1️⃣ Rechercher une formation précise<br>2️⃣ Explorer par thématique ?<br>Répondez avec '1' ou '2'."
        })

    # L'utilisateur choisit entre recherche directe ou par thème
    if state == 'waiting_choice':
        if '1' in user_input:
            session['chat_state'] = 'ask_keyword'
            return jsonify({"response": "Parfait ✅. Quel mot-clé cherches-tu ?"})
        elif '2' in user_input:
            session['chat_state'] = 'theme_choice'
            # Liste des domaines/thèmes disponibles
            domains = Formation.query.with_entities(Formation.domain).distinct()
            domain_list = [d.domain for d in domains]
            themes = '<br>'.join(f"- {theme}" for theme in domain_list)
            return jsonify({"response": f"Voici les thématiques disponibles :<br>{themes}<br>Écris un thème pour continuer."})
        else:
            return jsonify({"response": "Merci de choisir : '1' pour une recherche ou '2' pour explorer par thème."})

    # Recherche par mot-clé
    if state == 'ask_keyword':
        keyword_like = f"%{user_input}%"
        results = Formation.query.filter(
            db.or_(
                Formation.title.ilike(keyword_like),
                Formation.description.ilike(keyword_like),
                Formation.domain.ilike(keyword_like)
            )
        ).limit(3).all()

        if not results:
            return jsonify({"response": "Aucune formation trouvée. Essaie un autre mot-clé."})

        suggestions = []
        for f in results:
            video_embed = ""
            if f.type == 'video' and 'youtube' in f.link:
                video_id = f.link.split('v=')[-1].split('&')[0]
                video_embed = f"""<iframe width='100%' height='200' src='https://www.youtube.com/embed/{video_id}' frameborder='0' allowfullscreen></iframe>"""

            suggestions.append(f"""
                <strong>{f.title}</strong><br>
                <em>{f.description}</em><br>
                {video_embed}<br>
                <a href='{f.link}' target='_blank'>Ouvrir la formation</a><br><hr>
            """)

        session['chat_state'] = 'initial'
        return jsonify({"response": ''.join(suggestions)})

    # Exploration par thème
    if state == 'theme_choice':
        domain_selected = user_input.title()
        session['selected_theme'] = domain_selected

        theme_formations = Formation.query.filter_by(domain=domain_selected).all()
        if not theme_formations:
            return jsonify({"response": "Ce thème n'existe pas. Merci d'en choisir un parmi la liste précédente."})

        session['chat_state'] = 'theme_followup'
        return jsonify({"response": f"Super choix ! 🌟 Que cherches-tu dans le thème **{domain_selected}** ? (ex: débutant, avancé, rapide, complet)"})

    if state == 'theme_followup':
        keyword = user_input
        domain_selected = session.get('selected_theme')

        formations = Formation.query.filter(
            Formation.domain == domain_selected,
            db.or_(
                Formation.title.ilike(f"%{keyword}%"),
                Formation.description.ilike(f"%{keyword}%")
            )
        ).limit(3).all()

        if not formations:
            return jsonify({"response": "Aucune formation ne correspond exactement. Essaie un autre mot-clé."})

        responses = []
        for f in formations:
            video_embed = ""
            if f.type == 'video' and 'youtube' in f.link:
                video_id = f.link.split('v=')[-1].split('&')[0]
                video_embed = f"""<iframe width='100%' height='200' src='https://www.youtube.com/embed/{video_id}' frameborder='0' allowfullscreen></iframe>"""

            responses.append(f"""
                <strong>{f.title}</strong><br>
                <em>{f.description}</em><br>
                {video_embed}<br>
                <a href='{f.link}' target='_blank'>Voir la formation</a><br><hr>
            """)

        session['chat_state'] = 'initial'
        return jsonify({"response": ''.join(responses)})

    return jsonify({"response": "Je suis désolé, je n'ai pas compris. Recommençons !"})






@app.route('/edit_user_apprenant/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user_apprenant(user_id):
    if current_user.id != user_id:
        flash("Accès refusé : Vous ne pouvez modifier que vos propres informations.", "danger")
        return redirect(url_for('dashboard'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.name = request.form.get('name')
        user.email = request.form.get('email')
        if request.form.get('password'):
            user.password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        db.session.commit()
        flash("Vos informations ont été mises à jour avec succès.", "success")
        return redirect(url_for('dashboard'))

    return render_template('edit_user_apprenant.html', user=user)

if __name__ == '__main__':
    app.run(debug=True)
