"""
Label Lens - Food Label Analysis Engine
Performs text extraction, ingredient parsing, non-food detection, allergen detection,
diet verification, goal alignment, additive decoding, and scoring.
"""

import re
import os
import json
from additives_db import (
    ADDITIVES_CATALOG,
    SUGAR_ALIASES,
    UNHEALTHY_FATS,
    ALLERGEN_CATEGORIES,
    NON_VEG_INGREDIENTS,
    VEGAN_EXCLUSIONS,
    BENEFICIAL_INGREDIENTS,
    CATEGORY_BENCHMARKS
)

COMMON_FOOD_INDICATORS = [
    "ingredients", "ingredient", "contains", "sugar", "salt", "oil", "flour", "wheat",
    "water", "milk", "butter", "cocoa", "syrup", "extract", "acid", "starch", "flavor",
    "flavour", "preservative", "emulsifier", "stabilizer", "protein", "sodium", "fat",
    "fats", "carbohydrate", "energy", "calories", "kcal", "malt", "yeast", "spices",
    "masala", "powder", "gum", "lecithin", "sorbate", "benzoate", "gluten", "soy",
    "soya", "seeds", "nuts", "oats", "rice", "corn", "dextrose", "fructose", "glucose",
    "vitamins", "minerals", "calcium", "iron", "barley", "maida", "atta", "cream",
    "edible", "palm", "sunflower", "groundnut", "peanut", "paste", "puree", "juice",
    "fruit", "curd", "cheese", "sauce", "chilli", "onion", "garlic", "coriander",
    "turmeric", "cumin", "pepper", "cinnamon", "ginger", "clove", "cardamom",
    "servings", "serving size", "net wt", "net weight", "best before"
]

# Optional pytesseract backend support
PYTESSERACT_AVAILABLE = False
try:
    import pytesseract
    from PIL import Image
    possible_tess_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\HP\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    ]
    for p in possible_tess_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break
    PYTESSERACT_AVAILABLE = True
except Exception:
    PYTESSERACT_AVAILABLE = False

def extract_text_from_image(image_path):
    if not PYTESSERACT_AVAILABLE:
        return ""
    try:
        from PIL import Image
        img = Image.open(image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        print(f"Server OCR Error: {e}")
        return ""

def clean_and_normalize_text(raw_text):
    if not raw_text:
        return ""
    
    text = raw_text.replace("\r", " ").replace("\n", " ")
    
    # Isolate ingredients section if explicit ingredients header is present
    # Only stop at clearly distinct nutrition tables or manufacturer addresses
    match = re.search(
        r"(?:INGREDIENTS|INGREDIENT|CONTAINS)\s*[:\-]\s*(.*?)(?:NUTRITION(?:AL)?\s+(?:INFO|FACTS|VALUES|TABLE)|TYPICAL VALUES PER|BEST BEFORE DATE|$)",
        text,
        re.IGNORECASE
    )
    if match and len(match.group(1).strip()) > 15:
        isolated = match.group(1).strip()
    else:
        isolated = text

    # Remove excessive OCR formatting noise
    cleaned = re.sub(r"[\t|]+", " ", isolated)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def split_into_ingredient_list(text):
    if not text:
        return []
    
    tokens = re.split(r"[,;•|]+(?![^(]*\))", text)
    cleaned_tokens = []
    for token in tokens:
        cleaned = token.strip(" .[](){}-*:\t")
        if len(cleaned) > 1:
            cleaned_tokens.append(cleaned)
    return cleaned_tokens

def analyze_food_label(raw_text, user_profile=None, packet_price=None, servings=None, category="General Packaged Food"):
    """
    Performs comprehensive analysis against user preferences, typed allergens,
    diet restrictions, and health goals. Also validates whether the text represents
    a genuine food label or unrelated content.
    """
    user_profile = user_profile or {}
    user_allergies = [a.lower().strip() for a in user_profile.get("allergies", [])]
    custom_allergies = [ca.lower().strip() for ca in user_profile.get("custom_allergies", [])]
    user_diet = user_profile.get("dietary_preference", "Non-Vegetarian")
    user_avoid = [av.lower().strip() for av in user_profile.get("avoid_items", [])]
    user_goals = [g.lower().strip() for g in user_profile.get("health_goals", [])]
    custom_goals = [cg.lower().strip() for cg in user_profile.get("custom_goals", [])]
    
    raw_budget = user_profile.get("budget_target")
    user_budget = float(raw_budget) if raw_budget is not None and str(raw_budget).strip() != "" else None

    clean_text = clean_and_normalize_text(raw_text)
    ingredients_list = split_into_ingredient_list(clean_text)
    # Search across both cleaned text and full raw text so no additives or allergens are missed
    lower_text = " " + raw_text.lower() + " " + clean_text.lower() + " "

    # 1. Detect Additives & INS/E Numbers
    detected_additives = []
    seen_additive_keys = set()
    
    ins_matches = re.findall(
        r"(?:INS|E|1NS|lNS)[\s\.\-]*(?:No\.?)?[\s\-]*([0-9]{3,4}[a-z]?(?:\([iIvVxX0-9]+\))?)",
        lower_text,
        re.IGNORECASE
    )
    paren_matches = re.findall(r"\(([0-9]{3,4}[a-z]?(?:\([iIvVxX0-9]+\))?)\)", lower_text)
    func_matches = re.findall(
        r"(?:thickener|acidity regulator|stabilizer|emulsifier|preservative|flavour enhancer|flavor enhancer|colour|color|humectant|raising agent|anti-?caking agent)s?[\s\:]*([0-9]{3,4}[a-z]?(?:\([iIvVxX0-9]+\))?)",
        lower_text,
        re.IGNORECASE
    )
    comma_matches = re.findall(r"(?:,|and|\()\s*([0-9]{3,4}[a-z]?(?:\([iIvVxX0-9]+\))?)\s*(?:\)|,|\b)", lower_text)

    # Normalize codes (e.g. '501(i)' -> '501', '501i' -> '501')
    raw_extracted_codes = set(ins_matches + paren_matches + func_matches + comma_matches)
    normalized_codes = set()
    for c in raw_extracted_codes:
        normalized_codes.add(c.lower())
        num_only = re.sub(r"[\(\)iIvVxX\s]", "", c.lower())
        if num_only:
            normalized_codes.add(num_only)

    for code, details in ADDITIVES_CATALOG.items():
        base_code = code.lower()
        matched = False
        for c in normalized_codes:
            if c.startswith(base_code) or (base_code.startswith(c) and len(c) >= 3):
                matched = True
                break
        
        if not matched:
            name_parts = details["name"].lower().split("(")
            primary_name = name_parts[0].strip()
            if primary_name and len(primary_name) > 3 and primary_name in lower_text:
                matched = True
        
        if matched and code not in seen_additive_keys:
            seen_additive_keys.add(code)
            detected_additives.append({
                "code": code,
                "name": details["name"],
                "category": details["category"],
                "risk": details["risk"],
                "safety": details["safety"],
                "vegan": details["vegan"],
                "vegetarian": details["vegetarian"],
                "description": details["description"]
            })

    # 2. Detect Added & Hidden Sugars
    detected_sugars = []
    for sugar in SUGAR_ALIASES:
        pattern = r"\b" + re.escape(sugar) + r"\b"
        if re.search(pattern, lower_text):
            if sugar.title() not in detected_sugars:
                detected_sugars.append(sugar.title())

    # 3. Detect Unhealthy & Ultra-Processed Oils / Fats
    detected_fats = []
    for fat in UNHEALTHY_FATS:
        pattern = r"\b" + re.escape(fat) + r"\b"
        if re.search(pattern, lower_text):
            if fat.title() not in detected_fats:
                detected_fats.append(fat.title())

    # 4. Check Allergens (Standard Options + Custom Typed)
    detected_allergens = []
    user_allergen_warnings = []
    
    for allergy_key, keywords in ALLERGEN_CATEGORIES.items():
        found = False
        matching_keyword = ""
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, lower_text):
                found = True
                matching_keyword = kw
                break
        if found:
            display_name = allergy_key.replace("_", " ").title()
            detected_allergens.append({
                "type": allergy_key,
                "keyword": matching_keyword,
                "display": display_name
            })
            if allergy_key in user_allergies or any(allergy_key in ua for ua in user_allergies):
                user_allergen_warnings.append(display_name)

    # Check custom typed allergens
    for custom_al in custom_allergies:
        if custom_al and len(custom_al) >= 2:
            pattern = r"\b" + re.escape(custom_al) + r"\b"
            if re.search(pattern, lower_text):
                warning_label = custom_al.title()
                if warning_label not in user_allergen_warnings:
                    user_allergen_warnings.append(warning_label)

    # 5. Check Dietary Compatibility
    diet_conflicts = []
    is_non_veg = False
    is_non_vegan = False

    for item in NON_VEG_INGREDIENTS:
        pattern = r"\b" + re.escape(item) + r"\b"
        if re.search(pattern, lower_text):
            is_non_veg = True
            is_non_vegan = True
            if user_diet in ["Vegetarian", "Vegan"]:
                diet_conflicts.append(f"Non-Vegetarian ingredient found: '{item.title()}'")
            elif user_diet == "Pescatarian" and item not in ["fish", "shrimp", "anchovy", "crab", "prawn"]:
                diet_conflicts.append(f"Non-Pescatarian animal derivative: '{item.title()}'")
            break

    if not is_non_veg:
        for item in VEGAN_EXCLUSIONS:
            pattern = r"\b" + re.escape(item) + r"\b"
            if re.search(pattern, lower_text):
                is_non_vegan = True
                if user_diet == "Vegan":
                    diet_conflicts.append(f"Animal or dairy derivative found: '{item.title()}' (Unsuitable for Vegans)")
                break

    # 6. Check Personal Avoid Blacklist
    avoid_conflicts = []
    for item in user_avoid:
        if item and len(item) > 2:
            pattern = r"\b" + re.escape(item) + r"\b"
            if re.search(pattern, lower_text):
                avoid_conflicts.append(item.title())

    # 7. Beneficial / Positive Ingredients
    detected_beneficial = []
    for good in BENEFICIAL_INGREDIENTS:
        pattern = r"\b" + re.escape(good) + r"\b"
        if re.search(pattern, lower_text):
            if good.title() not in detected_beneficial:
                detected_beneficial.append(good.title())

    # 8. Check Health Goals & Custom Objectives Alignment
    goal_feedbacks = []
    for goal in user_goals:
        if goal in ["reduced_sugar", "reduced sugar", "diabetic"]:
            if len(detected_sugars) >= 2:
                goal_feedbacks.append({
                    "goal": "Reduced Sugar",
                    "status": "warning",
                    "message": f"Contains {len(detected_sugars)} types of added sugars ({', '.join(detected_sugars[:3])}). High glycemic impact."
                })
            elif len(detected_sugars) == 1:
                goal_feedbacks.append({
                    "goal": "Reduced Sugar",
                    "status": "caution",
                    "message": f"Contains added sugar ({detected_sugars[0]}). Monitor portion size."
                })
            else:
                goal_feedbacks.append({
                    "goal": "Reduced Sugar",
                    "status": "good",
                    "message": "No obvious added sugar synonyms detected in ingredients list."
                })

        elif goal in ["increased_protein", "increased protein", "fitness"]:
            protein_markers = ["protein", "whey", "soy protein", "pea protein", "nuts", "almonds", "seeds", "egg", "lentils"]
            found_protein = any(re.search(r"\b" + re.escape(pm) + r"\b", lower_text) for pm in protein_markers)
            if found_protein:
                goal_feedbacks.append({
                    "goal": "Increased Protein",
                    "status": "good",
                    "message": "Contains protein-dense ingredients supporting fitness aims."
                })
            else:
                goal_feedbacks.append({
                    "goal": "Increased Protein",
                    "status": "neutral",
                    "message": "Does not highlight substantial natural protein sources."
                })

        elif goal in ["low_sodium", "low sodium", "bp_care"]:
            sodium_markers = ["salt", "sodium", "msg", "monosodium glutamate", "ins 621", "ins 211", "ins 500"]
            found_sodium = [sm for sm in sodium_markers if re.search(r"\b" + re.escape(sm) + r"\b", lower_text)]
            if len(found_sodium) >= 2:
                goal_feedbacks.append({
                    "goal": "Low Sodium",
                    "status": "warning",
                    "message": f"Contains multiple sodium-bearing additives ({', '.join(found_sodium[:3])})."
                })
            elif found_sodium:
                goal_feedbacks.append({
                    "goal": "Low Sodium",
                    "status": "caution",
                    "message": "Contains added salt or sodium salts."
                })

        elif goal in ["clean_eating", "clean eating", "preservative_free"]:
            unclean_count = len(detected_additives) + len(detected_fats)
            if unclean_count > 2:
                goal_feedbacks.append({
                    "goal": "Clean Eating",
                    "status": "warning",
                    "message": f"Ultra-processed formulation with {unclean_count} synthetic additives and industrial fats."
                })
            elif unclean_count == 0:
                goal_feedbacks.append({
                    "goal": "Clean Eating",
                    "status": "good",
                    "message": "Clean formulation: free from artificial preservatives and synthetic additives."
                })

    for cg in custom_goals:
        if cg and len(cg) >= 2:
            if "gluten" in cg and any(al["type"] == "wheat" for al in detected_allergens):
                goal_feedbacks.append({
                    "goal": cg.title(),
                    "status": "warning",
                    "message": f"Goal '{cg.title()}' conflicted: Contains gluten/wheat components."
                })
            elif "sugar" in cg and detected_sugars:
                goal_feedbacks.append({
                    "goal": cg.title(),
                    "status": "warning",
                    "message": f"Contains {len(detected_sugars)} types of added sugars."
                })
            else:
                goal_feedbacks.append({
                    "goal": cg.title(),
                    "status": "neutral",
                    "message": f"Custom objective '{cg.title()}' monitored during formulation scan."
                })

    # 9. Non-Food Content Detection Check
    food_word_count = sum(1 for w in COMMON_FOOD_INDICATORS if re.search(r"\b" + re.escape(w) + r"\b", lower_text))
    total_signals = len(detected_additives) + len(detected_sugars) + len(detected_fats) + len(detected_allergens) + len(detected_beneficial) + food_word_count

    is_valid_food_label = True
    non_food_warning = False

    if len(clean_text) < 10:
        is_valid_food_label = False
        non_food_warning = True
    elif total_signals == 0 and len(clean_text) > 30:
        # Long text without any food terms, additives, allergens, or ingredients
        is_valid_food_label = False
        non_food_warning = True

    # 10. Calculate Budget & Serving Value (Optional Handling)
    price = None
    if packet_price is not None:
        try:
            val = float(packet_price)
            if val > 0:
                price = val
        except (ValueError, TypeError):
            price = None

    srv = None
    if servings is not None:
        try:
            val = float(servings)
            if val > 0:
                srv = val
        except (ValueError, TypeError):
            srv = None

    cost_per_serving = round(price / srv, 2) if (price is not None and srv is not None) else None
    
    benchmark = CATEGORY_BENCHMARKS.get(category, CATEGORY_BENCHMARKS["General Packaged Food"])
    avg_cat_cost = benchmark["avg_cost_per_serving"]

    if cost_per_serving is not None:
        if user_budget is not None and user_budget > 0:
            if cost_per_serving <= user_budget:
                budget_status = "within_budget"
                budget_msg = f"At ₹{cost_per_serving:.2f} per serving, this comfortably fits within your target budget of ₹{user_budget:.2f}."
            else:
                budget_status = "over_budget"
                budget_msg = f"At ₹{cost_per_serving:.2f} per serving, this exceeds your target budget of ₹{user_budget:.2f}."
        else:
            budget_status = "not_set"
            budget_msg = f"Calculated portion cost: ₹{cost_per_serving:.2f} per serving (category benchmark: approx ₹{avg_cat_cost:.2f})."

        budget_feedback = {
            "packet_price": price,
            "servings": srv,
            "cost_per_serving": cost_per_serving,
            "user_budget": user_budget,
            "category_avg": avg_cat_cost,
            "status": budget_status,
            "message": budget_msg
        }
    else:
        budget_feedback = {
            "packet_price": price,
            "servings": srv,
            "cost_per_serving": None,
            "user_budget": user_budget,
            "category_avg": avg_cat_cost,
            "status": "unspecified",
            "message": "Packet price and/or portion count not specified. Cost per serving comparison omitted."
        }

    # 11. Scoring Algorithm
    if not is_valid_food_label:
        score = 30
        star_rating = 1.5
        verdict = "Non-Food Content / Unrecognized Label"
        verdict_badge = "caution"
        eat_recommendation = "Notice: The scanned text does not appear to contain food packaging declarations or ingredient clauses. Please ensure your camera is positioned over the ingredient list or nutritional facts panel."
        reasons = [
            "Extracted content lacks recognizable food ingredients, additives, or nutritional declarations.",
            "Verify that packaging text was clearly illuminated and within camera bounds."
        ]
    else:
        score = 75

        for add in detected_additives:
            if add["safety"] == "avoid":
                score -= 16
            elif add["safety"] == "caution":
                score -= 8
            elif add["safety"] == "beneficial":
                score += 6

        sugar_count = len(detected_sugars)
        if sugar_count >= 3:
            score -= 18
        elif sugar_count == 2:
            score -= 10
        elif sugar_count == 1:
            score -= 5

        fat_count = len(detected_fats)
        if fat_count >= 2:
            score -= 16
        elif fat_count == 1:
            score -= 10

        score += min(20, len(detected_beneficial) * 6)

        if user_allergen_warnings:
            score -= 40
        
        if diet_conflicts:
            score -= 30

        if avoid_conflicts:
            score -= (len(avoid_conflicts) * 15)

        score = max(8, min(98, score))
        raw_stars = round((score / 100.0) * 5.0, 1)
        star_rating = max(1.0, min(5.0, raw_stars))

        if user_allergen_warnings:
            verdict = "Severe Allergen Risk - Do Not Consume"
            verdict_badge = "danger"
            eat_recommendation = f"Avoid. Contains allergens ({', '.join(user_allergen_warnings)}) matching your active health profile."
        elif diet_conflicts:
            verdict = f"Unsuitable for Your Diet ({user_diet})"
            verdict_badge = "warning"
            eat_recommendation = f"Avoid. This product conflicts with your {user_diet} preference."
        elif avoid_conflicts:
            verdict = "Contains Items on Your Avoid List"
            verdict_badge = "warning"
            eat_recommendation = f"Caution. Contains {', '.join(avoid_conflicts)}, which you specified to avoid."
        elif star_rating >= 4.3:
            verdict = "Strongly Recommended"
            verdict_badge = "safe"
            eat_recommendation = "Suitable for everyday consumption with clean, nutritious ingredients."
        elif star_rating >= 3.6:
            verdict = "Good Choice / Safe to Eat"
            verdict_badge = "safe"
            eat_recommendation = "Relatively balanced formulation with minimal chemical processing."
        elif star_rating >= 2.6:
            verdict = "Consume in Moderation"
            verdict_badge = "caution"
            eat_recommendation = "Consume in moderation due to processed fats, sweeteners, or additive density."
        else:
            verdict = "Not Recommended / Ultra-Processed"
            verdict_badge = "avoid"
            eat_recommendation = "High concentration of industrial fats, multiple sugar synonyms, or flagged additives."

        reasons = []
        if user_allergen_warnings:
            reasons.append(f"Allergen Alert: Contains {', '.join(user_allergen_warnings)}")
        if diet_conflicts:
            reasons.append(f"Diet Conflict: {diet_conflicts[0]}")
        if detected_fats:
            reasons.append(f"Contains low-grade industrial fats: {', '.join(detected_fats[:2])}")
        if len(detected_sugars) >= 2:
            reasons.append(f"Contains multiple hidden sugars ({len(detected_sugars)} types)")
        if detected_beneficial:
            reasons.append(f"Good nutrients inside: {', '.join(detected_beneficial[:3])}")
        if detected_additives:
            high_risk = [a["name"].split("(")[0].strip() for a in detected_additives if a["safety"] == "avoid"]
            if high_risk:
                reasons.append(f"Contains flagged chemical additives: {', '.join(high_risk[:2])}")
            elif len(reasons) < 3:
                reasons.append(f"Identified {len(detected_additives)} food additive codes with safety classifications.")

        if not reasons:
            reasons.append("Standard packaged food composition with no critical flags.")

    return {
        "score": score,
        "star_rating": star_rating,
        "verdict": verdict,
        "verdict_badge": verdict_badge,
        "eat_recommendation": eat_recommendation,
        "reasons": reasons,
        "is_valid_food_label": is_valid_food_label,
        "non_food_warning": non_food_warning,
        "detected_additives": detected_additives,
        "detected_sugars": detected_sugars,
        "detected_fats": detected_fats,
        "detected_allergens": detected_allergens,
        "user_allergen_warnings": user_allergen_warnings,
        "diet_conflicts": diet_conflicts,
        "avoid_conflicts": avoid_conflicts,
        "detected_beneficial": detected_beneficial,
        "goal_feedbacks": goal_feedbacks,
        "budget_feedback": budget_feedback,
        "cost_per_serving": cost_per_serving,
        "packet_price": price,
        "servings": srv,
        "ingredients_count": len(ingredients_list),
        "clean_ingredients": clean_text
    }
