# app.py

import os
from flask import Flask, render_template, request, redirect, url_for, flash, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index, and_
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql.expression import func
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import uuid
from functools import wraps
from datetime import datetime
from terms_and_conditions import TERMS_AND_CONDITIONS
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from sqlalchemy import MetaData
from urllib.parse import urlparse, quote
from flask_talisman import Talisman

import re
from bs4 import BeautifulSoup

from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

csp = {
    'default-src': "'self'",
    'script-src': ["'self'", "'unsafe-inline'", "https://cdnjs.cloudflare.com"],
    'style-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", "data:", "https:", "http:"],
    'font-src': ["'self'", "data:", "https:"],
}

if 'DATABASE_URL' in os.environ:
    # PostgreSQL database on Heroku
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL'].replace("postgres://", "postgresql://", 1)
    if "postgres" in app.config['SQLALCHEMY_DATABASE_URI']:
        app.config['SERVER_NAME'] = 'www.xn--ummlagreining-5fb.is'
        Talisman(app, force_https=True, content_security_policy=csp)
else:
    # SQLite database for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'trustllmeu@gmail.com')
app.config['MAIL_SUPPRESS_SEND'] = os.environ.get('MAIL_SUPPRESS_SEND', 'false').lower() in ['true', 'on', '1']

# Add this near the top of your file, after your imports
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)

db = SQLAlchemy(app, metadata=metadata)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)

migrate = Migrate(app, db)

serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

admin_created = False

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Customize Flask-Login messages
login_manager.login_message = "Vinsamlegast skráðu þig inn til að fá aðgang að þessari síðu."
login_manager.login_message_category = "info"

# You can add more custom messages if needed:
login_manager.needs_refresh_message = "Vinsamlegast skráðu þig inn aftur til að staðfesta auðkenningu."
login_manager.needs_refresh_message_category = "info"

task_guidelines = {
    'sentiment': "Taktu afstöðu til þess hvort ummælin séu almennt jákvæð, neikvæð eða hlutlaus. Þetta er huglægt mat á heildarblæ ummælanna, óháð efni þeirra.",
    'toxicity': "Ummæli teljast eitruð ef þau innihalda til dæmis dónaskap, vanvirðingu við viðmælandann, óæskilegt orðalag (svo sem blótsyrði eða fordómafull hugtök) eða annað slíkt og eru líkleg til að láta viðmælendur eða lesendur yfirgefa umræðuna",
    'politeness': "Taktu afstöðu til þess hvort ummælin séu kurteis.",
    'hate_speech_presence': "Ummæli flokkast sem hatursorðræða ef þau innihalda fjandskap, hótanir eða ærumeiðingar gagnvart hópi eða einstaklingi á grundvelli eiginleika eins og kynþætti, þjóðerni, trú, uppruna, kynhneigð, fötlun eða kyni/kynvitund. Góð þumalputtaregla er að hatursorðræða beinist að eiginleikum sem einstaklingur hefur enga stjórn á en ef ummælin beinast t.d. að stjórnmálaskoðunum viðmælandans er betra að flokka þau sem eitruð ummæli. Þetta er þó matsatriði hverju sinni og hver og einn þátttakandi verður að taka afstöðu til þess hvað er flokkað sem hatursorðræða.",
    'social_acceptability_strangers': "Taktu afstöðu til þess hvort ummælin væru viðeigandi ef þau væru sögð við ókunnugan á almannafæri. Íhugaðu t.d. hvort þér þætti í lagi að manneskja sem þú ert að hitta í fyrsta skipti segði þetta við þig í heita pottinum í sundi. Athugið að hér er einungis átt við hvort að ummælin séu viðeigandi eða ekki í þessum aðstæðum. Reyndu að forðast að dæma ummælin út frá eigin skoðunum, t.a.m. varðandi stjórnmál.",
    'social_acceptability_acquaintances': "Taktu afstöðu til þess hvort ummælin væru viðeigandi ef þau væru sögð við kunningja í óformlegum aðstæðum. Íhugaðu t.d. hvort þér þætti í lagi að manneskja sem þú þekkir lítillega segði þetta við þig í veislu hjá sameiginlegum vini ykkar. Athugið að hér er einungis átt við hvort að ummælin séu viðeigandi eða ekki í þessum aðstæðum. Reyndu að forðast að dæma ummælin út frá eigin skoðunum, t.a.m. varðandi stjórnmál.",
    'social_acceptability_close_friend': "Taktu afstöðu til þess hvort ummælin væru viðeigandi ef þau væru sögð við náinn vin í einrúmi. Íhugaðu t.d. hvort þér þætti í lagi að manneskja sem þú þekkir vel segði þetta við þig í einrúmi. Athugið að hér er einungis átt við hvort að ummælin séu viðeigandi eða ekki í þessum aðstæðum. Reyndu að forðast að dæma ummælin út frá eigin skoðunum, t.a.m. varðandi stjórnmál.",
    'social_acceptability_educational_young': "Taktu afstöðu til þess hvort ummælin væru viðeigandief kennari segði þetta við unga nemendur (t.d. við 6-8 ára nemendur í grunnskóla). Þú þarft ekki að taka tillit til þess hvort orðaforðinn er í takt við málskilning barna á þessum aldri heldur skaltu aðeins hugsa um verkefnið út frá umræðuefninu. Athugið að hér er einungis átt við hvort að ummælin séu viðeigandi eða ekki í þessum aðstæðum. Reyndu að forðast að dæma ummælin út frá eigin skoðunum, t.a.m. varðandi stjórnmál.",
    'social_acceptability_educational_older': "Taktu afstöðu til þess hvort ummælin væru viðeigandi ef kennari segði þetta við eldri nemendur (t.d. við 13-15 ára nemendur í grunnskóla). Þú þarft ekki að taka tillit til þess hvort orðaforðinn er í takt við málskilning barna á þessum aldri heldur skaltu aðeins hugsa um verkefnið út frá umræðuefninu. Athugið að hér er einungis átt við hvort að ummælin séu viðeigandi eða ekki í þessum aðstæðum. Reyndu að forðast að dæma ummælin út frá eigin skoðunum, t.a.m. varðandi stjórnmál.",
    'social_acceptability_parliament': "Taktu afstöðu til þess hvort ummælin væru ásættanleg ef þau væru sögð í formlegri umræðu á þingi. Íhugaðu t.d. hvort þér þætti í lagi að þingmaður segði þetta í pontu, annaðhvort í eigin ræðu eða sem andsvar við ræðu annarra. Athugið að hér er einungis átt við hvort að ummælin séu viðeigandi eða ekki í þessum aðstæðum. Reyndu að forðast að dæma ummælin út frá eigin skoðunum, t.a.m. varðandi stjórnmál.",
    'emotion_anger': "Taktu afstöðu til þess hvort ummælin tjái reiði.",
    'emotion_joy': "Taktu afstöðu til þess hvort ummælin tjái gleði eða hamingju.",
    'emotion_sadness': "Taktu afstöðu til þess hvort ummælin tjái sorg.",
    'emotion_fear': "Taktu afstöðu til þess hvort ummælin tjái ótta.",
    'emotion_disgust': "Taktu afstöðu til þess hvort ummælin tjái viðbjóð (þ.e.a.s. að höfundur ummælanna finni til viðbjóðs gagnvart umræðuefninu).",
    'emotion_surprise': "Taktu afstöðu til þess hvort ummælin tjái undrun.",
    'emotion_contempt': "Taktu afstöðu til þess hvort ummælin tjái fyrirlitningu.",
    'emotion_indignation': "Taktu afstöðu til þess hvort ummælin tjái hneykslun.",
    'sarcasm': "Taktu afstöðu til þess hvort ummælin innihaldi eða tjái kaldhæðni (hér er bæði átt við íroníu (e. irony) og kaldhæðni (e. sarcasm)).",
    'constructiveness': "Taktu afstöðu til þess hvort ummælin séu uppbyggileg, veiti gagnlega endurgjöf eða leggi eitthvað jákvætt til umræðunnar.",
    'encouragement_presence': "Taktu afstöðu til þess hvort ummælin innihaldi hvatningarorð eða stuðning.",
    'sympathy': "Taktu afstöðu til þess hvort ummælin tjái samúð, meðaumkun eða skilning á aðstæðum einhvers annars.",
    'trolling_behavior': "Taktu afstöðu til þess hvort ummælin virðist vera viljandi ögrandi eða móðgandi, ætluð til að framkalla tilfinningaleg viðbrögð viðmælenda eða lesenda. Góð þumalputtaregla er að nettröll skrifa oftast ummæli undir gervinafni. Það er þó ekki algilt.",
    #'trolling_anonymity': "Taktu afstöðu til þess hvort höfundurinn sé að nota nafnlausan aðgang.",
    'mansplaining': "Taktu afstöðu til þess hvort ummælin séu hrútskýring. Hrútskýring er blanda af orðunum „hrútur“ og „útskýring“ og er íslensk þýðing á enska hugtakinu „mansplaining“. Það vísar í grófum dráttum til þess þegar karlmaður útskýrir hluti fyrir konu á yfirlætislegan og lítillækkandi máta, gjarnan hluti sem konan veit þó meira um en karlmaðurinn. Sem dæmi um hrútskýringar eru fullyrðingar sem innihalda: „Nei þú skilur ekki alveg“ eða „Það sem þú ert að reyna að segja er…“. Hrútskýring er stundum skilgreind á víðtækari hátt og getur þá átt við um ummæli sem kona og/eða karlmaður segir við aðra manneskju, en hér eigum við aðeins við ummæli sem karlmaður segir við konu.",
    'group_generalization_presence': "Taktu afstöðu til þess hvort ummælin geri víðtækar alhæfingar um hóp fólks byggt á einkennum eins og kynþætti, kyni, þjóðerni, pólitískum skoðunum og fleira. Athugið að hér er ekki endilega átt við neikvæðar fullyrðingar (samanber hatursorðræðu) heldur hvers kyns alhæfingar. Sem dæmi: „Konur eru betri í að sjá um uppeldi en karlar“."
}


@login_manager.unauthorized_handler
def unauthorized():
    flash("Vinsamlegast skráðu þig inn til að fá aðgang að þessari síðu.", "warning")
    return redirect(url_for('login', next=request.url))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(50), unique=True, nullable=True)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    education_level = db.Column(db.String(50))
    first_language = db.Column(db.String(50))
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    terms_accepted = db.Column(db.Boolean, default=False)
    terms_accepted_date = db.Column(db.DateTime)
    feedback_enabled = db.Column(db.Boolean, default=False)
    has_read_guidelines = db.Column(db.Boolean, default=False)
    email_consent = db.Column(db.Boolean, default=False) # We are allowed to contact the user

    __table_args__ = (Index('idx_user_id', 'id'),)

class Blog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    date = db.Column(db.String(255), nullable=True)
    title = db.Column(db.String(1023), nullable=False)
    full_link = db.Column(db.String(1023), nullable=False)
    blog_content = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(20))
    objectivity = db.Column(db.Integer)
    controversy_level = db.Column(db.Integer)
    toxicity = db.Column(db.Integer)
    clickbait_score = db.Column(db.Integer)
    author_gender = db.Column(db.String(20))

    __table_args__ = (
        Index('idx_blog_id', 'id'),
        Index('idx_blog_uuid', 'uuid'),
    )

class Comment(db.Model):
    uuid = db.Column(db.String(36), primary_key=True)
    blog_uuid = db.Column(db.String(36), db.ForeignKey('blog.uuid'), nullable=False)
    comment_text = db.Column(db.Text, nullable=False)
    author_website = db.Column(db.String(1023))
    author_name = db.Column(db.String(1023))
    comment_datetime = db.Column(db.DateTime)
    sentiment = db.Column(db.String(20))
    author_gender = db.Column(db.String(20))
    
    # Add new columns for each task
    toxicity = db.Column(db.Float, nullable=True)
    politeness = db.Column(db.Float, nullable=True)
    hate_speech_presence = db.Column(db.Float, nullable=True)
    social_acceptability_strangers = db.Column(db.Float, nullable=True)
    social_acceptability_acquaintances = db.Column(db.Float, nullable=True)
    social_acceptability_close_friend = db.Column(db.Float, nullable=True)
    social_acceptability_educational_young = db.Column(db.Float, nullable=True)
    social_acceptability_educational_older = db.Column(db.Float, nullable=True)
    social_acceptability_parliament = db.Column(db.Float, nullable=True)
    emotion_anger = db.Column(db.Float, nullable=True)
    emotion_joy = db.Column(db.Float, nullable=True)
    emotion_sadness = db.Column(db.Float, nullable=True)
    emotion_fear = db.Column(db.Float, nullable=True)
    emotion_disgust = db.Column(db.Float, nullable=True)
    emotion_surprise = db.Column(db.Float, nullable=True)
    emotion_contempt = db.Column(db.Float, nullable=True)
    emotion_indignation = db.Column(db.Float, nullable=True)
    sarcasm = db.Column(db.Float, nullable=True)
    constructiveness = db.Column(db.Float, nullable=True)
    encouragement_presence = db.Column(db.Float, nullable=True)
    sympathy = db.Column(db.Float, nullable=True)
    trolling_behavior = db.Column(db.Float, nullable=True)
    trolling_anonymity = db.Column(db.Float, nullable=True)
    mansplaining = db.Column(db.Float, nullable=True)
    group_generalization_presence = db.Column(db.Float, nullable=True)

    __table_args__ = (
        Index('idx_comment_uuid', 'uuid'),
    )

class AnnotationTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    comment_uuid = db.Column(db.String(36), db.ForeignKey('comment.uuid'), nullable=False)
    task = db.Column(db.String(50), nullable=False)
    counter = db.Column(db.Integer, default=0)

    # Add a unique constraint to ensure one task per comment
    __table_args__ = (db.UniqueConstraint('comment_uuid', 'task', name='_comment_task_uc'),)
    __table_args__ = (Index('idx_annotation_task_id', 'id'),)
    
class Annotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_uuid = db.Column(db.String(36), db.ForeignKey('comment.uuid'), nullable=False)
    task = db.Column(db.String(50), nullable=False)
    value = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    time_taken = db.Column(db.Float, nullable=False)
    prior_comments_viewing_time = db.Column(db.Float, default=0.0)
    blog_post_viewing_time = db.Column(db.Float, default=0.0)
    feedback_active = db.Column(db.Boolean, default=False)

    __table_args__ = (
        Index('idx_annotation_id', 'id'),
        Index('idx_annotation_user_id', 'user_id'),
        Index('idx_annotation_task', 'task'),
    )

class ReportedIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issue_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (Index('idx_reported_issue_id', 'id'),)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Þú þarft að vera stjórnandi til að fá aðgang að þessari síðu.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def get_initials(name):
    # Check if the name has more than five whitespaces
    if name.count(' ') > 5:
        # If so, join it into a single word
        name = ''.join(name.split())
    
    # Split the name into words
    words = name.split()
    initials = ''.join(word[0].upper() for word in words if word)
    return initials

@app.context_processor
def utility_processor():
    return dict(get_initials=get_initials)

@app.route('/')
def index():
    if current_user.is_authenticated:
        user_progress = get_user_progress(current_user.id)
        leaderboard = get_leaderboard()
        return render_template('dashboard.html', user_progress=user_progress, leaderboard=leaderboard, current_user=current_user)
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        display_name = request.form.get('display_name')
        age = request.form.get('age')
        gender = request.form.get('gender')
        education_level = request.form.get('education_level')
        first_language = request.form.get('first_language')
        terms_accepted = request.form.get('terms_accepted') == 'on'
        email_consent = request.form.get('email_consent') == 'on'

        if not terms_accepted:
            flash('Þú verður að samþykkja skilmála og skilyrði til að skrá þig.', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Lykilorð passa ekki saman.', 'danger')
            return redirect(url_for('register'))
        
        if int(age) < 18:
            flash('Þú verður að vera að minnsta kosti 18 ára til að skrá þig.', 'danger')
            return redirect(url_for('register'))

        try:
            user = User.query.filter((User.email == email) | (User.display_name == display_name)).first()
            if user:
                if user.email == email:
                    flash('Tölvupóstfang er þegar til.', 'danger')
                else:
                    flash('Birtingarnafn er þegar til.', 'danger')
                return redirect(url_for('register'))

            new_user = User(
                email=email,
                password=generate_password_hash(password, method='pbkdf2:sha256'),
                display_name=display_name,
                age=age,
                gender=gender,
                education_level=education_level,
                first_language=first_language,
                terms_accepted=terms_accepted,
                terms_accepted_date=datetime.utcnow() if terms_accepted else None,
                email_consent=email_consent
            )
            db.session.add(new_user)
            db.session.commit()

            send_verification_email(new_user)

            flash('Skráning tókst. Vinsamlegast athugaðu tölvupóstinn þinn til að staðfesta aðganginn þinn. Tilkynningin gæti hafa verið flögguð sem ruslpóstur.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Registration failed: {str(e)}")
            flash('An error occurred during registration. Please try again later.', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html', terms_and_conditions=TERMS_AND_CONDITIONS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            if not user.is_verified:
                flash('Vinsamlegast staðfestu tölvupóstinn þinn áður en þú skráir þig inn.', 'warning')
                return redirect(url_for('login'))
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Ógilt tölvupóstfang eða lykilorð.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/verify/<token>')
def verify_email(token):
    user_id = verify_token(token)
    if user_id is None:
        flash('Staðfestingarhlekkurinn er ógildur eða útrunninn.', 'danger')
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)
    if user:
        if user.is_verified:
            flash('Aðgangur þegar staðfestur. Vinsamlegast skráðu þig inn.', 'info')
        else:
            user.is_verified = True
            db.session.commit()
            flash('Tölvupósturinn þinn hefur verið staðfestur. Þú getur nú skráð þig inn.', 'success')
    else:
        flash('Notandi fannst ekki.', 'danger')
    
    return redirect(url_for('login'))

def preprocess_blog_content(content, full_link):
    # Parse the HTML content
    soup = BeautifulSoup(content, 'html.parser')

    # Remove iframe and everything after it
    iframe = soup.find('iframe')
    if iframe:
        for element in iframe.find_all_next():
            element.decompose()
        iframe.decompose()

    # Extract the base URL from full_link
    parsed_url = urlparse(full_link)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    # Update image sources
    for img in soup.find_all('img'):
        src = img.get('src')
        if src:
            if not src.startswith(('http://', 'https://', '//')):
                img['src'] = f"{base_url}/{src.lstrip('/')}"

    # Return the modified HTML as a string
    return str(soup)

@app.route('/annotate/<task>')
@login_required
def annotate(task):    
    # Get all annotation tasks for the given task, excluding those annotated by the current user
    subquery = db.session.query(Annotation.comment_uuid).filter(
        Annotation.user_id == current_user.id,
        Annotation.task == task
    ).subquery()
    
    available_tasks = AnnotationTask.query.filter(
        AnnotationTask.task == task,
        ~AnnotationTask.comment_uuid.in_(subquery)
    ).order_by(func.random()).first()
    
    if not available_tasks:
        flash('Ekki fleiri ummæli í boði fyrir merkingu í þessu verkefni.', 'info')
        return redirect(url_for('index'))
    
    comment = Comment.query.get(available_tasks.comment_uuid)
    blog_post = Blog.query.filter_by(uuid=comment.blog_uuid).first()
    
    # Preprocess the blog content
    if blog_post:
        blog_post.blog_content = preprocess_blog_content(blog_post.blog_content, blog_post.full_link)
    
    previous_comments = Comment.query.filter(
        Comment.blog_uuid == comment.blog_uuid,
        Comment.comment_datetime < comment.comment_datetime
    ).order_by(Comment.comment_datetime.desc()).all()

    task_names = {
        'sentiment': "Lyndisgreining",
        'toxicity': 'Eitruð ummæli',
        'politeness': 'Kurteisi',
        'hate_speech_presence': 'Hatursorðræða',
        'social_acceptability_strangers': 'Félagslegt samþykki (ókunnugir)',
        'social_acceptability_acquaintances': 'Félagslegt samþykki (kunningjar)',
        'social_acceptability_close_friend': 'Félagslegt samþykki (náinn vinur)',
        'social_acceptability_educational_young': 'Félagslegt samþykki (1.-3. bekkur)',
        'social_acceptability_educational_older': 'Félagslegt samþykki (8.-10. bekkur)',
        'social_acceptability_parliament': 'Félagslegt samþykki (í þingræðu)',
        'emotion_anger': 'Tilfinning: Reiði',
        'emotion_joy': 'Tilfinning: Gleði',
        'emotion_sadness': 'Tilfinning: Sorg',
        'emotion_fear': 'Tilfinning: Ótti',
        'emotion_disgust': 'Tilfinning: Viðbjóður',
        'emotion_surprise': 'Tilfinning: Undrun',
        'emotion_contempt': 'Tilfinning: Fyrirlitningu',
        'emotion_indignation': 'Tilfinning: Hneykslun',
        'sarcasm': 'Kaldhæðni',
        'constructiveness': 'Uppbyggileg orðræða',
        'encouragement_presence': 'Hvatning',
        'sympathy': 'Samúð',
        'trolling_behavior': 'Nettröll',
        'trolling_anonymity': 'Nafnleynd nettrölla',
        'mansplaining': 'Hrútskýringar',
        'group_generalization_presence': 'Alhæfingar um hópa'
    }

    task_questions = {
        'sentiment': 'Hvert er lyndi ummælanna?',
        'toxicity': 'Eru ummælin að ofan eitruð?',
        'politeness': 'Eru ummælin að ofan kurteis?',
        'hate_speech_presence': 'Teljast ummælin að ofan sem hatursorðræða?',
        'social_acceptability_strangers': 'Væri viðeigandi að segja ummælin við ókunnugan?',
        'social_acceptability_acquaintances': 'Væri viðeigandi að segja ummælin við kunningja?',
        'social_acceptability_close_friend': 'Væri viðeigandi að segja ummælin við náinn vin?',
        'social_acceptability_educational_young': 'Væri viðeigandi fyrir kennara að segja ummælin við nemendur í 1.-3. bekk?',
        'social_acceptability_educational_older': 'Væri viðeigandi fyrir kennara að segja ummælin við nemendur í 8.-10. bekk?',
        'social_acceptability_parliament': 'Eru ummælin ásættanleg í þingræðu?',
        'emotion_anger': 'Tjá ummælin reiði?',
        'emotion_joy': 'Tjá ummælin gleði?',
        'emotion_sadness': 'Tjá ummælin sorg?',
        'emotion_fear': 'Tjá ummælin ótta?',
        'emotion_disgust': 'Tjá ummælin viðbjóð?',
        'emotion_surprise': 'Tjá ummælin undrun?',
        'emotion_contempt': 'Tjá ummælin fyrirlitningu?',
        'emotion_indignation': 'Tjá ummælin hneysklun?',
        'sarcasm': 'Eru ummælin kaldhæðin?',
        'constructiveness': 'Eru ummælin uppbyggileg?',
        'encouragement_presence': 'Innihalda ummælin hvatningu?',
        'sympathy': 'Sýna ummælin samúð?',
        'trolling_behavior': 'Eru ummælin frá nettrölli?',
        'trolling_anonymity': 'Er höfundur ummælanna að nota nafnlausan aðgang?',
        'mansplaining': 'Eru ummælin dæmi um hrútskýringu?',
        'group_generalization_presence': 'Innihalda ummælin alhæfingar um hópa?'
    }

    # Get number of annotations for the current user in the current task
    #user_annotations_count = Annotation.query.filter_by(user_id=current_user.id, task=task).count()
    user_annotations_count = Annotation.query.filter(
        and_(
            Annotation.user_id == current_user.id,
            Annotation.task == task,
            Annotation.value != 'skip'
        )
    ).count()
    # Calculate next_prize_count
    prize_thresholds = [10, 50, 100, 250, 500, 1000]
    next_prize = next((threshold for threshold in prize_thresholds if threshold > user_annotations_count), None)
    next_prize_count = next_prize - user_annotations_count if next_prize else -1

    return render_template('annotate.html', 
                           comment=comment, 
                           task=task, 
                           blog_post=blog_post, 
                           previous_comments=previous_comments, 
                           task_names=task_names, 
                           task_questions=task_questions,
                           task_guidelines=task_guidelines,
                           user_annotations_count=user_annotations_count,
                           next_prize_count=next_prize_count)

@app.route('/submit_annotation', methods=['POST'])
@login_required
def submit_annotation():
    data = request.json
    comment_uuid = data['comment_uuid']
    task = data['task']
    value = data['annotation']
    time_taken = data['time_taken']
    prior_comments_viewing_time = data['prior_comments_viewing_time']
    blog_post_viewing_time = data['blog_post_viewing_time']

    if task == 'sentiment':
        if value == 'positive':
            value = '2'
        elif value == 'negative':
            value = '0'
        elif value == 'neutral':
            value = '1'

    annotation = Annotation(
        user_id=current_user.id,
        comment_uuid=comment_uuid,
        task=task,
        value=value,
        time_taken=time_taken,
        prior_comments_viewing_time=prior_comments_viewing_time,
        blog_post_viewing_time=blog_post_viewing_time,
        feedback_active=current_user.feedback_enabled
    )
    db.session.add(annotation)

    annotation_task = AnnotationTask.query.filter_by(comment_uuid=comment_uuid, task=task).first()
    if annotation_task:
        annotation_task.counter += 1

    db.session.commit()

    feedback = None
    if current_user.feedback_enabled and value != 'skip':
        comment = Comment.query.get(comment_uuid)
        gpt_value = getattr(comment, task)
        if gpt_value is not None:
            if task == 'sentiment':
                user_sentiment = 'jákvæð' if value == '2' else 'neikvæð' if value == '0' else 'hlutlaus'
                model_sentiment = 'jákvæð' if gpt_value == 'positive' else 'neikvæð' if gpt_value == 'negative' else 'hlutlaus'
                
                if user_sentiment == model_sentiment:
                    feedback = f"Merking þín er í samræmi við spá gervigreindarlíkans. Þið merktuð bæði ummælin sem {user_sentiment}."
                else:
                    feedback = f"Merking þín er ekki í samræmi við spá gervigreindarlíkans. Þú merktir ummælin sem {user_sentiment}, en líkanið merkti þau sem {model_sentiment}."
            else:
                if ((value == '1' and gpt_value > 2) or (value == '0' and gpt_value <= 2)):
                    feedback = "Merking þín er í samræmi við spá gervigreindarlíkans."
                else:
                    feedback = "Merking þín er ekki í samræmi við spá gervigreindarlíkans."
        else:
            feedback = "Engin spá frá gervigreindarlíkani er til fyrir þessi ummæli."
    
    return jsonify({
        'status': 'success',
        'feedback_enabled': current_user.feedback_enabled and value != 'skip',
        'feedback': feedback
    })

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

def get_user_progress(user_id):
    tasks = [
        'sentiment', 'toxicity', 'politeness', 'hate_speech_presence', 'social_acceptability_strangers',
        'social_acceptability_acquaintances', 'social_acceptability_close_friend',
        'social_acceptability_educational_young', 'social_acceptability_educational_older',
        'social_acceptability_parliament', 'emotion_anger', 'emotion_joy', 'emotion_sadness',
        'emotion_fear', 'emotion_disgust', 'emotion_surprise', 'emotion_contempt',
        'emotion_indignation', 'sarcasm', 'constructiveness', 'encouragement_presence',
        'sympathy', 'trolling_behavior', 'mansplaining',
        'group_generalization_presence'
    ]
    
    progress = {}
    for task in tasks:
        user_annotations = Annotation.query.filter(
            Annotation.user_id == user_id,
            Annotation.task == task,
        ).count()

        user_annotations_without_skip = Annotation.query.filter(
            Annotation.user_id == user_id,
            Annotation.task == task,
            Annotation.value != 'skip'
        ).count()

        total_annotations = Annotation.query.filter(
            Annotation.task == task,
        ).count()
        
        agreement_ratio = None
        if current_user.feedback_enabled and user_annotations_without_skip > 0:
            if task == 'sentiment':
                agreed_annotations = Annotation.query.filter(
                    Annotation.user_id == user_id,
                    Annotation.task == task,
                    Annotation.value != 'skip'
                ).join(Comment).filter(
                    ((Annotation.value == '2') & (Comment.sentiment == 'positive')) |
                    ((Annotation.value == '0') & (Comment.sentiment == 'negative')) |
                    ((Annotation.value == '1') & (Comment.sentiment == 'neutral'))
                ).count()
            elif task != "trolling_anonymity":
                agreed_annotations = Annotation.query.filter(
                    Annotation.user_id == user_id,
                    Annotation.task == task,
                    Annotation.value != 'skip'
                ).join(Comment).filter(
                    ((Annotation.value == '1') & (getattr(Comment, task) > 2)) |
                    ((Annotation.value == '0') & (getattr(Comment, task) <= 2))
                ).count()
            else:
                agreed_annotations = Annotation.query.filter(
                    Annotation.user_id == user_id,
                    Annotation.task == task,
                    Annotation.value != 'skip'
                ).join(Comment).filter(
                    ((Annotation.value == '1') & (getattr(Comment, task) > 0)) |
                    ((Annotation.value == '0') & (getattr(Comment, task) < 1))
                ).count()
            agreement_ratio = round((agreed_annotations / user_annotations_without_skip) * 100, 2)
        
        progress[task] = {
            'user': user_annotations,
            'user_without_skip': user_annotations_without_skip,
            'total': total_annotations,
            'agreement_ratio': agreement_ratio
        }
    
    return progress

def get_leaderboard():
    users = User.query.filter_by(is_admin=False).all()
    leaderboard = []
    for user in users:
        total_annotations = Annotation.query.filter_by(user_id=user.id).count()
        leaderboard.append({
            'display_name': user.display_name,
            'total_annotations': total_annotations
        })
    
    leaderboard.sort(key=lambda x: x['total_annotations'], reverse=True)
    
    return leaderboard[:10]

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user = User.query.get(current_user.id)
    user.age = request.form.get('age')
    user.gender = request.form.get('gender')
    user.education_level = request.form.get('education_level')
    user.first_language = request.form.get('first_language')
    user.email_consent = request.form.get('email_consent') == 'on'
    
    db.session.commit()
    flash('Prófíll uppfærður.', 'success')
    return redirect(url_for('profile'))

@app.route('/admin/export')
@login_required
@admin_required
def export_annotations():
    annotations = Annotation.query.all()
    
    csv_data = "user_id,comment_uuid,task,value,timestamp,time_taken,prior_comments_viewed,blog_post_viewed\n"
    for annotation in annotations:
        csv_data += f"{annotation.user_id},{annotation.comment_uuid},{annotation.task},{annotation.value},"
        csv_data += f"{annotation.timestamp},{annotation.time_taken},{annotation.prior_comments_viewed},"
        csv_data += f"{annotation.blog_post_viewed}\n"
    
    response = make_response(csv_data)
    response.headers["Content-Disposition"] = "attachment; filename=annotations_export.csv"
    response.headers["Content-type"] = "text/csv"
    
    return response

@app.route('/report_issue', methods=['GET', 'POST'])
@login_required
def report_issue():
    if request.method == 'POST':
        issue_type = request.form.get('issue_type')
        description = request.form.get('description')
        
        new_issue = ReportedIssue(
            user_id=current_user.id,
            issue_type=issue_type,
            description=description
        )
        
        db.session.add(new_issue)
        db.session.commit()
        
        # Send email
        try:
            msg = Message(
                subject="Nýtt vandamál tilkynnt",
                recipients=["hafsteinne@hi.is", "srf2@hi.is"],
                body=f"""
                Nýtt vandamál hefur verið tilkynnt:
                
                Tegund vandamáls: {issue_type}
                Lýsing: {description}
                
                Tilkynnt af notanda: {current_user.email}
                """,
                sender=app.config['MAIL_DEFAULT_SENDER']
            )
            mail.send(msg)
        except Exception as e:
            # Log the error, but don't prevent the user from submitting the issue
            app.logger.error(f"Failed to send email: {str(e)}")
        
        flash('Vandamál tilkynnt. Takk fyrir ábendinguna.', 'success')
        return redirect(url_for('index'))
    
    return render_template('report_issue.html')

def send_verification_email(user):
    token = generate_token(user.id)
    verify_url = url_for('verify_email', token=token, _external=True)
    subject = 'Staðfestu netfangið þitt fyrir ummælagreiningu'
    body = f'Smelltu vinsamlegast á eftirfarandi hlekk til að staðfesta netfangið þitt: {verify_url}'
    
    if app.config['MAIL_SUPPRESS_SEND']:
        # Log the email instead of sending it
        app.logger.info(f"Email suppressed. Would have sent to {user.email}: {body}")
        # Optionally, you can automatically verify the user in development
        user.is_verified = True
        db.session.commit()
    else:
        try:
            msg = Message(subject, recipients=[user.email], body=body)
            mail.send(msg)
        except Exception as e:
            app.logger.error(f"Failed to send email: {str(e)}")
            # Handle the error appropriately (e.g., flash a message to the user)

def generate_token(user_id):
    return serializer.dumps(user_id, salt='email-confirm-salt')

def verify_token(token, expiration=3600):
    try:
        user_id = serializer.loads(token, salt='email-confirm-salt', max_age=expiration)
        return user_id
    except (SignatureExpired, BadSignature):
        return None

def create_tables():
    with app.app_context():
        try:
            db.create_all()
            print("Tables created successfully")
        except OperationalError as e:
            print(f"An error occurred while creating tables: {e}")

@app.route('/terms')
def terms():
    return render_template('terms.html', terms_and_conditions=TERMS_AND_CONDITIONS)

@app.route('/toggle_feedback', methods=['POST'])
@login_required
def toggle_feedback():
    current_user.feedback_enabled = not current_user.feedback_enabled
    db.session.commit()
    return jsonify({'status': 'success', 'feedback_enabled': current_user.feedback_enabled})

@app.route('/guidelines')
def guidelines():
    return render_template('guidelines.html')

@app.route('/check_guidelines_status')
@login_required
def check_guidelines_status():
    return jsonify({'has_read_guidelines': current_user.has_read_guidelines})

@app.route('/mark_guidelines_read', methods=['POST'])
@login_required
def mark_guidelines_read():
    current_user.has_read_guidelines = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/about')
def about():
    return render_template('about.html')

def create_admin_user():
    global admin_created
    if admin_created:
        return
    
    with app.app_context():
        admin_user = User.query.filter_by(email='admin@admin.com').first()
        if not admin_user:
            admin_user = User(
                email='admin@admin.com',
                password=generate_password_hash('adminadmin', method='pbkdf2:sha256'),
                is_verified=True,
                is_admin=True,
                terms_accepted=True,
                terms_accepted_date=datetime.utcnow()
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created successfully.")
        else:
            print("Admin user already exists.")
    
    admin_created = True

# Add this function to generate share messages
def generate_share_messages(total_annotations, agreement_percentage):
    agreement_percentage_formatted = "{:.1f}".format(agreement_percentage).replace('.', ',')
    agreement_percentage_reverse_formatted = "{:.1f}".format(100-agreement_percentage).replace('.', ',')
    messages = [
        f"Ég hef merkt {total_annotations} ummæli í ummælagreiningarverkefninu og er sammála gervigreindarlíkani í {agreement_percentage_formatted}% tilvika. Taktu þátt og hjálpaðu til við að varðveita og efla íslensku í stafrænum heimi! #Ummælagreining",
        f"Viltu hjálpa til við að bæta íslenska gervigreind? Ég hef lokið við að merkja {total_annotations} ummæli. Komdu og taktu þátt í ummælagreiningarverkefninu! #ÍslenskUmmælagreining",
        f"Spennandi tímar fyrir íslensku í tækniheiminum! Ég er búin(n/ð) að merkja {total_annotations} ummæli. Viltu vera með? #UmmælagreiningÍslands",
        f"Gervigreind og íslenska: Ég er sammála gervigreindarlíkani í {agreement_percentage_formatted}% tilvika. Hvað með þig? Taktu þátt í Ummælagreiningarverkefninu! #ÍslenskGervigreind",
        f"Verndum íslenskuna saman! Ég hef lagt mitt af mörkum með {total_annotations} merkingum. Viltu vera hluti af þessu mikilvæga verkefni? #StöndumVörðUmÍslensku",
        f"Íslenska í stafrænum heimi: Með {total_annotations} merkingum er ég að hjálpa til við að bæta íslenska gervigreind. Komdu og vertu með! #StafrænÍslenska",
        f"Ummælagreiningarverkefnið: Þar sem tungumál og tækni mætast. Ég er búin(n/ð) með {total_annotations} merkingar. Hvernig væri að þú prófaðir líka? #Íslenska #Tækni",
        f"Framtíð íslenskunnar er í okkar höndum! Ég hef merkt {total_annotations} ummæli. Taktu þátt og hjálpaðu til við að móta framtíðina! #FramtíðÍslenskunnar",
        f"Ég er sammála gervigreind í {agreement_percentage_formatted}% tilfella! Ég er að leggja mitt af mörkum til að bæta íslenska máltækni. Viltu vera með? #ÍslenskMáltækni",
        f"Íslenska og gervigreind: Spennandi blanda! Ég hef þegar merkt {total_annotations} ummæli. Komdu og vertu hluti af þessari byltingu! #GervigreindÍslands",    
        f"Ný frétt: Manneskja les {total_annotations} ummæli á netinu af fúsum og frjálsum vilja! Í öðrum fréttum, gervigreind er {agreement_percentage_reverse_formatted}% ósammála þessari manneskju. Er þetta upphafið að uppreisn vélanna eða bara dæmigerður dagur á íslensku interneti? Komdu og dæmdu sjálf(ur) í Ummælagreiningarverkefninu!",
                        
        f"Ég er búin(n/ð) að vera sammála gervigreind í {agreement_percentage_formatted}% tilvika. Það er meira en ég er sammála mömmu minni! Er ég að verða að vélmenni eða er gervigreindin að verða of mannleg? Komdu og hjálpaðu okkur í Ummælagreiningarverkefninu!",
        
        f"Frétt: Einstaklingur merkir {total_annotations} ummæli og öðlast ofurkraft til að skilja alla kaldhæðni á netinu! Næsta skref: Kenna gervigreind að skilja íslenskan húmor. Ertu nógu hugrakkur/hugrökk/hugrakkt til að taka þátt í þessu verkefni?",
                
        f"Staðreynd: Ég hef lesið {total_annotations} ummæli á netinu. Niðurstaða: Íslendingar eru ennþá jafn skemmtilegir, skapandi og stundum svolítið skrýtnir og þeir hafa alltaf verið. Hjálpaðu okkur að kenna gervigreind að meta þessa einstöku blöndu af íslenskum persónuleikum!",
        
        f"Eftir að hafa merkt {total_annotations} ummæli er ég komin(n/ð) með þá kenningu að íslenska sé í raun dulmál. Gervigreindin er sammála mér í {agreement_percentage_formatted}% tilvika, þannig að annaðhvort erum við bæði að nálgast stórkostlegan sannleika eða að missa vitið saman. Viltu hjálpa til við að ákveða hvor kenningin er rétt?",
    ]
    return messages

@app.route('/share_progress')
@login_required
def share_progress():
    total_annotations = Annotation.query.filter_by(user_id=current_user.id).count()
    
    agreement_count = 0
    total_count = 0
    for task, progress in get_user_progress(current_user.id).items():
        if progress['agreement_ratio'] is not None:
            agreement_count += progress['agreement_ratio'] * progress['user_without_skip'] / 100
            total_count += progress['user_without_skip']
    
    agreement_percentage = (agreement_count / total_count * 100) if total_count > 0 else 0
    agreement_percentage_formatted = "{:.1f}".format(agreement_percentage).replace('.', ',')
    
    share_messages = generate_share_messages(total_annotations, agreement_percentage)
    
    facebook_share_url = f"https://www.facebook.com/sharer/sharer.php?u={quote(url_for('index', _external=True))}"
    twitter_share_url = f"https://twitter.com/intent/tweet?url={quote(url_for('index', _external=True))}"
    
    return render_template('share_progress.html', 
                           total_annotations=total_annotations, 
                           agreement_percentage=agreement_percentage_formatted,
                           facebook_share_url=facebook_share_url,
                           twitter_share_url=twitter_share_url,
                           share_messages=share_messages)

@app.before_request
def before_request():
    create_admin_user()

if __name__ == '__main__':
    with app.app_context():
        create_tables()
    app.run(debug=True)