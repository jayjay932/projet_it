# Corrigeons les erreurs de syntaxe et de logique dans le code Flask pour une application fonctionnelle


from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import requests
import re

app = Flask(__name__)

# Configuration MySQL (via XAMPP par exemple)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/elearning'
app.config['SECRET_KEY'] = 'secret_key'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

YOUTUBE_API_KEY = 'AIzaSyCZLcohByyczj9MjtT0YBeI5HobTytnxlI'

def get_video_duration(video_id):
    url = f"https://www.googleapis.com/youtube/v3/videos?id={video_id}&part=contentDetails&key={YOUTUBE_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if "items" in data and len(data["items"]) > 0:
            duration = data["items"][0]["contentDetails"]["duration"]
            return parse_youtube_duration(duration)
    return "Durée inconnue"

def parse_youtube_duration(duration):
    match = re.match(r'PT(?:(\\d+)H)?(?:(\\d+)M)?(?:(\\d+)S)?', duration)
    if not match:
        return "Inconnu"
    hours, minutes, seconds = match.groups()
    hours = int(hours) if hours else 0
    minutes = int(minutes) if minutes else 0
    seconds = int(seconds) if seconds else 0
    return f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='apprenant')

class Formation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    domain = db.Column(db.Enum('Développement Web', 'Intelligence Artificielle', 'Finance et Comptabilité', 
                                'Marketing Digital', 'Santé et Bien-être'), nullable=False)
    type = db.Column(db.Enum('video', 'pdf'), nullable=False)
    link = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        role = request.form.get('role', 'apprenant')
        user = User(name=name, email=email, password=password, role=role)
        db.session.add(user)
        db.session.commit()
        flash('Inscription réussie, connecte-toi !', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

from flask import jsonify



# Création d'une version fonctionnelle et autonome de la route /chat
# Elle recherche les mots-clés dans les colonnes title, description et domain avec SQLAlchemy

from flask import jsonify


@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get("message", "").lower()
    if not user_input:
        return jsonify({"response": "Je n’ai pas compris ta question. Peux-tu reformuler ?"})

    keywords = user_input.split()
    matched_formations = []

    for keyword in keywords:
        keyword_like = f"%{keyword}%"
        results = Formation.query.filter(
            db.or_(
                Formation.title.ilike(keyword_like),
                Formation.description.ilike(keyword_like),
                Formation.domain.ilike(keyword_like)
            )
        ).all()
        matched_formations.extend(results)

    # Supprimer les doublons par ID
    unique_formations = {f.id: f for f in matched_formations}.values()

    if not unique_formations:
        return jsonify({"response": "Désolé, je n’ai trouvé aucune formation liée à ta demande."})

    responses = []
    for f in list(unique_formations)[:3]:
        if f.type == "video" and "youtube.com" in f.link:
            video_id = f.link.split("v=")[1] if "v=" in f.link else ""
            video_embed = f"""<iframe width="100%" height="200" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>"""
        else:
            video_embed = ""

        block = f"""
        <strong>{f.title}</strong><br>
        <em>{f.description}</em><br>
        <a href="{f.link}" target="_blank">Accéder à la formation</a><br>
        {video_embed}
        """
        responses.append(block)

    return jsonify({"response": "<hr>".join(responses)})







@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'dashboard'))
        flash('Échec de la connexion, vérifie tes identifiants.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    formations = Formation.query.all()
    for formation in formations:
        if formation.type == 'video':
            video_id = formation.link.split('v=')[1] if 'v=' in formation.link else None
            if video_id:
                formation.duration = get_video_duration(video_id)
    return render_template('dashboard.html', name=current_user.name, formations=formations)

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Accès refusé : Vous n\'êtes pas administrateur.', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('admin_dashboard.html', name=current_user.name)

@app.route('/admin/add_formation', methods=['POST'])
@login_required
def add_formation():
    if current_user.role != 'admin':
        flash("Accès refusé : Vous n'êtes pas administrateur.", "danger")
        return redirect(url_for('dashboard'))
    title = request.form.get('title')
    description = request.form.get('description')
    domain = request.form.get('domain')
    type = request.form.get('type')
    link = request.form.get('link')

    if not title or not description or not domain or not type or not link:
        flash("Tous les champs sont obligatoires.", "danger")
        return redirect(url_for('add_formation_page'))

    existing_formation = Formation.query.filter_by(title=title).first()
    if existing_formation:
        flash("Une formation avec ce titre existe déjà.", "danger")
        return redirect(url_for('add_formation_page'))

    new_formation = Formation(title=title, description=description, domain=domain, type=type, link=link)
    db.session.add(new_formation)
    db.session.commit()
    flash("Formation ajoutée avec succès.", "success")
    return redirect(url_for('admin_dashboard'))

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














if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

