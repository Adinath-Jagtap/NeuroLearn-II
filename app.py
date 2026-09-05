"""
NeuroLearn 2.0 — AI-Based Cognitive Gaming & Memory Assistance Platform
For Elderly Dementia Patients | SIH26003 | MDoNER
"""

import os
import sys
import json
import time
import uuid
import random
import string

# Fix Windows encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response, send_from_directory, stream_with_context
from werkzeug.utils import secure_filename
from flask_session import Session
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import requests

from utils.ai_processor import call_llm
from utils.tts_engine import generate_chapter_audio_stream, get_voice_for_language
from utils.cognitive_engine import (
    generate_recognition_game, generate_pattern_game,
    calculate_game_score, get_adaptive_difficulty,
    get_daily_routine, calculate_domain_scores,
    calculate_overall_score, check_for_alerts,
    generate_minicog_words, score_minicog
)
from utils.email_service import send_sos_alert, send_daily_report, send_smart_alert, send_doctor_report
from utils.rag_engine import save_caregiver_notes, query_care_context, format_context_for_prompt, load_patient_chunks
from utils.storage import upload_image

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "neurolearn_v2_secret_key_2026")

# Session Config
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
Session(app)

# Upload Config
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

from utils.translations import get_translations

def generate_patient_code():
    """Generate a 6-char unique patient code for linking."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.context_processor
def inject_translations():
    """Inject localized UI translation dictionary into all templates."""
    lang = request.args.get("lang")
    if lang:
        session["preferred_language"] = lang
    else:
        profile = session.get("patient_profile", {})
        # If logged in as patient, ensure language matches their profile unless manually chosen
        if session.get("role") == "patient" and profile.get("language") and not session.get("lang_manually_set"):
            session["preferred_language"] = profile["language"]
        elif not session.get("preferred_language"):
            session["preferred_language"] = profile.get("language") or request.cookies.get("preferred_language", "en")
    
    current_lang = session.get("preferred_language", "en")
    return {
        "t": get_translations(current_lang),
        "current_language": current_lang,
        "supported_languages": [
            {"code": "en", "name": "English"},
            {"code": "hi", "name": "Hindi (हिंदी)"},
            {"code": "mr", "name": "Marathi (मराठी)"},
            {"code": "as", "name": "Assamese (অসমীয়া)"},
            {"code": "bn", "name": "Bengali (বাংলা)"},
            {"code": "mni", "name": "Manipuri (মৈতৈলোন্)"},
        ]
    }

# --- FIREBASE DATABASE (Realtime Database & Firestore Support) ---
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "neurolearn-2")
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "")
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "").rstrip("/")
REST_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"
USE_RTDB = bool(FIREBASE_DATABASE_URL)


def py_to_firestore(val):
    if val is None: return {'nullValue': None}
    elif isinstance(val, bool): return {'booleanValue': val}
    elif isinstance(val, int): return {'integerValue': str(val)}
    elif isinstance(val, float): return {'doubleValue': val}
    elif isinstance(val, str): return {'stringValue': val}
    elif isinstance(val, list): return {'arrayValue': {'values': [py_to_firestore(x) for x in val]}}
    elif isinstance(val, dict): return {'mapValue': {'fields': {k: py_to_firestore(v) for k, v in val.items()}}}
    return {'stringValue': str(val)}


def firestore_to_py(val):
    if not isinstance(val, dict): return None
    if 'stringValue' in val: return val['stringValue']
    elif 'integerValue' in val: return int(val['integerValue'])
    elif 'doubleValue' in val: return float(val['doubleValue'])
    elif 'booleanValue' in val: return val['booleanValue']
    elif 'nullValue' in val: return None
    elif 'mapValue' in val: return {k: firestore_to_py(v) for k, v in val.get('mapValue', {}).get('fields', {}).items()}
    elif 'arrayValue' in val: return [firestore_to_py(x) for x in val.get('arrayValue', {}).get('values', [])]
    return None


class MemoryDoc:
    def __init__(self, doc_id, data):
        self.id = str(doc_id)
        self._data = data or {}
        self.exists = data is not None and bool(data)
    def to_dict(self):
        return dict(self._data)
    def get(self, key, default=None):
        return self._data.get(key, default)


class MemoryQuery:
    def __init__(self, items):
        self._items = items
    def order_by(self, field, direction=None):
        return self
    def limit(self, count):
        self._items = self._items[:count]
        return self
    def get(self):
        return self._items
    def __len__(self):
        return len(self._items)
    def __iter__(self):
        return iter(self._items)


class RESTDocumentRef:
    def __init__(self, store, collection_name, doc_id):
        self._store = store
        self.collection_name = collection_name
        self.id = str(doc_id)
        if USE_RTDB:
            self.url = f"{FIREBASE_DATABASE_URL}/{self.collection_name}/{self.id}.json"
        else:
            self.url = f"{REST_BASE_URL}/{self.collection_name}/{self.id}?key={FIREBASE_API_KEY}"

    def get(self):
        cached = self._store.get_cached(self.collection_name, self.id)
        if cached is not None:
            return MemoryDoc(self.id, cached)
        try:
            r = requests.get(self.url, timeout=5)
            if r.status_code == 200 and r.text != 'null':
                if USE_RTDB:
                    data = r.json() or {}
                else:
                    fields = r.json().get('fields', {})
                    data = {k: firestore_to_py(v) for k, v in fields.items()}
                self._store.set_cached(self.collection_name, self.id, data)
                return MemoryDoc(self.id, data)
        except Exception as e:
            print(f"⚠️ [FIREBASE] Get error on {self.collection_name}/{self.id}: {e}")
        return MemoryDoc(self.id, cached if cached is not None else None)

    def set(self, data, merge=False):
        existing = self._store.get_cached(self.collection_name, self.id) or {}
        new_data = {**existing, **data} if merge else dict(data)
        self._store.set_cached(self.collection_name, self.id, new_data)
        try:
            if USE_RTDB:
                if merge:
                    r = requests.patch(self.url, json=new_data, timeout=5)
                else:
                    r = requests.put(self.url, json=new_data, timeout=5)
                if r.status_code == 200:
                    print(f"🔥 [FIREBASE RTDB] Saved to /{self.collection_name}/{self.id}")
            else:
                fields = {k: py_to_firestore(v) for k, v in new_data.items()}
                requests.patch(self.url, json={'fields': fields}, timeout=5)
        except Exception as e:
            print(f"⚠️ [FIREBASE] Set error on {self.collection_name}/{self.id}: {e}")

    def update(self, data):
        self.set(data, merge=True)

    def delete(self):
        self._store.delete_cached(self.collection_name, self.id)
        try:
            requests.delete(self.url, timeout=5)
            print(f"🔥 [FIREBASE RTDB] Deleted /{self.collection_name}/{self.id}")
        except Exception as e:
            print(f"⚠️ [FIREBASE] Delete error on {self.collection_name}/{self.id}: {e}")


class RESTCollection:
    def __init__(self, store, name):
        self._store = store
        self.name = name

    def document(self, doc_id=None):
        if not doc_id:
            doc_id = str(uuid.uuid4()).replace('-', '')[:16]
        return RESTDocumentRef(self._store, self.name, str(doc_id))

    def where(self, field, op, val):
        docs = self._get_all()
        matches = []
        for d in docs:
            field_val = d.to_dict().get(field)
            if op in ('==', 'equal'):
                if field_val == val or str(field_val) == str(val):
                    matches.append(d)
        return MemoryQuery(matches)

    def add(self, data):
        doc_id = str(uuid.uuid4()).replace('-', '')[:16]
        ref = self.document(doc_id)
        ref.set(data)
        return ref

    def _get_all(self):
        docs = []
        try:
            if USE_RTDB:
                url = f"{FIREBASE_DATABASE_URL}/{self.name}.json"
                r = requests.get(url, timeout=5)
                if r.status_code == 200 and r.text != 'null':
                    json_data = r.json()
                    if isinstance(json_data, dict):
                        for d_id, data in json_data.items():
                            if isinstance(data, dict):
                                self._store.set_cached(self.name, d_id, data)
                                docs.append(MemoryDoc(d_id, data))
                        return docs
            else:
                url = f"{REST_BASE_URL}/{self.name}?key={FIREBASE_API_KEY}"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    raw_docs = r.json().get('documents', [])
                    for rd in raw_docs:
                        name_parts = rd.get('name', '').split('/')
                        d_id = name_parts[-1] if name_parts else 'unknown'
                        fields = rd.get('fields', {})
                        data = {k: firestore_to_py(v) for k, v in fields.items()}
                        self._store.set_cached(self.name, d_id, data)
                        docs.append(MemoryDoc(d_id, data))
                    return docs
        except Exception as e:
            print(f"⚠️ [FIREBASE] List error on {self.name}: {e}")
        cached_coll = self._store._cache.get(self.name, {})
        return [MemoryDoc(k, v) for k, v in cached_coll.items()]

    def get(self):
        return self._get_all()

    def list_documents(self):
        docs = self._get_all()
        return [RESTDocumentRef(self._store, self.name, d.id) for d in docs]


class ResilientRESTFirestore:
    def __init__(self):
        self._cache = {}

    def get_cached(self, collection, doc_id):
        return self._cache.get(collection, {}).get(str(doc_id))

    def set_cached(self, collection, doc_id, data):
        if collection not in self._cache:
            self._cache[collection] = {}
        self._cache[collection][str(doc_id)] = data

    def delete_cached(self, collection, doc_id):
        if collection in self._cache:
            self._cache[collection].pop(str(doc_id), None)

    def collection(self, name):
        return RESTCollection(self, name)


db = ResilientRESTFirestore()
if USE_RTDB:
    print(f"🔥 [FIREBASE] Realtime Database ready at '{FIREBASE_DATABASE_URL}'")
else:
    print(f"🔥 [FIREBASE] REST Firestore client ready for project '{FIREBASE_PROJECT_ID}'")


# --- AUTH HELPERS ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        doc = db.collection('users').document(str(user_id)).get()
        if doc.exists:
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            return user_data
    except Exception as e:
        print(f"⚠️ [AUTH] Error: {e}")
    return None


# --- FAVICON ---
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.svg', mimetype='image/svg+xml')


# --- PWA ROUTES ---
@app.route('/manifest.json')
def manifest():
    return send_from_directory(app.root_path, 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory(app.root_path, 'sw.js', mimetype='application/javascript')


# --- AUTH ROUTES ---

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user_id"):
        role = session.get("role", "patient")
        if role in ("caregiver", "doctor"):
            return redirect(url_for("caregiver_dashboard"))
        return redirect(url_for("dashboard"))
    
    # Patients CANNOT self-register — they must be added by a caregiver
    role = request.args.get("role", "caregiver")
    if role == "patient":
        return redirect(url_for("login_pin"))
    if role not in ("caregiver", "doctor"):
        role = "caregiver"
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", role)
        if role not in ("caregiver", "doctor"):
            role = "caregiver"

        errors = []
        if not name or len(name) < 2:
            errors.append("Name must be at least 2 characters.")
        if not email or "@" not in email:
            errors.append("Please enter a valid email address.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            return render_template("signup.html", errors=errors, name=name, email=email, role=role)

        # Check if email already registered
        email_query = db.collection('users').where('email', '==', email).limit(1).get()
        if len(email_query) > 0:
            return render_template("signup.html", errors=["Email already registered."], name=name, email=email, role=role)

        # Create caregiver/doctor account
        pw_hash = generate_password_hash(password)
        user_ref = db.collection('users').document()
        user_data = {
            'name': name,
            'email': email,
            'password_hash': pw_hash,
            'role': role,
            'created_at': time.time()
        }
        user_ref.set(user_data)
        user_id = user_ref.id

        session["user_id"] = user_id
        session["name"] = name
        session["email"] = email
        session["role"] = role
        session.modified = True

        print(f"🔥 [AUTH] New {role} registered: {name} (id={user_id})")
        return redirect(url_for("caregiver_dashboard"))

    return render_template("signup.html", errors=[], name="", email="", role=role)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        users = db.collection('users').where('email', '==', email).limit(1).get()
        if len(users) == 0:
            return render_template("login.html", error="Invalid email or password.", email=email)

        user_doc = users[0]
        user_data = user_doc.to_dict()
        
        if not check_password_hash(user_data.get("password_hash", ""), password):
            return render_template("login.html", error="Invalid email or password.", email=email)

        session["user_id"] = user_doc.id
        session["name"] = user_data.get("name")
        session["email"] = user_data.get("email")
        session["role"] = user_data.get("role", "patient")
        session.modified = True

        # Load patient profile if exists
        if user_data.get("patient_profile_json"):
            try:
                session["patient_profile"] = json.loads(user_data["patient_profile_json"])
            except:
                pass
        
        # Store linked patient ID for caregiver/doctor
        if user_data.get("linked_patient_id"):
            session["linked_patient_id"] = user_data["linked_patient_id"]
        
        # Store patient code for patients
        if user_data.get("patient_code"):
            session["patient_code"] = user_data["patient_code"]

        print(f"🔥 [AUTH] Login: {user_data.get('name')} ({user_data.get('role')})")
        
        role = user_data.get("role", "patient")
        if role == 'caregiver':
            return redirect(url_for("caregiver_dashboard"))
        elif role == 'doctor':
            return redirect(url_for("doctor_dashboard"))
        return redirect(url_for("dashboard"))

    return render_template("login.html", error=None, email="")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# --- CAREGIVER: ADD PATIENT SYSTEM ---

@app.route("/api/add-patient", methods=["POST"])
@login_required
def api_add_patient():
    """Caregiver creates a patient account with all profile details + PIN."""
    if session.get("role") not in ("caregiver", "doctor"):
        return jsonify({"error": "Only caregivers can add patients"}), 403
    
    caregiver_id = session["user_id"]
    data = request.json or {}
    
    patient_name = data.get("patient_name", "").strip()
    if not patient_name or len(patient_name) < 2:
        return jsonify({"error": "Patient name must be at least 2 characters"}), 400
    
    # Generate 4-digit PIN and unique patient code
    pin = ''.join(random.choices(string.digits, k=4))
    patient_code = generate_patient_code()
    
    # Build patient profile from caregiver-provided data
    profile = {
        "patient_name": patient_name,
        "age": int(data.get("age", 70)),
        "gender": data.get("gender", "male"),
        "region": data.get("region", "Assam"),
        "language": data.get("language", "en"),
        "dementia_stage": data.get("dementia_stage", "mild"),
        "caregiver_name": session.get("name", ""),
        "caregiver_email": session.get("email", ""),
        "caregiver_relationship": data.get("caregiver_relationship", "Family"),
        "doctor_name": data.get("doctor_name", ""),
        "doctor_email": data.get("doctor_email", ""),
        "alerts_enabled": True,
        "daily_reports": True,
        "sos_enabled": True,
    }
    
    # Generate unique invite token
    token = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    base_url = request.host_url.rstrip("/")
    invite_link = f"{base_url}/join/{token}"
    
    # Create patient account in Firebase
    user_ref = db.collection('users').document()
    user_data = {
        'name': patient_name,
        'email': f"patient_{patient_code.lower()}@neurolearn.care",
        'password_hash': generate_password_hash(pin),
        'pin': pin,
        'role': 'patient',
        'patient_code': patient_code,
        'linked_caregiver_id': caregiver_id,
        'patient_profile_json': json.dumps(profile),
        'patient_name': patient_name,
        'dementia_stage': profile["dementia_stage"],
        'created_at': time.time(),
        'created_via': 'caregiver_added',
        'invite_token': token,
        'needs_minicog': True  # Patient still needs to complete Mini-Cog
    }
    user_ref.set(user_data)
    patient_id = user_ref.id
    
    # Store invite token
    db.collection('invites').document(token).set({
        'token': token,
        'caregiver_id': caregiver_id,
        'caregiver_name': session.get("name", "Caregiver"),
        'caregiver_email': session.get("email", ""),
        'patient_id': patient_id,
        'patient_name': patient_name,
        'pin': pin,
        'created_at': time.time(),
        'used': False
    })
    
    # Link caregiver to this patient
    db.collection('users').document(str(caregiver_id)).update({
        'linked_patient_id': patient_id,
        'linked_patient_name': patient_name,
        'patient_pin': pin
    })
    
    # Update caregiver session
    session["linked_patient_id"] = patient_id
    session.modified = True
    
    print(f"👴 [ADD-PATIENT] Caregiver {session.get('name')} added patient '{patient_name}' (PIN: {pin}, token: {token})")
    
    return jsonify({
        "success": True,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "pin": pin,
        "patient_code": patient_code,
        "invite_link": invite_link,
        "token": token
    })


@app.route("/api/generate-invite", methods=["POST"])
@login_required
def generate_invite():
    """Generate a new invite link for the currently linked patient (re-invite)."""
    if session.get("role") not in ("caregiver", "doctor"):
        return jsonify({"error": "Only caregivers can generate invite links"}), 403
    
    caregiver_id = session["user_id"]
    linked_patient_id = session.get("linked_patient_id")
    
    # Get patient info if linked
    patient_name = "Patient"
    pin = ""
    if linked_patient_id:
        try:
            p_doc = db.collection('users').document(str(linked_patient_id)).get()
            if p_doc.exists:
                p_data = p_doc.to_dict()
                patient_name = p_data.get('patient_name', p_data.get('name', 'Patient'))
                pin = p_data.get('pin', '')
        except:
            pass
    
    # Generate new invite token
    token = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    base_url = request.host_url.rstrip("/")
    invite_link = f"{base_url}/join/{token}"
    
    db.collection('invites').document(token).set({
        'token': token,
        'caregiver_id': caregiver_id,
        'caregiver_name': session.get("name", "Caregiver"),
        'caregiver_email': session.get("email", ""),
        'patient_id': linked_patient_id,
        'patient_name': patient_name,
        'pin': pin,
        'created_at': time.time(),
        'used': False
    })
    
    print(f"🔗 [INVITE] New link created by {session.get('name')}: {token}")
    return jsonify({"success": True, "invite_link": invite_link, "token": token})


@app.route("/join/<token>", methods=["GET", "POST"])
def join_via_invite(token):
    """Patient opens invite link and logs in with their 4-digit PIN."""
    
    # Validate invite
    invite_doc = db.collection('invites').document(token).get()
    if not invite_doc.exists:
        return render_template("join_invite.html", token=token, 
                               caregiver_name="", error="Invalid or expired invite link.",
                               patient_name="", mode="invalid")
    
    invite = invite_doc.to_dict()
    caregiver_name = invite.get("caregiver_name", "Your Caregiver")
    patient_name = invite.get("patient_name", "")
    patient_id = invite.get("patient_id")
    correct_pin = invite.get("pin", "")
    
    if request.method == "POST":
        entered_pin = request.form.get("pin", "").strip()
        
        if not entered_pin or len(entered_pin) != 4:
            return render_template("join_invite.html", token=token, caregiver_name=caregiver_name,
                                   patient_name=patient_name, error="Please enter your 4-digit PIN.", mode="pin")
        
        # Verify PIN against invite record or patient record
        pin_valid = False
        if correct_pin and entered_pin == correct_pin:
            pin_valid = True
        elif patient_id:
            # Also check directly on patient document
            try:
                p_doc = db.collection('users').document(str(patient_id)).get()
                if p_doc.exists:
                    stored_pin = p_doc.to_dict().get('pin', '')
                    if entered_pin == stored_pin:
                        pin_valid = True
            except:
                pass
        
        if not pin_valid:
            return render_template("join_invite.html", token=token, caregiver_name=caregiver_name,
                                   patient_name=patient_name, error="Wrong PIN. Please try again.", mode="pin")
        
        # Load patient data
        p_data = {}
        patient_code = ""
        profile = {}
        needs_minicog = True
        if patient_id:
            try:
                p_doc = db.collection('users').document(str(patient_id)).get()
                if p_doc.exists:
                    p_data = p_doc.to_dict()
                    patient_code = p_data.get('patient_code', '')
                    needs_minicog = p_data.get('needs_minicog', True)
                    if p_data.get('patient_profile_json'):
                        profile = json.loads(p_data['patient_profile_json'])
            except:
                pass
        
        # Mark invite as used
        db.collection('invites').document(token).update({'used': True, 'used_at': time.time()})
        
        # Log in the patient
        actual_name = p_data.get('patient_name', p_data.get('name', patient_name))
        session["user_id"] = patient_id
        session["name"] = actual_name
        session["email"] = p_data.get("email", "")
        session["role"] = "patient"
        session["patient_code"] = patient_code
        session["patient_profile"] = profile
        session["patient_name"] = actual_name
        if profile.get("language"):
            session["preferred_language"] = profile["language"]
        session.modified = True
        
        print(f"🔑 [JOIN] Patient '{actual_name}' logged in via invite link")
        
        # If patient still needs Mini-Cog, go to onboarding
        if needs_minicog:
            return redirect(url_for("onboarding"))
        return redirect(url_for("dashboard"))
    
    # GET — show PIN entry form
    return render_template("join_invite.html", token=token, caregiver_name=caregiver_name,
                           patient_name=patient_name, error=None, mode="pin")


@app.route("/login-pin", methods=["GET", "POST"])
def login_pin():
    """PIN-based login for patients (dementia-friendly — just name + 4 digits)."""
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        patient_code = request.form.get("patient_code", "").strip().upper()
        pin = request.form.get("pin", "").strip()
        
        if not patient_code or not pin:
            return render_template("login_pin.html", error="Please enter your code and PIN.")
        
        # Find patient by code
        patients = db.collection('users').where('patient_code', '==', patient_code).limit(1).get()
        if len(patients) == 0:
            return render_template("login_pin.html", error="Patient code not found.")
        
        patient_doc = patients[0]
        patient_data = patient_doc.to_dict()
        
        # Check PIN
        if patient_data.get("pin") != pin:
            return render_template("login_pin.html", error="Wrong PIN. Please try again.")
        
        # Login
        session["user_id"] = patient_doc.id
        session["name"] = patient_data.get("name")
        session["email"] = patient_data.get("email")
        session["role"] = "patient"
        session["patient_code"] = patient_code
        session["patient_name"] = patient_data.get("patient_name") or patient_data.get("name", "Patient")
        
        # Load profile
        profile = {}
        if patient_data.get("patient_profile_json"):
            try:
                profile = json.loads(patient_data["patient_profile_json"])
                session["patient_profile"] = profile
            except:
                pass
        
        # Set preferred_language to patient's assigned language
        patient_lang = profile.get("language") or patient_data.get("language") or "en"
        session["preferred_language"] = patient_lang
        session.modified = True
        
        print(f"🔑 [PIN LOGIN] {patient_data.get('name')} logged in via PIN (lang: {patient_lang})")
        return redirect(url_for("dashboard"))
    
    return render_template("login_pin.html", error=None)


# --- MAIN ROUTES ---

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    if request.method == "POST":
        data = request.json or request.form
        
        step = data.get("step", "info")
        
        if step == "complete":
            # Merge Mini-Cog result into existing profile (set by caregiver)
            profile = session.get("patient_profile", {})
            if not profile:
                # Fallback: load from Firebase if not in session
                try:
                    u_doc = db.collection('users').document(str(session["user_id"])).get()
                    if u_doc.exists and u_doc.to_dict().get('patient_profile_json'):
                        profile = json.loads(u_doc.to_dict()['patient_profile_json'])
                except:
                    pass
            
            # Update only Mini-Cog result; rest of profile was set by caregiver
            profile["minicog_score"] = data.get("minicog_score", {})
            profile["patient_name"] = profile.get("patient_name", session.get("name", "Patient"))
            
            session["patient_profile"] = profile
            session["patient_name"] = profile["patient_name"]
            if profile.get("language"):
                session["preferred_language"] = profile["language"]
            session.modified = True
            
            # Save updated profile to Firebase and mark minicog complete
            user_id = session.get("user_id")
            if user_id:
                db.collection('users').document(str(user_id)).update({
                    'patient_profile_json': json.dumps(profile),
                    'needs_minicog': False
                })
                print(f"🔥 [ONBOARDING] Mini-Cog complete for: {profile['patient_name']}")
            
            return jsonify({"success": True, "redirect": url_for("dashboard")})
        
        elif step == "minicog_words":
            lang = data.get("language") or session.get("preferred_language", "en")
            words = generate_minicog_words(lang)
            session["minicog_words"] = words
            session.modified = True
            return jsonify({"success": True, "words": words})
        
        elif step == "minicog_score":
            words_recalled = int(data.get("words_recalled", 0))
            clock_score = int(data.get("clock_score", 0))
            result = score_minicog(words_recalled, clock_score)
            return jsonify({"success": True, "result": result})
    
    # GET — load patient profile to show their name, generate Mini-Cog words
    profile = session.get("patient_profile", {})
    if not profile:
        try:
            u_doc = db.collection('users').document(str(session["user_id"])).get()
            if u_doc.exists and u_doc.to_dict().get('patient_profile_json'):
                profile = json.loads(u_doc.to_dict()['patient_profile_json'])
                session["patient_profile"] = profile
                session.modified = True
        except:
            pass
    
    lang = profile.get("language") or session.get("preferred_language") or "en"
    minicog_words = generate_minicog_words(lang)
    session["minicog_words"] = minicog_words
    session.modified = True
    
    return render_template("onboarding.html", 
                           name=profile.get("patient_name", session.get("name", "")),
                           profile=profile,
                           minicog_words=minicog_words)




@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    role = session.get("role", "patient")
    
    if role in ("caregiver", "doctor"):
        return redirect(url_for("caregiver_dashboard"))
    
    profile = session.get("patient_profile", {})
    patient_name = profile.get("patient_name", session.get("name", "Patient"))
    
    # Auto-sync user to Firebase RTDB if created during earlier offline session
    try:
        u_doc = db.collection('users').document(str(user_id)).get()
        if not u_doc.exists:
            db.collection('users').document(str(user_id)).set({
                'name': session.get('name', patient_name),
                'email': session.get('email', ''),
                'role': role,
                'patient_code': session.get('patient_code', ''),
                'patient_profile_json': json.dumps(profile) if profile else '',
                'patient_name': patient_name,
                'dementia_stage': profile.get('dementia_stage', 'mild'),
                'created_at': time.time()
            })
    except Exception as e:
        print(f"⚠️ [SYNC] User sync error: {e}")

    # Get daily routine in patient's preferred language
    current_lang = session.get("preferred_language") or profile.get("language") or "en"
    routine = get_daily_routine(current_lang)
    
    # Check game history for today's completions
    game_results = []
    try:
        docs = db.collection('game_results').where('user_id', '==', user_id).get()
        game_results = [d.to_dict() for d in docs]
    except:
        pass
    
    # Today's results
    import datetime
    today = datetime.date.today().isoformat()
    today_results = [g for g in game_results if g.get("date") == today]
    
    # Mark completed exercises
    completed_types = set(g.get("game_type") for g in today_results)
    for item in routine:
        if item["game_type"] in completed_types:
            item["completed"] = True
    
    # Calculate streak
    streak = session.get("streak", 0)
    total_xp = sum(g.get("xp", 0) for g in game_results)
    total_games = len(game_results)
    
    return render_template("dashboard.html",
                           patient_name=patient_name,
                           routine=routine,
                           streak=streak,
                           total_xp=total_xp,
                           total_games=total_games,
                           today_completed=len(today_results),
                           profile=profile)


# --- COGNITIVE GAMES ---

@app.route("/game/<game_type>")
@login_required
def game(game_type):
    if game_type not in ("recognition", "pattern", "bagh-baak"):
        return redirect(url_for("dashboard"))
    
    profile = session.get("patient_profile", {})
    language = session.get("preferred_language") or profile.get("language", "en")
    
    # Get adaptive difficulty
    game_history = session.get("game_history", [])
    difficulty = get_adaptive_difficulty(game_history)
    
    # Bagh-Baak uses its own template
    if game_type == "bagh-baak":
        return render_template("game_bagh.html",
                               difficulty=difficulty,
                               language=language,
                               patient_name=profile.get("patient_name", "Patient"))
    
    return render_template("game.html",
                           game_type=game_type,
                           difficulty=difficulty,
                           language=language,
                           patient_name=profile.get("patient_name", "Patient"))


@app.route("/api/game-data/<game_type>")
@login_required
def api_game_data(game_type):
    """Generate game content via cognitive engine. Uses family photos if available."""
    profile = session.get("patient_profile", {})
    language = session.get("preferred_language") or profile.get("language", "en")
    user_id = session["user_id"]
    
    game_history = session.get("game_history", [])
    difficulty = get_adaptive_difficulty(game_history)
    
    if game_type == "recognition":
        # Fetch uploaded family photos for personalized game
        family_photos = []
        try:
            photo_docs = db.collection('family_photos').where('patient_id', '==', user_id).get()
            family_photos = [d.to_dict() for d in photo_docs]
        except:
            pass
        
        game_data = generate_recognition_game(difficulty, language, family_photos=family_photos)
    elif game_type == "pattern":
        game_data = generate_pattern_game(difficulty, language)
    elif game_type == "bagh-baak":
        # Bagh-Baak is client-side; return config only
        return jsonify({"game_type": "bagh-baak", "difficulty": difficulty})
    else:
        return jsonify({"error": "Unknown game type"}), 400
    
    return jsonify(game_data)


@app.route("/api/game-complete", methods=["POST"])
@login_required
def api_game_complete():
    """Submit game results, update scores, check for alerts."""
    data = request.json
    game_type = data.get("game_type")
    correct = data.get("correct", 0)
    total = data.get("total", 0)
    domain = data.get("domain", "Memory")
    
    # Calculate score
    result = calculate_game_score(correct, total)
    result["game_type"] = game_type
    result["domain"] = domain
    result["date"] = time.strftime("%Y-%m-%d")
    result["timestamp"] = time.time()
    
    # Update session history
    if "game_history" not in session:
        session["game_history"] = []
    session["game_history"].append(result)
    session["total_xp"] = session.get("total_xp", 0) + result["xp"]
    session.modified = True
    
    # Save to Firestore
    user_id = session["user_id"]
    result["user_id"] = user_id
    db.collection('game_results').add(result)
    
    # Check for alerts
    domain_scores = calculate_domain_scores(session.get("game_history", []))
    overall_score = calculate_overall_score(domain_scores)
    
    previous_scores = session.get("previous_domain_scores")
    alerts = check_for_alerts(domain_scores, previous_scores)
    session["previous_domain_scores"] = domain_scores
    session.modified = True
    
    # Send alert emails if needed
    profile = session.get("patient_profile", {})
    caregiver_email = profile.get("caregiver_email")
    if caregiver_email and alerts:
        for alert in alerts:
            if alert["type"] in ("critical", "warning"):
                send_smart_alert(
                    profile.get("patient_name", "Patient"),
                    caregiver_email,
                    alert["type"],
                    alert["message"]
                )
    
    print(f"🎮 [GAME] {game_type} complete: {correct}/{total} = {result['accuracy']}% | XP: {result['xp']}")
    
    return jsonify({
        "success": True,
        "result": result,
        "domain_scores": domain_scores,
        "overall_score": overall_score,
        "alerts": alerts
    })


@app.route("/results")
@login_required
def results():
    last_result = {}
    if session.get("game_history"):
        last_result = session["game_history"][-1]
    
    profile = session.get("patient_profile", {})
    return render_template("results.html",
                           result=last_result,
                           total_xp=session.get("total_xp", 0),
                           patient_name=profile.get("patient_name", "Patient"))


# --- AI MEMORY COMPANION ---

@app.route("/companion")
@login_required
def companion():
    profile = session.get("patient_profile", {})
    lang = session.get("preferred_language") or profile.get("language") or "en"
    p_name = session.get("patient_name") or session.get("name") or profile.get("patient_name", "Patient")
    return render_template("companion.html",
                           patient_name=p_name,
                           language=lang)


@app.route("/api/companion-chat", methods=["POST"])
@login_required
def api_companion_chat():
    """AI Memory Companion — reminiscence therapy chatbot."""
    # Language fallback messages (localized)
    lang_fallbacks = {
        "mr":  "माफ करा, मला नीट कळले नाही. कृपया पुन्हा सांगाल का?",
        "hi":  "माफ कीजिए, मुझे सुनाई नहीं दिया. क्या आप फिर से कह सकते हैं?",
        "as":  "মাফ কৰিব, মই ভালদৰে বুজিব পৰা নাইলোং। আথাই আবাৰ কৰাৱকৈ কব?",
        "bn":  "মাফ করবেন, আমি ঠিকমতো বুঝতে পারিনি। আবার বলবেন কি?",
        "mni": "মাফ করো, আমি ठीकমতো বুঝিনি। আবার বলবে কি?",
        "ta":  "மன்னிக்கவும், எனக்கு சரியாக கேட்கவில்லை. தயவுசெய்து மீண்டும் சொல்லுங்கள்?",
        "en":  "I'm sorry, I had a little trouble there. Could you say that again?"
    }

    try:
        data = request.json
        message = data.get("message", "").strip()
        
        if not message:
            return jsonify({"error": "No message"}), 400
        
        profile = session.get("patient_profile", {})
        patient_name = session.get("patient_name") or session.get("name") or profile.get("patient_name", "Friend")
        age = profile.get("age", 70)
        region = profile.get("region", "India")
        stage = profile.get("dementia_stage", "mild")
        
        # Detect language: session preferred > request body > profile > cookie
        language = (
            session.get("preferred_language")
            or data.get("language")
            or profile.get("language")
            or request.cookies.get("lang")
            or "en"
        )
        if language not in ("en", "hi", "mr", "as", "bn", "mni", "ta"):
            language = "en"
        
        # Build conversation history
        if "companion_history" not in session:
            session["companion_history"] = []
        
        session["companion_history"].append({"role": "user", "content": message})
        
        # Keep last 10 messages for context
        recent_history = session["companion_history"][-10:]
        history_text = "\n".join([f"{'Patient' if m['role']=='user' else 'Companion'}: {m['content']}" for m in recent_history[:-1]])
        
        lang_map = {
            "hi":  "Hindi (हिन्दी)",
            "mr":  "Marathi (मराठी)",
            "as":  "Assamese (অসমীয়া)",
            "bn":  "Bengali (বাংলা)",
            "mni": "Manipuri/Meitei (মৈতৈলোন্)",
            "ta":  "Tamil (தமிழ்)",
            "en":  "English"
        }
        lang_name = lang_map.get(language, "English")
        
        # RAG Context Retrieval: retrieve top relevant caregiver notes & personal facts
        patient_id = session.get("linked_patient_id") or session.get("user_id")
        rag_context = query_care_context(patient_id, message, db=db, top_k=3)
        rag_prompt_fragment = format_context_for_prompt(rag_context)
        
        system_prompt = f"""You are a warm, caring AI Memory Companion for an elderly dementia patient in India.

PATIENT PROFILE:
- Name: {patient_name}
- Age: {age}
- Region: {region}
- Dementia Stage: {stage}
- Language: {lang_name}
{rag_prompt_fragment}

CRITICAL LANGUAGE RULE: You MUST respond ONLY in {lang_name}. Every single word of your response must be in {lang_name}. Do NOT mix languages.

YOUR ROLE (Reminiscence Therapy):
- Be extremely warm, patient, and encouraging
- Ask about childhood memories, family, festivals (Bihu, Diwali, Holi, Ganesh Chaturthi), food, music
- NEVER say "you already told me that" — always respond as if hearing it for the first time
- Keep responses to 2-3 sentences maximum
- Use simple, clear language appropriate for elderly
- If the patient seems confused, gently redirect to a comforting topic
- Occasionally mention cultural elements from {region} (local festivals, foods, landmarks)
- Always end with a gentle follow-up question
- Use warm emoji sparingly (🌸, 😊, 🎵, ☀️)

CONVERSATION HISTORY:
{history_text}"""

        user_prompt = f"Patient says: {message}"
        
        model = os.getenv("COMPANION_MODEL", "groq/compound-mini")
        response = call_llm(system_prompt, user_prompt, model=model)
        response = response.strip().strip('"')
        
        session["companion_history"].append({"role": "assistant", "content": response})
        session.modified = True
        
        # Save conversation to Firebase
        user_id = session.get("user_id")
        if user_id:
            try:
                db.collection('companion_logs').add({
                    'user_id': user_id,
                    'patient_message': message,
                    'ai_response': response,
                    'language': language,
                    'timestamp': time.time()
                })
            except Exception:
                pass
        
        safe_patient = message[:40].encode('ascii', 'replace').decode()
        safe_ai = response[:60].encode('ascii', 'replace').decode()
        print(f"💬 [COMPANION] [{language}] Patient: {safe_patient}... | AI: {safe_ai}...")
        return jsonify({"success": True, "response": response, "language": language, "rag_active": bool(rag_context)})
        
    except Exception as e:
        print(f"✗ [COMPANION] Error: {str(e)}")
        # Return localized fallback
        lang = (
            request.json.get("language") if request.json else None
            or request.cookies.get("lang", "en")
        )
        fallback = lang_fallbacks.get(lang, lang_fallbacks["en"])
        return jsonify({"success": True, "response": fallback, "language": lang})


# --- CAREGIVER NOTES (RAG MEMORY ANCHORS) ---

@app.route("/api/caregiver-notes", methods=["GET", "POST"])
@login_required
def api_caregiver_notes():
    """Get or save caregiver knowledge notes for RAG memory companion."""
    patient_id = session.get("linked_patient_id") or session.get("user_id")
    
    if request.method == "POST":
        data = request.json or {}
        save_caregiver_notes(patient_id, data, db=db)
        print(f"📝 [RAG] Caregiver notes updated for patient {patient_id}")
        return jsonify({"success": True, "message": "Care notes saved & indexed successfully!"})
    
    # GET: Return indexed chunks & raw notes
    chunks = load_patient_chunks(patient_id, db=db)
    raw = {}
    try:
        doc = db.collection("caregiver_notes").document(str(patient_id)).get()
        if doc.exists:
            raw = doc.to_dict().get("raw_notes", {})
    except Exception:
        pass
    return jsonify({"success": True, "chunks": chunks, "raw_notes": raw})



# --- TTS ---

@app.route("/api/tts/speak", methods=["POST"])
def tts_speak():
    """Stream TTS audio for any text."""
    try:
        data = request.get_json(force=True)
        text = (data.get("text") or "").strip()
        lang = data.get("lang", session.get("preferred_language", "en"))
        voice_key = data.get("voice", "standard_female")

        if not text:
            return jsonify({"error": "No text"}), 400

        lang_voice = get_voice_for_language(lang, voice_key)
        voice = lang_voice if lang_voice else "en-US-AriaNeural"

        print(f"[TTS] lang={lang}, voice={voice}, chars={len(text)}")
        audio_stream = generate_chapter_audio_stream(text, voice_id=voice, target_lang=lang)
        return Response(stream_with_context(audio_stream), mimetype="audio/mpeg", direct_passthrough=True)

    except Exception as e:
        print(f"✗ [TTS] Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


# --- HELPER: Get linked patient data ---

def get_linked_patient_data(linked_patient_id):
    """Get patient profile, game results, location, and photos from Firestore."""
    profile = {}
    game_results = []
    last_location = {}
    patient_name = "Patient"
    family_photos = []
    patient_code = ""
    patient_pin = ""
    
    if linked_patient_id:
        try:
            patient_doc = db.collection('users').document(str(linked_patient_id)).get()
            if patient_doc.exists:
                patient_data = patient_doc.to_dict()
                patient_name = patient_data.get('patient_name', patient_data.get('name', 'Patient'))
                patient_code = patient_data.get('patient_code', '')
                patient_pin = patient_data.get('pin', '')
                if patient_data.get('patient_profile_json'):
                    profile = json.loads(patient_data['patient_profile_json'])
        except Exception as e:
            print(f"⚠️ [LINK] Error loading patient: {e}")
        
        try:
            docs = db.collection('game_results').where('user_id', '==', linked_patient_id).get()
            game_results = [d.to_dict() for d in docs]
        except:
            pass
        
        try:
            loc_doc = db.collection('locations').document(str(linked_patient_id)).get()
            if loc_doc.exists:
                loc_data = loc_doc.to_dict()
                last_location = {
                    'lat': loc_data.get('latitude'),
                    'lng': loc_data.get('longitude'),
                    'url': loc_data.get('url'),
                    'timestamp': loc_data.get('timestamp'),
                    'address': f"Lat: {round(loc_data.get('latitude', 0), 4)}, Lng: {round(loc_data.get('longitude', 0), 4)}"
                }
        except:
            pass
        
        try:
            photo_docs = db.collection('family_photos').where('patient_id', '==', linked_patient_id).get()
            family_photos = [d.to_dict() | {'doc_id': d.id} for d in photo_docs]
        except:
            pass
    
    return {
        'profile': profile,
        'patient_name': patient_name,
        'patient_code': patient_code,
        'pin': patient_pin,
        'game_results': game_results,
        'last_location': last_location,
        'family_photos': family_photos,
        'assigned_doctor_name': patient_data.get('assigned_doctor_name', '') if patient_doc and patient_doc.exists else '',
        'assigned_doctor_email': patient_data.get('assigned_doctor_email', '') if patient_doc and patient_doc.exists else '',
        'assigned_doctor_id': patient_data.get('assigned_doctor_id', '') if patient_doc and patient_doc.exists else ''
    }


# --- CAREGIVER DASHBOARD ---

@app.route("/caregiver-dashboard")
@login_required
def caregiver_dashboard():
    user_id = session["user_id"]
    role = session.get("role", "patient")
    
    if role not in ("caregiver", "doctor"):
        return redirect(url_for("dashboard"))
    
    # Auto-sync user to Firebase
    try:
        cg_doc = db.collection('users').document(str(user_id)).get()
        if not cg_doc.exists:
            db.collection('users').document(str(user_id)).set({
                'name': session.get('name', 'Caregiver'),
                'email': session.get('email', ''),
                'role': role,
                'linked_patient_id': session.get('linked_patient_id', ''),
                'created_at': time.time()
            })
    except Exception as e:
        print(f"⚠️ [SYNC] Caregiver sync error: {e}")

    linked_patient_id = session.get("linked_patient_id")
    assigned_doctor_name = ""
    assigned_doctor_email = ""
    patient_code = ""
    patient_pin = ""
    
    if linked_patient_id:
        patient_data = get_linked_patient_data(linked_patient_id)
        profile = patient_data['profile']
        patient_name = patient_data['patient_name']
        patient_code = patient_data.get('patient_code', '')
        patient_pin = patient_data.get('pin', '')
        game_results = patient_data['game_results']
        last_location = patient_data['last_location']
        family_photos = patient_data['family_photos']
        assigned_doctor_name = patient_data.get('assigned_doctor_name', '')
        assigned_doctor_email = patient_data.get('assigned_doctor_email', '')
    else:
        # Caregiver not linked yet
        profile = session.get("patient_profile", {})
        patient_name = profile.get("patient_name", session.get("name", "Patient"))
        patient_code = profile.get("patient_code", "")
        patient_pin = ""
        game_results = []
        last_location = {}
        family_photos = []
    
    # Calculate domain scores
    domain_scores = calculate_domain_scores(game_results)
    overall_score = calculate_overall_score(domain_scores)
    
    # Get alerts
    alerts = check_for_alerts(domain_scores, None)
    
    # Stats
    total_games = len(game_results)
    total_xp = sum(g.get("xp", 0) for g in game_results)
    avg_accuracy = round(sum(g.get("accuracy", 0) for g in game_results) / max(1, total_games))
    streak = 0
    
    return render_template("caregiver_dashboard.html",
                           patient_name=patient_name,
                           patient_code=patient_code,
                           patient_pin=patient_pin,
                           profile=profile,
                           domain_scores=domain_scores,
                           overall_score=overall_score,
                           alerts=alerts,
                           total_games=total_games,
                           total_xp=total_xp,
                           avg_accuracy=avg_accuracy,
                           streak=streak,
                           game_results=game_results[-20:],
                           last_location=last_location,
                           family_photos=family_photos,
                           linked_patient_id=linked_patient_id,
                           assigned_doctor_name=assigned_doctor_name,
                           assigned_doctor_email=assigned_doctor_email,
                           role=role)


# --- DOCTOR DASHBOARD ---

@app.route("/doctor-dashboard")
@login_required
def doctor_dashboard():
    role = session.get("role", "patient")
    linked_patient_id = session.get("linked_patient_id")
    
    # Auto-resolve assigned patient from DB if not yet in session
    if not linked_patient_id:
        try:
            doc_user = db.collection('users').document(str(session["user_id"])).get()
            if doc_user.exists and doc_user.to_dict().get("linked_patient_id"):
                linked_patient_id = doc_user.to_dict()["linked_patient_id"]
                session["linked_patient_id"] = linked_patient_id
                session.modified = True
            else:
                assigned_patients = db.collection('users').where('assigned_doctor_id', '==', str(session["user_id"])).limit(1).get()
                if assigned_patients:
                    linked_patient_id = assigned_patients[0].id
                    session["linked_patient_id"] = linked_patient_id
                    session.modified = True
        except Exception as e:
            print(f"[DOCTOR] Auto-resolve error: {e}")
    
    if linked_patient_id:
        patient_data = get_linked_patient_data(linked_patient_id)
        profile = patient_data['profile']
        patient_name = patient_data['patient_name']
        game_results = patient_data['game_results']
        last_location = patient_data['last_location']
    else:
        profile = {}
        patient_name = "No Patient Linked"
        game_results = []
        last_location = {}
    
    domain_scores = calculate_domain_scores(game_results)
    overall_score = calculate_overall_score(domain_scores)
    alerts = check_for_alerts(domain_scores, None)
    
    total_games = len(game_results)
    avg_accuracy = round(sum(g.get("accuracy", 0) for g in game_results) / max(1, total_games))
    
    return render_template("doctor_dashboard.html",
                           patient_name=patient_name,
                           patient_code=patient_data.get('patient_code', '') if linked_patient_id else '',
                           profile=profile,
                           domain_scores=domain_scores,
                           overall_score=overall_score,
                           alerts=alerts,
                           total_games=total_games,
                           avg_accuracy=avg_accuracy,
                           game_results=game_results[-20:],
                           last_location=last_location,
                           linked_patient_id=linked_patient_id,
                           role=role)


# --- FAMILY PHOTO MANAGEMENT ---

@app.route("/api/upload-family-photo", methods=["POST"])
@login_required
def api_upload_family_photo():
    """Caregiver uploads a family photo with name and relationship."""
    person_name = request.form.get("person_name", "").strip()
    relationship = request.form.get("relationship", "").strip()
    
    if not person_name:
        return jsonify({"error": "Person name is required"}), 400
    
    file = request.files.get("photo")
    if not file or not allowed_file(file.filename):
        return jsonify({"error": "Please upload a valid image (PNG, JPG, GIF, WEBP)"}), 400
    
    linked_patient_id = session.get("linked_patient_id")
    if not linked_patient_id:
        return jsonify({"error": "No patient linked"}), 400
    
    # Upload to Cloudinary if configured, else save locally
    filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
    cloud_url = upload_image(file, filename, folder=f"neurolearn/{linked_patient_id}")
    
    if cloud_url:
        photo_url = cloud_url
    else:
        patient_dir = os.path.join(UPLOAD_FOLDER, str(linked_patient_id))
        os.makedirs(patient_dir, exist_ok=True)
        filepath = os.path.join(patient_dir, filename)
        file.save(filepath)
        photo_url = f"/static/uploads/{linked_patient_id}/{filename}"
    
    # Save metadata to Firestore
    db.collection('family_photos').add({
        'patient_id': linked_patient_id,
        'uploaded_by': session["user_id"],
        'person_name': person_name,
        'relationship': relationship,
        'photo_url': photo_url,
        'filename': filename,
        'uploaded_at': time.time()
    })
    
    print(f"📸 [PHOTO] Uploaded: {person_name} ({relationship}) for patient {linked_patient_id}")
    return jsonify({"success": True, "photo_url": photo_url, "person_name": person_name})


@app.route("/api/delete-family-photo", methods=["POST"])
@login_required
def api_delete_family_photo():
    """Delete a family photo."""
    doc_id = request.json.get("doc_id")
    if doc_id:
        try:
            photo_doc = db.collection('family_photos').document(doc_id).get()
            if photo_doc.exists:
                photo_data = photo_doc.to_dict()
                # Delete file
                filepath = os.path.join(app.root_path, photo_data.get('photo_url', '').lstrip('/'))
                if os.path.exists(filepath):
                    os.remove(filepath)
                # Delete Firestore doc
                db.collection('family_photos').document(doc_id).delete()
                return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Missing doc_id"}), 400


@app.route("/api/family-photos")
@login_required
def api_family_photos():
    """Get all family photos for a patient."""
    linked_patient_id = session.get("linked_patient_id", session.get("user_id"))
    photos = []
    try:
        docs = db.collection('family_photos').where('patient_id', '==', linked_patient_id).get()
        photos = [d.to_dict() | {'doc_id': d.id} for d in docs]
    except:
        pass
    return jsonify({"photos": photos})


@app.route("/api/patient-pin")
@login_required
def api_patient_pin():
    """Return the linked patient's PIN for caregiver dashboard display."""
    if session.get("role") not in ("caregiver", "doctor"):
        return jsonify({"error": "Forbidden"}), 403
    linked_patient_id = session.get("linked_patient_id")
    if not linked_patient_id:
        return jsonify({"error": "No patient linked"}), 404
    try:
        p_doc = db.collection('users').document(str(linked_patient_id)).get()
        if p_doc.exists:
            p_dict = p_doc.to_dict()
            pin = p_dict.get('pin', '')
            patient_code = p_dict.get('patient_code', '')
            return jsonify({"success": True, "pin": pin, "patient_code": patient_code})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Patient not found"}), 404


@app.route("/api/doctors")
@login_required
def api_doctors():
    """List all registered doctors for caregiver to pick from."""
    if session.get("role") not in ("caregiver", "doctor"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        docs = db.collection('users').where('role', '==', 'doctor').get()
        doctors = []
        for d in docs:
            doc_data = d.to_dict()
            doctors.append({
                "id": d.id,
                "name": doc_data.get("name", "Dr. Unknown"),
                "email": doc_data.get("email", ""),
                "specialization": doc_data.get("specialization", ""),
                "hospital": doc_data.get("hospital", "")
            })
        return jsonify({"success": True, "doctors": doctors})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/assign-doctor", methods=["POST"])
@login_required
def api_assign_doctor():
    """Caregiver assigns a doctor to the linked patient."""
    if session.get("role") not in ("caregiver", "doctor"):
        return jsonify({"error": "Only caregivers can assign doctors"}), 403

    data = request.json or {}
    doctor_id = data.get("doctor_id", "").strip()
    if not doctor_id:
        return jsonify({"error": "doctor_id is required"}), 400

    linked_patient_id = session.get("linked_patient_id")
    if not linked_patient_id:
        return jsonify({"error": "No patient linked to this caregiver"}), 400

    # Get doctor details
    try:
        doc_doc = db.collection('users').document(doctor_id).get()
        if not doc_doc.exists or doc_doc.to_dict().get("role") != "doctor":
            return jsonify({"error": "Doctor not found"}), 404
        doctor_data = doc_doc.to_dict()
        doctor_name = doctor_data.get("name", "Doctor")
        doctor_email = doctor_data.get("email", "")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Link doctor to patient (on patient doc)
    try:
        db.collection('users').document(str(linked_patient_id)).update({
            'assigned_doctor_id': doctor_id,
            'assigned_doctor_name': doctor_name,
            'assigned_doctor_email': doctor_email
        })
    except Exception as e:
        return jsonify({"error": f"Failed to update patient: {e}"}), 500

    # Link patient to doctor (on doctor doc)
    try:
        db.collection('users').document(doctor_id).update({
            'linked_patient_id': linked_patient_id,
            'linked_patient_name': session.get("patient_profile", {}).get("patient_name", "Patient")
        })
    except Exception as e:
        print(f"⚠️ [ASSIGN-DOCTOR] Could not update doctor doc: {e}")

    # Update patient profile with doctor email for SOS / reports
    try:
        p_doc = db.collection('users').document(str(linked_patient_id)).get()
        if p_doc.exists:
            p_data = p_doc.to_dict()
            profile_json = p_data.get('patient_profile_json', '{}')
            try:
                profile = json.loads(profile_json)
            except:
                profile = {}
            profile['doctor_name'] = doctor_name
            profile['doctor_email'] = doctor_email
            db.collection('users').document(str(linked_patient_id)).update({
                'patient_profile_json': json.dumps(profile)
            })
    except Exception as e:
        print(f"⚠️ [ASSIGN-DOCTOR] Profile update error: {e}")

    print(f"🩺 [ASSIGN-DOCTOR] Doctor '{doctor_name}' assigned to patient (linked_patient_id={linked_patient_id})")
    return jsonify({
        "success": True,
        "doctor_name": doctor_name,
        "doctor_email": doctor_email,
        "doctor_id": doctor_id
    })


# --- LINK PATIENT (for caregivers/doctors who didn't link at signup) ---

@app.route("/api/link-patient", methods=["POST"])
@login_required
def api_link_patient():
    """Link a caregiver or doctor to a patient via patient code."""
    data = request.json
    patient_code = data.get("patient_code", "").strip().upper()
    
    if not patient_code:
        return jsonify({"error": "Patient code is required"}), 400
    
    patient_docs = db.collection('users').where('patient_code', '==', patient_code).limit(1).get()
    if len(patient_docs) == 0:
        return jsonify({"error": f"Patient code '{patient_code}' not found"}), 404
    
    patient_id = patient_docs[0].id
    patient_data = patient_docs[0].to_dict()
    
    # Save link
    session["linked_patient_id"] = patient_id
    session.modified = True
    
    db.collection('users').document(str(session["user_id"])).update({
        'linked_patient_id': patient_id
    })
    
    print(f"🔗 [LINK] {session.get('name')} linked to patient {patient_data.get('name')} (code={patient_code})")
    return jsonify({
        "success": True,
        "patient_name": patient_data.get('patient_name', patient_data.get('name', 'Patient')),
        "patient_id": patient_id
    })


# --- COGNITIVE REPORT ---

@app.route("/report")
@login_required
def cognitive_report():
    user_id = session.get("user_id")
    role = session.get("role", "patient")
    target_patient_id = request.args.get("patient_id") or session.get("linked_patient_id")
    
    profile = {}
    patient_name = "Patient"
    game_results = []
    patient_code = ""
    
    if role in ("caregiver", "doctor") and target_patient_id:
        patient_data = get_linked_patient_data(target_patient_id)
        profile = patient_data.get('profile', {})
        patient_name = patient_data.get('patient_name', 'Patient')
        game_results = patient_data.get('game_results', [])
        patient_code = patient_data.get('patient_code', '')
    else:
        # Patient view
        profile = session.get("patient_profile", {})
        patient_name = profile.get("patient_name") or session.get("name", "Patient")
        patient_code = profile.get("patient_code", "")
        
        # If profile missing from session, fetch from Firestore
        if not profile:
            try:
                u_doc = db.collection('users').document(str(user_id)).get()
                if u_doc.exists:
                    u_data = u_doc.to_dict()
                    patient_name = u_data.get('patient_name', u_data.get('name', 'Patient'))
                    patient_code = u_data.get('patient_code', '')
                    if u_data.get('patient_profile_json'):
                        profile = json.loads(u_data['patient_profile_json'])
            except Exception as e:
                print(f"⚠️ [REPORT] User fetch error: {e}")
        
        # Load game results from Firestore
        try:
            docs = db.collection('game_results').where('user_id', '==', user_id).get()
            game_results = [d.to_dict() for d in docs]
        except Exception as e:
            print(f"⚠️ [REPORT] Game results fetch error: {e}")
        
        # Also combine with any game results from current session
        session_games = session.get("game_history", [])
        if session_games:
            existing_ts = {g.get("timestamp") for g in game_results if g.get("timestamp")}
            for sg in session_games:
                if sg.get("timestamp") not in existing_ts:
                    game_results.append(sg)
    
    domain_scores = calculate_domain_scores(game_results)
    overall_score = calculate_overall_score(domain_scores)
    
    total_games = len(game_results)
    avg_accuracy = round(sum(g.get("accuracy", 0) for g in game_results) / max(1, total_games)) if total_games > 0 else 0
    
    return render_template("cognitive_report.html",
                           patient_name=patient_name,
                           patient_code=patient_code,
                           profile=profile,
                           domain_scores=domain_scores,
                           overall_score=overall_score,
                           total_games=total_games,
                           avg_accuracy=avg_accuracy,
                           game_results=game_results)


@app.route("/api/email-report", methods=["POST"])
@login_required
def api_email_report():
    """Email cognitive report to doctor."""
    user_id = session.get("user_id")
    role = session.get("role", "patient")
    target_patient_id = request.args.get("patient_id") or session.get("linked_patient_id")
    
    profile = {}
    patient_name = "Patient"
    game_results = []
    
    if role in ("caregiver", "doctor") and target_patient_id:
        patient_data = get_linked_patient_data(target_patient_id)
        profile = patient_data.get('profile', {})
        patient_name = patient_data.get('patient_name', 'Patient')
        game_results = patient_data.get('game_results', [])
    else:
        profile = session.get("patient_profile", {})
        patient_name = profile.get("patient_name") or session.get("name", "Patient")
        try:
            docs = db.collection('game_results').where('user_id', '==', user_id).get()
            game_results = [d.to_dict() for d in docs]
        except:
            pass
        session_games = session.get("game_history", [])
        if session_games:
            existing_ts = {g.get("timestamp") for g in game_results if g.get("timestamp")}
            for sg in session_games:
                if sg.get("timestamp") not in existing_ts:
                    game_results.append(sg)
                    
    doctor_email = profile.get("doctor_email")
    if not doctor_email:
        return jsonify({"error": "No doctor email configured"}), 400
    
    domain_scores = calculate_domain_scores(game_results)
    overall_score = calculate_overall_score(domain_scores)
    
    report_data = {
        "domain_scores": domain_scores,
        "overall_score": overall_score,
        "period": time.strftime("%B %Y"),
        "location": session.get("last_location", {}).get("address", "Not shared")
    }
    
    success = send_doctor_report(
        patient_name,
        doctor_email,
        report_data
    )
    
    return jsonify({"success": success})


# --- SOS & LOCATION ---

@app.route("/api/sos-alert", methods=["POST"])
@login_required
def api_sos_alert():
    """Emergency SOS — email caregiver + doctor + share location."""
    try:
        data = request.json
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        
        location_url = None
        if latitude and longitude:
            location_url = f"https://www.google.com/maps?q={latitude},{longitude}"
            session["last_location"] = {
                "lat": latitude,
                "lng": longitude,
                "url": location_url,
                "timestamp": time.time(),
                "address": f"Lat: {latitude}, Lng: {longitude}"
            }
            session.modified = True
        
        profile = session.get("patient_profile", {})
        patient_name = profile.get("patient_name", session.get("name", "Patient"))
        caregiver_email = profile.get("caregiver_email")
        doctor_email = profile.get("doctor_email")
        patient_id = session.get("user_id")

        # Robust Caregiver Email Resolution Fix
        if not caregiver_email and patient_id:
            try:
                p_doc = db.collection('users').document(str(patient_id)).get()
                if p_doc.exists:
                    p_data = p_doc.to_dict()
                    # 1. Check linked caregiver id on patient doc
                    cg_id = p_data.get("linked_caregiver_id")
                    if cg_id:
                        cg_doc = db.collection('users').document(str(cg_id)).get()
                        if cg_doc.exists:
                            caregiver_email = cg_doc.to_dict().get("email")
                    # 2. Check invite record
                    token = p_data.get("invite_token")
                    if not caregiver_email and token:
                        inv = db.collection('invites').document(token).get()
                        if inv.exists:
                            caregiver_email = inv.to_dict().get("caregiver_email")
                
                # 3. Check any caregiver who has linked this patient
                if not caregiver_email:
                    cg_query = db.collection('users').where('linked_patient_id', '==', str(patient_id)).get()
                    if len(cg_query) > 0:
                        caregiver_email = cg_query[0].to_dict().get("email")
            except Exception as ex:
                print(f"⚠️ [SOS] Error resolving caregiver email: {ex}")

        sent = False
        if caregiver_email:
            sent = send_sos_alert(patient_name, caregiver_email, doctor_email, location_url)
            print(f"📧 [SOS] Email sent to caregiver: {caregiver_email}")
        else:
            print(f"⚠️ [SOS] No caregiver email found for patient {patient_name}")
        
        # Log SOS event
        db.collection('sos_logs').add({
            'user_id': session.get("user_id"),
            'patient_name': patient_name,
            'location_url': location_url or "Not available",
            'timestamp': time.time()
        })
        
        print(f"🆘 [SOS] Alert triggered by {patient_name} | Location: {location_url}")
        
        return jsonify({
            "success": True,
            "email_sent": sent,
            "location_shared": bool(location_url),
            "message": "Help is on the way! Your caregiver has been notified."
        })
    except Exception as e:
        print(f"✗ [SOS] Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/share-location", methods=["POST"])
@login_required
def api_share_location():
    """Share patient's live location."""
    data = request.json
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    
    if latitude and longitude:
        location_url = f"https://www.google.com/maps?q={latitude},{longitude}"
        session["last_location"] = {
            "lat": latitude,
            "lng": longitude,
            "url": location_url,
            "timestamp": time.time(),
            "address": f"Lat: {round(latitude, 4)}, Lng: {round(longitude, 4)}"
        }
        session.modified = True
        
        # Save to Firestore
        db.collection('locations').document(str(session["user_id"])).set({
            'latitude': latitude,
            'longitude': longitude,
            'url': location_url,
            'timestamp': time.time()
        })
        
        return jsonify({"success": True, "url": location_url})
    
    return jsonify({"error": "No location data"}), 400


@app.route("/api/patient-live-location")
@login_required
def api_patient_live_location():
    """Retrieve live location for caregiver or doctor dashboard map."""
    linked_patient_id = session.get("linked_patient_id")
    role = session.get("role", "patient")

    # If caregiver/doctor and not in session, check DB
    if not linked_patient_id and role in ("caregiver", "doctor"):
        try:
            u_doc = db.collection('users').document(str(session.get("user_id"))).get()
            if u_doc.exists:
                linked_patient_id = u_doc.to_dict().get("linked_patient_id")
                if linked_patient_id:
                    session["linked_patient_id"] = linked_patient_id
                    session.modified = True
        except Exception as e:
            print(f"⚠️ [MAP] Lookup linked patient error: {e}")

    target_id = linked_patient_id if linked_patient_id else session.get("user_id")

    # 1. Try target patient doc
    data = None
    if target_id:
        try:
            loc_doc = db.collection('locations').document(str(target_id)).get()
            if loc_doc.exists:
                data = loc_doc.to_dict()
        except Exception as e:
            print(f"⚠️ [MAP] Error fetching target location: {e}")

    # 2. If not found and user is caregiver/doctor, fallback to the latest active location in DB
    if (not data or data.get("latitude") is None) and role in ("caregiver", "doctor"):
        try:
            all_locs = db.collection('locations').get()
            if all_locs:
                # Sort by timestamp descending
                sorted_locs = sorted(all_locs, key=lambda d: d.to_dict().get('timestamp', 0), reverse=True)
                if sorted_locs and sorted_locs[0].to_dict().get('latitude') is not None:
                    data = sorted_locs[0].to_dict()
        except Exception as e:
            print(f"⚠️ [MAP] Fallback location query error: {e}")

    # 3. Session fallback
    if not data or data.get("latitude") is None:
        session_loc = session.get("last_location")
        if session_loc and session_loc.get("lat"):
            data = {
                "latitude": session_loc.get("lat"),
                "longitude": session_loc.get("lng"),
                "url": session_loc.get("url"),
                "timestamp": session_loc.get("timestamp", time.time())
            }

    if data and data.get("latitude") is not None and data.get("longitude") is not None:
        lat = float(data.get("latitude"))
        lng = float(data.get("longitude"))
        ts = data.get("timestamp", time.time())
        diff_sec = max(0, int(time.time() - ts))
        if diff_sec < 10:
            time_str = "Just now"
        elif diff_sec < 60:
            time_str = f"{diff_sec}s ago"
        elif diff_sec < 3600:
            time_str = f"{diff_sec // 60}m ago"
        else:
            time_str = f"{diff_sec // 3600}h ago"

        return jsonify({
            "success": True,
            "lat": lat,
            "lng": lng,
            "url": data.get("url") or f"https://www.google.com/maps?q={lat},{lng}",
            "timestamp": ts,
            "time_ago": time_str,
            "address": f"Lat: {round(lat, 4)}, Lng: {round(lng, 4)}"
        })

    return jsonify({"error": "Location not yet shared"}), 404


# --- COGNITIVE TRENDS API ---

@app.route("/api/cognitive-trends")
@login_required
def api_cognitive_trends():
    """Get cognitive trend data for charts."""
    role = session.get("role", "patient")
    linked_patient_id = session.get("linked_patient_id")
    
    # If caregiver/doctor, query patient's results
    if role in ("caregiver", "doctor"):
        target_id = linked_patient_id
    else:
        target_id = session.get("user_id")

    game_results = []
    try:
        if target_id:
            docs = db.collection('game_results').where('user_id', '==', target_id).get()
            game_results = [d.to_dict() for d in docs]
        
        # Fallback if unlinked or in test mode
        if not game_results and role in ("caregiver", "doctor"):
            all_results = db.collection('game_results').get()
            if all_results:
                game_results = [d.to_dict() for d in all_results]
    except Exception as e:
        print(f"⚠️ [TRENDS] Error querying game results: {e}")
    
    # Group by date
    by_date = {}
    for g in game_results:
        date = g.get("date", "unknown")
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(g)
    
    # Daily averages
    daily_scores = []
    for date, games in sorted(by_date.items()):
        avg = round(sum(g.get("accuracy", 0) for g in games) / len(games))
        daily_scores.append({"date": date, "score": avg, "games": len(games)})
    
    domain_scores = calculate_domain_scores(game_results)
    overall_score = calculate_overall_score(domain_scores)
    
    return jsonify({
        "daily_scores": daily_scores[-30:],  # Last 30 days
        "domain_scores": domain_scores,
        "overall_score": overall_score,
        "total_games": len(game_results)
    })


# --- DAILY ROUTINE API ---

@app.route("/api/daily-routine")
def api_daily_routine():
    lang = request.args.get("lang") or session.get("preferred_language") or "en"
    routine = get_daily_routine(lang)
    return jsonify({"routine": routine})


# --- PUSH NOTIFICATION (placeholder for FCM) ---

@app.route("/api/save-push-token", methods=["POST"])
def api_save_push_token():
    """Save FCM push token for the user."""
    data = request.json
    token = data.get("token")
    user_id = session.get("user_id")
    
    if token and user_id:
        db.collection('push_tokens').document(str(user_id)).set({
            'token': token,
            'updated_at': time.time()
        })
        return jsonify({"success": True})
    
    return jsonify({"error": "Missing data"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
