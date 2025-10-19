#!/usr/bin/env python3
"""
Launch Campaign from Contacts
Lance une campagne d'appels à partir des contacts en base de données
Récupère les contacts avec status='New' ou 'No_answer'
"""

import sys
import os
import argparse
from datetime import datetime
import uuid
import time

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Contact, Campaign, CallQueue, Call
from logger_config import get_logger

logger = get_logger(__name__)


def get_eligible_contacts(db, limit=None):
    """
    Récupère les contacts éligibles pour une campagne

    Args:
        db: Session DB
        limit: Nombre max de contacts (None = tous)

    Returns:
        List[Contact]: Liste des contacts
    """
    query = db.query(Contact).filter(
        Contact.status.in_(['New', 'No_answer'])
    ).order_by(Contact.created_at.asc())

    if limit:
        query = query.limit(limit)

    return query.all()


def create_campaign_from_contacts(
    name: str,
    scenario: str = "production",
    description: str = None,
    limit: int = None,
    priority: int = 1
):
    """
    Crée une campagne à partir des contacts en DB

    Args:
        name: Nom de la campagne
        scenario: Scénario à utiliser (test, basique, avancee, rdv)
        description: Description optionnelle
        limit: Limite de contacts (None = tous)
        priority: Priorité des appels (1=normal, 2=high, 3=urgent)

    Returns:
        dict: Résultat de la création
    """
    db = SessionLocal()

    try:
        logger.info("=" * 80)
        logger.info(f"🚀 LANCEMENT CAMPAGNE: {name}")
        logger.info("=" * 80)

        # 1. Récupérer les contacts éligibles
        logger.info("🔍 Recherche contacts éligibles (status='New' ou 'No_answer')...")
        contacts = get_eligible_contacts(db, limit)

        if not contacts:
            logger.warning("⚠️  Aucun contact éligible trouvé!")
            logger.info("💡 Vérifiez que vous avez des contacts avec status='New' ou 'No_answer'")
            return {
                "success": False,
                "error": "No eligible contacts found"
            }

        logger.info(f"✅ {len(contacts)} contact(s) trouvé(s)")

        # Afficher répartition des statuts
        status_counts = {}
        for contact in contacts:
            status_counts[contact.status] = status_counts.get(contact.status, 0) + 1

        for status, count in status_counts.items():
            logger.info(f"   • {status}: {count} contact(s)")

        # 2. Valider le scénario (production uniquement)
        valid_scenarios = ["production"]
        if scenario not in valid_scenarios:
            logger.error(f"❌ Scénario invalide: {scenario}")
            logger.info(f"💡 Scénario valide: production")
            return {
                "success": False,
                "error": f"Invalid scenario. Must be: production"
            }

        # 3. Créer la campagne
        campaign_id = f"camp_{uuid.uuid4().hex[:8]}"

        campaign = Campaign(
            campaign_id=campaign_id,
            name=name,
            description=description or f"Campagne automatique depuis contacts (status=New/No_answer)",
            total_calls=len(contacts),
            status="active",
            started_at=datetime.now()
        )

        db.add(campaign)
        db.commit()

        logger.info(f"✅ Campagne créée: {campaign_id}")
        logger.info(f"   • Nom: {name}")
        logger.info(f"   • Scénario: {scenario}")
        logger.info(f"   • Total appels: {len(contacts)}")

        # 4. Ajouter les contacts dans call_queue
        logger.info("📋 Ajout des contacts dans la file d'attente...")

        queued_count = 0
        failed_count = 0

        for contact in contacts:
            try:
                # Créer entrée dans call_queue
                queue_item = CallQueue(
                    campaign_id=campaign_id,
                    phone_number=contact.phone,
                    scenario=scenario,
                    status="pending",
                    priority=priority,
                    max_attempts=1
                )

                db.add(queue_item)
                queued_count += 1

                # Mettre à jour le statut du contact
                contact.status = "Queued"  # Nouveau statut pour indiquer qu'il est en file d'attente

            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Erreur ajout contact {contact.phone}: {e}")

        # Commit tous les ajouts
        db.commit()

        logger.info("=" * 80)
        logger.info("✅ CAMPAGNE LANCÉE AVEC SUCCÈS")
        logger.info("=" * 80)
        logger.info(f"📊 Résumé:")
        logger.info(f"   • Campagne ID: {campaign_id}")
        logger.info(f"   • Contacts en queue: {queued_count}")
        logger.info(f"   • Échecs: {failed_count}")
        logger.info(f"   • Priorité: {priority}")
        logger.info("=" * 80)
        logger.info("🤖 Le batch_caller va traiter ces appels automatiquement")
        logger.info(f"   • Max {os.getenv('MAX_CONCURRENT_CALLS', '8')} appels simultanés")
        logger.info(f"   • Vérification toutes les {os.getenv('QUEUE_CHECK_INTERVAL', '5')}s")
        logger.info("=" * 80)

        return {
            "success": True,
            "campaign_id": campaign_id,
            "name": name,
            "scenario": scenario,
            "total_contacts": len(contacts),
            "queued": queued_count,
            "failed": failed_count,
            "status_breakdown": status_counts
        }

    except Exception as e:
        logger.error(f"❌ Erreur création campagne: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        db.close()


def monitor_campaign(campaign_id):
    """
    Monitore la campagne en temps réel et affiche les stats

    Args:
        campaign_id: ID de la campagne à monitorer
    """
    print("\n" + "=" * 70)
    print("📊 MONITORING CAMPAGNE EN TEMPS RÉEL")
    print("=" * 70)
    print("💡 Appuyez sur Ctrl+C pour arrêter le monitoring\n")

    try:
        while True:
            db = SessionLocal()

            try:
                # Récupérer stats call_queue
                total_in_queue = db.query(CallQueue).filter(
                    CallQueue.campaign_id == campaign_id
                ).count()

                calling = db.query(CallQueue).filter(
                    CallQueue.campaign_id == campaign_id,
                    CallQueue.status == "calling"
                ).count()

                pending = db.query(CallQueue).filter(
                    CallQueue.campaign_id == campaign_id,
                    CallQueue.status == "pending"
                ).count()

                completed_queue = db.query(CallQueue).filter(
                    CallQueue.campaign_id == campaign_id,
                    CallQueue.status == "completed"
                ).count()

                failed_queue = db.query(CallQueue).filter(
                    CallQueue.campaign_id == campaign_id,
                    CallQueue.status == "failed"
                ).count()

                # Récupérer stats contacts
                leads = db.query(Contact).filter(
                    Contact.status == "Leads"
                ).count()

                no_answer = db.query(Contact).filter(
                    Contact.status == "No_answer"
                ).count()

                not_interested = db.query(Contact).filter(
                    Contact.status == "Not_interested"
                ).count()

                # Afficher le dashboard (effacer et réécrire)
                print("\033[2J\033[H", end='')  # Effacer écran et remettre curseur en haut

                print("=" * 70)
                print(f"📊 CAMPAGNE: {campaign_id}")
                print(f"🕐 {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 70)
                print()

                # Section appels en cours
                print("📞 APPELS EN COURS")
                print("-" * 70)
                print(f"   🔵 En cours   : {calling:3d}")
                print(f"   ⏳ En attente : {pending:3d}")
                print()

                # Section appels terminés
                print("✅ APPELS TERMINÉS")
                print("-" * 70)
                print(f"   ✅ Complétés  : {completed_queue:3d}")
                print(f"   ❌ Échecs     : {failed_queue:3d}")
                print(f"   📊 Total      : {total_in_queue:3d}")
                print()

                # Section résultats
                print("🎯 RÉSULTATS")
                print("-" * 70)
                print(f"   🌟 Leads              : {leads:3d}")
                print(f"   📞 No_answer          : {no_answer:3d}")
                print(f"   ❌ Not_interested     : {not_interested:3d}")
                print()

                # Progression
                if total_in_queue > 0:
                    progress = (completed_queue + failed_queue) / total_in_queue * 100
                    bar_length = 40
                    filled = int(bar_length * progress / 100)
                    bar = "█" * filled + "░" * (bar_length - filled)
                    print(f"📈 PROGRESSION: [{bar}] {progress:.1f}%")
                    print()

                # Vérifier si terminé
                if pending == 0 and calling == 0 and (completed_queue + failed_queue) == total_in_queue:
                    print("=" * 70)
                    print("🎉 CAMPAGNE TERMINÉE !")
                    print("=" * 70)
                    break

                print("=" * 70)
                print("💡 Appuyez sur Ctrl+C pour arrêter le monitoring")
                print("   Le batch_caller continue de traiter les appels")

            finally:
                db.close()

            # Attendre avant rafraîchissement
            time.sleep(3)

    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring arrêté (la campagne continue en arrière-plan)")
        print(f"   Logs: tail -f logs/batch_caller_console.log\n")


def main():
    """Point d'entrée CLI"""
    parser = argparse.ArgumentParser(
        description="Lance une campagne d'appels depuis les contacts en DB (status=New ou No_answer)",
        epilog="Exemple: python3 system/launch_campaign_from_contacts.py --limit 100"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite de contacts à appeler (default: tous les New/No_answer)"
    )

    parser.add_argument(
        "--scenario",
        type=str,
        default="production",
        choices=["production"],
        help="Scénario à utiliser (production uniquement)"
    )

    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Nom de la campagne (default: auto-généré avec date)"
    )

    parser.add_argument(
        "--priority",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help="Priorité des appels (1=normal, 2=high, 3=urgent, default: 1)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode test: affiche les contacts sans lancer la campagne"
    )

    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Afficher le monitoring temps réel après lancement"
    )

    args = parser.parse_args()

    # Auto-générer le nom si non fourni
    if not args.name:
        args.name = f"Campagne {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        logger.info(f"📝 Nom auto-généré: {args.name}")

    # Mode dry-run
    if args.dry_run:
        logger.info("🧪 MODE DRY-RUN - Aucune campagne ne sera lancée")
        db = SessionLocal()
        try:
            contacts = get_eligible_contacts(db, args.limit)
            logger.info(f"📊 {len(contacts)} contact(s) seraient appelés:")

            status_counts = {}
            for contact in contacts[:10]:  # Afficher max 10
                logger.info(f"   • {contact.phone} ({contact.status})")
                status_counts[contact.status] = status_counts.get(contact.status, 0) + 1

            if len(contacts) > 10:
                logger.info(f"   ... et {len(contacts) - 10} autre(s)")

            logger.info(f"\n📊 Répartition par statut:")
            for status, count in status_counts.items():
                logger.info(f"   • {status}: {count}")

        finally:
            db.close()
        return

    # Lancement réel
    result = create_campaign_from_contacts(
        name=args.name,
        scenario=args.scenario,
        description=None,
        limit=args.limit,
        priority=args.priority
    )

    if result["success"]:
        print("\n✅ Campagne lancée avec succès!")
        print(f"Campaign ID: {result['campaign_id']}")

        # Lancer le monitoring si demandé
        if args.monitor:
            time.sleep(2)  # Petite pause pour laisser batch_caller démarrer
            monitor_campaign(result['campaign_id'])

        sys.exit(0)
    else:
        print(f"\n❌ Échec: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
