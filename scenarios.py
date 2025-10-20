#!/usr/bin/env python3
"""
Scénarios d'appel pour MiniBotPanel v2
Version complètement refaite - Compatible avec nouveau robot_ari.py
"""

from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Call, CallInteraction, Contact
from logger_config import get_logger
import time
import os

logger = get_logger(__name__)

# Import des services d'assemblage et transcription
try:
    from services.audio_assembly_service import audio_assembly_service
    from services.transcript_service import transcript_service
    ASSEMBLY_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️  Audio assembly/transcript services not available: {e}")
    ASSEMBLY_AVAILABLE = False

# ============================================================================
# ⏱️ CONFIGURATION DES TEMPS D'ÉCOUTE PAR ÉTAPE
# ============================================================================
# Tu peux modifier ces valeurs facilement selon tes besoins !
#
# Paramètres:
#   - max_silence_seconds: Secondes de silence pour considérer que la réponse est terminée
#   - wait_before_stop: Temps maximum total d'écoute (en secondes)
#
# Astuce: Si les réponses sont coupées trop tôt → Augmenter wait_before_stop
#         Si le robot attend trop longtemps après la réponse → Réduire max_silence_seconds

LISTEN_TIMEOUTS = {
    "hello": {
        "max_silence_seconds": 2,
        "wait_before_stop": 15  # Augmenté de 8 → 15s pour laisser le temps de répondre
    },
    "retry": {
        "max_silence_seconds": 2,
        "wait_before_stop": 15  # Augmenté de 6 → 15s pour laisser le temps de répondre
    },
    "q1": {
        "max_silence_seconds": 2,
        "wait_before_stop": 15  # Augmenté de 10 → 15s pour laisser le temps de répondre
    },
    "q2": {
        "max_silence_seconds": 2,
        "wait_before_stop": 15  # Augmenté de 10 → 15s pour laisser le temps de répondre
    },
    "q3": {
        "max_silence_seconds": 2,
        "wait_before_stop": 15  # Augmenté de 10 → 15s pour laisser le temps de répondre
    },
    "is_leads": {
        "max_silence_seconds": 2,
        "wait_before_stop": 15  # Augmenté de 8 → 15s pour laisser le temps de répondre
    },
    "confirm": {
        "max_silence_seconds": 2,
        "wait_before_stop": 15  # Augmenté de 6 → 15s pour laisser le temps de répondre
    }
}

def is_answering_machine(transcription):
    """
    Détecte si la transcription correspond à un répondeur

    Args:
        transcription: Texte transcrit par Whisper

    Returns:
        bool: True si répondeur détecté, False sinon
    """
    if not transcription or transcription in ["silence", "error"]:
        return False

    # Normaliser le texte (minuscules, sans accents pour la détection)
    text_lower = transcription.lower()

    # Mots-clés typiques des répondeurs français - LISTE CONSOLIDÉE ET EXHAUSTIVE
    answering_machine_keywords = [
        # Messages standards
        "message", "messagerie", "boîte vocale", "boite vocale",
        "laisser un message", "déposer un message", "laissez un message",
        "déposez un message", "enregistrer un message", "enregistrez votre message",
        "répondeur", "repondeur",

        # État d'indisponibilité (SANS "occupé" car trop de faux positifs avec vraies personnes)
        "joignable", "absent", "indisponible",
        "actuellement indisponible", "pas disponible actuellement",
        "pour le moment", "en ce moment",
        "ne suis pas là", "ne peux pas répondre", "momentanément absent",
        "en déplacement", "en réunion",

        # Actions - Verbes d'instruction (NOUVEAUX - découverts lors des tests)
        "appuyez", "appuyer", "tapez", "taper", "composez", "composer",
        "touchez", "toucher", "pressez", "presser", "saisissez", "saisir",
        "faites", "faire", "enregistrez", "enregistrer",
        "modifiez", "modifier", "changez", "changer",

        # Touches et symboles téléphoniques (NOUVEAUX)
        "touche", "la touche", "dièse", "diez", "diese", "dieèse",
        "étoile", "etoile", "astérisque", "asterisque",
        "touche étoile", "touche dièse", "touche diez",
        "touche 1", "touche 2", "touche 3", "touche 4", "touche 5",
        "touche 10", "sur la touche", "la touche numéro",

        # Instructions de rappel
        "rappeler", "rappellerai", "rappellera", "rappellerez", "recontacter",
        "vous rappeler", "je vous rappelle", "nous vous rappelons",
        "rappelé dès que possible", "vous recontacte",

        # Signaux sonores
        "bip", "le bip", "après le bip", "au bip sonore", "signal",
        "tonalité", "signal sonore", "bip sonore", "au signal",

        # Phrases d'accueil typiques
        "vous êtes bien", "bienvenue sur", "merci d'avoir appelé",
        "vous avez appelé", "vous êtes sur", "ici le répondeur",
        "bonjour vous êtes", "vous avez joint", "vous êtes en communication",

        # Instructions finales (NOUVEAUX - basés sur tests réels)
        "terminé", "terminez", "pour terminer", "fin du message",
        "raccrochez", "pour raccrocher",

        # Prépositions + actions (patterns complets)
        "pour déposer", "pour laisser", "pour enregistrer", "pour modifier",
        "afin de laisser", "afin de déposer", "si vous souhaitez",
        "veuillez laisser", "veuillez déposer", "veuillez patienter",

        # Patterns de choix multiples (menus vocaux)
        "pour joindre", "pour parler", "pour être rappelé",
        "appuyez sur 1", "tapez 1", "faites le 1", "composez le",
        "option 1", "option 2", "choix 1", "choix 2"
    ]

    # Vérifier si au moins un mot-clé est présent
    for keyword in answering_machine_keywords:
        if keyword in text_lower:
            logger.info(f"🤖 Answering machine detected: keyword '{keyword}' found")
            return True

    return False

def update_contact_status_from_call(phone_number, amd_result=None, final_sentiment=None, is_lead_qualified=False, call_completed=True):
    """
    Met à jour le statut du contact selon le résultat de l'appel

    Statuts possibles :
    - New : Jamais appelé (défaut à l'import)
    - No_answer : Répondeur ou erreur technique → À RAPPELER
    - Leads : Lead qualifié (réponse positive à question de qualification) → NE PAS RAPPELER
    - Not_interested : Pas intéressé ou raccroche → NE PAS RAPPELER

    Args:
        phone_number: Numéro du contact
        amd_result: Résultat AMD (human/machine/unknown)
        final_sentiment: Sentiment final de l'appel
        is_lead_qualified: True si réponse positive à la question de qualification
        call_completed: False si erreur technique (pour retry)
    """
    db = SessionLocal()
    try:
        contact = db.query(Contact).filter(Contact.phone == phone_number).first()
        if contact:
            # Logique de statut selon les 4 cas possibles
            if not call_completed:
                # Erreur technique → No_answer pour permettre retry
                contact.status = "No_answer"
                logger.info(f"   ❌ Erreur technique → No_answer (retry possible)")

            elif amd_result == "machine":
                # Répondeur détecté → No_answer pour permettre retry
                contact.status = "No_answer"
                logger.info(f"   🤖 Répondeur détecté → No_answer (retry possible)")

            elif is_lead_qualified:
                # Lead qualifié ! (réponse positive à question de qualification)
                contact.status = "Leads"
                logger.info(f"   ✅ Lead qualifié → Leads")

            else:
                # Pas intéressé (sentiment négatif ou raccroche)
                contact.status = "Not_interested"
                logger.info(f"   ❌ Pas intéressé → Not_interested")

            # Mise à jour des compteurs
            contact.attempts += 1
            contact.last_attempt = datetime.now()

            db.commit()
            logger.info(f"📊 Contact status updated: {phone_number} → {contact.status}")
        else:
            logger.warning(f"⚠️ Contact {phone_number} not found in database")

    except Exception as e:
        logger.error(f"❌ Failed to update contact status: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

# ============================================================================
# SCENARIO TEST - DÉSACTIVÉ (conservé pour référence/debug)
# ============================================================================
# Le scénario TEST est maintenant remplacé par scenario_production
# Il est gardé ici uniquement pour référence ou debug futur

def scenario_test(robot, channel_id, phone_number, campaign_id=None):
    """
    ⚠️ DÉSACTIVÉ - Scénario TEST conservé pour référence uniquement

    Scénario TEST avec détection de sentiment améliorée:
    1. Intro
    2. Analyse du sentiment de la réponse:
       - POSITIVE → question_1
       - INTERROGATIF → reponse_question (répond aux questions "Qui?", "Pourquoi?", etc.)
       - NEGATIVE → retry
       - UNCLEAR → retry
    3. Conclusion

    Args:
        robot: Instance de RobotARI pour accès aux méthodes
        channel_id: ID du canal Asterisk
        phone_number: Numéro appelé
        campaign_id: ID de la campagne (optionnel)
    """
    try:
        logger.info(f"🎬 Starting scenario TEST for {phone_number}")
        logger.info(f"   Channel: {channel_id}")
        logger.info(f"   Campaign: {campaign_id or 'None'}")

        # 🤖 AUTO-TRACKING: Plus besoin de gérer interaction_sequence manuellement !
        # Le robot tracke automatiquement tous les fichiers audio joués

        # 1. MESSAGE D'INTRODUCTION (attend automatiquement la fin!)
        logger.info("📢 Playing intro message...")
        robot.play_audio_file(channel_id, "intro")  # 🤖 Auto-tracké !

        # 2. ENREGISTRER LA RÉPONSE AVEC DÉTECTION DE SILENCE (STREAMING OU BATCH)
        logger.info("🎤 Recording customer response with silence detection...")
        recording_name = f"test_{channel_id}_{int(time.time())}"

        # Enregistrement batch avec détection de silence
        transcription, sentiment = robot.record_with_silence_detection(
            channel_id,
            recording_name,
            max_silence_seconds=2,    # 2 secondes de silence = réponse terminée
            wait_before_stop=5        # Max 5s (temps total maximum)
        )

        if transcription and transcription not in ["silence", "error"]:
            logger.info(f"📝 Transcription: '{transcription[:100]}...'")
            logger.info(f"💭 Sentiment detected: {sentiment}")
            # 🤖 Auto-tracké par record_with_silence_detection !

            # 3. DÉTECTION INTELLIGENTE DE RÉPONDEUR
            if is_answering_machine(transcription):
                logger.warning(f"🤖 ANSWERING MACHINE DETECTED!")
                logger.warning(f"   Transcription: '{transcription}'")
                logger.warning(f"   ⏹️  Hanging up immediately to save time")

                # Sauvegarder qu'on a détecté un répondeur
                robot.save_interaction(
                    call_id=channel_id,
                    question_num=1,
                    question_type="intro_response",
                    transcription=transcription,
                    sentiment="answering_machine"
                )

                # Mettre à jour le statut de l'appel avec "answering_machine"
                update_final_call_status(channel_id, "answering_machine")

                # Mettre à jour le statut du contact → No_answer (pour retry)
                update_contact_status_from_call(
                    phone_number=phone_number,
                    amd_result="machine",
                    final_sentiment="answering_machine",
                    is_lead_qualified=False,
                    call_completed=True
                )

                # Raccrocher immédiatement
                logger.info(f"📞 Hanging up - Total call duration saved!")
                return  # Sortir du scénario, le finally() va raccrocher

            # 4. SAUVEGARDER L'INTERACTION (si pas répondeur)
            robot.save_interaction(
                call_id=channel_id,
                question_num=1,
                question_type="intro_response",
                transcription=transcription,
                sentiment=sentiment
            )

            # 5. JOUER MESSAGE APPROPRIÉ SELON SENTIMENT
            if sentiment == "positive":  # ATTENTION: sentiment_service retourne "positive" pas "positif" !
                logger.info("😊 Positive response detected → Playing question_1")
                robot.play_audio_file(channel_id, "question_1")  # 🤖 Auto-tracké !

                # Enregistrer réponse à question_1 avec détection de silence
                recording2_name = f"test_q1_{channel_id}_{int(time.time())}"
                trans2, sent2 = robot.record_with_silence_detection(
                    channel_id,
                    recording2_name,
                    max_silence_seconds=2,    # 2 secondes de silence = réponse terminée
                    wait_before_stop=5        # Max 5s pour répondre
                )
                # 🤖 Auto-tracké !

                if trans2 and trans2 not in ["silence", "error"]:
                    logger.info(f"📝 Q1 Response: '{trans2[:50]}...' → {sent2}")
                    robot.save_interaction(
                        call_id=channel_id,
                        question_num=2,
                        question_type="question_1",
                        transcription=trans2,
                        sentiment=sent2
                    )

            elif sentiment == "interrogatif":  # NOUVEAU: questions/méfiance → retry pour l'instant
                logger.info("❓ Interrogative response detected → Playing retry message (temporary)")
                robot.play_audio_file(channel_id, "retry")  # 🤖 Auto-tracké !

                # Enregistrer réponse après retry
                recording_question_name = f"test_interrogatif_{channel_id}_{int(time.time())}"
                trans_question, sent_question = robot.record_with_silence_detection(
                    channel_id,
                    recording_question_name,
                    max_silence_seconds=2,    # 2 secondes de silence = réponse terminée
                    wait_before_stop=5        # Max 5s pour répondre
                )
                # 🤖 Auto-tracké !

                if trans_question and trans_question not in ["silence", "error"]:
                    logger.info(f"📝 After Interrogatif Response: '{trans_question[:50]}...' → {sent_question}")
                    robot.save_interaction(
                        call_id=channel_id,
                        question_num=2,
                        question_type="after_interrogatif",
                        transcription=trans_question,
                        sentiment=sent_question
                    )

            elif sentiment == "negative":  # "negative" pas "negatif"
                logger.info("😞 Negative response detected → Playing retry message")
                robot.play_audio_file(channel_id, "retry")  # 🤖 Auto-tracké !

                # Enregistrer réponse après retry
                recording_retry_name = f"test_retry_{channel_id}_{int(time.time())}"
                trans_retry, sent_retry = robot.record_with_silence_detection(
                    channel_id,
                    recording_retry_name,
                    max_silence_seconds=2,    # 2 secondes de silence = réponse terminée
                    wait_before_stop=5        # Max 5s pour répondre
                )
                # 🤖 Auto-tracké !

                if trans_retry and trans_retry not in ["silence", "error"]:
                    logger.info(f"📝 Retry Response: '{trans_retry[:50]}...' → {sent_retry}")
                    robot.save_interaction(
                        call_id=channel_id,
                        question_num=2,
                        question_type="retry",
                        transcription=trans_retry,
                        sentiment=sent_retry
                    )

            else:  # neutre ou unclear
                logger.info("🤷 Neutral/unclear response → Playing retry message")
                robot.play_audio_file(channel_id, "retry")  # 🤖 Auto-tracké !

                # Enregistrer réponse après retry
                recording_retry_name = f"test_retry_{channel_id}_{int(time.time())}"
                trans_retry, sent_retry = robot.record_with_silence_detection(
                    channel_id,
                    recording_retry_name,
                    max_silence_seconds=2,    # 2 secondes de silence = réponse terminée
                    wait_before_stop=5        # Max 5s pour répondre
                )
                # 🤖 Auto-tracké !

                if trans_retry and trans_retry not in ["silence", "error"]:
                    logger.info(f"📝 Retry Response: '{trans_retry[:50]}...' → {sent_retry}")
                    robot.save_interaction(
                        call_id=channel_id,
                        question_num=2,
                        question_type="retry",
                        transcription=trans_retry,
                        sentiment=sent_retry
                    )

        else:
            logger.warning("⚠️ No transcription captured")
            # Pas de bip, on passe directement à la conclusion

        # 6. MESSAGE DE CONCLUSION
        logger.info("👋 Playing conclusion message...")
        robot.play_audio_file(channel_id, "conclusion")  # 🤖 Auto-tracké !

        # 7. METTRE À JOUR LE STATUT FINAL DE L'APPEL
        final_sentiment = sentiment if 'sentiment' in locals() else "unknown"
        update_final_call_status(channel_id, final_sentiment)

        # 7.5 METTRE À JOUR LE STATUT DU CONTACT
        # Pour le scénario TEST, on qualifie en lead si positive aux 2 questions
        # Dans ton scénario final, tu changeras cette logique pour ta question de qualification
        is_lead = False
        if 'sentiment' in locals() and 'sent2' in locals():
            # Lead si sentiment initial positif ET sentiment question_1 positif
            is_lead = (sentiment == "positive" and sent2 == "positive")

        # Récupérer l'AMD result depuis la base
        db_temp = SessionLocal()
        try:
            call_temp = db_temp.query(Call).filter(Call.call_id == channel_id).first()
            amd = call_temp.amd_result if call_temp else None
        finally:
            db_temp.close()

        # Mettre à jour le statut du contact
        update_contact_status_from_call(
            phone_number=phone_number,
            amd_result=amd,
            final_sentiment=final_sentiment,
            is_lead_qualified=is_lead,
            call_completed=True
        )

        # 8. GÉNÉRER AUDIO COMPLET + TRANSCRIPTION (si services disponibles)
        if ASSEMBLY_AVAILABLE:
            try:
                logger.info("🎬 Generating complete call audio and transcript...")

                # 🤖 AUTO-TRACKING: Récupérer la séquence complète automatiquement
                interaction_sequence = robot.get_call_sequence(channel_id)

                # Assembler tous les fichiers audio
                assembled_audio = audio_assembly_service.assemble_call_audio(
                    call_id=channel_id,
                    audio_sequence=interaction_sequence
                )

                # Récupérer les données de l'appel pour la transcription
                db = SessionLocal()
                try:
                    call = db.query(Call).filter(Call.call_id == channel_id).first()
                    if call and assembled_audio:
                        # Mettre à jour le chemin de l'audio assemblé
                        call.assembled_audio_path = assembled_audio
                        db.commit()

                        # Générer la transcription complète
                        call_data = {
                            "call_id": channel_id,
                            "phone_number": phone_number,
                            "campaign_id": campaign_id,
                            "amd_result": call.amd_result,
                            "duration": call.duration,
                            "started_at": call.started_at,
                            "ended_at": call.ended_at,
                            "final_sentiment": final_sentiment,
                            "interested": call.is_interested,
                            "assembled_audio": assembled_audio
                        }

                        # Formater les interactions depuis interaction_sequence
                        formatted_interactions = []
                        for item in interaction_sequence:
                            if item["type"] == "bot":
                                formatted_interactions.append({
                                    "speaker": "bot",
                                    "audio_file": item["file"],
                                    "timestamp": item["timestamp"].isoformat() if item.get("timestamp") else None
                                })
                            else:  # client
                                formatted_interactions.append({
                                    "speaker": "client",
                                    "audio_file": item["file"],
                                    "transcription": item.get("transcription", ""),
                                    "sentiment": item.get("sentiment", "unclear"),
                                    "confidence": 0.8,
                                    "timestamp": item["timestamp"].isoformat() if item.get("timestamp") else None
                                })

                        transcript = transcript_service.generate_transcript(call_data, formatted_interactions)
                        if transcript:
                            logger.info(f"✅ Complete transcript generated successfully")
                    else:
                        logger.warning("⚠️  Could not find call in database or audio assembly failed")
                finally:
                    db.close()

            except Exception as e:
                logger.error(f"❌ Error generating complete audio/transcript: {e}", exc_info=True)

        logger.info(f"✅ Scenario TEST completed for {phone_number}")

    except Exception as e:
        logger.error(f"❌ Error in scenario_test: {e}", exc_info=True)

        # En cas d'erreur, mettre le contact en No_answer pour retry
        try:
            update_contact_status_from_call(
                phone_number=phone_number,
                amd_result=None,
                final_sentiment="error",
                is_lead_qualified=False,
                call_completed=False  # Erreur technique → retry possible
            )
        except Exception as status_error:
            logger.error(f"❌ Failed to update contact status after error: {status_error}")
    finally:
        # Toujours raccrocher à la fin
        try:
            robot.hangup(channel_id)
        except Exception as e:
            logger.error(f"❌ Error during hangup: {e}")


def update_final_call_status(call_id, sentiment):
    """
    Met à jour le statut final de l'appel dans la base

    Args:
        call_id: ID de l'appel
        sentiment: Sentiment final détecté
    """
    db = SessionLocal()
    try:
        call = db.query(Call).filter(Call.call_id == call_id).first()
        if call:
            call.final_sentiment = sentiment
            call.is_interested = (sentiment == "positive")  # "positive" pas "positif"
            call.ended_at = datetime.now()

            if call.started_at:
                call.duration = int((call.ended_at - call.started_at).total_seconds())

            db.commit()
            logger.info(f"📊 Call status updated: {call_id}")
            logger.info(f"   Final sentiment: {sentiment}")
            logger.info(f"   Interested: {call.is_interested}")
            logger.info(f"   Duration: {call.duration}s")
        else:
            logger.warning(f"⚠️ Call {call_id} not found in database")

    except Exception as e:
        logger.error(f"❌ Failed to update call status: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


# ============================================================================
# SCENARIO PRODUCTION - SCÉNARIO ACTIF UNIQUE
# ============================================================================

def scenario_production(robot, channel_id, phone_number, campaign_id=None):
    """
    🎯 SCÉNARIO UNIVERSEL DE QUALIFICATION PROGRESSIVE

    Structure réutilisable pour toutes les campagnes - Il suffit de changer les 9 fichiers audio !

    📋 FLOW:
    1. Hello (intro + 3 questions) → Positive/Neutre: Q1 | Négatif/Interrogatif: Retry | Silence/Répondeur: Raccroche
    2. Retry (1x max) → Positive/Neutre: Q1 | Négatif: Bye_Failed (Not_interested)
    3. Q1 → Q2 → Q3 (toujours continuer, peu importe réponse Oui/Non)
    4. Is_Leads (question finale de qualification) → Positive/Neutre: LEAD | Négatif: NOT_INTERESTED
    5. Confirm (si Lead) → Demande créneau
    6. Bye_Success (Lead) ou Bye_Failed (Not_interested)

    🎵 FICHIERS AUDIO REQUIS (9):
    - hello.wav          : Introduction + "ça vous va ?"
    - retry.wav          : Relance si négatif/interrogatif
    - q1.wav             : Question 1 (qualifiante mais n'influence pas le statut)
    - q2.wav             : Question 2 (qualifiante mais n'influence pas le statut)
    - q3.wav             : Question 3 (qualifiante mais n'influence pas le statut)
    - is_leads.wav       : Question FINALE qui détermine Lead/Not_interested
    - confirm.wav        : Demande créneau (matin/après-midi/soir)
    - bye_success.wav    : Fin positive (Lead confirmé)
    - bye_failed.wav     : Fin négative (Not_interested)

    📊 STATUTS FINAUX:
    - Leads : Réponse Positive/Neutre à is_leads
    - Not_interested : Réponse Négative à is_leads OU raccrochage prématuré
    - No_answer : Répondeur détecté OU silence total

    Args:
        robot: Instance de RobotARI
        channel_id: ID du canal Asterisk
        phone_number: Numéro appelé
        campaign_id: ID de la campagne (optionnel)
    """
    try:
        logger.info(f"🎬 Starting PRODUCTION scenario for {phone_number}")
        logger.info(f"   Channel: {channel_id}")
        logger.info(f"   Campaign: {campaign_id or 'None'}")

        # Variables de tracking
        retry_used = False
        is_lead_qualified = False
        call_completed = True
        final_sentiment = "unknown"
        in_conversation = False  # Flag pour détecter raccrochage prématuré vs erreur technique

        # ========================================
        # 1. HELLO - INTRODUCTION
        # ========================================
        logger.info("=" * 60)
        logger.info("📢 STEP 1: HELLO - Introduction")
        logger.info("=" * 60)

        # Jouer hello et vérifier que ça marche (sinon = raccrochage)
        playback_id = robot.play_audio_file(channel_id, "hello")
        if playback_id is None:
            raise Exception("Channel disconnected during hello playback")

        # Enregistrer la réponse
        recording_hello = f"prod_hello_{channel_id}_{int(time.time())}"
        trans_hello, sent_hello = robot.record_with_silence_detection(
            channel_id,
            recording_hello,
            max_silence_seconds=LISTEN_TIMEOUTS["hello"]["max_silence_seconds"],
            wait_before_stop=LISTEN_TIMEOUTS["hello"]["wait_before_stop"]
        )

        logger.info(f"📝 Hello Response: '{trans_hello[:100] if trans_hello else 'No response'}...'")
        logger.info(f"💭 Sentiment: {sent_hello}")

        # ========================================
        # 1.1 VÉRIFIER RÉPONDEUR
        # ========================================
        if trans_hello and is_answering_machine(trans_hello):
            logger.warning("🤖 ANSWERING MACHINE DETECTED at Hello!")

            robot.save_interaction(
                call_id=channel_id,
                question_num=1,
                question_type="hello",
                transcription=trans_hello,
                sentiment="answering_machine"
            )

            update_final_call_status(channel_id, "answering_machine")
            update_contact_status_from_call(
                phone_number=phone_number,
                amd_result="machine",
                final_sentiment="answering_machine",
                is_lead_qualified=False,
                call_completed=True
            )

            logger.info("📞 Hanging up - Answering machine detected")
            return  # Raccrocher

        # ========================================
        # 1.2 VÉRIFIER SILENCE TOTAL
        # ========================================
        if not trans_hello or trans_hello in ["silence", "error"]:
            logger.warning("🔇 SILENCE or ERROR at Hello - No response detected")

            robot.save_interaction(
                call_id=channel_id,
                question_num=1,
                question_type="hello",
                transcription="silence",
                sentiment="silence"
            )

            update_final_call_status(channel_id, "silence")

            # ✅ CORRECTION: Silence = No_answer (rappelable, pas une vraie réponse négative)
            # Utiliser call_completed=False pour forcer No_answer (échec de communication = retry)
            update_contact_status_from_call(
                phone_number=phone_number,
                amd_result=None,
                final_sentiment="silence",
                is_lead_qualified=False,
                call_completed=False  # Échec de communication → No_answer (retry possible)
            )

            logger.info("📞 Hanging up - No response (will be retried)")
            return  # Raccrocher

        # Sauvegarder interaction Hello
        robot.save_interaction(
            call_id=channel_id,
            question_num=1,
            question_type="hello",
            transcription=trans_hello,
            sentiment=sent_hello
        )

        # ✅ MARQUER QU'ON EST MAINTENANT EN CONVERSATION
        # Si exception après ce point = raccrochage prématuré, pas erreur technique
        in_conversation = True

        # ========================================
        # 2. GESTION RETRY (si négatif/interrogatif)
        # ========================================
        if sent_hello in ["negative", "interrogatif"]:
            logger.info("=" * 60)
            logger.info("🔄 STEP 2: RETRY - Relance after negative/interrogatif")
            logger.info("=" * 60)

            retry_used = True
            playback_id = robot.play_audio_file(channel_id, "retry")
            if playback_id is None:
                raise Exception("Channel disconnected during retry playback")

            # Enregistrer réponse après retry
            recording_retry = f"prod_retry_{channel_id}_{int(time.time())}"
            trans_retry, sent_retry = robot.record_with_silence_detection(
                channel_id,
                recording_retry,
                max_silence_seconds=LISTEN_TIMEOUTS["retry"]["max_silence_seconds"],
                wait_before_stop=LISTEN_TIMEOUTS["retry"]["wait_before_stop"]
            )

            logger.info(f"📝 Retry Response: '{trans_retry[:100] if trans_retry else 'No response'}...'")
            logger.info(f"💭 Sentiment: {sent_retry}")

            robot.save_interaction(
                call_id=channel_id,
                question_num=2,
                question_type="retry",
                transcription=trans_retry or "silence",
                sentiment=sent_retry
            )

            # Si toujours négatif après retry → Bye_Failed
            if sent_retry == "negative":
                logger.info("❌ Still negative after retry → BYE_FAILED")
                playback_id = robot.play_audio_file(channel_id, "bye_failed")
                if playback_id is None:
                    raise Exception("Channel disconnected during bye_failed playback")

                final_sentiment = "negative"
                is_lead_qualified = False

                update_final_call_status(channel_id, final_sentiment)
                update_contact_status_from_call(
                    phone_number=phone_number,
                    amd_result=None,
                    final_sentiment=final_sentiment,
                    is_lead_qualified=is_lead_qualified,
                    call_completed=True
                )

                logger.info("✅ Scenario completed - Not interested")
                return  # Fin du scénario

        # ========================================
        # 3. QUESTIONS QUALIFIANTES (Q1, Q2, Q3)
        # ========================================
        # Ces questions N'INFLUENCENT PAS le statut final !
        # On continue toujours à la question suivante, peu importe Oui/Non

        for q_num in range(1, 4):  # Q1, Q2, Q3
            logger.info("=" * 60)
            logger.info(f"❓ STEP {2 + retry_used + q_num}: QUESTION {q_num}")
            logger.info("=" * 60)

            audio_file = f"q{q_num}"
            playback_id = robot.play_audio_file(channel_id, audio_file)
            if playback_id is None:
                raise Exception(f"Channel disconnected during {audio_file} playback")

            # Enregistrer réponse
            recording_q = f"prod_q{q_num}_{channel_id}_{int(time.time())}"
            trans_q, sent_q = robot.record_with_silence_detection(
                channel_id,
                recording_q,
                max_silence_seconds=LISTEN_TIMEOUTS[f"q{q_num}"]["max_silence_seconds"],
                wait_before_stop=LISTEN_TIMEOUTS[f"q{q_num}"]["wait_before_stop"]
            )

            logger.info(f"📝 Q{q_num} Response: '{trans_q[:100] if trans_q else 'No response'}...'")
            logger.info(f"💭 Sentiment: {sent_q}")

            robot.save_interaction(
                call_id=channel_id,
                question_num=2 + retry_used + q_num,
                question_type=f"q{q_num}",
                transcription=trans_q or "silence",
                sentiment=sent_q
            )

            # ⚠️ PAS DE LOGIQUE DE SORTIE ICI !
            # On continue toujours vers la question suivante

        # ========================================
        # 4. IS_LEADS - QUESTION FINALE DE QUALIFICATION
        # ========================================
        # 🎯 C'EST ICI QUE LE STATUT EST DÉTERMINÉ !

        logger.info("=" * 60)
        logger.info("🎯 STEP FINAL: IS_LEADS - Question de qualification")
        logger.info("=" * 60)

        playback_id = robot.play_audio_file(channel_id, "is_leads")
        if playback_id is None:
            raise Exception("Channel disconnected during is_leads playback")

        # Enregistrer réponse IS_LEADS
        recording_is_leads = f"prod_is_leads_{channel_id}_{int(time.time())}"
        trans_is_leads, sent_is_leads = robot.record_with_silence_detection(
            channel_id,
            recording_is_leads,
            max_silence_seconds=LISTEN_TIMEOUTS["is_leads"]["max_silence_seconds"],
            wait_before_stop=LISTEN_TIMEOUTS["is_leads"]["wait_before_stop"]
        )

        logger.info(f"📝 Is_Leads Response: '{trans_is_leads[:100] if trans_is_leads else 'No response'}...'")
        logger.info(f"💭 Sentiment: {sent_is_leads}")

        robot.save_interaction(
            call_id=channel_id,
            question_num=6 + retry_used,
            question_type="is_leads",
            transcription=trans_is_leads or "silence",
            sentiment=sent_is_leads
        )

        # ========================================
        # 5. DÉCISION FINALE : LEAD OU NOT_INTERESTED
        # ========================================

        if sent_is_leads in ["positive", "neutre"]:
            # ✅ LEAD QUALIFIÉ !
            logger.info("✅ LEAD QUALIFIED! (Positive/Neutre response to is_leads)")

            is_lead_qualified = True
            final_sentiment = sent_is_leads

            # ========================================
            # 6. CONFIRM - DEMANDE CRÉNEAU
            # ========================================
            logger.info("=" * 60)
            logger.info("📅 CONFIRM: Asking for time slot preference")
            logger.info("=" * 60)

            playback_id = robot.play_audio_file(channel_id, "confirm")
            if playback_id is None:
                raise Exception("Channel disconnected during confirm playback")

            # Enregistrer réponse Confirm
            recording_confirm = f"prod_confirm_{channel_id}_{int(time.time())}"
            trans_confirm, sent_confirm = robot.record_with_silence_detection(
                channel_id,
                recording_confirm,
                max_silence_seconds=LISTEN_TIMEOUTS["confirm"]["max_silence_seconds"],
                wait_before_stop=LISTEN_TIMEOUTS["confirm"]["wait_before_stop"]
            )

            logger.info(f"📝 Confirm Response: '{trans_confirm[:100] if trans_confirm else 'No response'}...'")
            logger.info(f"💭 Sentiment: {sent_confirm}")

            robot.save_interaction(
                call_id=channel_id,
                question_num=7 + retry_used,
                question_type="confirm",
                transcription=trans_confirm or "silence",
                sentiment=sent_confirm
            )

            # ========================================
            # 7. BYE_SUCCESS
            # ========================================
            logger.info("=" * 60)
            logger.info("🎉 BYE_SUCCESS: Ending call with qualified lead")
            logger.info("=" * 60)

            playback_id = robot.play_audio_file(channel_id, "bye_success")
            if playback_id is None:
                raise Exception("Channel disconnected during bye_success playback")

        else:
            # ❌ NOT INTERESTED
            logger.info("❌ NOT INTERESTED (Negative response to is_leads)")

            is_lead_qualified = False
            final_sentiment = "negative"

            # ========================================
            # 8. BYE_FAILED
            # ========================================
            logger.info("=" * 60)
            logger.info("👋 BYE_FAILED: Ending call - not interested")
            logger.info("=" * 60)

            playback_id = robot.play_audio_file(channel_id, "bye_failed")
            if playback_id is None:
                raise Exception("Channel disconnected during bye_failed playback")

        # ========================================
        # 9. MISE À JOUR STATUTS FINAUX
        # ========================================
        logger.info("=" * 60)
        logger.info("📊 Updating final statuses")
        logger.info("=" * 60)

        update_final_call_status(channel_id, final_sentiment)

        # Récupérer AMD result depuis la base
        db_temp = SessionLocal()
        try:
            call_temp = db_temp.query(Call).filter(Call.call_id == channel_id).first()
            amd = call_temp.amd_result if call_temp else None
        finally:
            db_temp.close()

        update_contact_status_from_call(
            phone_number=phone_number,
            amd_result=amd,
            final_sentiment=final_sentiment,
            is_lead_qualified=is_lead_qualified,
            call_completed=call_completed
        )

        # ========================================
        # 10. GÉNÉRATION AUDIO COMPLET + TRANSCRIPTION
        # ========================================
        if ASSEMBLY_AVAILABLE:
            try:
                logger.info("=" * 60)
                logger.info("🎬 Generating complete call audio and transcript")
                logger.info("=" * 60)

                # Récupérer la séquence complète automatiquement
                interaction_sequence = robot.get_call_sequence(channel_id)

                # Assembler tous les fichiers audio
                assembled_audio = audio_assembly_service.assemble_call_audio(
                    call_id=channel_id,
                    audio_sequence=interaction_sequence
                )

                # Générer transcription complète
                db = SessionLocal()
                try:
                    call = db.query(Call).filter(Call.call_id == channel_id).first()
                    if call and assembled_audio:
                        # Mettre à jour le chemin de l'audio assemblé
                        call.assembled_audio_path = assembled_audio
                        db.commit()

                        # Préparer les données pour la transcription
                        call_data = {
                            "call_id": channel_id,
                            "phone_number": phone_number,
                            "campaign_id": campaign_id,
                            "amd_result": call.amd_result,
                            "duration": call.duration,
                            "started_at": call.started_at,
                            "ended_at": call.ended_at,
                            "final_sentiment": final_sentiment,
                            "interested": call.is_interested,
                            "assembled_audio": assembled_audio
                        }

                        # Formater les interactions
                        formatted_interactions = []
                        for item in interaction_sequence:
                            if item["type"] == "bot":
                                formatted_interactions.append({
                                    "speaker": "bot",
                                    "audio_file": item["file"],
                                    "timestamp": item["timestamp"].isoformat() if item.get("timestamp") else None
                                })
                            else:  # client
                                formatted_interactions.append({
                                    "speaker": "client",
                                    "audio_file": item["file"],
                                    "transcription": item.get("transcription", ""),
                                    "sentiment": item.get("sentiment", "unclear"),
                                    "confidence": 0.8,
                                    "timestamp": item["timestamp"].isoformat() if item.get("timestamp") else None
                                })

                        transcript = transcript_service.generate_transcript(call_data, formatted_interactions)
                        if transcript:
                            logger.info(f"✅ Complete transcript generated successfully")
                    else:
                        logger.warning("⚠️  Could not find call in database or audio assembly failed")
                finally:
                    db.close()

            except Exception as e:
                logger.error(f"❌ Error generating complete audio/transcript: {e}", exc_info=True)

        logger.info("=" * 60)
        logger.info(f"✅ PRODUCTION Scenario completed for {phone_number}")
        logger.info(f"   Lead qualified: {is_lead_qualified}")
        logger.info(f"   Final sentiment: {final_sentiment}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Error in scenario_production: {e}", exc_info=True)

        # ✅ CORRECTION: Différencier raccrochage prématuré vs erreur technique
        try:
            if 'in_conversation' in locals() and in_conversation:
                # Le client était en conversation et a raccroché
                # → C'est un refus = Not_interested
                logger.warning("📞 Client hung up during conversation → Not_interested")
                update_contact_status_from_call(
                    phone_number=phone_number,
                    amd_result=None,
                    final_sentiment="hangup",
                    is_lead_qualified=False,
                    call_completed=True  # Appel terminé (raccrochage = refus)
                )
            else:
                # Erreur avant même de commencer la conversation
                # → Erreur technique = No_answer (retry possible)
                logger.warning("⚠️ Technical error before conversation → No_answer (retry)")
                update_contact_status_from_call(
                    phone_number=phone_number,
                    amd_result=None,
                    final_sentiment="error",
                    is_lead_qualified=False,
                    call_completed=False  # Erreur technique → retry possible
                )
        except Exception as status_error:
            logger.error(f"❌ Failed to update contact status after error: {status_error}")

    finally:
        # Toujours raccrocher à la fin
        try:
            robot.hangup(channel_id)
        except Exception as e:
            logger.error(f"❌ Error during hangup: {e}")