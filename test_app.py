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

if __name__ == "__main__":
    unittest.main()
