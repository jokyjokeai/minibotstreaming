#!/usr/bin/env python3
"""
Batch Caller - Service de lancement d'appels avec throttling intelligent
Lance les appels depuis la queue call_queue avec respect des limites provider
"""

import sys
import os
import time
import signal
from datetime import datetime, timedelta
from sqlalchemy import and_, or_

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import CallQueue, Call, Campaign, Contact
from services.call_launcher import launch_call
from logger_config import get_logger
import config

logger = get_logger(__name__)

# ============================================
# CONFIGURATION
# ============================================

# Nombre maximum d'appels simultanés (IMPORTANT: ton provider limite à 10)
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_CALLS", "8"))

# Délai entre chaque lancement d'appel (en secondes)
DELAY_BETWEEN_CALLS = int(os.getenv("DELAY_BETWEEN_CALLS", "2"))

# Intervalle de vérification de la queue (en secondes)
QUEUE_CHECK_INTERVAL = int(os.getenv("QUEUE_CHECK_INTERVAL", "5"))

# Délai avant retry en cas d'échec (en secondes)
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "300"))  # 5 minutes

# Timeout pour considérer un appel comme bloqué (en secondes)
CALL_TIMEOUT = int(os.getenv("CALL_TIMEOUT", "120"))  # 2 minutes

# ============================================
# ÉTAT GLOBAL
# ============================================

running = True
active_calls = {}  # {call_id: {"phone": xxx, "started_at": xxx}}

def signal_handler(signum, frame):
    """Gestion de l'arrêt propre"""
    global running
    logger.info("🛑 Signal d'arrêt reçu, arrêt gracieux...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ============================================
# FONCTIONS PRINCIPALES
# ============================================

def count_active_calls(db):
    """
    Compte le nombre d'appels réellement actifs en cours

    Returns:
        int: Nombre d'appels actifs
    """
    # Compter les appels qui sont en cours (status = calling) et pas encore terminés
    active_in_queue = db.query(CallQueue).filter(
        and_(
            CallQueue.status == "calling",
            or_(
                CallQueue.last_attempt_at == None,
                CallQueue.last_attempt_at > datetime.now() - timedelta(seconds=CALL_TIMEOUT)
            )
        )
    ).count()

    return active_in_queue

def cleanup_stuck_calls(db):
    """
    Nettoie les appels bloqués en status 'calling' depuis trop longtemps
    """
    timeout_threshold = datetime.now() - timedelta(seconds=CALL_TIMEOUT)

    stuck_calls = db.query(CallQueue).filter(
        and_(
            CallQueue.status == "calling",
            CallQueue.last_attempt_at < timeout_threshold
        )
    ).all()

    for call in stuck_calls:
        logger.warning(f"⚠️  Appel bloqué détecté: {call.phone_number} (ID: {call.call_id})")

        # Vérifier si l'appel existe dans la table calls
        if call.call_id:
            call_record = db.query(Call).filter(Call.call_id == call.call_id).first()

            if call_record and call_record.ended_at:
                # L'appel est terminé dans calls, marquer comme completed
                call.status = "completed"
                logger.info(f"✅ Appel {call.call_id} marqué comme completed")
            else:
                # L'appel n'est pas terminé, considérer comme échec et retry
                call.status = "pending" if call.attempts < call.max_attempts else "failed"
                call.error_message = "Timeout - appel bloqué"
                logger.warning(f"⚠️  Appel {call.call_id} remis en pending pour retry")
        else:
            # Pas de call_id, remettre en pending
            call.status = "pending"

    if stuck_calls:
        db.commit()
        logger.info(f"🧹 {len(stuck_calls)} appel(s) bloqué(s) nettoyé(s)")

def update_completed_calls(db):
    """
    Met à jour les appels terminés dans call_queue
    """
    # Récupérer les appels en "calling" qui ont un call_id
    calling_queue = db.query(CallQueue).filter(
        and_(
            CallQueue.status == "calling",
            CallQueue.call_id != None
        )
    ).all()

    completed_count = 0

    for queue_item in calling_queue:
        # Vérifier si l'appel est terminé dans la table calls
        call_record = db.query(Call).filter(Call.call_id == queue_item.call_id).first()

        if call_record and call_record.ended_at:
            # Appel terminé !
            queue_item.status = "completed"
            completed_count += 1

            logger.info(f"✅ Appel terminé: {queue_item.phone_number} (durée: {call_record.duration}s, sentiment: {call_record.final_sentiment})")

            # Mettre à jour le contact
            contact = db.query(Contact).filter(Contact.phone == queue_item.phone_number).first()
            if contact:
                # CORRECTION: Si contact.status est toujours "Calling", le scénario n'a pas été exécuté
                # (répondeur détecté par AMD avant le scénario, ou appel échoué immédiatement)
                # → Mettre à "No_answer" pour permettre retry
                if contact.status == "Calling":
                    if call_record.amd_result == "machine" or call_record.duration == 0:
                        contact.status = "No_answer"
                        logger.info(f"   🤖 Répondeur/appel court détecté → No_answer (retry possible)")
                    else:
                        contact.status = "No_answer"  # Erreur technique générique
                        logger.info(f"   ⚠️  Appel terminé sans scénario → No_answer (retry)")

                # NE PAS écraser contact.status s'il a déjà été mis à jour par le scénario!
                # (Leads, Not_interested, No_answer, etc.) via update_contact_status_from_call()
                contact.attempts = queue_item.attempts
                contact.last_attempt = queue_item.last_attempt_at
                contact.audio_recording_path = call_record.recording_path
                contact.call_duration = call_record.duration
                contact.final_status = call_record.status
                contact.transcript = f"Sentiment: {call_record.final_sentiment}, Interested: {call_record.is_interested}"

            # Mettre à jour les stats de campagne
            campaign = db.query(Campaign).filter(Campaign.campaign_id == queue_item.campaign_id).first()
            if campaign:
                if call_record.status == "completed":
                    campaign.successful_calls += 1

                if call_record.final_sentiment == "positive" or call_record.is_interested:
                    campaign.positive_responses += 1
                elif call_record.final_sentiment == "negative":
                    campaign.negative_responses += 1

    if completed_count > 0:
        db.commit()
        logger.info(f"📊 {completed_count} appel(s) marqué(s) comme complété(s)")

    return completed_count

def launch_next_calls(db, slots_available):
    """
    Lance les prochains appels en attente

    Args:
        db: Session DB
        slots_available: Nombre de slots disponibles

    Returns:
        int: Nombre d'appels lancés
    """
    if slots_available <= 0:
        return 0

    # Récupérer les prochains appels en attente (triés par priorité et date)
    pending_calls = db.query(CallQueue).filter(
        CallQueue.status == "pending"
    ).order_by(
        CallQueue.priority.desc(),  # Priorité haute d'abord
        CallQueue.created_at.asc()  # Plus ancien d'abord
    ).limit(slots_available).all()

    if not pending_calls:
        return 0

    launched_count = 0

    for queue_item in pending_calls:
        try:
            # Vérifier que la campagne est toujours active
            campaign = db.query(Campaign).filter(Campaign.campaign_id == queue_item.campaign_id).first()

            if not campaign:
                logger.error(f"❌ Campagne {queue_item.campaign_id} introuvable, skip")
                queue_item.status = "failed"
                queue_item.error_message = "Campaign not found"
                continue

            if campaign.status == "paused":
                logger.info(f"⏸️  Campagne {campaign.name} en pause, skip")
                continue

            if campaign.status == "completed":
                logger.info(f"✅ Campagne {campaign.name} terminée, skip")
                queue_item.status = "failed"
                queue_item.error_message = "Campaign completed"
                continue

            # Lancer l'appel
            logger.info(f"🚀 Lancement appel {launched_count + 1}/{slots_available}: {queue_item.phone_number} (campagne: {campaign.name})")

            call_id = launch_call(
                phone_number=queue_item.phone_number,
                scenario=queue_item.scenario,
                campaign_id=queue_item.campaign_id
            )

            # Mettre à jour la queue
            queue_item.status = "calling"
            queue_item.call_id = call_id
            queue_item.attempts += 1
            queue_item.last_attempt_at = datetime.now()
            queue_item.error_message = None

            # Mettre à jour le contact
            contact = db.query(Contact).filter(Contact.phone == queue_item.phone_number).first()
            if contact:
                contact.status = "Calling"
                contact.attempts = queue_item.attempts
                contact.last_attempt = datetime.now()

            launched_count += 1

            # Commit après chaque lancement pour ne pas perdre l'état
            db.commit()

            logger.info(f"✅ Appel lancé: {call_id} → {queue_item.phone_number}")

            # Délai avant le prochain lancement
            if launched_count < slots_available:
                time.sleep(DELAY_BETWEEN_CALLS)

        except Exception as e:
            logger.error(f"❌ Erreur lancement {queue_item.phone_number}: {e}")

            # Incrémenter attempts et vérifier si on doit retry
            queue_item.attempts += 1
            queue_item.last_attempt_at = datetime.now()
            queue_item.error_message = str(e)

            if queue_item.attempts >= queue_item.max_attempts:
                queue_item.status = "failed"
                logger.error(f"❌ Appel {queue_item.phone_number} échoué après {queue_item.attempts} tentatives")
            else:
                queue_item.status = "pending"  # Retry plus tard
                logger.warning(f"⚠️  Appel {queue_item.phone_number} retry {queue_item.attempts}/{queue_item.max_attempts}")

            db.commit()

    return launched_count

def process_queue():
    """
    Boucle principale de traitement de la queue
    """
    logger.info("=" * 80)
    logger.info("🚀 BATCH CALLER - Service de lancement d'appels")
    logger.info("=" * 80)
    logger.info(f"⚙️  Configuration:")
    logger.info(f"   - Max appels simultanés: {MAX_CONCURRENT_CALLS}")
    logger.info(f"   - Délai entre appels: {DELAY_BETWEEN_CALLS}s")
    logger.info(f"   - Intervalle vérification: {QUEUE_CHECK_INTERVAL}s")
    logger.info(f"   - Timeout appel: {CALL_TIMEOUT}s")
    logger.info(f"   - Délai retry: {RETRY_DELAY}s")
    logger.info("=" * 80)

    iteration = 0

    while running:
        iteration += 1
        db = SessionLocal()

        try:
            # 1. Nettoyer les appels bloqués
            cleanup_stuck_calls(db)

            # 2. Mettre à jour les appels terminés
            update_completed_calls(db)

            # 3. Compter les appels actifs
            active_count = count_active_calls(db)

            # 4. Calculer les slots disponibles
            slots_available = MAX_CONCURRENT_CALLS - active_count

            # 5. Compter les appels en attente
            pending_count = db.query(CallQueue).filter(CallQueue.status == "pending").count()

            # Log status toutes les 5 itérations
            if iteration % 5 == 1:
                logger.info(f"📊 Status: {active_count}/{MAX_CONCURRENT_CALLS} actifs | {pending_count} en attente | {slots_available} slots libres")

            # 6. Lancer de nouveaux appels si des slots sont disponibles
            if slots_available > 0 and pending_count > 0:
                launched = launch_next_calls(db, slots_available)

                if launched > 0:
                    logger.info(f"🎯 {launched} nouvel(aux) appel(s) lancé(s)")
            elif pending_count == 0 and active_count == 0:
                # Plus rien à faire
                if iteration % 20 == 1:
                    logger.info("😴 Aucun appel en attente, attente de nouveaux contacts...")

        except Exception as e:
            logger.error(f"❌ Erreur traitement queue: {e}")
            import traceback
            logger.error(traceback.format_exc())

        finally:
            db.close()

        # Attendre avant le prochain cycle
        time.sleep(QUEUE_CHECK_INTERVAL)

    logger.info("🛑 Batch Caller arrêté proprement")

# ============================================
# MAIN
# ============================================

def main():
    """Point d'entrée principal"""
    try:
        logger.info("🎬 Démarrage Batch Caller...")

        # Vérifier connexion DB
        db = SessionLocal()
        try:
            # Test simple
            pending = db.query(CallQueue).filter(CallQueue.status == "pending").count()
            logger.info(f"✅ Connexion DB OK - {pending} appel(s) en attente")
        finally:
            db.close()

        # Lancer le traitement
        process_queue()

    except KeyboardInterrupt:
        logger.info("🛑 Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
