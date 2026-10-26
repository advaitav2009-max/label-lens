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

        # 3. Short random keystrokes
        short_random = "asdf qwer zxcv 1234"
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

if __name__ == "__main__":
    unittest.main()
