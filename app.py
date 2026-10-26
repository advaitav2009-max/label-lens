"""
Label Lens - Main Flask Application
Features:
- Multi-image capture and multi-photo upload for complete packet coverage
- Camera input (Phone via Iriun Webcam / Laptop webcam)
- Flexible multi-product comparison (2, 3, 4+ products)
- Optical Character Recognition (OCR)
- Allergen detection (standard options + custom typed)
- Dietary lifestyle check (Vegetarian, Vegan, Non-Vegetarian, Pescatarian)
- Health aims alignment (structured + custom typed objectives)
- Additives & INS number decoder
- 5-Star recommendation & simplified verdict
- Optional budget & serving recommendation
"""

import os
import re
import json
import base64
import uuid
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify, g, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import database
from analyzer import analyze_food_label, extract_text_from_image
from sample_data import SAMPLE_PRODUCTS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IS_SERVERLESS = (
    os.environ.get("VERCEL") is not None
    or os.environ.get("VERCEL_ENV") is not None
    or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
    or os.environ.get("LAMBDA_TASK_ROOT") is not None
    or os.path.exists("/var/task")
)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.secret_key = os.environ.get("SECRET_KEY", "label-lens-super-secure-key-2026")

# Strict session cookie configuration for persistent authentication across navigations & Vercel rewrites
app.config["APPLICATION_ROOT"] = "/"
app.config["SESSION_COOKIE_NAME"] = "label_lens_session"
app.config["SESSION_COOKIE_PATH"] = "/"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=90)

if IS_SERVERLESS:
    UPLOAD_FOLDER = "/tmp/uploads"
else:
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB max for multiple images

@app.route("/static/uploads/<path:filename>")
def custom_static_uploads(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

with app.app_context():
    database.init_db()

@app.before_request
def load_logged_in_user():
    # Keep session active
    session.permanent = True

    # 1. Device identification (stored in cookie + session for anonymous device history)
    device_id = request.cookies.get("device_id") or session.get("device_id")
    if not device_id:
        device_id = uuid.uuid4().hex
        session["device_id"] = device_id
    g.device_id = device_id

    # 2. User profile session
    user_id = session.get("user_id")
    user_profile = session.get("user_profile")

    if user_id is None and not user_profile:
        g.user = None
    else:
        user = None
        if user_id:
            user = database.get_user_by_id(user_id)

        # In serverless environments, rehydrate user into the current container's SQLite if missing
        if user is None and user_profile:
            try:
                database.restore_user_from_session(user_profile)
                user = database.get_user_by_id(user_profile.get("id"))
            except Exception as e:
                print(f"Error restoring user from session: {e}")
                user = None

        # Fallback profile dictionary if database is temporarily unavailable
        if user is None and user_profile:
            user = {
                "id": user_profile.get("id"),
                "username": user_profile.get("username", "User"),
                "email": user_profile.get("email", ""),
                "password_hash": user_profile.get("password_hash", ""),
                "allergies": user_profile.get("allergies", []),
                "custom_allergies": user_profile.get("custom_allergies", []),
                "dietary_preference": user_profile.get("dietary_preference", "Non-Vegetarian"),
                "avoid_items": user_profile.get("avoid_items", []),
                "health_goals": user_profile.get("health_goals", []),
                "custom_goals": user_profile.get("custom_goals", []),
                "budget_target": user_profile.get("budget_target", 50.0),
                "currency": user_profile.get("currency", "₹"),
                "created_at": "Active"
            }

        g.user = user
        if user and "id" in user:
            session["user_id"] = user["id"]

    # 3. Rehydrate scans from session across serverless micro-VMs
    if session.get("recent_scans"):
        try:
            database.restore_scans_from_session(session.get("recent_scans"))
        except Exception:
            pass

    # 4. Associate anonymous device scans if user is authenticated
    if g.user and hasattr(g, "device_id") and g.device_id:
        try:
            database.claim_device_scans_for_user(g.user["id"], g.device_id)
        except Exception:
            pass

@app.after_request
def set_device_cookie(response):
    if hasattr(g, "device_id") and request.cookies.get("device_id") != g.device_id:
        response.set_cookie(
            "device_id",
            g.device_id,
            max_age=315360000, # 10 years persistent
            path="/",
            httponly=True,
            samesite="Lax"
        )
    return response

@app.context_processor
def inject_user_and_samples():
    return {
        "current_user": g.user,
        "samples": SAMPLE_PRODUCTS
    }

# -------------------------------------------------------------
# Core Authentication & Profile Routes
# -------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        dietary_preference = request.form.get("dietary_preference", "Non-Vegetarian")
        allergies = request.form.getlist("allergies")
        
        # Custom typed medical allergens
        custom_allergies_raw = request.form.get("custom_allergies", "")
        custom_allergies = [a.strip() for a in custom_allergies_raw.split(",") if a.strip()]

        health_goals = request.form.getlist("health_goals")
        custom_goals_raw = request.form.get("custom_goals", "")
        custom_goals = [g.strip() for g in custom_goals_raw.split(",") if g.strip()]

        avoid_items_raw = request.form.get("avoid_items", "")
        avoid_items = [item.strip() for item in avoid_items_raw.split(",") if item.strip()]

        budget_raw = request.form.get("budget_target", "").strip()
        budget_target = float(budget_raw) if budget_raw else None
        currency = request.form.get("currency", "₹")

        if not username or not email or not password:
            flash("Please fill in all required credentials.", "danger")
            return render_template("register.html")

        if database.get_user_by_username(username):
            flash("That username is taken. Please select another.", "danger")
            return render_template("register.html")

        if database.get_user_by_email(email):
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("login"))

        password_hash = generate_password_hash(password)
        user_id = database.create_user(
            username=username,
            email=email,
            password_hash=password_hash,
            allergies=allergies,
            custom_allergies=custom_allergies,
            dietary_preference=dietary_preference,
            avoid_items=avoid_items,
            health_goals=health_goals,
            custom_goals=custom_goals,
            budget_target=budget_target,
            currency=currency
        )

        saved_device_id = session.get("device_id")
        saved_recent_scans = session.get("recent_scans", [])
        session.clear()
        if saved_device_id:
            session["device_id"] = saved_device_id
            try:
                database.claim_device_scans_for_user(user_id, saved_device_id)
            except Exception:
                pass
        if saved_recent_scans:
            for s in saved_recent_scans:
                s["user_id"] = user_id
            session["recent_scans"] = saved_recent_scans
        session["user_id"] = user_id
        session["user_profile"] = {
            "id": user_id,
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "allergies": allergies,
            "custom_allergies": custom_allergies,
            "dietary_preference": dietary_preference,
            "avoid_items": avoid_items,
            "health_goals": health_goals,
            "custom_goals": custom_goals,
            "budget_target": budget_target,
            "currency": currency
        }
        session.permanent = True
        flash(f"Welcome to Label Lens, {username}. Your preferences are saved.", "success")
        return redirect(url_for("scan"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = database.get_user_by_username(identifier)
        if not user:
            user = database.get_user_by_email(identifier.lower())

        if user and check_password_hash(user["password_hash"], password):
            saved_device_id = session.get("device_id")
            saved_recent_scans = session.get("recent_scans", [])
            session.clear()
            if saved_device_id:
                session["device_id"] = saved_device_id
                try:
                    database.claim_device_scans_for_user(user["id"], saved_device_id)
                except Exception:
                    pass
            if saved_recent_scans:
                for s in saved_recent_scans:
                    s["user_id"] = user["id"]
                session["recent_scans"] = saved_recent_scans
            session["user_id"] = user["id"]
            session["user_profile"] = {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "password_hash": user["password_hash"],
                "allergies": user.get("allergies", []),
                "custom_allergies": user.get("custom_allergies", []),
                "dietary_preference": user.get("dietary_preference", "Non-Vegetarian"),
                "avoid_items": user.get("avoid_items", []),
                "health_goals": user.get("health_goals", []),
                "custom_goals": user.get("custom_goals", []),
                "budget_target": user.get("budget_target", 50.0),
                "currency": user.get("currency", "₹")
            }
            session.permanent = True
            flash(f"Authenticated as {user['username']}.", "success")
            return redirect(url_for("scan"))
        else:
            flash("Invalid credentials provided.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    saved_device_id = session.get("device_id")
    session.clear()
    if saved_device_id:
        session["device_id"] = saved_device_id
    flash("Session terminated.", "info")
    return redirect(url_for("index"))

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not g.user:
        flash("Please sign in to manage preferences.", "info")
        return redirect(url_for("login"))

    if request.method == "POST":
        dietary_preference = request.form.get("dietary_preference", "Non-Vegetarian")
        allergies = request.form.getlist("allergies")
        
        custom_allergies_raw = request.form.get("custom_allergies", "")
        custom_allergies = [a.strip() for a in custom_allergies_raw.split(",") if a.strip()]

        health_goals = request.form.getlist("health_goals")
        custom_goals_raw = request.form.get("custom_goals", "")
        custom_goals = [g.strip() for g in custom_goals_raw.split(",") if g.strip()]

        avoid_items_raw = request.form.get("avoid_items", "")
        avoid_items = [item.strip() for item in avoid_items_raw.split(",") if item.strip()]

        budget_raw = request.form.get("budget_target", "").strip()
        budget_target = float(budget_raw) if budget_raw else None
        currency = request.form.get("currency", "₹")

        database.update_user_profile(
            user_id=g.user["id"],
            allergies=allergies,
            custom_allergies=custom_allergies,
            dietary_preference=dietary_preference,
            avoid_items=avoid_items,
            health_goals=health_goals,
            custom_goals=custom_goals,
            budget_target=budget_target,
            currency=currency
        )
        updated_user = database.get_user_by_id(g.user["id"])
        session["user_profile"] = {
            "id": g.user["id"],
            "username": updated_user["username"] if updated_user else g.user.get("username", "User"),
            "email": updated_user["email"] if updated_user else g.user.get("email", ""),
            "password_hash": updated_user["password_hash"] if updated_user else g.user.get("password_hash", ""),
            "allergies": allergies,
            "custom_allergies": custom_allergies,
            "dietary_preference": dietary_preference,
            "avoid_items": avoid_items,
            "health_goals": health_goals,
            "custom_goals": custom_goals,
            "budget_target": budget_target,
            "currency": currency
        }
        session.permanent = True
        flash("Preferences updated successfully.", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html")

# -------------------------------------------------------------
# Scanner & Analysis Routes (Multiple Images Supported)
# -------------------------------------------------------------

@app.route("/scan", methods=["GET", "POST"])
def scan():
    if request.method == "POST":
        product_name = request.form.get("product_name", "").strip()
        category = request.form.get("category", "General Packaged Food")
        raw_text = request.form.get("raw_text", "").strip()

        price_raw = request.form.get("packet_price", "").strip()
        try:
            packet_price = float(price_raw) if price_raw else None
        except ValueError:
            packet_price = None

        servings_raw = request.form.get("servings", "").strip()
        try:
            servings = float(servings_raw) if servings_raw else None
        except ValueError:
            servings = None

        saved_image_rel_paths = []
        extracted_clauses = []

        # 1. Process multiple file uploads if provided
        uploaded_files = request.files.getlist("label_images")
        for file in uploaded_files:
            if file and file.filename != "":
                filename = secure_filename(f"{uuid.uuid4().hex[:10]}_{file.filename}")
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)
                rel_path = f"/static/uploads/{filename}"
                saved_image_rel_paths.append(rel_path)

                extracted = extract_text_from_image(filepath)
                if extracted:
                    extracted_clauses.append(extracted)

        # 2. Process multiple camera frame snapshots if provided
        camera_data_list = request.form.getlist("camera_data[]")
        single_camera_data = request.form.get("camera_data", "").strip()
        if single_camera_data and single_camera_data not in camera_data_list:
            camera_data_list.append(single_camera_data)

        for camera_data in camera_data_list:
            if camera_data and camera_data.startswith("data:image"):
                try:
                    header, encoded = camera_data.split(",", 1)
                    img_bytes = base64.b64decode(encoded)
                    filename = f"capture_{uuid.uuid4().hex[:10]}.jpg"
                    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)
                    saved_image_rel_paths.append(f"/static/uploads/{filename}")

                    extracted = extract_text_from_image(filepath)
                    if extracted:
                        extracted_clauses.append(extracted)
                except Exception as e:
                    print(f"Error handling frame capture: {e}")

        if not raw_text and extracted_clauses:
            raw_text = " ".join(extracted_clauses)

        if not product_name:
            product_name = "Scanned Food Item"

        if not raw_text:
            flash("Please capture or upload label image(s), or paste the ingredient text.", "warning")
            return redirect(url_for("scan"))

        user_profile = g.user if g.user else {
            "allergies": [],
            "custom_allergies": [],
            "dietary_preference": "Non-Vegetarian",
            "avoid_items": [],
            "health_goals": [],
            "custom_goals": [],
            "budget_target": None
        }

        # Analyze combined ingredient clause
        analysis = analyze_food_label(
            raw_text=raw_text,
            user_profile=user_profile,
            packet_price=packet_price,
            servings=servings,
            category=category
        )

        cost_per_serving = analysis.get("cost_per_serving") or 0.0
        primary_image_path = saved_image_rel_paths[0] if saved_image_rel_paths else None

        user_id = g.user["id"] if g.user else None
        device_id = getattr(g, "device_id", None)
        scan_id = database.save_scan(
            user_id=user_id,
            device_id=device_id,
            product_name=product_name,
            category=category,
            packet_price=packet_price or 0.0,
            servings=servings or 0.0,
            cost_per_serving=cost_per_serving,
            image_path=primary_image_path,
            raw_text=raw_text,
            clean_ingredients=analysis["clean_ingredients"],
            overall_score=analysis["score"],
            star_rating=analysis["star_rating"],
            verdict=analysis["verdict"],
            verdict_badge=analysis["verdict_badge"],
            analysis_dict=analysis
        )

        # Cache scan in signed session cookie for serverless container persistence
        recent_scans = session.get("recent_scans", [])
        scan_entry = {
            "id": scan_id,
            "user_id": user_id,
            "device_id": device_id,
            "product_name": product_name,
            "category": category,
            "packet_price": packet_price or 0.0,
            "servings": servings or 0.0,
            "cost_per_serving": cost_per_serving,
            "image_path": primary_image_path,
            "raw_text": raw_text,
            "clean_ingredients": analysis["clean_ingredients"],
            "overall_score": analysis["score"],
            "star_rating": analysis["star_rating"],
            "verdict": analysis["verdict"],
            "verdict_badge": analysis["verdict_badge"],
            "analysis": analysis,
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
        recent_scans = [s for s in recent_scans if s.get("id") != scan_id and s.get("product_name") != product_name][:10]
        recent_scans.insert(0, scan_entry)
        session["recent_scans"] = recent_scans
        session.permanent = True

        return redirect(url_for("view_scan", scan_id=scan_id))

    return render_template("scan.html")

@app.route("/edit_scan/<int:scan_id>", methods=["POST"])
def edit_scan(scan_id):
    scan = database.get_scan_by_id(scan_id)
    if not scan:
        flash("Record not located.", "danger")
        return redirect(url_for("history"))

    product_name = request.form.get("product_name", scan["product_name"]).strip()
    category = request.form.get("category", scan["category"]).strip()
    raw_text = request.form.get("raw_text", scan["raw_text"]).strip()

    price_raw = request.form.get("packet_price", "").strip()
    try:
        packet_price = float(price_raw) if price_raw else None
    except ValueError:
        packet_price = None

    servings_raw = request.form.get("servings", "").strip()
    try:
        servings = float(servings_raw) if servings_raw else None
    except ValueError:
        servings = None

    user_profile = g.user if g.user else {
        "allergies": [],
        "custom_allergies": [],
        "dietary_preference": "Non-Vegetarian",
        "avoid_items": [],
        "health_goals": [],
        "custom_goals": [],
        "budget_target": None
    }

    # Re-run analysis with corrected values
    analysis = analyze_food_label(
        raw_text=raw_text,
        user_profile=user_profile,
        packet_price=packet_price,
        servings=servings,
        category=category
    )

    cost_per_serving = analysis.get("cost_per_serving") or 0.0

    database.update_scan(
        scan_id=scan_id,
        product_name=product_name,
        category=category,
        packet_price=packet_price or 0.0,
        servings=servings or 0.0,
        cost_per_serving=cost_per_serving,
        raw_text=raw_text,
        clean_ingredients=analysis["clean_ingredients"],
        overall_score=analysis["score"],
        star_rating=analysis["star_rating"],
        verdict=analysis["verdict"],
        verdict_badge=analysis["verdict_badge"],
        analysis_dict=analysis
    )

    flash("Product details updated and re-evaluated successfully.", "success")
    return redirect(url_for("view_scan", scan_id=scan_id))

@app.route("/analyze_sample", methods=["POST"])
def analyze_sample():
    sample_id = request.form.get("sample_id")
    target_sample = None
    for s in SAMPLE_PRODUCTS:
        if s["id"] == sample_id:
            target_sample = s
            break

    if not target_sample:
        flash("Reference sample not found.", "warning")
        return redirect(url_for("scan"))

    user_profile = g.user if g.user else {
        "allergies": [],
        "custom_allergies": [],
        "dietary_preference": "Non-Vegetarian",
        "avoid_items": [],
        "health_goals": ["reduced_sugar", "clean_eating"],
        "custom_goals": [],
        "budget_target": None
    }

    analysis = analyze_food_label(
        raw_text=target_sample["raw_text"],
        user_profile=user_profile,
        packet_price=target_sample["packet_price"],
        servings=target_sample["servings"],
        category=target_sample["category"]
    )

    cost_per_serving = round(target_sample["packet_price"] / max(1.0, target_sample["servings"]), 2)
    user_id = g.user["id"] if g.user else None
    device_id = getattr(g, "device_id", None)

    scan_id = database.save_scan(
        user_id=user_id,
        device_id=device_id,
        product_name=target_sample["product_name"],
        category=target_sample["category"],
        packet_price=target_sample["packet_price"],
        servings=target_sample["servings"],
        cost_per_serving=cost_per_serving,
        image_path=target_sample["image_url"],
        raw_text=target_sample["raw_text"],
        clean_ingredients=analysis["clean_ingredients"],
        overall_score=analysis["score"],
        star_rating=analysis["star_rating"],
        verdict=analysis["verdict"],
        verdict_badge=analysis["verdict_badge"],
        analysis_dict=analysis
    )

    # Cache sample analysis in signed session cookie
    recent_scans = session.get("recent_scans", [])
    scan_entry = {
        "id": scan_id,
        "user_id": user_id,
        "device_id": device_id,
        "product_name": target_sample["product_name"],
        "category": target_sample["category"],
        "packet_price": target_sample["packet_price"],
        "servings": target_sample["servings"],
        "cost_per_serving": cost_per_serving,
        "image_path": target_sample["image_url"],
        "raw_text": target_sample["raw_text"],
        "clean_ingredients": analysis["clean_ingredients"],
        "overall_score": analysis["score"],
        "star_rating": analysis["star_rating"],
        "verdict": analysis["verdict"],
        "verdict_badge": analysis["verdict_badge"],
        "analysis": analysis,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    recent_scans = [s for s in recent_scans if s.get("id") != scan_id and s.get("product_name") != target_sample["product_name"]][:10]
    recent_scans.insert(0, scan_entry)
    session["recent_scans"] = recent_scans
    session.permanent = True

    return redirect(url_for("view_scan", scan_id=scan_id))

@app.route("/result/<int:scan_id>")
def view_scan(scan_id):
    scan = database.get_scan_by_id(scan_id)
    if not scan and session.get("recent_scans"):
        database.restore_scans_from_session(session.get("recent_scans"))
        scan = database.get_scan_by_id(scan_id)
    if not scan:
        flash("Record not located.", "danger")
        return redirect(url_for("history"))
    return render_template("result.html", scan=scan)

# -------------------------------------------------------------
# Multi-Product Comparison (2, 3, 4+ Products)
# -------------------------------------------------------------

@app.route("/compare")
def compare():
    if session.get("recent_scans"):
        database.restore_scans_from_session(session.get("recent_scans"))
    user_id = g.user["id"] if g.user else None
    device_id = getattr(g, "device_id", None)
    all_scans = database.get_user_scans(user_id=user_id, device_id=device_id, limit=50)

    # Allow arbitrary number of products via query params: ?prod=1&prod=2&prod=3
    selected_ids = request.args.getlist("prod", type=int)

    # Legacy support for ?prod1=1&prod2=2
    p1_legacy = request.args.get("prod1", type=int)
    p2_legacy = request.args.get("prod2", type=int)
    if p1_legacy and p1_legacy not in selected_ids:
        selected_ids.append(p1_legacy)
    if p2_legacy and p2_legacy not in selected_ids:
        selected_ids.append(p2_legacy)

    # Defaults if none selected
    if not selected_ids and len(all_scans) >= 2:
        selected_ids = [all_scans[0]["id"], all_scans[1]["id"]]
    elif not selected_ids and len(all_scans) == 1:
        selected_ids = [all_scans[0]["id"]]

    products = database.get_scans_by_ids(selected_ids)

    # Determine optimal winner among all selected products
    optimal_product = None
    if products:
        optimal_product = max(products, key=lambda p: (p["star_rating"], -p["cost_per_serving"] if p["cost_per_serving"] > 0 else -999))

    return render_template("compare.html", all_scans=all_scans, products=products, selected_ids=selected_ids, optimal_product=optimal_product)

@app.route("/compare_with/<int:scan_id>")
def compare_with(scan_id):
    primary = database.get_scan_by_id(scan_id)
    if not primary and session.get("recent_scans"):
        database.restore_scans_from_session(session.get("recent_scans"))
        primary = database.get_scan_by_id(scan_id)
    if not primary:
        return redirect(url_for("compare"))

    candidates = database.get_scans_by_category(primary["category"], exclude_id=scan_id)
    if candidates:
        other_ids = [candidates[0]["id"]]
    else:
        user_id = g.user["id"] if g.user else None
        device_id = getattr(g, "device_id", None)
        all_scans = database.get_user_scans(user_id=user_id, device_id=device_id, limit=10)
        other_ids = [all_scans[0]["id"]] if all_scans and all_scans[0]["id"] != scan_id else []

    params = [f"prod={scan_id}"] + [f"prod={oid}" for oid in other_ids]
    return redirect(f"/compare?{'&'.join(params)}")

@app.route("/history")
def history():
    if session.get("recent_scans"):
        database.restore_scans_from_session(session.get("recent_scans"))
    user_id = g.user["id"] if g.user else None
    device_id = getattr(g, "device_id", None)
    scans = database.get_user_scans(user_id=user_id, device_id=device_id)
    return render_template("history.html", scans=scans)

@app.route("/delete_scan/<int:scan_id>", methods=["POST"])
def delete_scan_route(scan_id):
    user_id = g.user["id"] if g.user else None
    device_id = getattr(g, "device_id", None)
    deleted = database.delete_scan(scan_id, user_id=user_id, device_id=device_id)
    recent_scans = session.get("recent_scans", [])
    if recent_scans:
        session["recent_scans"] = [s for s in recent_scans if s.get("id") != scan_id]
        session.permanent = True
    if deleted:
        flash("Record removed from history.", "info")
    else:
        flash("Record could not be removed or record not found.", "danger")
    return redirect(url_for("history"))

@app.route("/api/sync_scans", methods=["POST"])
def sync_scans():
    try:
        data = request.get_json(force=True, silent=True) or {}
        client_scans = data.get("scans", [])
        if not client_scans:
            return jsonify({"status": "empty", "synced": 0})

        user_id = g.user["id"] if g.user else None
        device_id = getattr(g, "device_id", None)

        for s in client_scans:
            if user_id and not s.get("user_id"):
                s["user_id"] = user_id
            if device_id and not s.get("device_id"):
                s["device_id"] = device_id

        database.restore_scans_from_session(client_scans)

        recent = session.get("recent_scans", [])
        existing_ids = {s.get("id") for s in recent}
        for s in client_scans:
            if s.get("id") not in existing_ids:
                recent.append(s)
                existing_ids.add(s.get("id"))
        session["recent_scans"] = recent[:10]
        session.permanent = True

        return jsonify({"status": "ok", "synced": len(client_scans)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/guide")
def guide():
    return render_template("guide.html")

@app.errorhandler(404)
def custom_404(e):
    return jsonify({
        "error": "Flask 404 Not Found",
        "path": request.path,
        "full_path": request.full_path,
        "url": request.url,
        "base_url": request.base_url,
        "PATH_INFO": request.environ.get("PATH_INFO"),
        "SCRIPT_NAME": request.environ.get("SCRIPT_NAME"),
        "RAW_URI": request.environ.get("RAW_URI"),
        "REQUEST_URI": request.environ.get("REQUEST_URI"),
        "QUERY_STRING": request.environ.get("QUERY_STRING"),
        "available_rules": [str(rule) for rule in app.url_map.iter_rules()]
    }), 404

# Register mirrored routes for Vercel serverless environments
# Ensures all endpoints resolve whether Vercel routes to '/' or '/api/index' or '/api/index/<route>'
for _rule in list(app.url_map.iter_rules()):
    if _rule.endpoint != "static" and not _rule.rule.startswith("/api/index"):
        _clean_rule = "" if _rule.rule == "/" else _rule.rule
        app.add_url_rule(
            f"/api/index{_clean_rule}",
            endpoint=f"vercel_{_rule.endpoint}",
            view_func=app.view_functions[_rule.endpoint],
            methods=_rule.methods,
            strict_slashes=False
        )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
