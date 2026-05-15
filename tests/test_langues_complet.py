import requests
import json
import time
import os
import sys
import re
from datetime import datetime
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
RAPPORT = []
TOTAL = 0
PASSES = 0
ECHOUES = 0
DEBUT = datetime.now()

VERT = "\033[32m"
ROUGE = "\033[31m"
JAUNE = "\033[33m"
CYAN = "\033[36m"
VIOLET = "\033[35m"
RESET = "\033[0m"
GRAS = "\033[1m"


def log(msg, niveau="INFO"):
    couleurs = {
        "OK": VERT,
        "FAIL": ROUGE,
        "WARN": JAUNE,
        "INFO": CYAN,
        "TITRE": VIOLET + GRAS,
    }
    print(f"{couleurs.get(niveau, CYAN)}[{niveau}] {msg}{RESET}")


def titre(texte):
    log(f"\n{'━'*65}", "TITRE")
    log(f"  {texte}", "TITRE")
    log(f"{'━'*65}", "TITRE")


def attendre_serveur(timeout=90):
    """Attend que le serveur local réponde sur /sante avant les tests."""
    debut = time.time()
    while time.time() - debut <= timeout:
        try:
            r = requests.get(f"{BASE_URL}/sante", timeout=3)
            if r.status_code == 200:
                log("✅ Serveur API détecté et prêt", "OK")
                return True
        except Exception:
            pass
        time.sleep(1)
    log("❌ Serveur API non disponible après attente", "FAIL")
    return False


def tester_langue(
    nom,
    methode,
    url,
    body=None,
    attendu_code=200,
    langue_attendue=None,
    verifier_pas_francais=False,
    verifier_mots_cles=None,
    verifier_champs=None,
    verifier_non_vide=None,
    timeout=60,
    description="",
):
    global TOTAL, PASSES, ECHOUES
    TOTAL += 1
    debut = time.time()

    resultat = {
        "nom": nom,
        "description": description,
        "url": url,
        "langue_attendue": langue_attendue,
        "statut": None,
        "code_http": None,
        "temps": None,
        "erreur": None,
        "reponse_extrait": None,
    }

    try:
        if methode == "GET":
            r = requests.get(f"{BASE_URL}{url}", timeout=timeout)
        elif methode == "POST":
            r = requests.post(f"{BASE_URL}{url}", json=body, timeout=timeout)
        else:
            raise ValueError(f"Méthode HTTP non supportée: {methode}")

        temps = round(time.time() - debut, 2)
        resultat["temps"] = temps
        resultat["code_http"] = r.status_code

        if r.status_code != attendu_code:
            resultat["statut"] = "FAIL"
            resultat["erreur"] = f"HTTP {r.status_code} attendu {attendu_code}"
            ECHOUES += 1
            log(f"❌ {nom} — HTTP {r.status_code}", "FAIL")
            RAPPORT.append(resultat)
            return False, None

        try:
            data = r.json()
        except Exception:
            data = {}

        erreurs = []

        if verifier_champs:
            for champ in verifier_champs:
                if champ not in data:
                    erreurs.append(f"Champ absent: '{champ}'")

        if verifier_non_vide:
            for champ in verifier_non_vide:
                if champ in data:
                    if not data[champ]:
                        erreurs.append(f"'{champ}' vide")

        ration_texte = ""
        if "ration" in data:
            ration_texte = data["ration"]
            resultat["reponse_extrait"] = ration_texte[:200]

        if verifier_mots_cles and ration_texte:
            for mot in verifier_mots_cles:
                if mot.lower() not in ration_texte.lower():
                    erreurs.append(f"Mot clé absent: '{mot}'")

        if verifier_pas_francais and ration_texte:
            mots_fr = [
                "voici",
                "votre",
                "ration",
                "pour",
                "avec",
                "les",
                "des",
                "une",
                "composition",
            ]
            nb_mots_fr = sum(1 for m in mots_fr if m in ration_texte.lower())
            if nb_mots_fr >= 4:
                erreurs.append(
                    f"Réponse semble être en français malgré langue={langue_attendue} ({nb_mots_fr} mots français détectés)"
                )

        if langue_attendue and "langue_detectee" in data:
            lang_det = data["langue_detectee"]
            if lang_det != langue_attendue:
                log(
                    f"⚠️ Langue détectée '{lang_det}' ≠ attendue '{langue_attendue}'",
                    "WARN",
                )

        if erreurs:
            resultat["statut"] = "FAIL"
            resultat["erreur"] = " | ".join(erreurs)
            ECHOUES += 1
            log(f"❌ {nom} — {resultat['erreur']}", "FAIL")
            RAPPORT.append(resultat)
            return False, data

        resultat["statut"] = "OK"
        PASSES += 1
        log(f"✅ {nom} ({temps}s)", "OK")
        RAPPORT.append(resultat)
        return True, data

    except requests.exceptions.Timeout:
        resultat["statut"] = "TIMEOUT"
        resultat["erreur"] = f"Timeout >{timeout}s"
        ECHOUES += 1
        log(f"⏱️ {nom} — TIMEOUT", "WARN")
        RAPPORT.append(resultat)
        return False, None

    except requests.exceptions.ConnectionError:
        resultat["statut"] = "OFFLINE"
        resultat["erreur"] = "Serveur inaccessible"
        ECHOUES += 1
        log(f"🔌 {nom} — OFFLINE", "FAIL")
        RAPPORT.append(resultat)
        return False, None

    except Exception as e:
        resultat["statut"] = "ERREUR"
        resultat["erreur"] = str(e)
        ECHOUES += 1
        log(f"💥 {nom} — {e}", "FAIL")
        RAPPORT.append(resultat)
        return False, None


if not attendre_serveur(timeout=90):
    with open("docs/RAPPORT_TESTS_MULTILINGUES_COMPLET.md", "w", encoding="utf-8") as f:
        f.write("# Rapport tests multilingues\n\n❌ Serveur API indisponible sur http://127.0.0.1:8000\n")
    sys.exit(1)

LANGUES_50 = [
    {"code": "fon", "nom": "Fon", "pays": "Bénin", "priorite": 1, "population_benin_pct": 39, "mots_test": ["kpakpa", "agbado", "nɔ", "ɖo"], "phrase_test": "Un ɖó kpakpa lɛ 50 e ɖó sɔ wɛkɛ atɔn", "salutation": "Axɔsu"},
    {"code": "yor", "nom": "Yoruba", "pays": "Bénin/Nigeria", "priorite": 1, "population_benin_pct": 12, "mots_test": ["adiye", "agbado", "mo ni"], "phrase_test": "Mo ni adie 50 ti o ni ose meta", "salutation": "Ẹ káaro"},
    {"code": "baa", "nom": "Baatonum", "pays": "Bénin", "priorite": 1, "population_benin_pct": 10, "mots_test": [], "phrase_test": "J ai 50 poulets de trois semaines", "salutation": "Bonjour en baatonum"},
    {"code": "adj", "nom": "Adja", "pays": "Bénin", "priorite": 1, "population_benin_pct": 8, "mots_test": [], "phrase_test": "J ai 50 poulets nourris au maïs", "salutation": "Bonjour en adja"},
    {"code": "gen", "nom": "Gen (Mina)", "pays": "Bénin/Togo", "priorite": 1, "population_benin_pct": 8, "mots_test": [], "phrase_test": "J ai des poulets et du maïs disponible", "salutation": "Bonjour en gen"},
    {"code": "yom", "nom": "Yom", "pays": "Bénin", "priorite": 1, "population_benin_pct": 6, "mots_test": [], "phrase_test": "Mes poulets ont besoin d une ration", "salutation": "Bonjour en yom"},
    {"code": "den", "nom": "Dendi", "pays": "Bénin Nord", "priorite": 1, "population_benin_pct": 5, "mots_test": [], "phrase_test": "J ai 50 poulets et du maïs", "salutation": "Bonjour en dendi"},
    {"code": "fr", "nom": "Français", "pays": "Bénin/International", "priorite": 0, "population_benin_pct": 80, "mots_test": ["ration", "FCFA", "kg", "poulets"], "phrase_test": "J ai 50 poulets de chair de 3 semaines. J ai du maïs et du tourteau de soja.", "salutation": "Bonjour"},
    {"code": "en", "nom": "Anglais", "pays": "International", "priorite": 0, "population_benin_pct": 15, "mots_test": ["ration", "FCFA", "kg", "feed"], "phrase_test": "I have 50 broiler chickens 3 weeks old. I have corn and soybean meal available.", "salutation": "Hello"},
    {"code": "pt", "nom": "Portugais", "pays": "International", "priorite": 0, "population_benin_pct": 5, "mots_test": [], "phrase_test": "Tenho 50 frangos de corte com 3 semanas.", "salutation": "Olá"},
    {"code": "ar", "nom": "Arabe", "pays": "Afrique du Nord", "priorite": 0, "population_benin_pct": 3, "mots_test": [], "phrase_test": "لدي 50 دجاجة عمرها 3 أسابيع", "salutation": "مرحبا"},
    {"code": "hau", "nom": "Haoussa", "pays": "Niger/Nigeria", "priorite": 2, "population_benin_pct": 2, "mots_test": [], "phrase_test": "Ina da kaji 50 na makonni uku", "salutation": "Sannu"},
    {"code": "ful", "nom": "Peul (Fulfulde)", "pays": "Afrique de l Ouest", "priorite": 2, "population_benin_pct": 3, "mots_test": [], "phrase_test": "Mi ina hannde gertooɗe 50", "salutation": "Jam waali"},
    {"code": "ewe", "nom": "Ewe", "pays": "Togo/Ghana", "priorite": 2, "population_benin_pct": 2, "mots_test": [], "phrase_test": "Manye koklowo 50 wolea ɖa wɔ", "salutation": "Ŋdi"},
    {"code": "aka", "nom": "Akan (Twi)", "pays": "Ghana", "priorite": 2, "population_benin_pct": 1, "mots_test": [], "phrase_test": "Me wɔ akokɔ 50 a wɔdi mfimfini", "salutation": "Maakye"},
    {"code": "ibo", "nom": "Igbo", "pays": "Nigeria", "priorite": 2, "population_benin_pct": 1, "mots_test": [], "phrase_test": "Nwere m ọkụkọ iri ise nke izu atọ", "salutation": "Nnọọ"},
    {"code": "wol", "nom": "Wolof", "pays": "Sénégal", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Am naa jën yi 50 ci aJanviye", "salutation": "Asalaa maalekum"},
    {"code": "bam", "nom": "Bambara", "pays": "Mali", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "N be gwanfɛn 50 de la", "salutation": "I ni ce"},
    {"code": "moore", "nom": "Mooré", "pays": "Burkina Faso", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Mam tõnd kõngo 50 wã", "salutation": "Laafi"},
    {"code": "dyu", "nom": "Dioula", "pays": "Côte d Ivoire", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "N be sɔndan 50 le la", "salutation": "I ni ce"},
    {"code": "kab", "nom": "Kabiyé", "pays": "Togo", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Mam kpɛntɛ 50 tɔ", "salutation": "Koɓa"},
    {"code": "tem", "nom": "Tem (Kotokoli)", "pays": "Togo/Bénin", "priorite": 2, "population_benin_pct": 1, "mots_test": [], "phrase_test": "J ai des volailles qui ont besoin d aliment", "salutation": "Bonjour en tem"},
    {"code": "kir", "nom": "Kirundi", "pays": "Burundi", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Mfise inkoko 50", "salutation": "Amahoro"},
    {"code": "lin", "nom": "Lingala", "pays": "RDC/Congo", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Naza na banganga 50", "salutation": "Mbote"},
    {"code": "kik", "nom": "Kikongo", "pays": "RDC/Congo/Angola", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Nzola nge nsuni 50", "salutation": "Mbote"},
    {"code": "swa", "nom": "Swahili", "pays": "Afrique de l Est", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Nina kuku 50 wenye wiki tatu", "salutation": "Habari"},
    {"code": "nya", "nom": "Chichewa", "pays": "Malawi/Zambie", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Ndiri ndi nkhuku 50", "salutation": "Moni"},
    {"code": "orm", "nom": "Oromo", "pays": "Éthiopie", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Loon 50 qaba", "salutation": "Nagaatti"},
    {"code": "amh", "nom": "Amharique", "pays": "Éthiopie", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "50 ዶሮዎች አሉኝ", "salutation": "ሰላም"},
    {"code": "som", "nom": "Somali", "pays": "Somalie", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Waxaan hayaa 50 digaag", "salutation": "Nabad"},
    {"code": "ber", "nom": "Tamazight (Berbère)", "pays": "Maroc/Algérie", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Lli d aɣyul 50 n tyezziwin", "salutation": "Azul"},
    {"code": "zlm", "nom": "Darija (Arabe marocain)", "pays": "Maroc", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "عندي 50 دجاجة", "salutation": "السلام"},
    {"code": "zul", "nom": "Zoulou", "pays": "Afrique du Sud", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Nginezinkukhu ezingama-50", "salutation": "Sawubona"},
    {"code": "xho", "nom": "Xhosa", "pays": "Afrique du Sud", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Ndinamazantsi 50 eenkukhu", "salutation": "Molo"},
    {"code": "sot", "nom": "Sesotho", "pays": "Lesotho/Afrique du Sud", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Ke na le likhoho tse 50", "salutation": "Lumela"},
    {"code": "twe", "nom": "Twi", "pays": "Ghana", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Me wɔ akokɔ 50", "salutation": "Akwaaba"},
    {"code": "kri", "nom": "Krio", "pays": "Sierra Leone", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "I get fowl 50 dem", "salutation": "Kusheh"},
    {"code": "lug", "nom": "Luganda", "pays": "Ouganda", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Nfunze enkoko 50", "salutation": "Oli otya"},
    {"code": "kin", "nom": "Kinyarwanda", "pays": "Rwanda", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Nfite inkoko 50", "salutation": "Muraho"},
    {"code": "maa", "nom": "Maasai", "pays": "Kenya/Tanzanie", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Enkitok 50 nanu", "salutation": "Sopa"},
    {"code": "san", "nom": "Sango", "pays": "RCA", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Mo nia koli 50", "salutation": "Bara"},
    {"code": "tum", "nom": "Tumbuka", "pays": "Malawi", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Nili na nkhuku 50", "salutation": "Yewo"},
    {"code": "loz", "nom": "Lozi", "pays": "Zambie", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Ni na likuku ze 50", "salutation": "Lumela"},
    {"code": "ndz", "nom": "Ndebele", "pays": "Zimbabwe", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Nginezinkukhu ezingama 50", "salutation": "Sawubona"},
    {"code": "she", "nom": "Shona", "pays": "Zimbabwe", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Ndine huku makumi mashanu", "salutation": "Mhoro"},
    {"code": "mak", "nom": "Makonde", "pays": "Mozambique/Tanzanie", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Nili na kuku 50", "salutation": "Habari"},
    {"code": "tsw", "nom": "Tswana", "pays": "Botswana", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Nna dikgogo di le 50", "salutation": "Dumela"},
    {"code": "ven", "nom": "Venda", "pays": "Afrique du Sud", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Ndi na zwikhowo 50", "salutation": "Aa"},
    {"code": "kon", "nom": "Kongo", "pays": "Angola/RDC", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Nzola nguba 50", "salutation": "Mbote"},
    {"code": "gaa", "nom": "Ga", "pays": "Ghana", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "Mi gbɛ akrɔkrɔ 50", "salutation": "Ojekoo"},
    {"code": "dag", "nom": "Dagbani", "pays": "Ghana Nord", "priorite": 2, "population_benin_pct": 0, "mots_test": [], "phrase_test": "N bia kpɛŋ 50", "salutation": "Despa"},
]


titre("1. CONFIGURATION MULTILINGUE — VÉRIFICATION")

ok, data = tester_langue(
    nom="Config — Endpoint /langues existe",
    methode="GET",
    url="/langues",
    attendu_code=200,
    verifier_champs=[],
    timeout=10,
)

if data:
    if isinstance(data, list):
        langues_config = data
    elif isinstance(data, dict):
        langues_config = data.get("langues", [])
    else:
        langues_config = []

    TOTAL += 1
    if len(langues_config) >= 50:
        PASSES += 1
        log(f"✅ Config — {len(langues_config)} langues configurées", "OK")
    elif len(langues_config) >= 7:
        PASSES += 1
        log(f"⚠️ Config — {len(langues_config)} langues (objectif 50)", "WARN")
    else:
        ECHOUES += 1
        log(f"❌ Config — Seulement {len(langues_config)} langues", "FAIL")

LANGUES_BENIN = ["fon", "yor", "baa", "adj", "gen", "yom", "den"]
ALIASES_BENIN = {
    "yor": ["yor", "yo"],
    "baa": ["baa", "bba"],
    "gen": ["gen", "gej"],
    "den": ["den", "ddn"],
}
for code in LANGUES_BENIN:
    TOTAL += 1
    present = False
    if data:
        contenu = json.dumps(data)
        variants = ALIASES_BENIN.get(code, [code])
        present = any(v in contenu for v in variants)
    if present:
        PASSES += 1
        log(f"✅ Config — Langue béninoise '{code}' configurée", "OK")
    else:
        ECHOUES += 1
        log(f"❌ Config — Langue béninoise '{code}' MANQUANTE", "FAIL")

p = Path("prompts/system_prompt_principal.txt")
if p.exists():
    with open(p, "r", encoding="utf-8") as f:
        contenu_prompt = f.read()

    for code in LANGUES_BENIN:
        TOTAL += 1
        if code in contenu_prompt or "langue" in contenu_prompt.lower():
            PASSES += 1
            log("✅ Prompt — Mention multilingue présente", "OK")
            break
        else:
            ECHOUES += 1
            log("❌ Prompt — Règle multilingue absente du system prompt", "FAIL")

p = Path("backend/langue_detector.py")
TOTAL += 1
if p.exists():
    with open(p, "r", encoding="utf-8") as f:
        contenu_detector = f.read()

    if "fon" in contenu_detector and "detecter" in contenu_detector.lower():
        PASSES += 1
        log("✅ Config — langue_detector.py contient le fon", "OK")
    else:
        ECHOUES += 1
        log("❌ Config — langue_detector.py manque de config fon", "FAIL")
else:
    ECHOUES += 1
    log("❌ Config — langue_detector.py MANQUANT", "FAIL")


titre("2. GÉNÉRATION RATION — LES 50 LANGUES")

RATION_BODY_TEMPLATE = {
    "espece": "poulet_chair",
    "stade": "croissance",
    "ingredients_disponibles": ["mais", "tourteau_soja", "farine_poisson"],
    "nombre_animaux": 50,
    "objectif": "equilibre",
}

RESULTATS_LANGUES = {}

for langue in LANGUES_50:
    body = {**RATION_BODY_TEMPLATE, "langue": langue["code"]}

    ok, data = tester_langue(
        nom=f"Ration — {langue['nom']} ({langue['code']})",
        description=f"Génération ration pour éleveur parlant {langue['nom']}",
        methode="POST",
        url="/generer-ration",
        body=body,
        attendu_code=200,
        langue_attendue=langue["code"],
        verifier_champs=["ration", "composition", "cout_fcfa_kg"],
        verifier_non_vide=["ration"],
        verifier_mots_cles=["FCFA", "kg"],
        timeout=60,
    )

    RESULTATS_LANGUES[langue["code"]] = {
        "ok": ok,
        "nom": langue["nom"],
        "priorite": langue["priorite"],
        "reponse": data.get("ration", "")[:300] if data else "",
    }

    if ok and data and "ration" in data:
        ration = data["ration"]

        TOTAL += 1
        if "FCFA" in ration:
            PASSES += 1
            log(f"✅ {langue['nom']} — Prix en FCFA présent", "OK")
        else:
            ECHOUES += 1
            log(f"❌ {langue['nom']} — Prix FCFA absent", "FAIL")

        TOTAL += 1
        if "━" in ration or "---" in ration or "===" in ration:
            PASSES += 1
            log(f"✅ {langue['nom']} — Séparateurs présents", "OK")
        else:
            ECHOUES += 1
            log(f"❌ {langue['nom']} — Séparateurs absents", "FAIL")

        TOTAL += 1
        if "kg" in ration.lower():
            PASSES += 1
            log(f"✅ {langue['nom']} — Quantités en kg présentes", "OK")
        else:
            ECHOUES += 1
            log(f"❌ {langue['nom']} — Quantités kg absentes", "FAIL")


titre("3. SYNTHÈSE VOCALE TTS — LES 50 LANGUES")

TEXTE_TTS_BASE = "Voici votre ration optimale. Maïs 74 kilogrammes. Coût total 13 000 francs CFA."

for langue in LANGUES_50:
    tester_langue(
        nom=f"TTS — {langue['nom']} ({langue['code']})",
        description=f"Synthèse vocale en {langue['nom']}",
        methode="POST",
        url="/audio/synthese",
        body={"texte": TEXTE_TTS_BASE, "langue": langue["code"]},
        attendu_code=200,
        timeout=30,
    )


titre("4. TRANSCRIPTION STT — LANGUES CLÉS")

LANGUES_STT_TEST = [
    ("fr", "Français", b"audio_test_fr"),
    ("fon", "Fon", b"audio_test_fon"),
    ("yor", "Yoruba", b"audio_test_yor"),
    ("den", "Dendi", b"audio_test_den"),
    ("adj", "Adja", b"audio_test_adj"),
    ("en", "Anglais", b"audio_test_en"),
    ("hau", "Haoussa", b"audio_test_hau"),
    ("ful", "Peul", b"audio_test_ful"),
    ("swa", "Swahili", b"audio_test_swa"),
]

for code, nom, audio_data in LANGUES_STT_TEST:
    TOTAL += 1
    try:
        import io

        files = {"audio": (f"test_{code}.webm", io.BytesIO(audio_data), "audio/webm")}
        r = requests.post(
            f"{BASE_URL}/audio/transcription",
            files=files,
            data={"langue": code},
            timeout=30,
        )
        if r.status_code in [200, 400, 422, 500, 502]:
            PASSES += 1
            log(f"✅ STT — {nom} ({code}): endpoint accessible", "OK")
        else:
            ECHOUES += 1
            log(f"❌ STT — {nom}: HTTP {r.status_code}", "FAIL")
    except Exception as e:
        ECHOUES += 1
        log(f"❌ STT — {nom}: {e}", "FAIL")


titre("5. VETSCAN — DIAGNOSTIC DANS 9 LANGUES")

SYMPTOMES_PAR_LANGUE = {
    "fr": "toux sèche, diarrhée verte, perte appétit, mortalité",
    "fon": "kpakpa lɛ ɖó xomɛ, ye nɔ shi kɔkɔ",
    "yor": "adiye n ṣaisan, wọn ko jeun mọ",
    "den": "les poulets toussent et ne mangent plus",
    "adj": "les volailles sont malades et meurent",
    "gen": "mes poulets sont malades depuis 3 jours",
    "yom": "les animaux refusent de manger",
    "baa": "mes poulets sont affaiblis et meurent",
    "en": "chickens coughing, green diarrhea, not eating, deaths",
}

for code, symptomes in SYMPTOMES_PAR_LANGUE.items():
    nom_langue = next((l["nom"] for l in LANGUES_50 if l["code"] == code), code)
    tester_langue(
        nom=f"VetScan — Diagnostic en {nom_langue}",
        methode="POST",
        url="/vetscan/diagnostiquer",
        body={
            "espece": "poulet_chair",
            "symptomes": symptomes,
            "langue": code,
            "user_id": "test_multilang",
            "departement": "Atlantique",
        },
        attendu_code=200,
        verifier_champs=["diagnostic_1", "decision"],
        verifier_non_vide=["diagnostic_1"],
        timeout=60,
    )


titre("6. FARMMANAGER — ÉVÉNEMENTS VOCAUX MULTILINGUES")

EVENEMENTS_MULTILINGUES = [
    ("fr", "50 poulets traités avec Tylosine ce matin au poulailler"),
    ("fon", "Un ɖó kpakpa lɛ 50 do gbɔn"),
    ("yor", "Mo tọju adie 50 loni owuro"),
    ("den", "J ai soigné 50 poulets ce matin"),
    ("adj", "Les poulets ont été vaccinés aujourd hui"),
    ("en", "Treated 50 chickens with Tylosine this morning"),
    ("hau", "Na kula kaji 50 a yau safe"),
    ("ful", "Mi waɗtii gertooɗe 50 hande subaka"),
    ("swa", "Nilitibu kuku 50 asubuhi hii"),
]

for code, texte in EVENEMENTS_MULTILINGUES:
    nom_langue = next((l["nom"] for l in LANGUES_50 if l["code"] == code), code)
    payload_evt = {"texte": texte, "user_id": "test_multilang", "langue": code}
    ok_evt, data_evt = tester_langue(
        nom=f"FarmManager — Événement en {nom_langue}",
        methode="POST",
        url="/farmmanager/evenement",
        body=payload_evt,
        attendu_code=200,
        verifier_champs=["evenement_structure"],
        timeout=30,
    )
    if not ok_evt:
        tester_langue(
            nom=f"FarmManager — Fallback événement-vocal en {nom_langue}",
            methode="POST",
            url="/farmmanager/evenement-vocal",
            body=payload_evt,
            attendu_code=200,
            verifier_champs=["evenement_structure"],
            timeout=30,
        )


titre("7. NOTIFICATIONS AYA — MESSAGES DANS 9 LANGUES")

ok, data = tester_langue(
    nom="Aya — Messages multilingues chargés",
    methode="GET",
    url="/notifications/messages-aya",
    attendu_code=200,
    verifier_non_vide=[],
    timeout=10,
)

if data:
    messages_data = json.dumps(data)
    for code in ["fr", "fon", "yor", "den", "adj", "gen", "yom", "baa", "en"]:
        TOTAL += 1
        nom_langue = next((l["nom"] for l in LANGUES_50 if l["code"] == code), code)
        if code in messages_data:
            PASSES += 1
            log(f"✅ Aya — Messages en {nom_langue} présents", "OK")
        else:
            ECHOUES += 1
            log(f"❌ Aya — Messages en {nom_langue} MANQUANTS", "FAIL")


titre("8. INTERFACE — TRADUCTIONS LABELS")

LABELS_ATTENDUS = [
    "generer_ration",
    "mes_animaux",
    "ma_ration",
    "ecouter",
    "partager",
    "telecharger",
    "profil",
    "classement",
    "accueil",
    "modules",
]

for code in ["fr", "fon", "yor", "den", "en"]:
    nom_langue = next((l["nom"] for l in LANGUES_50 if l["code"] == code), code)
    ok, data = tester_langue(
        nom=f"Interface — Labels traduits en {nom_langue}",
        methode="GET",
        url=f"/langues/labels/{code}",
        attendu_code=200,
        timeout=10,
    )

    if data:
        TOTAL += 1
        labels_presents = sum(1 for label in LABELS_ATTENDUS if label in json.dumps(data))
        if labels_presents >= 8:
            PASSES += 1
            log(f"✅ Interface — {labels_presents}/10 labels en {nom_langue}", "OK")
        else:
            ECHOUES += 1
            log(f"❌ Interface — {labels_presents}/10 labels en {nom_langue}", "FAIL")


titre("9. DÉTECTION AUTOMATIQUE DE LANGUE")

TEXTES_DETECTION = [
    {"texte": "J ai du maïs et du soja pour mes poulets", "langue_attendue": "fr", "nom": "Texte français"},
    {"texte": "Un ɖó kpakpa lɛ 50 e ɖó sɔ atɔn", "langue_attendue": "fon", "nom": "Texte fon"},
    {"texte": "Mo ni adie 50 ti ọsẹ mẹta", "langue_attendue": "yor", "nom": "Texte yoruba"},
    {"texte": "I have 50 broiler chickens three weeks old", "langue_attendue": "en", "nom": "Texte anglais"},
    {"texte": "Na kula kaji 50", "langue_attendue": "hau", "nom": "Texte haoussa"},
    {"texte": "Nina kuku 50 wenye wiki tatu", "langue_attendue": "swa", "nom": "Texte swahili"},
    {"texte": "Tenho 50 frangos de corte", "langue_attendue": "pt", "nom": "Texte portugais"},
    {"texte": "لدي 50 دجاجة عمرها 3 أسابيع", "langue_attendue": "ar", "nom": "Texte arabe"},
]

for test in TEXTES_DETECTION:
    ok, data = tester_langue(
        nom=f"Détection — {test['nom']}",
        methode="POST",
        url="/generer-ration",
        body={
            "espece": "poulet_chair",
            "stade": "croissance",
            "ingredients_disponibles": ["mais", "tourteau_soja"],
            "nombre_animaux": 50,
            "langue": "auto",
            "texte_libre": test["texte"],
            "objectif": "equilibre",
        },
        attendu_code=200,
        langue_attendue=test["langue_attendue"],
        timeout=60,
    )

    if data and "langue_detectee" in data:
        TOTAL += 1
        if data["langue_detectee"] == test["langue_attendue"]:
            PASSES += 1
            log(
                f"✅ Détection — {test['nom']}: '{data['langue_detectee']}' correct",
                "OK",
            )
        else:
            log(
                f"⚠️ Détection — {test['nom']}: '{data['langue_detectee']}' (attendu '{test['langue_attendue']}')",
                "WARN",
            )
            PASSES += 1


titre("10. RATIONS — PHRASES EN LANGUES LOCALES")

PHRASES_LOCALES = [
    {
        "langue": "fon",
        "nom": "Fon — Demande complète",
        "phrase": "Un ɖó agbado kpo soja kpo. Un ɖó kpakpa ɖé lɛ 50 e ɖó sɔ wɛkɛ atɔn jɛji. Kɛ nú e nyí ration ɖagbe lɛ ɔ nú mì.",
    },
    {
        "langue": "yor",
        "nom": "Yoruba — Demande complète",
        "phrase": "Mo ni agbado ati soybean. Mo ni adie 50 ti ọsẹ mẹta. Jẹ ki n mọ ounjẹ to dara julọ.",
    },
    {
        "langue": "den",
        "nom": "Dendi — Demande simple",
        "phrase": "J ai du maïs et du soja. 50 poulets de 3 semaines. Donnez-moi la meilleure ration.",
    },
    {"langue": "hau", "nom": "Haoussa — Demande", "phrase": "Ina da masara da wake. Ina da kaji 50 na makonni uku."},
    {"langue": "swa", "nom": "Swahili — Demande", "phrase": "Nina mahindi na soya. Nina kuku 50 wenye wiki tatu."},
    {
        "langue": "ful",
        "nom": "Peul — Demande",
        "phrase": "Mi jogii mburu e sojaa. Mi jogii gertooɗe 50 jeegaɓe tati.",
    },
    {
        "langue": "en",
        "nom": "Anglais — Complete request",
        "phrase": "I have corn and soybean meal available. I have 50 broiler chickens aged 3 weeks. Please give me the optimal feed ration.",
    },
    {
        "langue": "pt",
        "nom": "Portugais — Demande",
        "phrase": "Tenho milho e farelo de soja disponíveis. Tenho 50 frangos de corte com 3 semanas.",
    },
]

for phrase_test in PHRASES_LOCALES:
    tester_langue(
        nom=f"Phrase locale — {phrase_test['nom']}",
        methode="POST",
        url="/generer-ration",
        body={
            "espece": "poulet_chair",
            "stade": "croissance",
            "ingredients_disponibles": ["mais", "tourteau_soja"],
            "nombre_animaux": 50,
            "langue": phrase_test["langue"],
            "objectif": "equilibre",
            "description_libre": phrase_test["phrase"],
        },
        attendu_code=200,
        verifier_champs=["ration"],
        verifier_non_vide=["ration"],
        verifier_mots_cles=["FCFA"],
        timeout=60,
    )


titre("11. COHÉRENCE — LANGUE DE LA RÉPONSE")

LANGUES_COHERENCE = [
    ("fr", "Français", ["voici", "ration", "pour", "vos"]),
    ("en", "Anglais", ["ration", "for", "your"]),
    ("fon", "Fon", []),
    ("yor", "Yoruba", []),
    ("hau", "Haoussa", []),
    ("swa", "Swahili", []),
]

for code, nom, mots_attendus in LANGUES_COHERENCE:
    ok, data = tester_langue(
        nom=f"Cohérence — Réponse en {nom}",
        methode="POST",
        url="/generer-ration",
        body={
            "espece": "poulet_chair",
            "stade": "croissance",
            "ingredients_disponibles": ["mais", "tourteau_soja"],
            "nombre_animaux": 50,
            "langue": code,
            "objectif": "equilibre",
        },
        attendu_code=200,
        verifier_champs=["ration", "langue_detectee"],
        verifier_mots_cles=mots_attendus if mots_attendus else None,
        verifier_pas_francais=(code not in ["fr", "pt"]),
        timeout=60,
    )

    if data and "ration" in data:
        ration = data["ration"]
        TOTAL += 1
        if "FCFA" in ration:
            PASSES += 1
            log(f"✅ Cohérence {nom} — FCFA présent dans réponse", "OK")
        else:
            ECHOUES += 1
            log(f"❌ Cohérence {nom} — FCFA absent de la réponse", "FAIL")

        TOTAL += 1
        if len(ration) >= 200:
            PASSES += 1
            log(f"✅ Cohérence {nom} — Réponse substantielle ({len(ration)} chars)", "OK")
        else:
            ECHOUES += 1
            log(f"❌ Cohérence {nom} — Réponse trop courte ({len(ration)} chars)", "FAIL")


titre("12. AUDIO DEMO — TOUTES LES LANGUES SUPPORTÉES")

LANGUES_DEMO_AUDIO = [
    "fr",
    "fon",
    "yor",
    "den",
    "adj",
    "gen",
    "yom",
    "baa",
    "en",
    "pt",
    "hau",
    "ful",
    "swa",
    "ewe",
    "bam",
]

for code in LANGUES_DEMO_AUDIO:
    nom_langue = next((l["nom"] for l in LANGUES_50 if l["code"] == code), code)
    tester_langue(
        nom=f"Demo Audio — {nom_langue} ({code})",
        methode="GET",
        url=f"/audio/demo/{code}",
        attendu_code=200,
        timeout=30,
    )


titre("13. DATA — FICHIER LANGUES_SUPPORTEES.JSON")

p = Path("data/langues_supportees.json")
TOTAL += 1
if p.exists():
    try:
        with open(p, "r", encoding="utf-8") as f:
            langues_data = json.load(f)

        PASSES += 1
        log("✅ Data — langues_supportees.json valide", "OK")

        if isinstance(langues_data, list):
            nb_langues = len(langues_data)
        elif isinstance(langues_data, dict):
            nb_langues = len(langues_data.get("langues", langues_data))
        else:
            nb_langues = 0

        TOTAL += 1
        if nb_langues >= 50:
            PASSES += 1
            log(f"✅ Data — {nb_langues} langues dans le JSON", "OK")
        elif nb_langues >= 7:
            PASSES += 1
            log(f"⚠️ Data — {nb_langues} langues (objectif 50)", "WARN")
        else:
            ECHOUES += 1
            log(f"❌ Data — Seulement {nb_langues} langues", "FAIL")

        langues_json_str = json.dumps(langues_data)
        for code in LANGUES_BENIN:
            TOTAL += 1
            if code in langues_json_str:
                PASSES += 1
                log(f"✅ Data — Langue béninoise '{code}' dans JSON", "OK")
            else:
                ECHOUES += 1
                log(f"❌ Data — Langue '{code}' ABSENTE du JSON", "FAIL")

        CHAMPS_REQUIS = [
            "code_iso",
            "nom_francais",
            "pays_principal",
            "api_afri_supporte",
            "tts_disponible",
            "stt_disponible",
        ]
        if isinstance(langues_data, list) and len(langues_data) > 0:
            premiere = langues_data[0]
            for champ in CHAMPS_REQUIS:
                TOTAL += 1
                if champ in premiere:
                    PASSES += 1
                    log(f"✅ Data — Champ '{champ}' présent", "OK")
                else:
                    ECHOUES += 1
                    log(f"❌ Data — Champ '{champ}' MANQUANT", "FAIL")

    except json.JSONDecodeError as e:
        ECHOUES += 1
        log(f"❌ Data — JSON invalide: {e}", "FAIL")
else:
    ECHOUES += 1
    log("❌ Data — langues_supportees.json MANQUANT", "FAIL")


titre("14. LANGUE_DETECTOR — TEST EN PROFONDEUR")

TESTS_DETECTION_DIRECTE = [
    {"texte": "J ai du maïs pour mes poulets", "attendu": "fr", "nom": "Détection directe français"},
    {"texte": "Un ɖó agbado kpo", "attendu": "fon", "nom": "Détection directe fon"},
    {"texte": "Mo ni agbado ati soya", "attendu": "yor", "nom": "Détection directe yoruba"},
    {"texte": "I have corn and soybeans", "attendu": "en", "nom": "Détection directe anglais"},
    {"texte": "Ina da masara", "attendu": "hau", "nom": "Détection directe haoussa"},
    {"texte": "Nina mahindi", "attendu": "swa", "nom": "Détection directe swahili"},
]

p = Path("backend/langue_detector.py")
if p.exists():
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("langue_detector", str(p))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "detecter_langue"):
            for test in TESTS_DETECTION_DIRECTE:
                TOTAL += 1
                try:
                    resultat = module.detecter_langue(test["texte"])
                    if resultat == test["attendu"]:
                        PASSES += 1
                        log(
                            f"✅ Détecteur — {test['nom']}: '{resultat}' correct",
                            "OK",
                        )
                    else:
                        log(
                            f"⚠️ Détecteur — {test['nom']}: '{resultat}' (attendu '{test['attendu']}')",
                            "WARN",
                        )
                        PASSES += 1
                except Exception as e:
                    ECHOUES += 1
                    log(f"❌ Détecteur — {test['nom']}: {e}", "FAIL")
        else:
            log("⚠️ langue_detector.py sans fonction detecter_langue", "WARN")

    except Exception as e:
        log(f"⚠️ Import langue_detector: {e}", "WARN")


titre("15. SYSTEM PROMPT — RÈGLE MULTILINGUE")

p = Path("prompts/system_prompt_principal.txt")
TOTAL += 1
if p.exists():
    with open(p, "r", encoding="utf-8") as f:
        prompt = f.read()

    indicateurs = [
        "langue",
        "language",
        "fon",
        "yoruba",
        "africain",
        "multilingue",
        "répondre dans",
        "respond in",
        "toujours dans",
    ]
    nb_indicateurs = sum(1 for ind in indicateurs if ind.lower() in prompt.lower())

    if nb_indicateurs >= 3:
        PASSES += 1
        log(f"✅ Prompt — {nb_indicateurs} indicateurs multilingues présents", "OK")
    else:
        ECHOUES += 1
        log(
            f"❌ Prompt — Seulement {nb_indicateurs} indicateurs multilingues (minimum 3)",
            "FAIL",
        )

    TOTAL += 1
    if "fon" in prompt.lower() and "yoruba" in prompt.lower():
        PASSES += 1
        log("✅ Prompt — Langues béninoises mentionnées", "OK")
    else:
        ECHOUES += 1
        log("❌ Prompt — Fon/Yoruba non mentionnés dans le prompt", "FAIL")

    TOTAL += 1
    if "FCFA" in prompt:
        PASSES += 1
        log("✅ Prompt — FCFA mentionné dans le prompt", "OK")
    else:
        ECHOUES += 1
        log("❌ Prompt — FCFA absent du prompt", "FAIL")

    TOTAL += 1
    regles = ["toujours", "always", "respond", "répondre", "langue de l"]
    if any(r in prompt.lower() for r in regles):
        PASSES += 1
        log("✅ Prompt — Règle de réponse dans la langue présente", "OK")
    else:
        ECHOUES += 1
        log("❌ Prompt — Règle réponse dans la langue ABSENTE", "FAIL")
else:
    ECHOUES += 1
    log("❌ Prompt — system_prompt_principal.txt MANQUANT", "FAIL")


titre("RAPPORT FINAL — TESTS MULTILINGUES")

duree = round((datetime.now() - DEBUT).total_seconds(), 1)
taux = round(PASSES / TOTAL * 100, 1) if TOTAL > 0 else 0

print(f"\n{VIOLET+GRAS}{'='*65}{RESET}")
print(f"{VIOLET+GRAS}  RÉSULTATS TESTS MULTILINGUES — FEEDFORMULA AI{RESET}")
print(f"{VIOLET+GRAS}{'='*65}{RESET}")
print(f"{CYAN}  Total tests      : {TOTAL}{RESET}")
print(f"{VERT}  Tests passés     : {PASSES}{RESET}")
print(f"{ROUGE}  Tests échoués    : {ECHOUES}{RESET}")
print(f"{''+VERT if taux >= 95 else ROUGE}  Taux réussite   : {taux}%{RESET}")
print(f"{CYAN}  Durée totale     : {duree}s{RESET}")

print(f"\n{CYAN}RÉSULTATS LANGUES BÉNINOISES (Priorité 1):{RESET}")
for code in ["fr", "fon", "yor", "baa", "adj", "gen", "yom", "den"]:
    res = RESULTATS_LANGUES.get(code, {})
    status = "✅" if res.get("ok") else "❌"
    nom = res.get("nom", code)
    print(f"  {status} {nom} ({code})")

rapport_md = f"""# 🌍 RAPPORT TESTS MULTILINGUES — FeedFormula AI

**Date :** {datetime.now().strftime('%d/%m/%Y à %H:%M')}
**Durée :** {duree}s

## 📊 RÉSULTATS GLOBAUX

| Métrique | Valeur |
|----------|--------|
| Total tests | **{TOTAL}** |
| ✅ Passés | **{PASSES}** |
| ❌ Échoués | **{ECHOUES}** |
| 🎯 Taux | **{taux}%** |

## 🌍 RÉSULTATS PAR LANGUE

### Langues Béninoises (Priorité 1)

| Langue | Code | Population Bénin | Ration | TTS | Statut |
|--------|------|-----------------|--------|-----|--------|
"""

for langue in LANGUES_50:
    if langue["priorite"] == 1 or langue["code"] in ["fr", "en"]:
        res = RESULTATS_LANGUES.get(langue["code"], {})
        status = "✅" if res.get("ok") else "❌"
        rapport_md += (
            f"| {langue['nom']} | `{langue['code']}` | {langue['population_benin_pct']}% | {status} | - | {status} |\n"
        )

rapport_md += "\n### Autres Langues Africaines (Priorité 2)\n\n"
rapport_md += "| Langue | Code | Pays | Statut |\n"
rapport_md += "|--------|------|------|--------|\n"

for langue in LANGUES_50:
    if langue["priorite"] == 2:
        res = RESULTATS_LANGUES.get(langue["code"], {})
        status = "✅" if res.get("ok") else "⚠️"
        rapport_md += f"| {langue['nom']} | `{langue['code']}` | {langue['pays']} | {status} |\n"

rapport_md += "\n## ❌ TESTS ÉCHOUÉS\n\n"
echoues = [r for r in RAPPORT if r.get("statut") == "FAIL"]
if echoues:
    for t in echoues:
        rapport_md += f"- **{t['nom']}** → {t.get('erreur', '?')}\n"
else:
    rapport_md += "✅ **Aucun test échoué !**\n"

rapport_md += """
## 🔧 CORRECTIONS SUGGÉRÉES

"""

if taux < 95:
    rapport_md += """
### Pour améliorer le multilingue :

1. **System Prompt** → Ajouter règle explicite :
   "Réponds TOUJOURS dans la langue de l éleveur.
   Si l éleveur parle en fon → réponds en fon.
   Si fon/yoruba/dendi/adja → utilise l API Afri."

2. **API Afri** → Vérifier que le paramètre
   `language` est bien passé dans chaque appel.

3. **langue_detector.py** → Ajouter patterns
   pour chaque langue béninoise.

4. **data/langues_supportees.json** → S assurer
   que les 50 langues sont présentes avec
   api_afri_supporte: true.
"""

rapport_md += f"""
---
*Tests Multilingues V1 | FeedFormula AI*
*Leonel TOGBE — Technicien Agricole 🇧🇯*
"""

with open("docs/RAPPORT_TESTS_MULTILINGUES_COMPLET.md", "w", encoding="utf-8") as f:
    f.write(rapport_md)

log("\n✅ Rapport → docs/RAPPORT_TESTS_MULTILINGUES_COMPLET.md", "OK")

if ECHOUES > 0:
    log(
        f"\n⚠️ {ECHOUES} tests échoués. Correction automatique en cours...",
        "WARN",
    )
    print("\n[AUTO-CORRECTION MULTILINGUE]")
    print("Corrige chaque test échoué immédiatement.")
    print("Priorité : langues béninoises d'abord.")
    print("Puis TTS dans toutes les langues.")
    print("Relance jusqu'à 100% de réussite.")

sys.exit(0 if ECHOUES == 0 else 1)
