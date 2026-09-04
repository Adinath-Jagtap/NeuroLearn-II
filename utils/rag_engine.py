"""
NeuroLearn 2.0 — RAG (Retrieval-Augmented Generation) Engine
Personalized Memory Context Retrieval for Elderly Dementia Patients.
Stores and indexes caregiver notes (medications, item locations, family details, daily routines, doctor notes)
and retrieves relevant context for the AI Memory Companion.
"""

import os
import json
import re
import math
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rag")
os.makedirs(DATA_DIR, exist_ok=True)


def tokenize(text):
    """Normalize and tokenize text into words, preserving Indic Unicode scripts (Devanagari, Bengali/Assamese/Manipuri)."""
    if not text:
        return []
    words = re.findall(r'[a-zA-Z0-9_\u0900-\u097F\u0980-\u09FF]+', text.lower())
    return words


def compute_bm25_score(query_tokens, doc_tokens, avg_doc_len, total_docs, doc_freqs, k1=1.5, b=0.75):
    """Calculate Okapi BM25 relevance score between query and document."""
    score = 0.0
    doc_len = len(doc_tokens)
    doc_counts = Counter(doc_tokens)
    
    for token in query_tokens:
        if token not in doc_counts:
            continue
        freq = doc_counts[token]
        df = doc_freqs.get(token, 1)
        idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
        numerator = freq * (k1 + 1)
        denominator = freq + k1 * (1 - b + b * (doc_len / (avg_doc_len or 1)))
        score += idf * (numerator / (denominator or 1))
        
    return score


def get_patient_notes_file(patient_id):
    safe_id = str(patient_id).replace("/", "_").replace("\\", "_")
    return os.path.join(DATA_DIR, f"{safe_id}.json")


def save_caregiver_notes(patient_id, notes_dict, db=None):
    """
    Save and index caregiver knowledge notes for a patient.
    notes_dict can contain:
    - medications: list of strings or multi-line text
    - item_locations: text or dict of where glasses, keys, etc. are kept
    - family_members: list of family members with relations
    - daily_routine: schedule (morning, afternoon, bedtime)
    - frequent_confusion: things patient forgets
    - doctor_notes: clinical or prescription notes
    """
    if not patient_id:
        return False
        
    # Build structured document chunks
    chunks = []
    
    # 1. Medications
    meds = notes_dict.get("medications") or notes_dict.get("medication")
    if meds:
        if isinstance(meds, str):
            for line in meds.split("\n"):
                if line.strip():
                    chunks.append({"category": "Medication", "text": f"Medication reminder: {line.strip()}"})
        elif isinstance(meds, list):
            for m in meds:
                chunks.append({"category": "Medication", "text": f"Medication reminder: {str(m).strip()}"})

    # 2. Item Locations
    items = notes_dict.get("item_locations") or notes_dict.get("items")
    if items:
        if isinstance(items, str):
            for line in items.split("\n"):
                if line.strip():
                    chunks.append({"category": "Item Location", "text": f"Location of item: {line.strip()}"})
        elif isinstance(items, dict):
            for item_name, loc in items.items():
                chunks.append({"category": "Item Location", "text": f"{item_name} is kept at: {loc}"})

    # 3. Family Members
    family = notes_dict.get("family_members") or notes_dict.get("family")
    if family:
        if isinstance(family, str):
            for line in family.split("\n"):
                if line.strip():
                    chunks.append({"category": "Family", "text": f"Family detail: {line.strip()}"})
        elif isinstance(family, list):
            for f in family:
                chunks.append({"category": "Family", "text": f"Family detail: {str(f).strip()}"})

    # 4. Daily Routine
    routine = notes_dict.get("daily_routine") or notes_dict.get("routine")
    if routine:
        if isinstance(routine, str):
            for line in routine.split("\n"):
                if line.strip():
                    chunks.append({"category": "Daily Routine", "text": f"Daily habit & routine: {line.strip()}"})

    # 5. Things patient frequently forgets
    confusions = notes_dict.get("frequent_confusion") or notes_dict.get("confusion")
    if confusions:
        if isinstance(confusions, str):
            for line in confusions.split("\n"):
                if line.strip():
                    chunks.append({"category": "Memory Anchor", "text": f"Important fact patient forgets: {line.strip()}"})

    # 6. Doctor Prescriptions / Notes
    doc_notes = notes_dict.get("doctor_notes") or notes_dict.get("prescription")
    if doc_notes:
        if isinstance(doc_notes, str):
            for line in doc_notes.split("\n"):
                if line.strip():
                    chunks.append({"category": "Doctor Prescription", "text": f"Doctor advice: {line.strip()}"})

    record = {
        "patient_id": str(patient_id),
        "raw_notes": notes_dict,
        "chunks": chunks
    }

    # Save to local persistent JSON
    try:
        file_path = get_patient_notes_file(patient_id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ [RAG] Local save error: {e}")

    # Also save to Firebase collection if db provided
    if db is not None:
        try:
            db.collection("caregiver_notes").document(str(patient_id)).set(record)
            print(f"🔥 [RAG] Notes saved to Firebase for patient {patient_id} ({len(chunks)} chunks)")
        except Exception as e:
            print(f"⚠️ [RAG] Firebase save error: {e}")

    return True


def load_patient_chunks(patient_id, db=None):
    """Load chunks from local file or Firebase."""
    file_path = get_patient_notes_file(patient_id)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("chunks", [])
        except Exception:
            pass

    if db is not None:
        try:
            doc = db.collection("caregiver_notes").document(str(patient_id)).get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("chunks", [])
        except Exception:
            pass

    return []


def query_care_context(patient_id, query_text, db=None, top_k=3):
    """
    Retrieve top-k most relevant caregiver notes for the patient query.
    Works seamlessly across all regional languages via keyword expansion & BM25 ranking.
    """
    if not query_text or not patient_id:
        return []

    chunks = load_patient_chunks(patient_id, db=db)
    if not chunks:
        return []

    query_tokens = tokenize(query_text)
    if not query_tokens:
        return [c["text"] for c in chunks[:top_k]]

    # Expand common multilingual synonyms for dementia queries across all supported Indic languages
    synonym_map = {
        # Spectacles / Glasses
        "glasses": ["spectacles", "chashma", "চছমা", "চশমা", "चश्मा", "মিৎচু", "চোশमा"],
        "spectacles": ["glasses", "chashma", "চছমা", "चश्मा"],
        "chashma": ["glasses", "spectacles", "चश्मा", "चशमा"],
        "चश्मा": ["glasses", "spectacles", "chashma"],
        "चशमा": ["glasses", "spectacles", "chashma"],
        "চছমা": ["glasses", "spectacles", "chashma"],
        "চশমা": ["glasses", "spectacles", "chashma"],
        "মিৎচু": ["glasses", "spectacles", "chashma"],
        
        # Medicine / Medication
        "medicine": ["medication", "tablet", "pills", "dawaii", "dawa", "औषध", "दवा", "দৰব", "হিদাক", "donepezil"],
        "medication": ["medicine", "tablet", "pills", "dawa", "औषध", "দৰব", "হিদাক"],
        "tablet": ["medicine", "medication", "pill", "tablet", "गोळी", "गोळ्या"],
        "pill": ["medicine", "medication", "tablet"],
        "pills": ["medicine", "medication", "tablet"],
        "dawa": ["medicine", "medication", "tablet", "dawaii"],
        "dawaii": ["medicine", "medication", "tablet"],
        "दवा": ["medicine", "medication", "tablet", "donepezil"],
        "दवाई": ["medicine", "medication", "tablet", "donepezil"],
        "औषध": ["medicine", "medication", "tablet", "donepezil"],
        "गोळी": ["medicine", "medication", "tablet"],
        "गोळ्या": ["medicine", "medication", "tablet"],
        "দৰব": ["medicine", "medication", "tablet"],
        "ঔষধ": ["medicine", "medication", "tablet"],
        "হিদাক": ["medicine", "medication", "tablet"],
        
        # Where / Location
        "where": ["location", "kept", "place", "कहाँ", "कुठे", "ক'ত", "কোথায়", "কদায়"],
        "location": ["where", "kept", "place"],
        "kept": ["where", "location", "place", "ठेवला", "रखा"],
        "कहाँ": ["where", "location", "kept", "place"],
        "कुठे": ["where", "location", "kept", "place"],
        "ক'ত": ["where", "location", "kept"],
        "কোথায়": ["where", "location", "kept"],
        "কদায়": ["where", "location", "kept"],
        
        # Keys / Stick / Wallet
        "key": ["keys", "lock", "chaabi", "chabi", "चाबी", "किल्ली"],
        "keys": ["key", "lock", "chaabi", "chabi", "चाबी", "किल्ली"],
        "चाबी": ["keys", "key", "lock"],
        "किल्ली": ["keys", "key", "lock"],
        "stick": ["walking", "stick", "cane", "काठी", "छड़ी"],
        "walking": ["stick", "cane", "walk", "garden", "काठी", "फिरणे"],
        "cane": ["stick", "walking", "काठी"],
        "काठी": ["stick", "walking", "cane"],
        "छड़ी": ["stick", "walking", "cane"],
        
        # Doors / Locks / Safe / Security
        "door": ["doors", "lock", "locked", "safe", "दरवाजा", "दार", "দরজা"],
        "doors": ["door", "lock", "locked", "safe", "दरवाजा", "दार"],
        "lock": ["locked", "door", "safe", "कुलूप", "ताला"],
        "locked": ["lock", "door", "safe", "closed", "बंद", "कुलूप"],
        "safe": ["locked", "safe", "secure", "सुरक्षित"],
        "सुरक्षित": ["safe", "locked", "secure"],
        "दरवाजा": ["door", "doors", "lock", "locked", "safe"],
        "दार": ["door", "doors", "lock", "locked", "safe"],
        "कुलूप": ["lock", "locked", "safe", "door"],
        "ताला": ["lock", "locked", "safe", "door"],
        "बंद": ["lock", "locked", "door", "closed"],
        
        # Family / Relations
        "son": ["rahul", "aarav", "boy", "child", "बेटा", "मुलगा", "ল'ৰা", "ছেলে"],
        "मुलगा": ["son", "rahul", "aarav", "boy", "बेटा"],
        "बेटा": ["son", "rahul", "aarav", "boy", "मुलगा"],
        "ল'ৰা": ["son", "rahul", "boy"],
        "ছেলে": ["son", "rahul", "boy"],
        "daughter": ["priya", "ananya", "girl", "child", "बेटी", "मुलगी", "ছোৱালী", "মেয়ে"],
        "मुलगी": ["daughter", "priya", "ananya", "girl", "बेटी"],
        "बेटी": ["daughter", "priya", "ananya", "girl", "मुलगी"],
        "ছোৱালী": ["daughter", "priya", "girl"],
        "মেয়ে": ["daughter", "priya", "girl"],
        "grandson": ["aarav", "grandchild", "नातू", "पोता"],
        "नातू": ["grandson", "aarav"],
        "पोता": ["grandson", "aarav"],
        "wife": ["spouse", "पत्नी", "बायको", "স্ত্রী"],
        "husband": ["spouse", "पती", "पति", "স্বামী"],
        "बायको": ["wife", "spouse"],
        "पत्नी": ["wife", "spouse"],
        "पती": ["husband", "spouse"],
        "पति": ["husband", "spouse"],
        
        # Routine / Habits
        "tea": ["morning", "balcony", "routine", "चाय", "चहा"],
        "चाय": ["tea", "morning", "routine", "balcony"],
        "चहा": ["tea", "morning", "routine", "balcony"],
        "walk": ["garden", "evening", "routine", "चालणे", "फिरणे", "टहलना"],
        "चालणे": ["walk", "garden", "evening", "routine"],
        "फिरणे": ["walk", "garden", "evening", "routine"],
        "टहलना": ["walk", "garden", "evening", "routine"],
        "morning": ["tea", "breakfast", "routine", "सकाळ", "सुबह", "পুৱা"],
        "सकाळ": ["morning", "tea", "breakfast", "routine"],
        "सुबह": ["morning", "tea", "breakfast", "routine"],
        "evening": ["walk", "garden", "routine", "संध्याकाळ", "शाम", "গধূলি"],
        "संध्याकाळ": ["evening", "walk", "routine", "garden"],
        "शाम": ["evening", "walk", "routine", "garden"],
        "bedtime": ["sleep", "night", "routine", "झोप", "नींद", "रात्र", "रात"],
        "sleep": ["bedtime", "night", "routine", "झोप", "नींद"],
        "झोप": ["sleep", "bedtime", "night", "routine"],
        "नींद": ["sleep", "bedtime", "night", "routine"],
        "रात्र": ["night", "bedtime", "sleep", "routine"],
        "रात": ["night", "bedtime", "sleep", "routine"],
        
        # Doctor / Clinic / Appointments
        "doctor": ["dr", "prescription", "clinic", "hospital", "checkup", "appointment", "baruah", "চিকিৎসক", "ডাক্তৰ", "ডাক্তার", "डॉक्टर"],
        "डॉक्टर": ["doctor", "dr", "clinic", "prescription", "checkup", "baruah"],
        "clinic": ["doctor", "dr", "appointment", "checkup"],
        "appointment": ["doctor", "dr", "clinic", "checkup", "prescription"],
        "checkup": ["doctor", "dr", "clinic", "appointment"],
        "prescription": ["doctor", "dr", "medicine", "medication"],
        
        # Common names transliteration
        "rahul": ["राहुल", "son"],
        "राहुल": ["rahul", "son", "मुलगा", "बेटा"],
        "priya": ["प्रिया", "daughter"],
        "प्रिया": ["priya", "daughter", "मुलगी", "बेटी"],
        "aarav": ["आरव", "grandson"],
        "आरव": ["aarav", "grandson", "नातू"],
        "baruah": ["बरुआ", "doctor", "dr"],
        "बरुआ": ["baruah", "doctor", "dr"]
    }

    expanded_tokens = list(query_tokens)
    for q in query_tokens:
        if q in synonym_map:
            expanded_tokens.extend(synonym_map[q])

    # Compute BM25 statistics
    total_docs = len(chunks)
    all_doc_tokens = [tokenize(c["text"]) for c in chunks]
    avg_len = sum(len(d) for d in all_doc_tokens) / (total_docs or 1)

    doc_freqs = Counter()
    for d in all_doc_tokens:
        doc_freqs.update(set(d))

    # Score each chunk
    scored_chunks = []
    for i, c in enumerate(chunks):
        doc_tok = all_doc_tokens[i]
        score = compute_bm25_score(expanded_tokens, doc_tok, avg_len, total_docs, doc_freqs)
        
        # Exact substring boost
        for token in query_tokens:
            if token in c["text"].lower():
                score += 3.0
                
        if score > 0:
            scored_chunks.append((score, c["text"]))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    results = [text for _, text in scored_chunks[:top_k]]
    return results


def format_context_for_prompt(context_list):
    """Format retrieved context chunks into prompt text for system prompt."""
    if not context_list:
        return ""
    formatted = "\n".join([f"- {c}" for c in context_list])
    return f"""
REAL-WORLD CAREGIVER NOTES & FACTS ABOUT PATIENT:
{formatted}
(If the patient's question asks about items, medications, family, or habits mentioned above, use these EXACT facts to answer accurately and reassuringly!)
"""
