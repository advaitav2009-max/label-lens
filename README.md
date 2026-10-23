# Label Lens

**Decoding Food Labels. Know what's inside. Choose what's right.**

Label Lens is a packaged food diagnostic and label analysis web application developed with Python (Flask), SQLite, HTML5, CSS3, and JavaScript. It enables consumers to scan, transcribe, and analyze packaged food ingredient lists using their smartphone camera (via Iriun Webcam), laptop webcam, or image uploads. Extracted labels are diagnosed for hidden sugars, ultra-processed industrial oils, synthetic INS additives, medical allergens, and dietary preferences, delivering an objective 5-point rating and side-by-side product comparisons.

---

## Key Features

1. **Optical Character Recognition (OCR)**
   - High-performance, client-side OCR powered by Tesseract.js running directly in the browser.
   - Dual-mode input: direct live camera frame capture (laptop webcam or wireless phone camera via Iriun Webcam) or multi-image file upload for front and back label coverage.

2. **Additive & INS Diagnostic Engine**
   - Curated database of over 100 food additives and International Numbering System (INS) codes.
   - Categorized by functional purpose: preservatives, artificial colors, emulsifiers, flavor enhancers, and sweeteners.
   - Risk profiling: Safe, Moderate, or High-Risk indicators.

3. **Personalized Allergen & Dietary Safeguards**
   - User profile configuration for common medical allergens (Milk/Lactose, Peanuts, Tree Nuts, Soy, Wheat/Gluten, Egg, Fish, Shellfish, Sesame, Sulfites) plus free-text custom allergens.
   - Dietary lifestyle verification (Vegetarian, Vegan, Non-Vegetarian, Pescatarian).
   - Nutritional objectives tracking (Reduced Sugar, High Protein, Low Sodium, Zero Palm Oil, Low Calorie, Organic).

4. **Multi-Product Comparative Analysis**
   - Side-by-side comparison matrix for two or more products simultaneously.
   - Highlights ingredient differences, additive counts, allergen flags, and cost-per-serving metrics.

5. **Optional Serving & Price Calculations**
   - Evaluates budget compatibility when price and serving counts are supplied.
   - Gracefully handles packages where price or serving counts are not printed or specified.

6. **Non-Food Text Detection**
   - Automatically validates whether extracted text originates from an edible food label or non-food packaging (such as cosmetics, electronics, or household cleaners).

7. **Zero-Emoji Professional UI**
   - Tailored technical dark palette (`#080C14` / `#0E1422` with ice-blue and muted slate accents).
   - Clean, publication-grade typography using Inter and JetBrains Mono.

---

## Project Structure

```text
label-lens/
|-- api/
|   `-- index.py              # WSGI entrypoint for Vercel Serverless Functions
|-- static/
|   |-- css/
|   |   `-- style.css         # Dark theme styles & responsive design
|   |-- js/
|   |   |-- camera.js         # Camera feed, Iriun integration & frame capture
|   |   `-- ocr.js            # Tesseract.js OCR processing pipeline
|   `-- uploads/              # Local upload storage directory
|-- templates/                # Jinja2 HTML templates
|   |-- base.html
|   |-- index.html            # Landing page
|   |-- scan.html             # Camera scanner & image upload interface
|   |-- results.html          # Individual product evaluation & rating
|   |-- compare.html          # Multi-product comparison dashboard
|   |-- profile.html          # Allergen & dietary preference management
|   |-- login.html
|   |-- register.html
|   `-- history.html
|-- additives_db.py           # Additives, INS codes, allergens, and dietary catalogs
|-- analyzer.py               # Core ingredient parsing & scoring engine
|-- app.py                    # Flask application & route handlers
|-- database.py               # SQLite database layer (with /tmp fallback for serverless)
|-- sample_data.py            # Built-in reference food products
|-- requirements.txt          # Python dependencies
|-- vercel.json               # Vercel deployment routing configuration
`-- test_app.py               # Unit tests
```

---

## Local Development Setup

### Prerequisites
- Python 3.10+
- Modern web browser (Chrome, Edge, Firefox, or Safari) with camera permissions enabled
- (Optional) [Iriun Webcam](https://iriun.com/) installed on your PC and mobile device for high-resolution mobile camera scanning.

### Installation

1. Clone or download the repository:
   ```bash
   git clone https://github.com/<YOUR_USERNAME>/label-lens.git
   cd label-lens
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the development server:
   ```bash
   python app.py
   ```

5. Open your browser and navigate to:
   ```text
   http://127.0.0.1:5000
   ```

---

## Deploying to Vercel

Label Lens is structured for serverless deployment on Vercel:

### Step 1: Push to GitHub
1. Create a new repository on [GitHub](https://github.com/new) named `label-lens`.
2. Push your local repository to GitHub:
   ```bash
   git remote add origin https://github.com/<YOUR_USERNAME>/label-lens.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Deploy on Vercel
1. Log in to [Vercel](https://vercel.com).
2. Click **Add New...** -> **Project**.
3. Import the `label-lens` repository from GitHub.
4. Keep the default settings (Framework Preset: **Other**, Root Directory: `./`).
5. Click **Deploy**.

Vercel will detect `api/index.py` and `vercel.json` and deploy the application with live routing.

---

## License

This project is licensed under the MIT License.
