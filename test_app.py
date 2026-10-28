"""
Label Lens - Automated Test Suite
Verifies database integrity, OCR label parsing, allergen matching (options + typed),
non-food text detection, optional price/servings, editing scans, and HTTP routes.
"""

import os
import unittest
import json
import tempfile
import uuid
from app import app
import database
from analyzer import analyze_food_label

class LabelLensTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.temp_db_path
        database.init_db()
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        try:
            os.close(self.temp_db_fd)
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except Exception:
            pass

    def test_database_init_and_user_creation(self):
        rand = uuid.uuid4().hex[:6]
        user_id = database.create_user(
            username=f"nut_{rand}",
            email=f"nut_{rand}@example.com",
            password_hash="fakehash123",
            allergies=["peanuts", "milk"],
            custom_allergies=["kiwi", "strawberries"],
            dietary_preference="Vegetarian",
            avoid_items=["palm oil", "high fructose corn syrup"],
            health_goals=["reduced_sugar", "increased_protein"],
            custom_goals=["high fiber"],
            budget_target=45.0,
            currency="₹"
        )
        self.assertIsNotNone(user_id)
        user = database.get_user_by_id(user_id)
        self.assertEqual(user["username"], f"nut_{rand}")
        self.assertIn("peanuts", user["allergies"])
        self.assertEqual(user["dietary_preference"], "Vegetarian")

    def test_allergen_and_diet_analysis(self):
        user_profile = {
            "allergies": ["peanuts"],
            "custom_allergies": ["kiwi"],
            "dietary_preference": "Vegetarian",
            "avoid_items": ["palm oil"],
            "health_goals": ["reduced_sugar"],
            "budget_target": 30.0
        }

        # 1. Test Peanut Allergy Detection
        peanut_text = "Ingredients: Roasted Peanuts 99%, Salt 1%."
        res1 = analyze_food_label(peanut_text, user_profile=user_profile, packet_price=120.0, servings=4.0)
        self.assertTrue(len(res1["user_allergen_warnings"]) > 0)
        self.assertIn("Peanuts", res1["user_allergen_warnings"])
        self.assertEqual(res1["verdict_badge"], "danger")

        # 2. Test Custom Typed Allergen Detection (kiwi)
        kiwi_text = "Ingredients: Dried Kiwi slices, Cane Sugar, Citric Acid."
        res_kiwi = analyze_food_label(kiwi_text, user_profile=user_profile)
        self.assertTrue(len(res_kiwi["user_allergen_warnings"]) > 0)
        self.assertIn("Kiwi", res_kiwi["user_allergen_warnings"])

        # 3. Test Non-Vegetarian Detection
        gelatin_text = "Ingredients: Sugar, Gelatin, Citric Acid INS 330, Red 40."
        res2 = analyze_food_label(gelatin_text, user_profile=user_profile)
        self.assertTrue(len(res2["diet_conflicts"]) > 0)

        # 4. Test Clean Oats (High Stars) with optional price and servings
        clean_text = "Ingredients: 100% Whole Grain Rolled Oats, Chia Seeds, Roasted Pumpkin Seeds."
        res3 = analyze_food_label(clean_text, user_profile=user_profile, packet_price=None, servings=None)
        self.assertGreaterEqual(res3["star_rating"], 4.2)
        self.assertEqual(res3["verdict_badge"], "safe")
        self.assertIsNone(res3["cost_per_serving"])

        # 5. Test Non-Food Label Text Detection
        non_food_text = "The quick brown fox jumps over the lazy dog. Chapter 4: Principles of Quantum Computing."
        res_non_food = analyze_food_label(non_food_text, user_profile=user_profile)
        self.assertTrue(res_non_food["non_food_warning"])
        self.assertFalse(res_non_food["is_valid_food_label"])
        self.assertIn("Non-Food", res_non_food["verdict"])

    def test_web_routes_and_edit_scan(self):
        # Index
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"LabelLens", resp.data)
        self.assertIn(b"How LabelLens Works", resp.data)

        # Scanner
        resp = self.client.get("/scan")
        self.assertEqual(resp.status_code, 200)

        # Post Scan Form (without price/servings)
        scan_post_resp = self.client.post("/scan", data={
            "product_name": "Test Granola Bar",
            "category": "Breakfast Cereals",
            "packet_price": "",
            "servings": "",
            "raw_text": "Ingredients: Rolled oats, almonds, honey, chia seeds, cold pressed coconut oil."
        }, follow_redirects=True)
        self.assertEqual(scan_post_resp.status_code, 200)
        self.assertIn(b"Test Granola Bar", scan_post_resp.data)
        self.assertIn(b"Pricing Not Provided", scan_post_resp.data)

        # Fetch last inserted scan to test editing
        conn = database.get_db()
        scan_row = conn.execute("SELECT id FROM scans ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        self.assertIsNotNone(scan_row)
        scan_id = scan_row[0]

        # Edit Scan
        edit_resp = self.client.post(f"/edit_scan/{scan_id}", data={
            "product_name": "Updated Granola Bar",
            "category": "Breakfast Cereals",
            "packet_price": "150",
            "servings": "5",
            "raw_text": "Ingredients: Rolled oats, almonds, chia seeds, cold pressed coconut oil."
        }, follow_redirects=True)
        self.assertEqual(edit_resp.status_code, 200)
        self.assertIn(b"Updated Granola Bar", edit_resp.data)
        self.assertIn(b"Product details updated", edit_resp.data)

    def test_history_isolation_and_deletion(self):
        # 1. Device A performs a scan
        client_a = app.test_client()
        client_a.set_cookie("device_id", "device_aaa_111")
        resp_a = client_a.post("/scan", data={
            "product_name": "Device A Snack",
            "category": "Chips & Savory Snacks",
            "packet_price": "50",
            "servings": "2",
            "raw_text": "Ingredients: Potatoes, sunflower oil, iodised salt."
        }, follow_redirects=True)
        self.assertEqual(resp_a.status_code, 200)

        # 2. Device B performs a scan
        client_b = app.test_client()
        client_b.set_cookie("device_id", "device_bbb_222")
        resp_b = client_b.post("/scan", data={
            "product_name": "Device B Cookie",
            "category": "Biscuits & Cookies",
            "packet_price": "30",
            "servings": "1",
            "raw_text": "Ingredients: Wheat flour, butter, sugar."
        }, follow_redirects=True)
        self.assertEqual(resp_b.status_code, 200)

        # 3. Verify history isolation between devices
        hist_a = client_a.get("/history")
        self.assertIn(b"Device A Snack", hist_a.data)
        self.assertNotIn(b"Device B Cookie", hist_a.data)

        hist_b = client_b.get("/history")
        self.assertIn(b"Device B Cookie", hist_b.data)
        self.assertNotIn(b"Device A Snack", hist_b.data)

        # 4. Registered user logs in and tests a food
        user_id = database.create_user(
            username="user_tester",
            email="tester@example.com",
            password_hash="pw123",
            allergies=[],
            custom_allergies=[],
            dietary_preference="Vegetarian",
            avoid_items=[],
            health_goals=[],
            custom_goals=[],
            budget_target=50.0,
            currency="₹"
        )
        client_user = app.test_client()
        with client_user.session_transaction() as sess:
            sess["user_id"] = user_id

        resp_user = client_user.post("/scan", data={
            "product_name": "User Profile Cereal",
            "category": "Breakfast Cereals",
            "packet_price": "199",
            "servings": "6",
            "raw_text": "Ingredients: Whole oats, raisins, honey."
        }, follow_redirects=True)
        self.assertEqual(resp_user.status_code, 200)

        # User's history shows ONLY the user's scan, not device A or B
        hist_user = client_user.get("/history")
        self.assertIn(b"User Profile Cereal", hist_user.data)
        self.assertNotIn(b"Device A Snack", hist_user.data)
        self.assertNotIn(b"Device B Cookie", hist_user.data)

        # 5. Test Deletion: Device A deletes its scan
        scans_a = database.get_user_scans(device_id="device_aaa_111")
        self.assertEqual(len(scans_a), 1)
        scan_a_id = scans_a[0]["id"]

        del_resp = client_a.post(f"/delete_scan/{scan_a_id}", follow_redirects=True)
        self.assertEqual(del_resp.status_code, 200)
        self.assertIn(b"Record removed from history", del_resp.data)

        # Confirm Device A history is now empty
        hist_a_after = client_a.get("/history")
        self.assertNotIn(b"Device A Snack", hist_a_after.data)
        self.assertIn(b"Zero Recorded Evaluations", hist_a_after.data)

        # 6. Test Unauthorized Deletion: Device B tries to delete User's scan
        scans_u = database.get_user_scans(user_id=user_id)
        self.assertEqual(len(scans_u), 1)
        scan_u_id = scans_u[0]["id"]

        unauthorized_del = client_b.post(f"/delete_scan/{scan_u_id}", follow_redirects=True)
        self.assertIn(b"Record could not be removed or record not found", unauthorized_del.data)
        # Ensure User's scan is still intact
        self.assertEqual(len(database.get_user_scans(user_id=user_id)), 1)

    def test_cosmetic_skincare_detection(self):
        # User photographed skincare/cosmetic ingredients and labeled it as Mayonnaise
        skincare_text = "Ingredients: Water, Dimethicone, Cetearyl Alcohol, Niacinamide, Phenoxyethanol, Disodium EDTA, Fragrance."
        res = analyze_food_label(skincare_text)
        
        self.assertTrue(res["is_cosmetic"])
        self.assertFalse(res["is_valid_food_label"])
        self.assertEqual(res["score"], 0)
        self.assertEqual(res["verdict_badge"], "danger")
        self.assertIn("Non-Food / Inedible", res["verdict"])
        self.assertIn("DO NOT EAT / INEDIBLE", res["eat_recommendation"])
        self.assertGreaterEqual(len(res["detected_cosmetics"]), 3)

        # Test web submission via client
        resp = self.client.post("/scan", data={
            "product_name": "Mayonnaise",
            "category": "Sauces & Condiments",
            "packet_price": "85",
            "servings": "10",
            "raw_text": skincare_text
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Inedible Chemical Formulation", resp.data)
        self.assertIn(b"Skincare &amp; Cosmetic Chemicals Detected", resp.data)
        self.assertIn(b"DO NOT INGEST / DO NOT EAT", resp.data)

    def test_palm_oil_and_palmolein_detection(self):
        # 1. Exact raw transcription from user containing Pamolein and Allergen Contains at end
        user_raw = (
            "Potatoes (41%), Edible Vegetable OF ITED, (Pamolein, Cotton Seed, Rice Bran), Sugar Powe. 7, "
            "Rains (8.0%) Cashew Nuts Fox Ames 0 DIA Rice Flakes (2.0%), Sesame seeds, odised Salt "
            "Curry Leaves (1.23), Black Pepper Poder, Cumin M.COM Acidity Regulator (NS330. "
            "y Allergen Information: Contains Nut ___ - a LA. READY-TO-EAT SAVOURIES (PROPRIETARY FOOD) "
            "STORE IN A COOL 8 DRY PLACE, ONCE OPENER STORE \u00a5 1 A TERIAL IN AN AIR TIGHT CONTAINER"
        )
        res_user = analyze_food_label(user_raw)
        self.assertIn("Palmolein (Palm Olein)", res_user["detected_fats"])
        self.assertIn("Cottonseed Oil", res_user["detected_fats"])
        self.assertIn("Rice Bran Oil", res_user["detected_fats"])
        self.assertEqual(res_user["verdict"], "Consume in Moderation")
        self.assertEqual(res_user["verdict_badge"], "caution")
        self.assertLessEqual(res_user["star_rating"], 3.0)
        self.assertIn("Palmolein", res_user["eat_recommendation"])
        self.assertTrue(any("Palmolein" in r for r in res_user["reasons"]))

        # 2. Standalone Palm inside Edible Vegetable Oil parentheses
        res_palm_paren = analyze_food_label("Ingredients: Potatoes, Edible Vegetable Oil (Palm), Iodised Salt.")
        self.assertIn("Palm Oil", res_palm_paren["detected_fats"])
        self.assertEqual(res_palm_paren["verdict"], "Consume in Moderation")
        self.assertIn("Palm Oil", res_palm_paren["eat_recommendation"])
        self.assertLessEqual(res_palm_paren["star_rating"], 3.0)

        # 3. Palm with hyphen / concatenated
        res_hyphen = analyze_food_label("Ingredients: Wheat flour, sugar, palm-oil, salt.")
        self.assertIn("Palm Oil", res_hyphen["detected_fats"])
        self.assertIn("Palm Oil", res_hyphen["eat_recommendation"])

        res_concat = analyze_food_label("Ingredients: Wheat flour, sugar, palmoil, palm fat, salt.")
        self.assertIn("Palm Oil", res_concat["detected_fats"])

        # 4. False positive checks: palm sugar and hearts of palm should NOT trigger palm oil
        res_sugar = analyze_food_label("Ingredients: Organic rolled oats, palm sugar, coconut milk.")
        self.assertNotIn("Palm Oil", res_sugar["detected_fats"])
        self.assertNotIn("Palmolein (Palm Olein)", res_sugar["detected_fats"])

        res_hearts = analyze_food_label("Ingredients: Hearts of palm, water, salt, citric acid.")
        self.assertNotIn("Palm Oil", res_hearts["detected_fats"])

        # 5. Avoid list integration for palm oil
        user_avoid_profile = {
            "allergies": [],
            "custom_allergies": [],
            "dietary_preference": "Non-Vegetarian",
            "avoid_items": ["palm oil"],
            "health_goals": [],
            "custom_goals": [],
            "budget_target": None
        }
        res_avoid = analyze_food_label(user_raw, user_profile=user_avoid_profile)
        self.assertTrue(len(res_avoid["avoid_conflicts"]) > 0)
        self.assertEqual(res_avoid["verdict"], "Contains Items on Your Avoid List")
        self.assertEqual(res_avoid["verdict_badge"], "warning")

        # 6. Web form submission verification
        resp = self.client.post("/scan", data={
            "product_name": "Haldiram Savouries",
            "category": "Chips & Savory Snacks",
            "packet_price": "40",
            "servings": "2",
            "raw_text": user_raw
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Palmolein (Palm Olein)", resp.data)
        self.assertNotIn(b"Free from palm olein and hydrogenated vegetable fats", resp.data)
        self.assertIn(b"Notice: Contains Palmolein", resp.data)

    def test_blurry_and_illegible_photo_detection(self):
        # 1. OCR smear artifacts from severely blurry image
        smeared_text = ".. , _ - | o e a i"
        res_smeared = analyze_food_label(smeared_text)
        self.assertTrue(res_smeared["is_blurry"])
        self.assertFalse(res_smeared["is_valid_food_label"])
        self.assertEqual(res_smeared["verdict"], "Blurry / Illegible Image - Retake Photo")
        self.assertEqual(res_smeared["star_rating"], 1.0)
        self.assertEqual(res_smeared["verdict_badge"], "caution")
        self.assertIn("retake the photo", res_smeared["eat_recommendation"].lower())

        # 2. Fragmented gibberish characters
        gibberish_text = "x j k . ~ - q w e r t"
        res_gibberish = analyze_food_label(gibberish_text)
        self.assertTrue(res_gibberish["is_blurry"])
        self.assertEqual(res_gibberish["verdict"], "Blurry / Illegible Image - Retake Photo")

        # 3. Severe consonant motion blur smear
        short_random = "q z x c v b n m"
        res_random = analyze_food_label(short_random)
        self.assertTrue(res_random["is_blurry"])
        self.assertFalse(res_random["is_valid_food_label"])

        # 4. User sample: 'qaff' extracted from blurry food photo
        res_qaff = analyze_food_label("qaff")
        self.assertTrue(res_qaff["is_blurry"])
        self.assertFalse(res_qaff["is_valid_food_label"])
        self.assertEqual(res_qaff["verdict"], "Blurry / Illegible Image - Retake Photo")
        self.assertEqual(res_qaff["star_rating"], 1.0)
        self.assertEqual(res_qaff["verdict_badge"], "caution")
        self.assertIn("retake the photo", res_qaff["eat_recommendation"].lower())

        # 5. Web view rendering test for blurry advisory
        resp = self.client.post("/scan", data={
            "product_name": "Blurry Food Packet",
            "category": "General Packaged Food",
            "packet_price": "",
            "servings": "",
            "raw_text": "qaff"
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Photo Too Blurry to Read Ingredients", resp.data)
        self.assertIn(b"Retake Photo", resp.data)
        self.assertIn(b"Not evaluated: Image too blurry to resolve ingredients", resp.data)

    def test_makeup_and_expanded_cosmetics_detection(self):
        # 1. Foundation makeup
        foundation_text = "Aqua, Cyclopentasiloxane, Dimethicone, Isododecane, Mica, Phenoxyethanol, Ethylhexylglycerin, Titanium Dioxide, Iron Oxides."
        res_f = analyze_food_label(foundation_text)
        self.assertTrue(res_f["is_cosmetic"])
        self.assertEqual(res_f["score"], 0)
        self.assertEqual(res_f["verdict_badge"], "danger")
        self.assertIn("Non-Food / Inedible", res_f["verdict"])
        self.assertIn("DO NOT EAT / INEDIBLE", res_f["eat_recommendation"])

        # 2. Waterproof Mascara
        mascara_text = "Waterproof Mascara with Beeswax and Iron Oxides, Isododecane, Disteardimonium Hectorite, Propylene Carbonate."
        res_m = analyze_food_label(mascara_text)
        self.assertTrue(res_m["is_cosmetic"])
        self.assertEqual(res_m["verdict_badge"], "danger")

        # 3. Lipstick
        lipstick_text = "Matte Lipstick with Dimethicone, Polyethylene, Synthetic Wax, CI 77491, CI 15850, BHT."
        res_l = analyze_food_label(lipstick_text)
        self.assertTrue(res_l["is_cosmetic"])

        # 4. Sunscreen SPF
        sunscreen_text = "Ultra Sheer Sunscreen SPF 50 with Avobenzone 3%, Homosalate 10%, Octisalate 5%, Oxybenzone 6%, For external use only."
        res_s = analyze_food_label(sunscreen_text)
        self.assertTrue(res_s["is_cosmetic"])

    def test_non_food_general_documents(self):
        # 1. Invoice text
        invoice_text = "INVOICE #10294 Date: 2026-10-15 Customer: ABC Corp Subtotal: $450.00 Total Due: $486.00 Payment method: Credit Card"
        res_inv = analyze_food_label(invoice_text)
        self.assertTrue(res_inv["is_non_food"])
        self.assertFalse(res_inv["is_valid_food_label"])
        self.assertEqual(res_inv["verdict"], "Non-Food Content / Unrelated Text")

        # 2. Python technical instruction
        tech_text = "Install Python 3.11 and configure virtual environment. Run pip install flask. Then start the application with python app.py on port 5000."
        res_tech = analyze_food_label(tech_text)
        self.assertTrue(res_tech["is_non_food"])
        self.assertEqual(res_tech["verdict"], "Non-Food Content / Unrelated Text")

        # 3. Quantum physics article
        physics_text = "Quantum mechanics is a fundamental theory in physics that provides a description of the physical properties of nature at atomic scale."
        res_phy = analyze_food_label(physics_text)
        self.assertTrue(res_phy["is_non_food"])
        self.assertEqual(res_phy["verdict"], "Non-Food Content / Unrelated Text")

    def test_clean_whole_food_tea_and_botanicals(self):
        # User inquiry case: 2 ingredients green tea, dandelion root
        clean_tea_text = "Ingredients: green tea, dandelion root"
        res = analyze_food_label(clean_tea_text)
        
        self.assertGreaterEqual(res["score"], 95)
        self.assertGreaterEqual(res["star_rating"], 4.8)
        self.assertEqual(res["verdict"], "Strongly Recommended (100% Pure Formulation)")
        self.assertEqual(res["verdict_badge"], "safe")
        self.assertNotIn("minimal chemical processing", res["eat_recommendation"])
        self.assertIn("100% natural ingredients", res["eat_recommendation"])
        self.assertTrue(any("100% pure whole-food" in r for r in res["reasons"]))
        self.assertIn("Green Tea", res["detected_beneficial"])

        # Web submission test
        resp = self.client.post("/scan", data={
            "product_name": "Organic Green Tea",
            "category": "Juices & Beverages",
            "packet_price": "180",
            "servings": "25",
            "raw_text": "green tea, dandelion root for green tea"
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Strongly Recommended (100% Pure Formulation)", resp.data)
        self.assertNotIn(b"minimal chemical processing", resp.data)

    def test_session_persistence_and_serverless_rehydration(self):
        # 1. Register a user via the web interface
        unique_name = f"persist_{uuid.uuid4().hex[:6]}"
        reg_resp = self.client.post("/register", data={
            "username": unique_name,
            "email": f"{unique_name}@example.com",
            "password": "Password123!",
            "dietary_preference": "Vegetarian",
            "allergies": ["peanuts", "milk"],
            "custom_allergies": "hazelnut",
            "health_goals": ["reduced_sugar"],
            "custom_goals": "high protein",
            "avoid_items": "palm oil",
            "budget_target": "75.0",
            "currency": "₹"
        }, follow_redirects=True)
        self.assertEqual(reg_resp.status_code, 200)

        # 2. Verify user is logged in and session cookie is scoped to '/'
        cookie = self.client.get_cookie("label_lens_session")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.path, "/")

        # 3. Navigate across different pages: /scan, /history, /compare, /guide, /profile
        pages = ["/scan", "/history", "/compare", "/guide", "/profile"]
        for p in pages:
            res = self.client.get(p)
            self.assertEqual(res.status_code, 200)
            # The navigation bar must show the user's name and 'Sign Out', NOT 'Sign In'
            self.assertIn(unique_name.encode("utf-8"), res.data)
            self.assertIn(b"Sign Out", res.data)
            self.assertNotIn(b"Sign In", res.data)

        # 4. Simulate a new serverless container (ephemeral SQLite wiped / user missing from DB)
        conn = database.get_db()
        conn.execute("DELETE FROM users WHERE username = ?", (unique_name,))
        conn.commit()
        # Verify the user is gone from this database
        self.assertIsNone(database.get_user_by_username(unique_name))
        conn.close()

        # 5. Accessing /scan or /history on the new container must automatically rehydrate the user
        scan_page = self.client.get("/scan")
        self.assertEqual(scan_page.status_code, 200)
        self.assertIn(unique_name.encode("utf-8"), scan_page.data)
        self.assertIn(b"Sign Out", scan_page.data)

        # The user was re-inserted into the SQLite DB from session profile
        rehydrated = database.get_user_by_username(unique_name)
        self.assertIsNotNone(rehydrated)
        self.assertEqual(rehydrated["dietary_preference"], "Vegetarian")

    def test_chewing_candy_with_titanium_dioxide_is_edible_food(self):
        # User inquiry case: Davidoff Chewing Coffee Candy with Titanium Dioxide and food colors
        candy_text = (
            "Edible glucose, Non dairy creamer (Ghcsse : syrup, Refined coconut oil), Coffee powder (210%, "
            "fS Vaktodextrin, Gum arabic, Hydroxypropyl methyl INE lulose, Polyethylene glycol, "
            "Titanium dioxide S Caramel color, Alluring red aluminum lake, Surset N Telow aluminum Lake, "
            "Bright blue aluminum lake, Port bon black, edible Flavours. Sorage Place in a cool dry place, "
            "avoiding directly Snlght or moisture Yendacuring by: AS PER BL Gh Germany . El@ed SERN FTTRE"
        )
        res = analyze_food_label(candy_text)
        self.assertFalse(res["is_cosmetic"])
        self.assertTrue(res["is_valid_food_label"])
        detected_names = [a["name"] for a in res["detected_additives"]]
        self.assertIn("Titanium Dioxide (INS 171)", detected_names)
        self.assertIn("Sunset Yellow FCF (INS 110 / Yellow 6)", detected_names)
        self.assertIn("Allura Red AC (INS 129 / Red 40)", detected_names)
        self.assertNotIn("DO NOT EAT / INEDIBLE", res["eat_recommendation"])
        self.assertEqual(res["verdict"], "Not Recommended / Ultra-Processed")
        self.assertEqual(res["verdict_badge"], "avoid")

        # Test via web submission
        resp = self.client.post("/scan", data={
            "product_name": "Davidoff Chewing Coffee Candy",
            "category": "Biscuits & Cookies",
            "packet_price": "120",
            "servings": "10",
            "raw_text": candy_text
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b"Inedible Chemical Formulation", resp.data)
        self.assertNotIn(b"Skincare &amp; Cosmetic Chemicals Detected", resp.data)
        self.assertIn(b"Not Recommended / Ultra-Processed", resp.data)

    def test_history_and_compare_persistence_and_rehydration(self):
        # 1. Anonymous user scans two products
        tea_text = "Ingredients: Organic Green Tea Leaves, Dandelion Root."
        r1 = self.client.post("/scan", data={
            "product_name": "Organic Green Tea",
            "category": "Beverages & Tea",
            "packet_price": "250",
            "servings": "25",
            "raw_text": tea_text
        }, follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

        oats_text = "Ingredients: 100% Whole Grain Rolled Oats, Chia Seeds."
        r2 = self.client.post("/scan", data={
            "product_name": "Rolled Oats",
            "category": "Cereals & Breakfast",
            "packet_price": "180",
            "servings": "10",
            "raw_text": oats_text
        }, follow_redirects=True)
        self.assertEqual(r2.status_code, 200)

        # 2. Scans appear in history and compare
        hist_resp = self.client.get("/history")
        self.assertEqual(hist_resp.status_code, 200)
        self.assertIn(b"Organic Green Tea", hist_resp.data)
        self.assertIn(b"Rolled Oats", hist_resp.data)

        comp_resp = self.client.get("/compare")
        self.assertEqual(comp_resp.status_code, 200)
        self.assertIn(b"Organic Green Tea", comp_resp.data)
        self.assertIn(b"Rolled Oats", comp_resp.data)

        # 3. User registers / logs in; prior scans must persist and be claimed
        rand_user = f"persist_{uuid.uuid4().hex[:6]}"
        reg_resp = self.client.post("/register", data={
            "username": rand_user,
            "email": f"{rand_user}@example.com",
            "password": "Password123!",
            "dietary_preference": "None",
            "allergies": [],
            "custom_allergies": "",
            "health_goals": [],
            "custom_goals": "",
            "avoid_items": "",
            "budget_target": "",
            "currency": "₹"
        }, follow_redirects=True)
        self.assertEqual(reg_resp.status_code, 200)

        hist_logged_in = self.client.get("/history")
        self.assertIn(b"Organic Green Tea", hist_logged_in.data)
        self.assertIn(b"Rolled Oats", hist_logged_in.data)

        # 4. Simulate serverless container wipe (wiping SQLite database table)
        conn = database.get_db()
        conn.execute("DELETE FROM scans")
        conn.commit()
        conn.close()

        # Database is currently empty
        db_scans = database.get_user_scans()
        self.assertEqual(len(db_scans), 0)

        # Accessing /history or /compare must automatically rehydrate from session
        hist_after_wipe = self.client.get("/history")
        self.assertEqual(hist_after_wipe.status_code, 200)
        self.assertIn(b"Organic Green Tea", hist_after_wipe.data)
        self.assertIn(b"Rolled Oats", hist_after_wipe.data)

        comp_after_wipe = self.client.get("/compare")
        self.assertEqual(comp_after_wipe.status_code, 200)
        self.assertIn(b"Organic Green Tea", comp_after_wipe.data)
        self.assertIn(b"Rolled Oats", comp_after_wipe.data)

    def test_sync_scans_api(self):
        # Test client-side localStorage sync endpoint
        test_scan = {
            "id": 9999,
            "product_name": "Synced Almond Milk",
            "category": "Dairy & Alternatives",
            "star_rating": 4.5,
            "verdict": "Safe & Recommended",
            "verdict_badge": "safe",
            "cost_per_serving": 15.0,
            "packet_price": 150.0,
            "servings": 10.0,
            "analysis_result": {
                "detected_additives": [],
                "detected_sugars": [],
                "detected_fats": [],
                "detected_beneficial": ["Almonds"],
                "user_allergen_warnings": [],
                "diet_conflicts": []
            },
            "created_at": "2026-10-26 12:00:00"
        }

        resp = self.client.post(
            "/api/sync_scans",
            data=json.dumps({"scans": [test_scan]}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["synced"], 1)

        # Check it is present in /history
        hist_resp = self.client.get("/history")
        self.assertIn(b"Synced Almond Milk", hist_resp.data)

    def test_three_products_sync_and_coexist_in_history_and_compare(self):
        # User scenario: Rose Green Tea, Dandelion Green Tea, and Peanuts
        r1 = self.client.post("/scan", data={
            "product_name": "Rose Green Tea",
            "category": "Beverages & Tea",
            "packet_price": "240",
            "servings": "20",
            "raw_text": "Ingredients: Green Tea Leaves, Rose Petals."
        }, follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

        r2 = self.client.post("/scan", data={
            "product_name": "Dandelion Green Tea",
            "category": "Beverages & Tea",
            "packet_price": "260",
            "servings": "25",
            "raw_text": "Ingredients: Green Tea Leaves, Dandelion Root."
        }, follow_redirects=True)
        self.assertEqual(r2.status_code, 200)

        r3 = self.client.post("/scan", data={
            "product_name": "Roasted Salted Peanuts",
            "category": "Nuts & Snacks",
            "packet_price": "60",
            "servings": "2",
            "raw_text": "Ingredients: Peanuts 98%, Edible Vegetable Oil, Salt."
        }, follow_redirects=True)
        self.assertEqual(r3.status_code, 200)

        # 1. Verify all three exist in History
        hist = self.client.get("/history")
        self.assertEqual(hist.status_code, 200)
        self.assertIn(b"Rose Green Tea", hist.data)
        self.assertIn(b"Dandelion Green Tea", hist.data)
        self.assertIn(b"Roasted Salted Peanuts", hist.data)

        # 2. Verify all three exist in Compare (chips and comparison cards)
        comp = self.client.get("/compare")
        self.assertEqual(comp.status_code, 200)
        self.assertIn(b"Rose Green Tea", comp.data)
        self.assertIn(b"Dandelion Green Tea", comp.data)
        self.assertIn(b"Roasted Salted Peanuts", comp.data)

        # 3. Simulate another container missing Rose Green Tea
        conn = database.get_db()
        conn.execute("DELETE FROM scans WHERE product_name = 'Rose Green Tea'")
        conn.commit()
        conn.close()

        # Syncing from client restores the missing product and reports synced_new = 1
        rose_scan = {
            "id": 88881234,
            "product_name": "Rose Green Tea",
            "category": "Beverages & Tea",
            "packet_price": 240.0,
            "servings": 20.0,
            "cost_per_serving": 12.0,
            "overall_score": 85,
            "star_rating": 4.2,
            "verdict": "Safe & Clean Formulation",
            "verdict_badge": "safe",
            "analysis": {
                "detected_additives": [],
                "detected_sugars": [],
                "detected_fats": [],
                "detected_beneficial": ["Green Tea", "Rose Petals"],
                "user_allergen_warnings": [],
                "diet_conflicts": []
            },
            "created_at": "2026-10-26 15:00:00"
        }
        sync_resp = self.client.post(
            "/api/sync_scans",
            data=json.dumps({"scans": [rose_scan]}),
            content_type="application/json"
        )
        self.assertEqual(sync_resp.status_code, 200)
        sync_data = json.loads(sync_resp.data)
        self.assertEqual(sync_data["synced_new"], 1)

        # History and Compare both display all 3 again
        hist_restored = self.client.get("/history")
        self.assertIn(b"Rose Green Tea", hist_restored.data)
        self.assertIn(b"Dandelion Green Tea", hist_restored.data)
        self.assertIn(b"Roasted Salted Peanuts", hist_restored.data)

        comp_restored = self.client.get("/compare")
        self.assertIn(b"Rose Green Tea", comp_restored.data)
        self.assertIn(b"Dandelion Green Tea", comp_restored.data)
        self.assertIn(b"Roasted Salted Peanuts", comp_restored.data)

    def test_user_profile_preservation_and_login_after_logout_and_container_wipe(self):
        # 1. Register a user profile with specific preferences
        u_name = f"vault_user_{uuid.uuid4().hex[:6]}"
        u_pass = "VaultSecret2026!"
        reg = self.client.post("/register", data={
            "username": u_name,
            "email": f"{u_name}@testdomain.com",
            "password": u_pass,
            "dietary_preference": "Vegan",
            "allergies": ["milk", "soy"],
            "custom_allergies": "almonds",
            "health_goals": ["reduced_sugar"],
            "custom_goals": "zero palm oil",
            "avoid_items": "palm oil",
            "budget_target": "80.0",
            "currency": "₹"
        }, follow_redirects=True)
        self.assertEqual(reg.status_code, 200)

        # 2. User scans a product while logged in
        tea_text = "Ingredients: 100% Organic Chamomile and Mint Leaves."
        scan_res = self.client.post("/scan", data={
            "product_name": "Organic Chamomile Tea",
            "category": "Beverages & Tea",
            "packet_price": "220",
            "servings": "20",
            "raw_text": tea_text
        }, follow_redirects=True)
        self.assertEqual(scan_res.status_code, 200)

        # 3. User explicitly logs out
        logout_res = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(logout_res.status_code, 200)
        self.assertIn(b"Sign In", logout_res.data)
        self.assertNotIn(b"Sign Out", logout_res.data)

        # 4. Simulate fresh serverless container (wiping SQLite database completely)
        conn = database.get_db()
        conn.execute("DELETE FROM users WHERE username = ?", (u_name,))
        conn.commit()
        conn.close()

        # Verify user is completely absent from this container's SQLite database
        self.assertIsNone(database.get_user_by_username(u_name))

        # 5. User logs back in: must NOT show invalid credentials and must restore profile
        login_res = self.client.post("/login", data={
            "username": u_name,
            "password": u_pass
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertNotIn(b"Invalid credentials provided", login_res.data)
        self.assertIn(u_name.encode("utf-8"), login_res.data)
        self.assertIn(b"Sign Out", login_res.data)

        # Check database was rehydrated with correct profile preferences
        rehydrated_user = database.get_user_by_username(u_name)
        self.assertIsNotNone(rehydrated_user)
        self.assertEqual(rehydrated_user["dietary_preference"], "Vegan")
        self.assertIn("milk", rehydrated_user["allergies"])

        # 6. Verify History and Compare contain the previously scanned product
        hist = self.client.get("/history")
        self.assertEqual(hist.status_code, 200)
        self.assertIn(b"Organic Chamomile Tea", hist.data)

        comp = self.client.get("/compare")
        self.assertEqual(comp.status_code, 200)
        self.assertIn(b"Organic Chamomile Tea", comp.data)

    def test_cosmetic_and_culinary_differentiation(self):
        # 1. Bread with dough conditioners must NOT be flagged as cosmetic
        bread_label = "Enriched Wheat Flour, Water, Yeast, Dough Conditioner (Datem, Ascorbic Acid), Salt, Soybean Oil."
        res_bread = analyze_food_label(bread_label)
        self.assertTrue(res_bread["is_valid_food_label"])
        self.assertFalse(res_bread["is_cosmetic"])
        self.assertFalse(res_bread["non_food_warning"])

        # 2. Coffee candy with titanium dioxide and gum arabic must NOT be flagged as cosmetic
        candy_label = "Edible glucose, Non dairy creamer (Glucose syrup, Refined coconut oil), Coffee powder 20%, Maltodextrin, Gum arabic, Titanium dioxide, Caramel color, Edible Flavours."
        res_candy = analyze_food_label(candy_label)
        self.assertTrue(res_candy["is_valid_food_label"])
        self.assertFalse(res_candy["is_cosmetic"])
        self.assertFalse(res_candy["non_food_warning"])

        # 3. Whole culinary spices and teas (dandelion root, green tea, saffron) must have clean score and no non-food warning
        tea_label = "Ingredients: 100% Organic Green Tea, Dried Dandelion Root, Saffron Threads."
        res_tea = analyze_food_label(tea_label)
        self.assertTrue(res_tea["is_valid_food_label"])
        self.assertFalse(res_tea["is_cosmetic"])
        self.assertFalse(res_tea["non_food_warning"])
        self.assertGreaterEqual(res_tea["star_rating"], 4.2)

        # 4. Genuine cosmetic formulations must be flagged correctly
        cosmetic_label = "Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Dimethicone, Fragrance, Cetyl Alcohol, Hair Conditioner formulation for damaged hair. For external use only. Apply to wet scalp and rinse thoroughly."
        res_cosmetic = analyze_food_label(cosmetic_label)
        self.assertTrue(res_cosmetic["is_cosmetic"])
        self.assertFalse(res_cosmetic["is_valid_food_label"])
        self.assertTrue(res_cosmetic["non_food_warning"])
        self.assertIn("Skincare & Cosmetic", res_cosmetic["verdict"])

    def test_case_insensitive_login_and_sync(self):
        # Register user with mixed case
        c_name = f"TestUser_{uuid.uuid4().hex[:4]}"
        c_pass = "Password123!"
        reg = self.client.post("/register", data={
            "username": c_name,
            "email": f"{c_name.lower()}@testdomain.com",
            "password": c_pass,
            "dietary_preference": "Vegetarian",
            "allergies": ["peanuts"],
            "custom_allergies": "",
            "health_goals": ["reduced_sugar"],
            "custom_goals": "",
            "avoid_items": "",
            "budget_target": "50.0",
            "currency": "₹"
        }, follow_redirects=True)
        self.assertEqual(reg.status_code, 200)

        # Log out
        self.client.get("/logout")

        # Log in with all-lowercase username
        login_res = self.client.post("/login", data={
            "username": c_name.lower(),
            "password": c_pass
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertNotIn(b"Invalid credentials provided", login_res.data)
        self.assertIn(b"Sign Out", login_res.data)

if __name__ == "__main__":
    unittest.main()
