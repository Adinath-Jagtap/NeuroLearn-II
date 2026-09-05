"""
NeuroLearn 2.0 — Cognitive Engine
Game content generation, scoring, adaptive difficulty, and cognitive domain tracking.
"""

import os
import json
import random
import time

# Cognitive domains tracked
COGNITIVE_DOMAINS = ["Memory", "Attention", "Executive", "Strategy"]

# --- GAME CONTENT GENERATION ---

# Realistic Indian names for personalized photo recognition distractors
MALE_NAMES = [
    "Aarav", "Rohan", "Vikram", "Aditya", "Rahul", "Kabir", "Arjun", "Kunal", 
    "Siddharth", "Dev", "Alok", "Sameer", "Rajesh", "Nikhil", "Manish", "Gaurav",
    "Pranav", "Amit", "Sachin", "Deepak", "Vivek", "Sanjay", "Rakesh", "Suresh"
]

FEMALE_NAMES = [
    "Ananya", "Priya", "Neha", "Pooja", "Sunita", "Shreya", "Riya", "Kavita", 
    "Meera", "Deepa", "Ishita", "Sita", "Geeta", "Tanvi", "Aditi", "Sneha",
    "Radha", "Aarti", "Anjali", "Swati", "Rekha", "Shalini", "Divya", "Kiran"
]

COMMON_NAMES = MALE_NAMES + FEMALE_NAMES


def generate_recognition_game(difficulty="easy", language="en", family_photos=None):
    """Generate 'Mukh Chinibo' — multi-mode face recognition game.
    
    5 question modes:
    1. NAME_TEXT   — Show photo, pick correct name from text options
    2. RELATION    — Show photo, pick correct relationship from text options
    3. IMAGE_GRID  — "Who is your [daughter]?" + grid of family member photos
    4. LINEUP      — "Find [person name]" from lineup of photos
    5. YES_NO      — Show photo with a name, patient taps Yes/No
    """
    
    items = []
    
    # Localized strings
    mode_labels = {
        "en": {"name": "Who is this?", "relation": "What relation is this person?", 
               "grid": "Who is your", "lineup": "Find", "yesno": "Is this",
               "yes": "Yes ✓", "no": "No ✗"},
        "hi": {"name": "यह कौन है?", "relation": "यह व्यक्ति आपका क्या लगता है?",
               "grid": "आपकी/आपके", "lineup": "ढूंढिए", "yesno": "क्या यह",
               "yes": "हाँ ✓", "no": "नहीं ✗"},
        "as": {"name": "এয়া কোন?", "relation": "এই ব্যক্তি আপোনাৰ কি হয়?",
               "grid": "আপোনাৰ", "lineup": "বিচাৰক", "yesno": "এয়া",
               "yes": "হয় ✓", "no": "নহয় ✗"},
        "bn": {"name": "এটা কে?", "relation": "এই ব্যক্তি আপনার কী হন?",
               "grid": "আপনার", "lineup": "খুঁজুন", "yesno": "এটা কি",
               "yes": "হ্যাঁ ✓", "no": "না ✗"},
        "mni": {"name": "মসি কনানো?", "relation": "মসি মহাক্কী করিনো?",
                "grid": "নহাক্কী", "lineup": "থিবিয়ু", "yesno": "মসি",
                "yes": "হৌই ✓", "no": "নত্তে ✗"},
        "mr": {"name": "हे कोण आहे?", "relation": "ही व्यक्ती तुमची काय नाती?",
               "grid": "तुमची/तुमचा", "lineup": "शोधा", "yesno": "हे आहे का",
               "yes": "हो ✓", "no": "नाही ✗"},
    }
    
    L = mode_labels.get(language, mode_labels["en"])
    
    if family_photos and len(family_photos) >= 2:
        all_names = [p.get("person_name", "").strip() for p in family_photos if p.get("person_name")]
        all_relations = list(set(p.get("relationship", "Family").strip() for p in family_photos if p.get("relationship")))
        
        photos_with_data = [p for p in family_photos if p.get("person_name") and p.get("photo_url")]
        random.shuffle(photos_with_data)
        
        for i, photo in enumerate(photos_with_data):
            name = photo["person_name"].strip()
            rel = photo.get("relationship", "Family Member").strip()
            url = photo.get("photo_url", "")
            
            # Cycle through modes
            mode = i % 5
            
            if mode == 0:
                # MODE 1: Name the person (text options)
                wrong = [n for n in all_names if n.lower() != name.lower()]
                random.shuffle(wrong)
                if len(wrong) < 3:
                    pool = MALE_NAMES if any(m in rel.lower() for m in ["son","brother","father","uncle","husband","grandfather"]) else FEMALE_NAMES
                    wrong += [n for n in pool if n.lower() != name.lower()][:3]
                options = [name] + wrong[:3]
                random.shuffle(options)
                items.append({
                    "mode": "name_text",
                    "image_desc": f"{L['name']} ({rel})",
                    "correct": name,
                    "options": options,
                    "category": "family",
                    "photo_url": url,
                    "is_real_photo": True
                })
                
            elif mode == 1:
                # MODE 2: What relation? (text options)
                wrong_rels = [r for r in all_relations if r.lower() != rel.lower()]
                fallback_rels = ["Son", "Daughter", "Wife", "Husband", "Brother", "Sister", "Mother", "Father", "Friend", "Neighbour"]
                wrong_rels += [r for r in fallback_rels if r.lower() != rel.lower() and r not in wrong_rels]
                random.shuffle(wrong_rels)
                options = [rel] + wrong_rels[:3]
                random.shuffle(options)
                items.append({
                    "mode": "relation",
                    "image_desc": f"{L['relation']} ({name})",
                    "correct": rel,
                    "options": options,
                    "category": "family",
                    "photo_url": url,
                    "is_real_photo": True
                })
                
            elif mode == 2:
                # MODE 3: Image grid — "Who is your [daughter]?"
                others = [p for p in photos_with_data if p["person_name"].strip().lower() != name.lower()]
                if len(others) >= 2:
                    grid_wrong = random.sample(others, min(3, len(others)))
                    grid_items = [{"name": name, "url": url, "correct": True}]
                    for gw in grid_wrong:
                        grid_items.append({"name": gw["person_name"], "url": gw["photo_url"], "correct": False})
                    random.shuffle(grid_items)
                    items.append({
                        "mode": "image_grid",
                        "image_desc": f"{L['grid']} {rel}?",
                        "correct": name,
                        "photo_grid": grid_items,
                        "category": "family",
                        "is_real_photo": True
                    })
                else:
                    # Fallback to name_text if not enough photos
                    wrong = [n for n in COMMON_NAMES if n.lower() != name.lower()][:3]
                    options = [name] + wrong
                    random.shuffle(options)
                    items.append({
                        "mode": "name_text",
                        "image_desc": f"{L['name']} ({rel})",
                        "correct": name,
                        "options": options,
                        "category": "family",
                        "photo_url": url,
                        "is_real_photo": True
                    })
                    
            elif mode == 3:
                # MODE 4: Lineup — "Find [person name]"
                others = [p for p in photos_with_data if p["person_name"].strip().lower() != name.lower()]
                if len(others) >= 2:
                    lineup_wrong = random.sample(others, min(3, len(others)))
                    lineup_items = [{"name": name, "url": url, "correct": True}]
                    for lw in lineup_wrong:
                        lineup_items.append({"name": lw["person_name"], "url": lw["photo_url"], "correct": False})
                    random.shuffle(lineup_items)
                    items.append({
                        "mode": "lineup",
                        "image_desc": f"{L['lineup']} {name}",
                        "correct": name,
                        "photo_grid": lineup_items,
                        "category": "family",
                        "is_real_photo": True
                    })
                else:
                    wrong = [n for n in COMMON_NAMES if n.lower() != name.lower()][:3]
                    options = [name] + wrong
                    random.shuffle(options)
                    items.append({
                        "mode": "name_text",
                        "image_desc": f"{L['name']} ({rel})",
                        "correct": name,
                        "options": options,
                        "category": "family",
                        "photo_url": url,
                        "is_real_photo": True
                    })
                    
            else:
                # MODE 5: Yes/No — "Is this [wrong name]?"
                is_correct_shown = random.random() > 0.5
                if is_correct_shown:
                    shown_name = name
                    correct_answer = L["yes"]
                else:
                    wrong_pool = [n for n in all_names if n.lower() != name.lower()]
                    if not wrong_pool:
                        wrong_pool = COMMON_NAMES
                    shown_name = random.choice(wrong_pool)
                    correct_answer = L["no"]
                
                items.append({
                    "mode": "yes_no",
                    "image_desc": f"{L['yesno']} {shown_name}?",
                    "correct": correct_answer,
                    "options": [L["yes"], L["no"]],
                    "category": "family",
                    "photo_url": url,
                    "is_real_photo": True,
                    "shown_name": shown_name,
                    "actual_name": name
                })
        
        random.shuffle(items)
        items = items[:min(8, len(items))]
    
    # --- FALLBACK: GENERIC CONTENT (Multilingual) ---
    FALLBACK_RECOG_ITEMS = {
        "en": [
            {"mode": "name_text", "image_desc": "An elderly grandmother smiling warmly", "correct": "Grandmother", "options": ["Grandmother", "Mother", "Aunt", "Sister"], "category": "family"},
            {"mode": "name_text", "image_desc": "A young smiling son", "correct": "Son", "options": ["Son", "Brother", "Father", "Grandson"], "category": "family"},
            {"mode": "name_text", "image_desc": "A little granddaughter", "correct": "Granddaughter", "options": ["Granddaughter", "Daughter", "Niece", "Sister"], "category": "family"},
            {"mode": "name_text", "image_desc": "A traditional clay diya", "correct": "Diya", "options": ["Diya", "Candle", "Lantern", "Torch"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "A plate of delicious laddoos", "correct": "Laddoo", "options": ["Laddoo", "Rasgulla", "Gulab Jamun", "Jalebi"], "category": "food"},
            {"mode": "name_text", "image_desc": "An Assamese red and white Gamosa", "correct": "Gamosa", "options": ["Gamosa", "Dupatta", "Shawl", "Towel"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "People performing Bihu dance", "correct": "Bihu Dance", "options": ["Bihu Dance", "Garba", "Bhangra", "Kathak"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "A magnificent one-horned rhino", "correct": "Rhino", "options": ["Rhino", "Elephant", "Buffalo", "Tiger"], "category": "cultural"},
        ],
        "hi": [
            {"mode": "name_text", "image_desc": "मुस्कुराती हुई बुजुर्ग दादी / नानी", "correct": "दादी / नानी", "options": ["दादी / नानी", "माँ", "मौसी / चाची", "बहन"], "category": "family"},
            {"mode": "name_text", "image_desc": "मुस्कुराता हुआ नौजवान बेटा", "correct": "बेटा", "options": ["बेटा", "भाई", "पिता", "पोता"], "category": "family"},
            {"mode": "name_text", "image_desc": "प्यारी सी नन्हीं पोती / नातिन", "correct": "पोती / नातिन", "options": ["पोती / नातिन", "बेटी", "भांजी / भतीजी", "बहन"], "category": "family"},
            {"mode": "name_text", "image_desc": "पारंपरिक मिट्टी का दीया", "correct": "दीया", "options": ["दीया", "मोमबत्ती", "लालटेन", "मशाल"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "स्वादिष्ट गोल लड्डू की थाली", "correct": "लड्डू", "options": ["लड्डू", "रसगुल्ला", "गुलाब जामुन", "जलेबी"], "category": "food"},
            {"mode": "name_text", "image_desc": "लाल और सफेद असमिया गमोसा", "correct": "गमोसा", "options": ["गमोसा", "दुपट्टा", "शॉल", "तौलिया"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "पारंपरिक बिहू नृत्य", "correct": "बिहू नृत्य", "options": ["बिहू नृत्य", "गरबा", "भांगड़ा", "कथक"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "काजीरंगा का एक सींग वाला गैंडा", "correct": "गैंडा", "options": ["गैंडा", "हाथी", "भैंस", "बाघ"], "category": "cultural"},
        ],
        "as": [
            {"mode": "name_text", "image_desc": "মৰমিয়াল হাঁহিমুখীয়া আইতা", "correct": "আইতা", "options": ["আইতা", "মা", "খুড়ী", "ভনী"], "category": "family"},
            {"mode": "name_text", "image_desc": "এজন মৰমৰ ডেকা ল'ৰা বা পুত্ৰ", "correct": "পুত্ৰ", "options": ["পুত্ৰ", "ভাই-ককাই", "দেউতা", "নাতি"], "category": "family"},
            {"mode": "name_text", "image_desc": "এজনী মৰমলগা সৰু নাতিনী", "correct": "নাতিনী", "options": ["নাতিনী", "জীয়াৰী", "ভাগিনী", "ভনী"], "category": "family"},
            {"mode": "name_text", "image_desc": "মাটিৰ পৰম্পৰাগত চাকি", "correct": "চাকি", "options": ["চাকি", "মমবাতি", "লেম্প", "মশাল"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "স্বাদভৰা লাড়ুৰ কাঁহী", "correct": "লাড়ু", "options": ["লাড়ু", "ৰসগোল্লা", "গুলাব জামুন", "জিলেপী"], "category": "food"},
            {"mode": "name_text", "image_desc": "অসমৰ ঐতিহ্যবাহী ফুলাম গামোচা", "correct": "গামোচা", "options": ["গামোচা", "চেলেং", "শাল", "কাপোৰ"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "আনন্দমুখৰ বিহু নৃত্য", "correct": "বিহু নৃত্য", "options": ["বিহু নৃত্য", "গৰবা", "ভাংৰা", "ঝুমুৰ"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "কাজিৰঙাৰ এটা খড়্গযুক্ত গঁড়", "correct": "গঁড়", "options": ["গঁড়", "হাতী", "ম'হ", "বাঘ"], "category": "cultural"},
        ],
        "bn": [
            {"mode": "name_text", "image_desc": "স্নেহময়ী হাসিমুখ ঠাকুমা / দিদিমা", "correct": "ঠাকুমা / দিদিমা", "options": ["ঠাকুমা / দিদিমা", "মা", "মাসিমা / পিসিমা", "বোন"], "category": "family"},
            {"mode": "name_text", "image_desc": "এক তরুণ ছেলে বা পুত্র", "correct": "ছেলে / পুত্র", "options": ["ছেলে / পুত্র", "ভাই", "বাবা", "নাতি"], "category": "family"},
            {"mode": "name_text", "image_desc": "একটি মিষ্টি ছোট্ট নাতনি", "correct": "নাতনি", "options": ["নাতনি", "মেয়ে / কন্যা", "ভাগ্নি", "বোন"], "category": "family"},
            {"mode": "name_text", "image_desc": "ঐতিহ্যবাহী মাটির প্রদীপ বা দিয়া", "correct": "প্রদীপ / দিয়া", "options": ["প্রদীপ / দিয়া", "মোমবাতি", "লণ্ঠন", "মশাল"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "এক থালা সুস্বাদু মিষ্টি লাড্ডু", "correct": "লাড্ডু", "options": ["লাড্ডু", "রসগোল্লা", "গোলাপ জাম", "জিলিপি"], "category": "food"},
            {"mode": "name_text", "image_desc": "ঐতিহ্যবাহী লাল-সাদা গামোছা", "correct": "গামোছা", "options": ["গামোছা", "দোপাট্টা", "শাল", "তোয়ালে"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "ঐতিহ্যবাহী বিহু নাচ", "correct": "বিহু নাচ", "options": ["বিহু নাচ", "গরবা", "ভাংড়া", "কথক"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "কাজিরাঙ্গার একশৃঙ্গ গণ্ডার", "correct": "গণ্ডার", "options": ["গণ্ডার", "হাতি", "মহিষ", "বাঘ"], "category": "cultural"},
        ],
        "mni": [
            {"mode": "name_text", "image_desc": "হরাওনা নোংবা ইবেম্মোক", "correct": "ইবেম্মোক", "options": ["ইবেম্মোক", "ইমা", "ইনে", "ইচেন"], "category": "family"},
            {"mode": "name_text", "image_desc": "নৌনা নোংবা মচানুপা", "correct": "মচানুপা", "options": ["মচানুপা", "ইচিল-ইনাও", "ইপা", "ইশু"], "category": "family"},
            {"mode": "name_text", "image_desc": "মচানুপী অঙাং", "correct": "ইশুনুপী", "options": ["ইশুনুপী", "মচানুপী", "ইচে", "ইচল"], "category": "family"},
            {"mode": "name_text", "image_desc": "লৈপাক্কী থাউমৈ", "correct": "থাউমৈ", "options": ["থাউমৈ", "মোমবাতি", "লন্তর্ন", "মৈৰা"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "থুম্বা লদ্দু থাবা পুখাম", "correct": "লদ্দু", "options": ["লদ্দু", "রসগোল্লা", "গুলাব জামুন", "জিলেবী"], "category": "food"},
            {"mode": "name_text", "image_desc": "গামোছা ফি", "correct": "গামোছা", "options": ["গামোছা", "ইন্নাফি", "শাল", "খোদাংফি"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "বিহু জগোই", "correct": "বিহু জগোই", "options": ["বিহু জগোই", "গরবা", "ভাংড়া", "থাং-তা"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "কাযিরঙ্গাগী সমাল য়াবা গেন্দা", "correct": "গেন্দা", "options": ["গেন্দা", "সমু", "ইরোই", "কেই"], "category": "cultural"},
        ],
        "mr": [
            {"mode": "name_text", "image_desc": "हसमुख वृद्ध आजी", "correct": "आजी", "options": ["आजी", "आई", "काकू / मावशी", "बहीण"], "category": "family"},
            {"mode": "name_text", "image_desc": "आनंदी तरुण मुलगा", "correct": "मुलगा", "options": ["मुलगा", "भाऊ", "वडील", "नातू"], "category": "family"},
            {"mode": "name_text", "image_desc": "गोड लहान नात", "correct": "नात", "options": ["नात", "मुलगी", "भाची", "बहीण"], "category": "family"},
            {"mode": "name_text", "image_desc": "पारंपरिक मातीची पणती / दिवा", "correct": "दिवा / पणती", "options": ["दिवा / पणती", "मेणबत्ती", "कंदील", "मशाल"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "स्वादिष्ट लाडवांचे ताट", "correct": "लाडू", "options": ["लाडू", "रसगुल्ला", "गुलाबजाम", "जिलबी"], "category": "food"},
            {"mode": "name_text", "image_desc": "पारंपरिक लाल-पांढरा गमोसा", "correct": "गमोसा", "options": ["गमोसा", "दुपट्टा", "शाल", "टॉवेल"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "पारंपरिक बिहू नृत्य", "correct": "बिहू नृत्य", "options": ["बिहू नृत्य", "गरबा", "भांगडा", "लावणी"], "category": "cultural"},
            {"mode": "name_text", "image_desc": "काझीरंगाचा एकशिंगी गेंडा", "correct": "गेंडा", "options": ["गेंडा", "हत्ती", "रेडा / म्हैस", "वाघ"], "category": "cultural"},
        ],
    }
    
    if len(items) < 3:
        easy_items = FALLBACK_RECOG_ITEMS.get(language, FALLBACK_RECOG_ITEMS["en"])
        count = max(5, 5 - len(items))
        generic_items = random.sample(easy_items, min(count, len(easy_items)))
        for item in generic_items:
            item["is_real_photo"] = False
        items.extend(generic_items)
    
    for item in items:
        if "options" in item:
            random.shuffle(item["options"])
    
    has_real = any(i.get("is_real_photo") for i in items)
    
    titles = {
        "en": "Mukh Chinibo — Who Is This?",
        "hi": "मुख चिनिबो — यह कौन है?",
        "as": "মুখ চিনিবো — এয়া কোন?",
        "bn": "মুখ চিনিবো — এটা কে?",
        "mni": "মুখ চিনিবো — মসি কনানো?",
        "mr": "मुख चिनिबो — हे कोण?",
    }
    instructions = {
        "en": "Look at each photo and answer the question." if has_real else "Upload family photos for a personalized experience!",
        "hi": "हर फोटो देखें और सवाल का जवाब दें।" if has_real else "व्यक्तिगत अनुभव के लिए परिवार की तस्वीरें अपलोड करें!",
        "as": "প্ৰতিখন ফটো চাওক আৰু প্ৰশ্নৰ উত্তৰ দিয়ক।",
        "bn": "প্রতিটি ছবি দেখুন এবং প্রশ্নের উত্তর দিন।",
        "mni": "মশিং মাংগ চাবিয়ু অমসুং ৱাহং কাওবিয়ু।",
        "mr": "प्रत्येक फोटो पहा आणि प्रश्नाचे उत्तर द्या.",
    }
    
    return {
        "game_type": "recognition",
        "game_title": titles.get(language, titles["en"]),
        "game_instruction": instructions.get(language, instructions["en"]),
        "difficulty": difficulty,
        "items": items,
        "xp_reward": 200,
        "domain": "Memory",
        "has_real_photos": has_real
    }


def generate_pattern_game(difficulty="easy", language="en"):
    """Generate 'Bihu Rang' — NE India pattern recall game using cultural motifs."""
    
    # NE India cultural motifs (SVG inline icons rendered in frontend)
    motifs = ["gamosa", "kopou", "elephant", "peacock", "bamboo", "fish"]
    
    # Motif display names by language
    motif_names = {
        "en":  {"gamosa": "Gamosa",    "kopou": "Orchid",       "elephant": "Elephant",    "peacock": "Peacock",     "bamboo": "Bamboo",    "fish": "Fish"},
        "hi":  {"gamosa": "गमोसा",     "kopou": "ऑर्किड",       "elephant": "हाथी",        "peacock": "मोर",         "bamboo": "बांस",      "fish": "मछली"},
        "mr":  {"gamosa": "गमोसा",     "kopou": "ऑर्किड",       "elephant": "हत्ती",       "peacock": "मोर",         "bamboo": "बांबू",     "fish": "मासा"},
        "as":  {"gamosa": "গামোচা",    "kopou": "কপৌ ফুল",     "elephant": "হাতী",        "peacock": "ময়ূৰ",       "bamboo": "বাঁহ",      "fish": "মাছ"},
        "bn":  {"gamosa": "গামোছা",    "kopou": "অর্কিড",       "elephant": "হাতি",        "peacock": "ময়ূর",       "bamboo": "বাঁশ",      "fish": "মাছ"},
        "mni": {"gamosa": "গামোছা",    "kopou": "লৈ",          "elephant": "সা",          "peacock": "ময়ূর",       "bamboo": "ওয়া",      "fish": "ঙা"},
    }
    
    # Motif colors for CSS rendering
    motif_colors = {
        "gamosa":   "#C0392B",  # Gamosa red
        "kopou":    "#D63384",  # Pink orchid
        "elephant": "#E07B54",  # Terracotta
        "peacock":  "#1ABC9C",  # Teal
        "bamboo":   "#27AE60",  # Green
        "fish":     "#2980B9",  # Blue
    }
    
    # SVG path data for each motif (simple flat icons)
    motif_svgs = {
        "gamosa":   '<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="8" y="20" width="48" height="24" rx="3" fill="#FFF" stroke="#C0392B" stroke-width="2.5"/><line x1="8" y1="28" x2="56" y2="28" stroke="#C0392B" stroke-width="2"/><line x1="8" y1="36" x2="56" y2="36" stroke="#C0392B" stroke-width="2"/><path d="M12 24h4v4h-4zM20 24h4v4h-4zM28 24h4v4h-4z" fill="#C0392B" opacity="0.5"/></svg>',
        "kopou":    '<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><ellipse cx="32" cy="28" rx="10" ry="14" fill="#D63384" opacity="0.8"/><ellipse cx="24" cy="32" rx="8" ry="12" fill="#D63384" opacity="0.6" transform="rotate(-30 24 32)"/><ellipse cx="40" cy="32" rx="8" ry="12" fill="#D63384" opacity="0.6" transform="rotate(30 40 32)"/><circle cx="32" cy="30" r="4" fill="#FFD700"/><line x1="32" y1="42" x2="32" y2="56" stroke="#27AE60" stroke-width="2.5"/></svg>',
        "elephant": '<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><ellipse cx="32" cy="30" rx="18" ry="14" fill="#E07B54"/><circle cx="22" cy="24" r="3" fill="#FFF"/><circle cx="22" cy="24" r="1.5" fill="#333"/><path d="M14 30 Q8 40 12 50" stroke="#E07B54" stroke-width="4" fill="none" stroke-linecap="round"/><rect x="22" y="42" width="6" height="12" rx="2" fill="#E07B54"/><rect x="36" y="42" width="6" height="12" rx="2" fill="#E07B54"/><circle cx="42" cy="20" r="8" fill="#E07B54" opacity="0.7"/></svg>',
        "peacock":  '<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M32 8 Q48 16 48 32 Q48 48 32 52 Q16 48 16 32 Q16 16 32 8Z" fill="#1ABC9C" opacity="0.7"/><circle cx="28" cy="24" r="4" fill="#1E3A5F" opacity="0.5"/><circle cx="36" cy="24" r="4" fill="#1E3A5F" opacity="0.5"/><circle cx="32" cy="32" r="4" fill="#1E3A5F" opacity="0.5"/><ellipse cx="32" cy="50" rx="6" ry="4" fill="#1ABC9C"/><circle cx="30" cy="48" r="1" fill="#333"/><path d="M32 54 L32 60" stroke="#E07B54" stroke-width="2"/></svg>',
        "bamboo":   '<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="28" y="4" width="8" height="56" rx="3" fill="#27AE60"/><line x1="28" y1="16" x2="36" y2="16" stroke="#1D8348" stroke-width="2"/><line x1="28" y1="32" x2="36" y2="32" stroke="#1D8348" stroke-width="2"/><line x1="28" y1="48" x2="36" y2="48" stroke="#1D8348" stroke-width="2"/><path d="M36 14 Q44 10 48 16" stroke="#27AE60" stroke-width="1.5" fill="none"/><path d="M28 30 Q20 26 16 32" stroke="#27AE60" stroke-width="1.5" fill="none"/><path d="M36 46 Q44 42 48 48" stroke="#27AE60" stroke-width="1.5" fill="none"/></svg>',
        "fish":     '<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><ellipse cx="30" cy="32" rx="18" ry="12" fill="#2980B9"/><polygon points="48,32 60,20 60,44" fill="#2980B9"/><circle cx="20" cy="28" r="3" fill="#FFF"/><circle cx="20" cy="28" r="1.5" fill="#333"/><path d="M26 36 Q30 40 34 36" stroke="#1A5276" stroke-width="1.5" fill="none"/><line x1="36" y1="28" x2="42" y2="26" stroke="#1A5276" stroke-width="1"/><line x1="36" y1="32" x2="42" y2="32" stroke="#1A5276" stroke-width="1"/><line x1="36" y1="36" x2="42" y2="38" stroke="#1A5276" stroke-width="1"/></svg>',
    }
    
    lang_names = motif_names.get(language, motif_names["en"])
    
    if difficulty == "easy":
        pattern_length = 2
        rounds = 4
        display_time = 3000
    elif difficulty == "medium":
        pattern_length = 3
        rounds = 5
        display_time = 2500
    else:
        pattern_length = 4
        rounds = 6
        display_time = 2000
    
    rounds_data = []
    for i in range(rounds):
        current_length = min(pattern_length + (i // 2), 5)
        pattern = random.sample(motifs, current_length)
        rounds_data.append({
            "round": i + 1,
            "pattern": pattern,
            "pattern_names": [lang_names.get(m, m) for m in pattern],
            "display_time": display_time
        })
    
    # Localized game titles
    titles = {
        "en": "Bihu Rang — Pattern Recall",
        "hi": "बिहू रंग — याद करो",
        "mr": "बिहू रंग — लक्षात ठेवा",
        "as": "বিহু ৰং — মনত ৰাখক",
        "bn": "বিহু রং — মনে রাখো",
        "mni": "বিহু রং — নিংশিংবিয়ু",
    }
    instructions = {
        "en": "Watch the NE India motifs light up, then tap them in the same order.",
        "hi": "पूर्वोत्तर भारत के मोटिफ़ देखें, फिर उसी क्रम में टैप करें।",
        "mr": "ईशान्य भारताचे मोटिफ पहा, मग त्याच क्रमाने टॅप करा.",
        "as": "উত্তৰ-পূব ভাৰতৰ মটিফ চাওক, তাৰ পিছত একেটা ক্ৰমত টেপ কৰক।",
        "bn": "উত্তর-পূর্ব ভারতের মোটিফ দেখুন, তারপর সেই ক্রমে ট্যাপ করুন।",
        "mni": "ঈশান ভারতকী মোটিফ য়েংবিয়ু, অদুনা মখোয়দা থাবিয়ু।",
    }
    
    return {
        "game_type": "pattern",
        "game_title": titles.get(language, titles["en"]),
        "game_instruction": instructions.get(language, instructions["en"]),
        "difficulty": difficulty,
        "motifs_available": motifs,
        "motif_names": lang_names,
        "motif_colors": motif_colors,
        "motif_svgs": motif_svgs,
        "rounds": rounds_data,
        "xp_reward": 250,
        "domain": "Attention",
        # Legacy compat keys (frontend may reference these)
        "colors_available": motifs,
        "color_names": lang_names,
    }


# --- SCORING & ADAPTIVE DIFFICULTY ---

def calculate_game_score(correct, total, reaction_times=None):
    """Calculate score with accuracy and optional reaction time bonus."""
    if total == 0:
        return {"accuracy": 0, "score": 0, "xp": 50}
    
    accuracy = round((correct / total) * 100)
    
    # Base XP
    if accuracy >= 90:
        xp = 300
        grade = "Excellent! 🌟"
    elif accuracy >= 70:
        xp = 200
        grade = "Great job! 👏"
    elif accuracy >= 50:
        xp = 150
        grade = "Good effort! 💪"
    else:
        xp = 100
        grade = "Keep practicing! 🌱"
    
    return {
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "score": accuracy,
        "xp": xp,
        "grade": grade
    }


def get_adaptive_difficulty(game_history):
    """Determine next difficulty based on recent game performance."""
    if not game_history or len(game_history) < 2:
        return "easy"
    
    # Look at last 3 games
    recent = game_history[-3:]
    avg_accuracy = sum(g.get("accuracy", 0) for g in recent) / len(recent)
    
    if avg_accuracy >= 85:
        return "hard"
    elif avg_accuracy >= 60:
        return "medium"
    else:
        return "easy"


ROUTINE_I18N = {
    "en": {
        "morning_time": "🌅 Morning",
        "recog_title": "Mukh Chinibo — Who Is This?",
        "recog_desc": "Recognize family members and loved ones",
        "afternoon_time": "☀️ Afternoon",
        "pattern_title": "Bihu Rang — Pattern Recall",
        "pattern_desc": "Remember NE India motifs in the right order",
        "anytime": "🐯 Anytime",
        "bagh_title": "Bagh-Baak — Tiger Hunt",
        "bagh_desc": "Strategic board game — trap the tiger!",
        "comp_time": "💬 Anytime",
        "comp_title": "Talk to Companion",
        "comp_desc": "Chat about memories, family, and life",
        "dur_5": "5 min", "dur_8": "8 min", "dur_10": "10 min"
    },
    "hi": {
        "morning_time": "🌅 सुबह",
        "recog_title": "मुख चिनिबो — यह कौन है?",
        "recog_desc": "परिवार के सदस्यों और प्रियजनों को पहचानें",
        "afternoon_time": "☀️ दोपहर",
        "pattern_title": "बिहू रंग — याद करो",
        "pattern_desc": "पूर्वोत्तर भारत के प्रतीकों को सही क्रम में याद रखें",
        "anytime": "🐯 कभी भी",
        "bagh_title": "बाघ-बाक — बाघ का शिकार",
        "bagh_desc": "रणनीतिक खेल — बाघ को घेरें!",
        "comp_time": "💬 कभी भी",
        "comp_title": "स्मृति साथी से बात करें",
        "comp_desc": "पुरानी यादों, परिवार और जीवन के बारे में बातचीत",
        "dur_5": "5 मिनट", "dur_8": "8 मिनट", "dur_10": "10 मिनट"
    },
    "as": {
        "morning_time": "🌅 ৰাতিপুৱা",
        "recog_title": "মুখ চিনিবো — এয়া কোন?",
        "recog_desc": "পৰিয়ালৰ সদস্য আৰু আপোনজনক চিনাক্ত কৰক",
        "afternoon_time": "☀️ দুপৰীয়া",
        "pattern_title": "বিহু ৰং — মনত ৰাখক",
        "pattern_desc": "উত্তৰ-পূবৰ প্ৰতীকসমূহ সঠিক ক্ৰমত মনত ৰাখক",
        "anytime": "🐯 যিকোনো সময়ত",
        "bagh_title": "বাঘ-বাক — বাঘ চিকাৰ",
        "bagh_desc": "কৌশলী খেল — বাঘক আৱৰি ধৰক!",
        "comp_time": "💬 যিকোনো সময়ত",
        "comp_title": "সংগীৰ সৈতে কথা পাতক",
        "comp_desc": "পুৰণি স্মৃতি, পৰিয়াল আৰু জীৱনৰ কথা পাতক",
        "dur_5": "৫ মিনিট", "dur_8": "৮ মিনিট", "dur_10": "১০ মিনিট"
    },
    "bn": {
        "morning_time": "🌅 সকাল",
        "recog_title": "মুখ চিনিবো — এটা কে?",
        "recog_desc": "পরিবারের সদস্য ও প্রিয়জনদের চিনুন",
        "afternoon_time": "☀️ দুপুর",
        "pattern_title": "বিহু রং — মনে রাখো",
        "pattern_desc": "উত্তর-পূর্ব ভারতের প্রতীকগুলো সঠিক ক্রমে মনে রাখুন",
        "anytime": "🐯 যেকোনো সময়",
        "bagh_title": "বাঘ-বাক — বাঘ শিকার",
        "bagh_desc": "কৌশলী খেলা — বাঘকে ফাঁদে ফেলুন!",
        "comp_time": "💬 যেকোনো সময়",
        "comp_title": "স্মৃতি সঙ্গীর সাথে কথা বলুন",
        "comp_desc": "পুরোনো স্মৃতি, পরিবার ও জীবনের গল্প করুন",
        "dur_5": "৫ মিনিট", "dur_8": "৮ মিনিট", "dur_10": "১০ মিনিট"
    },
    "mni": {
        "morning_time": "🌅 অয়ুক",
        "recog_title": "মুখ চিনিবো — মসি কনানো?",
        "recog_desc": "ইমুং-মনুংগী মীশিংবু মশক খঙদোকউ",
        "afternoon_time": "☀️ নুমিৎ থাংবা",
        "pattern_title": "বিহু রং — নীংশিংবিয়ু",
        "pattern_desc": "মটিফশিং অচুম্বা পরিংদা নীংশিংবিয়ু",
        "anytime": "🐯 মতম চুপ্পদা",
        "bagh_title": "বাঘ-বাক — কেই তানবা",
        "bagh_desc": "কৌশলী শান্নবা — কেইবু ফাবিয়ু!",
        "comp_time": "💬 মতম চুপ্পদা",
        "comp_title": "মরুপকা ৱারী শানবিয়ু",
        "comp_desc": "নীংশিংবা ৱাফমশিং অমসুং পুন্সিগী ৱারী শানবিয়ু",
        "dur_5": "৫ মিনিট", "dur_8": "৮ মিনিট", "dur_10": "১০ মিনিট"
    },
    "mr": {
        "morning_time": "🌅 सकाळ",
        "recog_title": "मुख चिनिबो — हे कोण?",
        "recog_desc": "कुटुंबातील व्यक्ती आणि आप्तेष्टांना ओळखा",
        "afternoon_time": "☀️ दुपार",
        "pattern_title": "बिहू रंग — लक्षात ठेवा",
        "pattern_desc": "ईशान्य भारतातील चिन्हे योग्य क्रमाने लक्षात ठेवा",
        "anytime": "🐯 केव्हाही",
        "bagh_title": "वाघ-बकरी — वाघाची शिकार",
        "bagh_desc": "रणनीतीचा खेळ — वाघाला घेरून पकडा!",
        "comp_time": "💬 केव्हाही",
        "comp_title": "साथीदाराशी गप्पा मारा",
        "comp_desc": "आठवणी, कुटुंब आणि गप्पांचा आनंद घ्या",
        "dur_5": "५ मिनिटे", "dur_8": "८ मिनिटे", "dur_10": "१० मिनिटे"
    },
}


def get_daily_routine(language="en"):
    """Get today's exercise schedule — NE India themed games, fully localized."""
    lang_code = (language or "en").lower().strip()[:3]
    if lang_code.startswith("mn"): lang_code = "mni"
    elif lang_code.startswith("as"): lang_code = "as"
    elif lang_code.startswith("bn"): lang_code = "bn"
    elif lang_code.startswith("hi"): lang_code = "hi"
    elif lang_code.startswith("mr"): lang_code = "mr"
    else: lang_code = "en"

    txt = ROUTINE_I18N.get(lang_code, ROUTINE_I18N["en"])
    
    routine = []
    
    # Morning: Face recognition
    routine.append({
        "id": "morning",
        "time_label": txt["morning_time"],
        "game_type": "recognition",
        "title": txt["recog_title"],
        "description": txt["recog_desc"],
        "duration": txt["dur_5"],
        "icon": "👤",
        "available": True,
        "completed": False
    })
    
    # Afternoon: Bihu Rang pattern memory
    routine.append({
        "id": "afternoon",
        "time_label": txt["afternoon_time"],
        "game_type": "pattern",
        "title": txt["pattern_title"],
        "description": txt["pattern_desc"],
        "duration": txt["dur_8"],
        "icon": "🎨",
        "available": True,
        "completed": False
    })
    
    # Anytime: Bagh-Baak strategy (available always, not evening-locked)
    routine.append({
        "id": "bagh",
        "time_label": txt["anytime"],
        "game_type": "bagh-baak",
        "title": txt["bagh_title"],
        "description": txt["bagh_desc"],
        "duration": txt["dur_10"],
        "icon": "🐯",
        "available": True,
        "completed": False
    })
    
    # Anytime companion
    routine.append({
        "id": "companion",
        "time_label": txt["comp_time"],
        "game_type": "companion",
        "title": txt["comp_title"],
        "description": txt["comp_desc"],
        "duration": txt["dur_10"],
        "icon": "🤖",
        "available": True,
        "completed": False
    })
    
    return routine


# --- COGNITIVE DOMAIN TRACKING ---

def calculate_domain_scores(game_results):
    """Calculate cognitive domain scores from game history."""
    domain_scores = {}
    
    for domain in COGNITIVE_DOMAINS:
        domain_games = [g for g in game_results if g.get("domain") == domain]
        
        if not domain_games:
            domain_scores[domain] = {"score": 0, "trend": 0, "games_count": 0}
            continue
        
        recent = domain_games[-10:]  # Last 10 games
        avg_score = sum(g.get("accuracy", 0) for g in recent) / len(recent)
        
        # Calculate trend (compare first half vs second half)
        trend = 0
        if len(recent) >= 4:
            first_half = recent[:len(recent)//2]
            second_half = recent[len(recent)//2:]
            first_avg = sum(g.get("accuracy", 0) for g in first_half) / len(first_half)
            second_avg = sum(g.get("accuracy", 0) for g in second_half) / len(second_half)
            trend = round(second_avg - first_avg)
        
        domain_scores[domain] = {
            "score": round(avg_score),
            "trend": trend,
            "games_count": len(domain_games)
        }
    
    return domain_scores


def calculate_overall_score(domain_scores):
    """Calculate overall cognitive score from domain scores."""
    scores = [d["score"] for d in domain_scores.values() if d["score"] > 0]
    if not scores:
        return 0
    return round(sum(scores) / len(scores))


def check_for_alerts(domain_scores, previous_scores=None):
    """Check for significant changes that warrant caregiver alerts."""
    alerts = []
    
    if not previous_scores:
        return alerts
    
    for domain, current in domain_scores.items():
        prev = previous_scores.get(domain, {})
        
        if prev.get("score", 0) > 0 and current.get("score", 0) > 0:
            change = current["score"] - prev["score"]
            
            if change <= -15:
                alerts.append({
                    "type": "critical",
                    "domain": domain,
                    "message": f"{domain} score dropped by {abs(change)}% — consider professional review",
                    "change": change,
                    "timestamp": time.time()
                })
            elif change <= -8:
                alerts.append({
                    "type": "warning",
                    "domain": domain,
                    "message": f"{domain} score decreased by {abs(change)}% this week",
                    "change": change,
                    "timestamp": time.time()
                })
            elif change >= 10:
                alerts.append({
                    "type": "positive",
                    "domain": domain,
                    "message": f"{domain} score improved by {change}% — great progress!",
                    "change": change,
                    "timestamp": time.time()
                })
    
    return alerts


# --- MINI-COG ASSESSMENT ---

def generate_minicog_words(language="en"):
    """Generate 3 random culturally resonant words for Mini-Cog memory test in the patient's language."""
    words_by_lang = {
        "en": [
            ["River", "Bamboo", "Peacock"],
            ["Flower", "Mountain", "Elephant"],
            ["Tea", "Bridge", "Temple"],
            ["Apple", "Garden", "Sun"],
        ],
        "as": [
            ["নৈ (River)", "বাঁহ (Bamboo)", "হাতী (Elephant)"],
            ["ফুল (Flower)", "পাহাৰ (Mountain)", "গামোচা (Gamosa)"],
            ["চাহ (Tea)", "দলং (Bridge)", "মন্দিৰ (Temple)"],
            ["চৰাই (Bird)", "বজাৰ (Market)", "সূৰ্য (Sun)"],
        ],
        "bn": [
            ["নদী (River)", "বাঁশ (Bamboo)", "হাতি (Elephant)"],
            ["ফুল (Flower)", "পাহাড় (Mountain)", "গামোছা (Gamosa)"],
            ["চা (Tea)", "সেতু (Bridge)", "মন্দির (Temple)"],
            ["পাখি (Bird)", "বাজার (Market)", "সূর্য (Sun)"],
        ],
        "mni": [
            ["তুৰেল (River)", "ৱা (Bamboo)", "সা (Elephant)"],
            ["লৈ (Flower)", "চিং (Mountain)", "গামোছা (Gamosa)"],
            ["চা (Tea)", "থোং (Bridge)", "লাইশং (Temple)"],
        ],
        "hi": [
            ["नदी (River)", "बांस (Bamboo)", "हाथी (Elephant)"],
            ["फूल (Flower)", "पहाड़ (Mountain)", "गमोसा (Gamosa)"],
            ["चाय (Tea)", "पुल (Bridge)", "मंदिर (Temple)"],
        ],
        "mr": [
            ["नदी (River)", "बांबू (Bamboo)", "हत्ती (Elephant)"],
            ["फूल (Flower)", "डोंगर (Mountain)", "गमोसा (Gamosa)"],
            ["चहा (Tea)", "पूल (Bridge)", "मंदिर (Temple)"],
        ]
    }
    pool = words_by_lang.get(language, words_by_lang["en"])
    return random.choice(pool)


def score_minicog(words_recalled, clock_score):
    """
    Score Mini-Cog assessment.
    words_recalled: 0-3 (how many of 3 words the patient recalled)
    clock_score: 0-2 (0=abnormal, 1=partial, 2=normal)
    Returns: score (0-5) and suggested stage
    """
    total = words_recalled + clock_score
    
    if total >= 4:
        stage = "mci"
        description = "Mild Cognitive Impairment — mostly independent"
    elif total >= 2:
        stage = "mild"
        description = "Mild Dementia — some difficulty with daily tasks"
    elif total >= 1:
        stage = "moderate"
        description = "Moderate Dementia — needs regular assistance"
    else:
        stage = "severe"
        description = "Severe Dementia — needs full-time care"
    
    return {
        "total_score": total,
        "words_recalled": words_recalled,
        "clock_score": clock_score,
        "suggested_stage": stage,
        "description": description
    }
