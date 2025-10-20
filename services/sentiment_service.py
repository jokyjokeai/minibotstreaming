from typing import Tuple
import re
from logger_config import get_logger

logger = get_logger(__name__)

class SentimentService:
    """Service for sentiment analysis using keyword-based approach"""

    def __init__(self):
        # Positive keywords in French - CONSOLIDÉS ET RENFORCÉS
        self.positive_words = {
            # Affirmations basiques
            "oui", "ok", "okay", "ouais", "ouaip", "yep", "oké",

            # Accord
            "d'accord", "daccord", "d'ac", "dac", "entendu", "bien entendu",
            "tout à fait", "exactement", "correct", "parfait", "très bien",

            # Intérêt
            "intéressé", "intéressée", "intéressant", "intéressante", "intéresse",
            "ça m'intéresse", "ca m'intéresse", "je suis intéressé", "suis intéressée",
            "ça me plaît", "ca me plait", "me plaît", "ça me va", "me va",

            # Enthousiasme
            "super", "génial", "excellent", "formidable", "merveilleux", "fantastique",
            "magnifique", "parfait", "top", "cool", "nice", "grave", "carrément",

            # Accord fort
            "volontiers", "absolument", "certainement", "évidemment", "bien sûr",
            "bien sur", "évidemment", "clairement", "forcément", "assurément",

            # Positionnement positif
            "pourquoi pas", "allons-y", "allons", "allez", "allez-y", "vas-y", "banco",
            "go", "let's go", "on y va", "c'est parti", "cest parti", "c parti",
            "on se lance", "je me lance", "on fonce", "partez", "go go go",
            "je veux", "je veux bien", "je voudrais", "j'aimerais", "j'aimerai",
            "on peut", "c'est possible", "ça marche", "ca marche", "nickel", "impec",

            # Acceptation
            "accepte", "accepter", "j'accepte", "prendre", "je prends",
            "rendez-vous", "rdv", "avec plaisir", "volontiers",

            # Adjectifs positifs
            "bonne", "bon", "bien", "idée", "géniale", "excellente", "parfaite"
        }

        # Negative keywords in French - CONSOLIDÉS ET RENFORCÉS
        self.negative_words = {
            # Refus direct
            "non", "nan", "nope", "nenni", "jamais", "aucun", "aucune",

            # Refus poli
            "pas", "pas du tout", "pas vraiment", "pas tellement", "pas trop",
            "refus", "refuse", "refuser", "je refuse", "désolé", "desole",

            # Impossibilité
            "impossible", "peut pas", "peux pas", "ne peux pas", "ne peut pas",
            "incapable", "pas possible", "ça va pas", "ca va pas",

            # Désintérêt
            "inintéressé", "inintéressée", "pas intéressé", "pas intéressée",
            "m'intéresse pas", "intéresse pas", "me plaît pas", "plait pas",

            # Mauvais timing/situation
            "occupé", "occupée", "pas le temps", "pas de temps", "pas disponible",
            "indisponible", "pas libre", "moment", "là", "maintenant",

            # Confusion/erreur
            "c'est pas moi", "pas moi", "mauvais numéro", "mauvaise personne",
            "vous vous trompez", "erreur", "connais pas", "je connais pas",

            # Demande d'arrêt
            "stop", "arrêtez", "arrêter", "cessez", "ça suffit", "ca suffit",
            "laissez-moi", "tranquille", "paix", "foutez-moi", "fichez-moi",

            # Agacement/colère
            "dérangez", "déranger", "embêtez", "embêter", "emmerdez", "emmerder",
            "enquiquinez", "gavé", "gave", "soûlant", "soulant", "chiant",
            "relou", "lourd", "gonflant", "pénible", "penible", "énervé", "énervée",
            "agacé", "agacée", "insupportable",

            # Contexte négatif
            "spam", "solicitation", "démarchage", "vente", "commercial", "pub",
            "publicité", "arnaque", "escroquerie",

            # Actions de rejet
            "raccrochez", "raccrocher", "rappelez", "rappeler", "recontactez",
            "liste rouge", "opposition",

            # Jugements négatifs
            "mauvais", "mauvaise", "nul", "nulle", "terrible", "horrible",
            "affreux", "merdique"
        }

        # Interrogative patterns - NOUVEAU: détection des questions
        self.interrogative_patterns = [
            # Questions "qui"
            r'\b(qui|c\'est qui|vous êtes qui|qui êtes|qui es|t\'es qui|vous etes qui)\b',

            # Questions "comment"
            r'\b(comment\s+\w+|comment avez|comment vous|comment tu|comment t\'|comment c\'est)\b',

            # Questions "pourquoi"
            r'\b(pourquoi|pour quoi|pkoi|c\'est pourquoi|pourquoi vous|pourquoi tu)\b',

            # Questions "quoi"
            r'\b(c\'est quoi|quoi\s|qu\'est-ce|quest-ce|vous voulez quoi|tu veux quoi|pour quoi faire)\b',

            # Questions "où/d'où"
            r'\b(d\'où|d ou|vous appelez d|où vous|ou vous|d\'où vous)\b',

            # Questions "combien"
            r'\b(combien|ça coûte|ca coute|quel prix|quelle somme)\b',

            # Phrases interrogatives directes
            r'\b(quel|quelle|quels|quelles|lequel|laquelle)\b',

            # Patterns de méfiance/suspicion
            r'\b(comment (avez-vous|vous avez|tu as|t\'as) (eu|obtenu|trouvé|récupéré) mon (numéro|numero|contact|téléphone|telephone))\b',
            r'\b(d\'où (vient|provient) (ce|cet|cette) (appel|numéro|numero))\b',
            r'\b(vous (représentez|travaillez pour) qui|qui vous (envoie|mandate))\b'
        ]
    
    def analyze_sentiment(self, text: str) -> Tuple[str, float]:
        """
        Analyze sentiment of text using keyword counting

        Args:
            text: The transcribed text to analyze

        Returns:
            Tuple of (sentiment, confidence) where:
            - sentiment: "positive", "negative", "interrogatif", or "unclear"
            - confidence: float between 0 and 1
        """
        if not text or not text.strip():
            return "unclear", 0.0

        # Normalize text: lowercase and clean
        normalized_text = text.lower().strip()

        # ✅ FIX: Définir words dès le début pour éviter UnboundLocalError
        normalized_text_for_words = re.sub(r'[^\w\s]', ' ', normalized_text)
        words = normalized_text_for_words.split()

        logger.info(f"💭 Analyzing sentiment for: '{text[:50]}...'")

        # ============================================================
        # PRIORITÉ 0: EXPRESSIONS IDIOMATIQUES POSITIVES (avant tout!)
        # ============================================================
        # "pourquoi pas" = acceptation en français (doit être détecté AVANT "pourquoi" interrogatif)
        if "pourquoi pas" in normalized_text:
            logger.info("✅ Found positive idiom: 'pourquoi pas' (acceptance)")
            return "positive", 0.8

        # Autres expressions idiomatiques d'acceptation
        if "ça me va" in normalized_text or "ca me va" in normalized_text:
            logger.info("✅ Found positive idiom: 'ça me va'")
            return "positive", 0.75

        if "volontiers" in normalized_text:
            logger.info("✅ Found positive idiom: 'volontiers'")
            return "positive", 0.8

        # Expressions d'enthousiasme (c'est parti, allez, etc.)
        if any(expr in normalized_text for expr in ["c'est parti", "cest parti", "c parti"]):
            logger.info("✅ Found positive idiom: 'c'est parti' (let's go)")
            return "positive", 0.85

        if normalized_text.startswith(("allez", "allons", "vas-y", "go")):
            logger.info("✅ Found enthusiastic start expression")
            return "positive", 0.85

        # ============================================================
        # PRIORITÉ 1: EXPRESSIONS D'INCOMPRÉHENSION → NEUTRE (pas négatif!)
        # ============================================================
        # "Allô?", "Hein?", "Pardon?" = incompréhension, PAS refus → traiter comme neutre
        incomprehension_words = ["allô", "allo", "hein", "pardon", "comment", "quoi", "répétez", "repetez"]
        if any(word in normalized_text for word in incomprehension_words) and len(words) <= 3:
            logger.info(f"🤷 INCOMPRÉHENSION détectée ('{text[:30]}...') → NEUTRE (bénéfice du doute)")
            return "neutre", 0.6  # Neutre = Lead potentiel (bénéfice du doute)

        # ============================================================
        # PRIORITÉ 2: DÉTECTION INTERROGATIVE (questions/méfiance)
        # ============================================================
        for pattern in self.interrogative_patterns:
            if re.search(pattern, normalized_text, re.IGNORECASE):
                logger.info(f"❓ INTERROGATIF detected: pattern '{pattern[:30]}...' found")
                # Vérifier si c'est une vraie question (présence de "?" ou mots interrogatifs)
                if "?" in text or any(word in normalized_text for word in
                    ["qui", "quoi", "comment", "où", "combien", "quel", "quelle"]):
                    # Exclure "pourquoi" seul car déjà géré avec "pourquoi pas" ci-dessus
                    logger.info("❓ Confirmed: Interrogative sentiment")
                    return "interrogatif", 0.85

        # ============================================================
        # PRIORITÉ 3: DÉTECTION NÉGATIVE FORTE (phrases explicites)
        # ============================================================
        # Phrases de rejet très fortes
        if "laissez-moi tranquille" in normalized_text or "foutez-moi" in normalized_text:
            logger.info("🚫 Found VERY strong negative: 'laissez-moi tranquille' / 'foutez-moi'")
            return "negative", 0.95

        if "fichez-moi la paix" in normalized_text or "ça suffit" in normalized_text:
            logger.info("🚫 Found VERY strong negative: 'fichez-moi la paix' / 'ça suffit'")
            return "negative", 0.95

        # Désintérêt explicite
        if "m'intéresse pas" in normalized_text or "ne m'intéresse pas" in normalized_text:
            logger.info("🚫 Found explicit negative: 'ne m'intéresse pas'")
            return "negative", 0.9

        if "pas intéressé" in normalized_text or "pas intéressée" in normalized_text:
            logger.info("🚫 Found strong negative: 'pas intéressé(e)'")
            return "negative", 0.85

        # Refus catégorique
        if "pas du tout" in normalized_text:
            logger.info("🚫 Found strong negative: 'pas du tout'")
            return "negative", 0.85

        # Erreur de personne / mauvais numéro
        if "c'est pas moi" in normalized_text or "pas moi" in normalized_text:
            logger.info("🚫 Found negative: 'c'est pas moi'")
            return "negative", 0.8

        if "mauvais numéro" in normalized_text or "vous vous trompez" in normalized_text:
            logger.info("🚫 Found negative: 'mauvais numéro' / 'vous vous trompez'")
            return "negative", 0.8

        if "connais pas" in normalized_text or "je connais pas" in normalized_text:
            logger.info("🚫 Found negative: 'connais pas'")
            return "negative", 0.75

        # Occupé / pas le temps
        if "pas le temps" in normalized_text or "pas de temps" in normalized_text:
            logger.info("🚫 Found negative: 'pas le temps'")
            return "negative", 0.75

        if "je suis occupé" in normalized_text or "suis occupée" in normalized_text:
            logger.info("🚫 Found negative: 'je suis occupé(e)'")
            return "negative", 0.7

        # ============================================================
        # PRIORITÉ 4: DÉTECTION POSITIVE FORTE (phrases explicites)
        # ============================================================
        # Intérêt explicite
        if "ça m'intéresse" in normalized_text or "ca m'intéresse" in normalized_text:
            logger.info("✅ Found explicit positive: 'ça m'intéresse'")
            return "positive", 0.9

        if "je suis intéressé" in normalized_text or "suis intéressée" in normalized_text:
            logger.info("✅ Found explicit positive: 'je suis intéressé(e)'")
            return "positive", 0.9

        if "ça me plaît" in normalized_text or "ca me plait" in normalized_text:
            logger.info("✅ Found explicit positive: 'ça me plaît'")
            return "positive", 0.85

        # Oui en début (sans négation)
        if normalized_text.startswith("oui") and "pas" not in normalized_text:
            logger.info("✅ Found strong positive: starts with 'oui'")
            return "positive", 0.85

        if normalized_text.startswith("ouais") and "pas" not in normalized_text:
            logger.info("✅ Found strong positive: starts with 'ouais'")
            return "positive", 0.8

        # Accord
        if "d'accord" in normalized_text or "daccord" in normalized_text:
            logger.info("✅ Found strong positive: 'd'accord'")
            return "positive", 0.8

        if "bien sûr" in normalized_text or "bien sur" in normalized_text:
            logger.info("✅ Found strong positive: 'bien sûr'")
            return "positive", 0.8

        # Acceptation
        if "ça marche" in normalized_text or "ca marche" in normalized_text:
            logger.info("✅ Found positive: 'ça marche'")
            return "positive", 0.75

        if "je veux bien" in normalized_text:
            logger.info("✅ Found positive: 'je veux bien'")
            return "positive", 0.75

        # Count positive and negative words (words déjà défini au début)
        positive_count = 0
        negative_count = 0

        for word in words:
            if word in self.positive_words:
                positive_count += 1
                logger.debug(f"✅ Found positive word: '{word}'")
            elif word in self.negative_words:
                negative_count += 1
                logger.debug(f"❌ Found negative word: '{word}'")
        
        # Determine sentiment
        total_sentiment_words = positive_count + negative_count
        
        if total_sentiment_words == 0:
            logger.info("🤷 No sentiment words found - unclear")
            return "unclear", 0.0
        
        # Calculate confidence based on word count and text length
        text_length = len(words)
        confidence_base = min(total_sentiment_words / max(text_length, 1), 1.0)
        
        if positive_count > negative_count:
            sentiment = "positive"
            confidence = confidence_base * (positive_count / total_sentiment_words)
        elif negative_count > positive_count:
            sentiment = "negative" 
            confidence = confidence_base * (negative_count / total_sentiment_words)
        else:
            sentiment = "unclear"
            confidence = 0.5
        
        logger.info(f"📊 Sentiment: {sentiment} (confidence: {confidence:.2f}) - pos:{positive_count} neg:{negative_count}")
        
        return sentiment, confidence
    
    def is_interested(self, sentiment: str, confidence: float) -> bool:
        """
        Determine if the person seems interested based on sentiment analysis

        Args:
            sentiment: The determined sentiment ("positive", "negative", "interrogatif", "unclear")
            confidence: Confidence score (0-1)

        Returns:
            Boolean indicating if person seems interested
        """
        return sentiment == "positive" and confidence > 0.6

# Global instance
sentiment_service = SentimentService()