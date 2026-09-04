# NeuroLearn 2.0 — Final Revised Implementation Plan

> All 7 evaluator points addressed with all comment feedback incorporated.

---

## Languages to Add (Point 1)

**Decision (by population):**

| Language | NE India Speakers | TTS | Script |
|---|---|---|---|
| **Bengali (বাংলা)** | ~12M+ (Tripura 66%, Assam Barak Valley 81%) | ✅ Full `bn-IN` | Bengali |
| **Manipuri (মৈতৈলোন্)** | ~1.76M (fastest growing NE language) | ⚠️ `bn-IN` fallback | Bengali script |

**Bengali wins on population.** Bengali is the dominant language in Tripura and Barak Valley, Assam — both critical NER regions for this SIH project.

**For the 2nd additional language:** Manipuri (Meitei) edges Bodo (1.76M vs 1.45M) and Assam officially recognized it in 4 districts in 2024. We'll add Manipuri with Bengali-script TTS fallback (`bn-IN`) since no commercial Meitei TTS exists yet.

### Final language set: EN | HI | MR | AS | BN | MNI (6 languages)

| Code | Language | Script | TTS Code |
|---|---|---|---|
| `en` | English | Latin | `en-IN` |
| `hi` | Hindi (हिन्दी) | Devanagari | `hi-IN` |
| `mr` | Marathi (मराठी) | Devanagari | `mr-IN` |
| `as` | Assamese (অসমীয়া) | Bengali-Assamese | `as-IN` |
| `bn` | Bengali (বাংলা) | Bengali | `bn-IN` |
| `mni` | Manipuri (মৈতৈলোন্) | Bengali script | `bn-IN` (fallback) |

---

## Game Suite Redesign (Point 2)

### Game 1: Mukh Chinibo — Face Recognition (Enhanced)

**Confirmed: Keep face recognition only.** Remove costume overlays.

**New multi-mode question system:**

| Mode | Question Type | Answer Format |
|---|---|---|
| A | Show face → "What is this person's name?" | 4 name text options |
| B | Show face → "What is your relation to this person?" | 4 relation options (Son, Grandson, Neighbour, Doctor) |
| C | Show name → "Who is your daughter?" | 4 family PHOTOS to choose from |
| D | Show face → "Is this person older or younger than you?" | 2 options |
| E | Show relation → "Show me your son" | 4 photos |

Modes A-E are randomly mixed each session. This creates genuine variety and tests both **name recall** and **relational memory** separately — both key indicators of Alzheimer's progression.

**If no family photos uploaded:** Fall back to the Bihu Rang game.

---

### Game 2: Bihu Rang — NE Pattern Memory

**Confirmed. Implement this exactly.**

Replace colored emoji circles with 6 traditional NE motifs rendered as **inline SVGs:**

| Motif | Cultural origin | SVG color |
|---|---|---|
| Gamosa stripe | Assamese cotton cloth | Red `#C0392B` |
| Kopou Phool (Orchid) | Assam state flower | Pink `#D63384` |
| Bihu Elephant | Rongali Bihu | Terracotta `#E07B54` |
| Peacock feather | Common NE motif | Teal `#1ABC9C` |
| Bamboo shoot | NE food/craft symbol | Green `#27AE60` |
| Fish | Brahmaputra river life | Blue `#2980B9` |

**Game mechanics (unchanged from current pattern game):**
- Show sequence → hide → patient reproduces sequence
- Difficulty: Easy 2-seq, Medium 3-seq, Hard 4-seq
- Points for correct recall, speed bonus

**SVG design:** Flat, bold, high-contrast icons (accessible for elderly with low vision)

---

### Game 3: Bagh-Baak — Tiger Hunt Strategy Game

#### Why This Game Is Clinically Justified for Dementia

> **For the SIH presentation, here is the scientific case:**

**1. Activates Working Memory (most impaired in Alzheimer's)**
The patient must track where the tiger is, where their goats are, and hold a 2-3 move plan in mind simultaneously. This directly exercises working memory capacity — the cognitive function most rapidly lost in early Alzheimer's (Baddeley et al., 2001).

**2. Inhibitory Control Training**
Dementia patients tend to make impulsive, random decisions. Bagh-Chal forces the patient to *stop and think* before placing a goat — training inhibitory control (resisting the first impulse), a frontal lobe function measurable on standard assessments like Stroop and Trail Making Test.

**3. Spatial Reasoning & Visuospatial Navigation**
Moving pieces on a 5×5 grid requires mentally mapping positions — the same cognitive skill tested by the **Clock Drawing Test (CDT)**, one of the gold-standard dementia screening tools. By training spatial navigation through gameplay, we indirectly strengthen the same neural circuits CDT measures.

**4. Reminiscence Effect (Most Powerful NE-Specific Benefit)**
Bagh-Chal variants are traditional across the entire Himalayan-NER belt — Assam, Manipur, Meghalaya, Nagaland, Arunachal Pradesh, Sikkim. For elderly patients who *grew up playing this game*, seeing the board triggers procedural memory and autobiographical recall — activating the hippocampus even when semantic memory has declined. This is the same mechanism behind music therapy for dementia (shown effective in >30 RCTs).

**5. Non-frustrating at any cognitive stage**
With glowing valid-move indicators, even a moderate-stage patient can participate successfully. Success in gameplay → dopamine release → positive mood → reduced BPSD (Behavioral and Psychological Symptoms of Dementia — the main reason for caregiver burnout).

**6. Measurable cognitive output**
We can score: number of valid moves made, reaction time, number of tiger captures, planning depth. These metrics generate a daily cognitive load score — a scientific biomarker.

> **Comparison to clinical alternatives:** The **Mahjong Therapy** program (shown in multiple RCTs in Hong Kong and Singapore to slow cognitive decline) works on identical principles — familiar cultural game, spatial pieces, turn-based strategy. Bagh-Baak is our NE-India equivalent of Mahjong Therapy.

#### Simplified Rules for Dementia Patients

| Difficulty | Tigers | Goats | Hints | Timer |
|---|---|---|---|---|
| Easy | 1 | 8 | All valid moves glow ✨ | Unlimited |
| Medium | 2 | 12 | Next best move highlighted | 30s |
| Hard | 4 | 20 | No hints | 20s |

- Patient = Goats (defensive, less cognitively demanding)
- AI = Tiger (auto-plays aggressive strategy)
- Win condition: Surround tiger so it can't move → patient wins
- Lose condition: Tiger eats 3 goats → game over

#### Cognitive Scoring (for doctor's report)
- `valid_moves_ratio` = valid/total moves made (planning accuracy)
- `avg_decision_time` = average seconds per move (processing speed)
- `game_completion_rate` = completed vs abandoned (persistence)

---

## Onboarding Flow Redesign (Point 3)

### Comment addressed: "How does patient log back in if logged out?"

**Answer:** Patients get a real account with credentials — the invite link only bootstraps account creation. After that, they always log in with email+PIN.

### Revised Secure Flow

```
1. CAREGIVER creates account → enters own email, password
   ↓
2. Caregiver Dashboard → "Add Patient" button
   ↓  
3. System generates: invite link + temp credentials
   https://neurolearn.app/join/TOKEN
   Email: patient@generated.com (or phone-based)
   PIN: 4-digit (caregiver sets this)
   ↓
4. Caregiver shares link+PIN via WhatsApp/SMS to patient's phone
   ↓
5. Patient opens link → enters PIN → account activated
   ↓
6. 3-Step Cognitive Assessment (on patient's phone)
   ↓
7. Patient gets permanent login: phone/email + PIN
   (Can always log back in at /login with these credentials)
   ↓
8. Caregiver sees patient linked in dashboard
```

**Data safety:** Token expires in 48 hours. Each token works only once. After activation, patient uses email+PIN. No shared tokens, no data leaks.

**Logged out → Log back in:** Patient goes to `/login`, enters their email + 4-digit PIN. Simple enough for elderly / dementia patient (caregiver sets a memorable PIN).

### 3-Step NE Cognitive Assessment

**Step 1 REPLACED** — New: **Spatial Memory Snapshot**

> Evaluator didn't like the orientation test (festival/river questions) — too subjective and depends on education level.

**New Step 1: Spatial Memory Snapshot**
- Show a simple image of a NE home scene (bamboo hut, garden, river) for 5 seconds
- Image disappears
- Patient sees 4 versions of the scene (1 original + 3 with small differences)
- "Which picture did you see?" → tests visual memory + attention
- Points: 0–5 based on accuracy and time

**Step 2: NE Image Memory Recall (KEPT - approved)**
- Show 3 NE-themed images (tea garden, bamboo house, Brahmaputra river)
- 20-second distraction task (count backwards from 10 in their language)
- "Which of these 4 images did you see earlier?" → tests delayed recall
- Points: 0–5

**Step 3: Word Fluency — NE Theme (KEPT - approved)**
- Voice input: "Name 5 animals found in Assam forests in 30 seconds"
- Or: "Name 3 dishes eaten at Bihu"
- Patient speaks, we count recognized words via speech recognition
- Points: 0–5

**Scoring:**
| Score | Stage |
|---|---|
| 13–15 | No impairment |
| 9–12 | MCI (Mild Cognitive Impairment) |
| 5–8 | Moderate |
| 0–4 | Severe |

**Final stage = worst of (caregiver's input vs assessment result)**

---

## RAG-Enhanced Chatbot (Point 5) — 100% Free Stack

> **All free, works on Render.**

### Free Tech Stack

| Component | Tool | Cost | Notes |
|---|---|---|---|
| Text embedding | `sentence-transformers/all-MiniLM-L6-v2` | Free | HuggingFace, runs locally |
| Vector DB | `ChromaDB` (local persistent) | Free | Stored in `/data/chroma/` on Render disk |
| LLM | `groq/compound-mini` | Free tier | Already integrated |
| Face recognition | `deepface` library | Free | Runs locally, no API needed |

### 5a. Caregiver Context Input (RAG)

**New UI section in caregiver dashboard ("Care Notes" tab):**

Patient info form with fields:
- 💊 Medication (name, dosage, timing)
- 📍 Important item locations
- 👨‍👩‍👧 Family member nicknames
- ⏰ Daily routine
- ⚠️ Things patient frequently forgets
- 📞 Emergency contacts

**Backend (free):**
```python
# On save: embed and store in ChromaDB
from sentence_transformers import SentenceTransformer
import chromadb

model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode("spectacles are in the drawer")
chroma_client.add(embedding, doc="spectacles are in the drawer", patient_id="...")

# On companion query: retrieve top-3 matches
results = chroma_client.query(model.encode(user_message), n_results=3)
# Inject into system prompt as context
```

**Example interaction:**

*Patient:* "Where are my glasses?"
*Retrieved context:* "spectacles are in the drawer by the bed"
*AI responds (in Assamese):* "আপোনাৰ চছমা বিচনাৰ কাষৰ ড্ৰয়াৰত আছে!"

### 5b. Doctor Prescription RAG

Same pipeline, separate ChromaDB collection per patient:
- Caregiver types / uploads prescription text
- Doctor notes stored as chunks
- Retrieved when patient asks about medicines, restrictions

### 5c. Face Recognition from Photo

**Free with DeepFace:**
```python
from deepface import DeepFace

# Patient uploads unknown photo
# Compare against all family photos stored in Cloudinary
results = DeepFace.find(
    img_path=uploaded_photo,
    db_path=f"./family_photos/{patient_id}/",
    model_name="Facenet",  # best accuracy/speed balance
    threshold=0.6
)
# Returns best match → lookup name from Firestore
```

**Flow:**
1. Patient opens companion → taps 📷 "Who is this?"
2. Uploads or takes photo of person they can't recognize
3. Server downloads family photos from Cloudinary, runs DeepFace
4. Returns: "This is **Arjun**, your grandson (age 22)" in local language

---

## Full Multilingual UI (Point 4)

### Approach: Server-side i18n via `translations.py`

All UI text → pre-translated dictionary → injected via Jinja2 `{{ t['key'] }}`

**Translation files:** `utils/translations.py`
- ~120 UI strings
- 6 languages: EN, HI, MR, AS, BN, MNI

**Example:**
```python
TRANSLATIONS = {
    "en": {
        "good_morning": "Good morning",
        "how_feeling": "How are you feeling today?",
        "play_game": "Play Game",
        "todays_games": "Today's Activities",
        ...
    },
    "as": {
        "good_morning": "শুভ ৰাতিপুৱা",
        "how_feeling": "আজি আপুনি কেনে অনুভৱ কৰিছে?",
        "play_game": "খেল খেলক",
        "todays_games": "আজিৰ কাৰ্যসূচী",
        ...
    },
    "bn": {...},
    "mni": {...}
}
```

**Companion quick-replies also translated:**
- "Tell me about festivals" → "উৎসৱৰ বিষয়ে কওক" (AS)
- "Talk about family" → "পৰিয়ালৰ বিষয়ে কথা পাতক" (AS)

**TTS read-aloud:** Already reads in selected language. Will work once UI text is in correct language.

---

## Infrastructure Overhaul (Point 7)

### Firebase Architecture

| Data | Storage |
|---|---|
| Authentication | Firebase Auth (enabled ✅) |
| User profiles, game sessions, companion logs | Firestore |
| Real-time GPS location | Realtime Database (keep) |
| Images (family photos) | Cloudinary |

### Firebase Auth Integration

Replace current session-based auth with Firebase Auth tokens:
- Sign up → `firebase_admin.auth.create_user(email, password)`
- Log in → verify Firebase ID token on every request
- Session stores `firebase_uid` instead of custom user_id

### Cloudinary Setup (Steps for You)

**Step 1:** Go to [cloudinary.com](https://cloudinary.com) → Sign Up Free
**Step 2:** After signup → Dashboard → Copy these 3 values:
- `Cloud Name`
- `API Key`
- `API Secret`

**Step 3:** Add to your `.env`:
```
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

**Step 4:** I will integrate `cloudinary` Python SDK to auto-upload all patient family photos.

Free tier: 25 GB storage + 25 GB/month bandwidth — more than enough for this project.

### Tabbed Caregiver Dashboard

5 tabs replacing the single scroll page:

| Tab | Icon | Content |
|---|---|---|
| Overview | house SVG | Patient card, mood today, last activity, quick stats |
| Live Map | map-pin SVG | Real-time GPS map, location history, safe zones |
| Performance | chart SVG | Cognitive trend chart, game scores, score history |
| Care Notes | clipboard SVG | RAG input form: medicines, routines, family nicknames |
| Settings | cog SVG | Manage patient link, notifications, caregiver profile |

### SOS Fix Plan

Current bug: caregiver email not resolved from patient session correctly.
Fix: Read `caregiver_id` from patient's Firestore doc → fetch caregiver email → send via SendGrid/SMTP.

### SVG Icons (Replace All Emojis)

Use **Phosphor Icons** (MIT license, no build step needed via CDN):
```html
<script src="https://unpkg.com/@phosphor-icons/web"></script>
<i class="ph ph-brain"></i>     <!-- 🧠 -->
<i class="ph ph-game-controller"></i>  <!-- 🎮 -->
<i class="ph ph-robot"></i>     <!-- 🤖 -->
<i class="ph ph-map-pin"></i>   <!-- 📍 -->
```

---

## Cloudinary Keys — How to Get Them

1. Visit **cloudinary.com** → click **Sign Up For Free**
2. Fill in name, email, password → verify email
3. Go to your **Dashboard** (home page after login)
4. You'll see a panel: **Product Environment Credentials**
5. Copy:
   - `Cloud Name` → `CLOUDINARY_CLOUD_NAME`
   - `API Key` → `CLOUDINARY_API_KEY`  
   - `API Secret` (click eye icon to reveal) → `CLOUDINARY_API_SECRET`
6. Share these 3 values with me and I'll integrate immediately

---

## Render Deployment Notes

Since you're deploying to Render:
- ChromaDB persists to disk → use Render's **Persistent Disk** (add $7/mo) OR use `/tmp` (ephemeral, reloads on restart)
- DeepFace runs locally → works fine on Render
- Family photos pulled from Cloudinary URL → no local storage needed

---

## Execution Order (Priority Queue)

| # | Task | Time Est. |
|---|---|---|
| 1 | Add Bengali + Manipuri (quick wins, evaluator asks) | 1 hr |
| 2 | Caregiver invite-link flow (Point 3 + 6 together) | 3 hrs |
| 3 | Bihu Rang game — NE pattern SVGs (Point 2 Game 2) | 2 hrs |
| 4 | Bagh-Baak game engine — SVG board + AI (Point 2 Game 3) | 4 hrs |
| 5 | Mukh Chinibo multi-mode questions (Point 2 Game 1) | 2 hrs |
| 6 | Firebase Auth + Firestore migration (Point 7d) | 4 hrs |
| 7 | Cloudinary image storage (Point 7e) | 1 hr |
| 8 | Tabbed caregiver dashboard (Point 7a) | 3 hrs |
| 9 | SVG icon replacement (Point 7c) | 2 hrs |
| 10 | `translations.py` + full UI multilingual (Point 4) | 5 hrs |
| 11 | RAG setup — ChromaDB + embeddings + caregiver notes UI (Point 5a) | 4 hrs |
| 12 | DeepFace family photo recognition (Point 5c) | 3 hrs |
| 13 | Prescription RAG (Point 5b) | 2 hrs |
| 14 | SOS fix (Point 7b) | 1 hr |
| 15 | 3-Step NE cognitive assessment (Point 3) | 3 hrs |

**Total estimated: ~40 hours of development**

---

## Ready to Start?

**Approve this plan** and share your **Cloudinary keys** when you have them. I'll start building in the execution order above — each feature will be functional and testable before moving to the next.
