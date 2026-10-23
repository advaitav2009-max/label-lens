"""
Label Lens - Additives and Food Ingredients Knowledge Base
Contains detailed classification of INS/E numbers, allergens, sugar synonyms,
unhealthy ultra-processed markers, dietary flags, and beneficial nutrients.
"""

# INS and E-Number Catalog
ADDITIVES_CATALOG = {
    # Artificial Colors
    "102": {
        "name": "Tartrazine (INS 102 / Yellow 5)",
        "category": "Artificial Color",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Synthetic lemon-yellow azo dye. Linked in clinical studies to hyperactivity in sensitive children and mild allergic hives."
    },
    "110": {
        "name": "Sunset Yellow FCF (INS 110 / Yellow 6)",
        "category": "Artificial Color",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Petroleum-derived orange dye. Can trigger allergies and bronchoconstriction in aspirin-sensitive individuals."
    },
    "120": {
        "name": "Carmine / Cochineal (INS 120 / Natural Red 4)",
        "category": "Natural Color (Insect-derived)",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": False,
        "vegetarian": False,
        "description": "Red pigment extracted from crushed female cochineal insects. Not vegetarian or vegan, known allergen for asthma/hives."
    },
    "122": {
        "name": "Azorubine / Carmoisine (INS 122)",
        "category": "Artificial Color",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Synthetic red food dye. Subject to European warning label requirements regarding children's attention."
    },
    "129": {
        "name": "Allura Red AC (INS 129 / Red 40)",
        "category": "Artificial Color",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Synthetic coal-tar derived red dye. Very common in candies and sodas. Potential irritant for gut lining."
    },
    "133": {
        "name": "Brilliant Blue FCF (INS 133 / Blue 1)",
        "category": "Artificial Color",
        "risk": "Low-Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Synthetic blue color. Poorly absorbed by intestines, mostly excreted unchanged."
    },
    "150d": {
        "name": "Caramel IV - Sulfite Ammonia (INS 150d)",
        "category": "Coloring Agent",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Brown color made by heating sugars with ammonia and sulfites. High intake forms trace by-products (4-MEI)."
    },
    "171": {
        "name": "Titanium Dioxide (INS 171)",
        "category": "Whitening Agent",
        "risk": "High",
        "safety": "avoid",
        "vegan": True,
        "vegetarian": True,
        "description": "Inorganic white pigment nanoparticles. Banned as a food additive in the European Union due to genotoxicity concerns."
    },

    # Preservatives
    "200": {
        "name": "Sorbic Acid (INS 200)",
        "category": "Preservative",
        "risk": "Low",
        "safety": "safe",
        "vegan": True,
        "vegetarian": True,
        "description": "Naturally occurring antifungal preservative. Generally well tolerated."
    },
    "202": {
        "name": "Potassium Sorbate (INS 202)",
        "category": "Preservative",
        "risk": "Low",
        "safety": "safe",
        "vegan": True,
        "vegetarian": True,
        "description": "Mild, widely used mold inhibitor in cheese, beverages, and baked goods."
    },
    "211": {
        "name": "Sodium Benzoate (INS 211)",
        "category": "Preservative",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Common antimicrobial preservative in acidic beverages. When combined with Vitamin C (Ascorbic Acid), it may form traces of benzene."
    },
    "220": {
        "name": "Sulphur Dioxide (INS 220)",
        "category": "Preservative / Antioxidant",
        "risk": "High",
        "safety": "caution",
        "allergen": "sulfites",
        "vegan": True,
        "vegetarian": True,
        "description": "Sulfite preservative used in dried fruits and juices. Frequent trigger for asthma and sulfite-sensitive reactions."
    },
    "223": {
        "name": "Sodium Metabisulphite (INS 223)",
        "category": "Preservative / Bleaching Agent",
        "risk": "Moderate-High",
        "safety": "caution",
        "allergen": "sulfites",
        "vegan": True,
        "vegetarian": True,
        "description": "Sulfite compound used in dough conditioners and canned foods. Major allergen trigger."
    },
    "250": {
        "name": "Sodium Nitrite (INS 250)",
        "category": "Curing Preservative",
        "risk": "High",
        "safety": "avoid",
        "vegan": True,
        "vegetarian": True,
        "description": "Used in processed cured meats to prevent botulism and maintain pink color. Can form carcinogenic nitrosamines when cooked at high heat."
    },
    "282": {
        "name": "Calcium Propionate (INS 282)",
        "category": "Mold Inhibitor",
        "risk": "Low",
        "safety": "safe",
        "vegan": True,
        "vegetarian": True,
        "description": "Prevents bread mold and bacteria. Safe for most individuals, occasionally linked to irritability in sensitive kids."
    },

    # Antioxidants
    "300": {
        "name": "Ascorbic Acid (INS 300 / Vitamin C)",
        "category": "Antioxidant / Vitamin",
        "risk": "None",
        "safety": "beneficial",
        "vegan": True,
        "vegetarian": True,
        "description": "Natural antioxidant and essential nutrient (Vitamin C). Prevents oxidation and adds nutritional value."
    },
    "307": {
        "name": "Tocopherols (INS 307 / Vitamin E)",
        "category": "Antioxidant / Vitamin",
        "risk": "None",
        "safety": "beneficial",
        "vegan": True,
        "vegetarian": True,
        "description": "Natural antioxidant form of Vitamin E that protects fats from rancidity."
    },
    "319": {
        "name": "Tertiary Butylhydroquinone / TBHQ (INS 319)",
        "category": "Synthetic Antioxidant",
        "risk": "Moderate-High",
        "safety": "avoid",
        "vegan": True,
        "vegetarian": True,
        "description": "Synthetic fat stabilizer used to extend shelf-life of processed oils and fried snacks. Restricted limits in many countries."
    },
    "320": {
        "name": "Butylated Hydroxyanisole / BHA (INS 320)",
        "category": "Synthetic Antioxidant",
        "risk": "High",
        "safety": "avoid",
        "vegan": True,
        "vegetarian": True,
        "description": "Synthetic preservative in edible oils and cereals. Classified as an endocrine disruptor and possible carcinogen in animal studies."
    },
    "321": {
        "name": "Butylated Hydroxytoluene / BHT (INS 321)",
        "category": "Synthetic Antioxidant",
        "risk": "High",
        "safety": "avoid",
        "vegan": True,
        "vegetarian": True,
        "description": "Synthetic preservative closely related to BHA. Frequently flagged for potential hormonal disruptions."
    },
    "322": {
        "name": "Lecithin (INS 322)",
        "category": "Emulsifier",
        "risk": "Low",
        "safety": "safe",
        "allergen": "soy",  # Usually soy lecithin unless sunflower
        "vegan": True,
        "vegetarian": True,
        "description": "Natural fat emulsifier extracted predominantly from soybeans or sunflower seeds. Improves chocolate texture and dough blending."
    },
    "330": {
        "name": "Citric Acid (INS 330)",
        "category": "Acidity Regulator",
        "risk": "None",
        "safety": "safe",
        "vegan": True,
        "vegetarian": True,
        "description": "Naturally occurring fruit acid used to regulate tartness and preserve freshness. Safe and benign."
    },

    # Thickeners & Emulsifiers
    "407": {
        "name": "Carrageenan (INS 407)",
        "category": "Thickener / Stabilizer",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Red seaweed extract used in dairy and plant milks. Degraded carrageenan forms have been linked to gastrointestinal inflammation."
    },
    "412": {
        "name": "Guar Gum (INS 412)",
        "category": "Natural Thickener",
        "risk": "Low",
        "safety": "safe",
        "vegan": True,
        "vegetarian": True,
        "description": "Soluble dietary fiber extracted from guar beans. Safe natural stabilizer."
    },
    "415": {
        "name": "Xanthan Gum (INS 415)",
        "category": "Natural Thickener",
        "risk": "Low",
        "safety": "safe",
        "vegan": True,
        "vegetarian": True,
        "description": "Fermented plant polysaccharide used to stabilize dressings and gluten-free baked products."
    },
    "471": {
        "name": "Mono- and Di-glycerides of Fatty Acids (INS 471)",
        "category": "Emulsifier",
        "risk": "Low-Moderate",
        "safety": "caution",
        "vegan": "Uncertain",
        "vegetarian": "Uncertain",
        "description": "Widely used bakery and ice cream emulsifier. Derived from either plant oil or animal fats; may contain small amounts of trans fats."
    },

    # Flavor Enhancers
    "621": {
        "name": "Monosodium Glutamate / MSG (INS 621)",
        "category": "Flavor Enhancer",
        "risk": "Low-Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Savory umami flavor enhancer. Safe for the general population according to FDA/WHO, though some individuals experience sensitivity headaches or flushing."
    },
    "627": {
        "name": "Disodium Guanylate (INS 627)",
        "category": "Flavor Enhancer",
        "risk": "Low-Moderate",
        "safety": "caution",
        "vegan": "Uncertain",
        "vegetarian": "Uncertain",
        "description": "Often combined with MSG. Can be produced from tapioca or fish/meat sources. High in purines, not advised for gout sufferers."
    },
    "631": {
        "name": "Disodium Inosinate (INS 631)",
        "category": "Flavor Enhancer",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": False,
        "vegetarian": False,
        "description": "Umami enhancer typically prepared from meat or dried sardines/fish. Usually non-vegetarian."
    },

    # Artificial & Low-Calorie Sweeteners
    "950": {
        "name": "Acesulfame Potassium / Ace-K (INS 950)",
        "category": "Artificial Sweetener",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Zero-calorie intense sweetener 200x sweeter than sucrose. Heat stable, often blended with sucralose. Emerging questions around gut microbiome."
    },
    "951": {
        "name": "Aspartame (INS 951)",
        "category": "Artificial Sweetener",
        "risk": "Moderate-High",
        "safety": "avoid",
        "vegan": True,
        "vegetarian": True,
        "description": "Low-calorie sweetener. Dangerous for individuals with Phenylketonuria (PKU). Classified as 'possibly carcinogenic to humans' (Group 2B) by IARC/WHO in 2023."
    },
    "954": {
        "name": "Saccharin (INS 954)",
        "category": "Artificial Sweetener",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Oldest synthetic sweetener with a slightly bitter metallic aftertaste."
    },
    "955": {
        "name": "Sucralose (INS 955)",
        "category": "Artificial Sweetener",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Chlorinated sucrose derivative 600x sweeter than sugar. Zero calories, but may alter gut bacteria composition."
    },
    "960": {
        "name": "Steviol Glycosides (INS 960 / Stevia)",
        "category": "Plant-Derived Sweetener",
        "risk": "Low",
        "safety": "safe",
        "vegan": True,
        "vegetarian": True,
        "description": "Zero-calorie natural sweetener extracted from Stevia rebaudiana plant leaves."
    },
    "965": {
        "name": "Maltitol (INS 965)",
        "category": "Sugar Alcohol (Polyol)",
        "risk": "Low-Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Sugar alcohol used in sugar-free chocolates. Has a high glycemic index for a polyol and can cause gas, cramps, and diarrhea in moderate quantities."
    },
    "968": {
        "name": "Erythritol (INS 968)",
        "category": "Sugar Alcohol (Polyol)",
        "risk": "Moderate",
        "safety": "caution",
        "vegan": True,
        "vegetarian": True,
        "description": "Zero-calorie sugar alcohol. Well-tolerated digestively, but recent cardiovascular studies suggest caution with high habitual consumption."
    },

    # Glazing & Animal Derivatives
    "904": {
        "name": "Shellac (INS 904)",
        "category": "Glazing Agent",
        "risk": "Low",
        "safety": "safe",
        "vegan": False,
        "vegetarian": True,
        "description": "Resinous glaze secreted by female lac insects onto trees. Used to give confectionery shiny finishes. Not vegan."
    },
    "901": {
        "name": "Beeswax (INS 901)",
        "category": "Glazing Agent",
        "risk": "Low",
        "safety": "safe",
        "vegan": False,
        "vegetarian": True,
        "description": "Natural wax made by honey bees. Vegetarian, but not vegan."
    }
}

# Aliases for Added & Hidden Sugars
SUGAR_ALIASES = [
    "sugar", "refined sugar", "cane sugar", "brown sugar", "raw sugar", "beet sugar",
    "high fructose corn syrup", "hfcs", "corn syrup", "corn syrup solids", "invert sugar",
    "invert syrup", "liquid glucose", "glucose syrup", "glucose-fructose syrup", "dextrose",
    "fructose", "maltose", "sucrose", "maltodextrin", "agave nectar", "agave syrup",
    "maple syrup", "molasses", "brown rice syrup", "barley malt", "malt extract",
    "fruit juice concentrate", "concentrated apple juice", "grape juice concentrate",
    "caramel", "treacle", "golden syrup", "isoglucose", "honey"
]

# Ultra-processed & Unhealthy Oils / Fats
UNHEALTHY_FATS = [
    "palm oil", "palmolein", "palm olein", "refined palm oil", "fractionated palm kernel oil",
    "hydrogenated vegetable oil", "partially hydrogenated vegetable oil", "hydrogenated fat",
    "interesterified vegetable fat", "vanaspati", "margarine", "shortening",
    "cottonseed oil", "refined cottonseed oil", "trans fat", "trans-fatty acids"
]

# Major Common Food Allergens
ALLERGEN_CATEGORIES = {
    "peanuts": ["peanut", "peanuts", "groundnut", "groundnuts", "peanut butter", "peanut flour", "arachis oil"],
    "tree_nuts": ["almond", "almonds", "cashew", "cashews", "walnut", "walnuts", "pistachio", "pistachios",
                  "hazelnut", "hazelnuts", "pecan", "pecans", "macadamia", "brazil nut", "brazil nuts", "praline"],
    "milk": ["milk", "dairy", "whey", "casein", "caseinate", "milk solids", "lactose", "butter", "ghee",
             "cheese", "cream", "skimmed milk", "whole milk powder", "curd", "yogurt"],
    "soy": ["soy", "soya", "soybean", "soybeans", "soy lecithin", "soya flour", "tofu", "edamame",
            "hydrolyzed soy protein", "textured vegetable protein"],
    "wheat": ["wheat", "gluten", "refined wheat flour", "maida", "semolina", "suji", "rava", "atta",
              "barley", "rye", "malt", "spelt", "durum wheat", "farina", "wheat bran"],
    "eggs": ["egg", "eggs", "egg powder", "egg albumin", "albumin", "egg yolk", "lysozyme", "ovalbumin"],
    "fish": ["fish", "anchovy", "anchovies", "tuna", "salmon", "cod", "fish oil", "fish sauce", "surimi", "isinglass"],
    "shellfish": ["shrimp", "prawn", "prawns", "crab", "lobster", "crayfish", "clam", "oyster", "mussel", "scallop"],
    "sesame": ["sesame", "sesame seeds", "til", "tahini", "sesame oil"],
    "mustard": ["mustard", "mustard seeds", "mustard powder", "mustard oil", "rai"],
    "sulfites": ["sulfite", "sulfites", "sulphite", "sulphites", "sulphur dioxide", "sodium metabisulphite", "e220", "e223"]
}

# Non-Vegetarian Ingredients Check
NON_VEG_INGREDIENTS = [
    "gelatin", "gelatine", "beef", "pork", "chicken", "meat", "mutton", "lamb",
    "bacon", "lard", "tallow", "bone char", "animal fat", "carmine", "cochineal",
    "ins 120", "e120", "fish", "shrimp", "anchovy", "crab", "prawn", "animal rennet",
    "pepsin", "ins 631", "e631", "bone phosphate", "ins 542", "duck", "turkey"
]

# Vegan Exclusions (Non-veg + Dairy/Beeswax/Honey/Shellac)
VEGAN_EXCLUSIONS = NON_VEG_INGREDIENTS + [
    "milk", "dairy", "whey", "casein", "caseinate", "milk solids", "butter", "ghee",
    "cheese", "cream", "lactose", "yogurt", "curd", "honey", "beeswax", "e901", "ins 901",
    "shellac", "e904", "ins 904", "egg", "eggs", "egg powder", "egg albumin", "lanolin"
]

# High Value / Beneficial Nutritious Ingredients
BENEFICIAL_INGREDIENTS = [
    "whole wheat", "whole grain", "rolled oats", "oat bran", "oats", "chia seeds", "flax seeds",
    "pumpkin seeds", "sunflower seeds", "almonds", "walnuts", "pistachios", "quinoa",
    "millet", "ragi", "jowar", "bajra", "lentils", "chickpeas", "mung beans", "dietary fiber",
    "whey protein isolate", "pea protein", "brown rice protein", "spirulina", "raw cacao",
    "dark cocoa", "turmeric", "curcumin", "ginger", "probiotics", "prebiotics", "inulin",
    "green tea extract", "ashwagandha", "cold pressed oil", "extra virgin olive oil"
]

# Category benchmarks for average price per serving (in local currency e.g. INR / USD scaled)
CATEGORY_BENCHMARKS = {
    "Biscuits & Cookies": {"typical_servings": 4, "avg_cost_per_serving": 10.0, "sweet_warning": True},
    "Breakfast Cereals": {"typical_servings": 10, "avg_cost_per_serving": 25.0, "sweet_warning": True},
    "Breads & Bakery": {"typical_servings": 8, "avg_cost_per_serving": 6.0, "sweet_warning": False},
    "Chips & Savory Snacks": {"typical_servings": 2, "avg_cost_per_serving": 15.0, "sweet_warning": False},
    "Chocolates & Candies": {"typical_servings": 2, "avg_cost_per_serving": 20.0, "sweet_warning": True},
    "Instant Noodles & Soups": {"typical_servings": 1, "avg_cost_per_serving": 20.0, "sweet_warning": False},
    "Juices & Beverages": {"typical_servings": 1, "avg_cost_per_serving": 30.0, "sweet_warning": True},
    "Dairy & Plant Milks": {"typical_servings": 4, "avg_cost_per_serving": 20.0, "sweet_warning": False},
    "Sauces & Condiments": {"typical_servings": 20, "avg_cost_per_serving": 5.0, "sweet_warning": True},
    "Protein & Energy Bars": {"typical_servings": 1, "avg_cost_per_serving": 60.0, "sweet_warning": False},
    "General Packaged Food": {"typical_servings": 3, "avg_cost_per_serving": 25.0, "sweet_warning": False}
}
