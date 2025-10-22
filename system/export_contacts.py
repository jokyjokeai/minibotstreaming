#!/usr/bin/env python3
"""
Script d'export de contacts et résultats d'appels
Export vers CSV avec options de filtrage
"""

import csv
import sys
import os
import json
import argparse
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Contact, Call
from logger_config import get_logger
import config

logger = get_logger(__name__)

class ContactExporter:
    """Exporte les contacts et résultats vers CSV"""

    def __init__(self, api_base_url=None):
        self.db = SessionLocal()
        # Utiliser PUBLIC_API_URL depuis config par défaut
        self.api_base_url = api_base_url or config.PUBLIC_API_URL

    def path_to_url(self, file_path):
        """
        Convertit un chemin local en URL HTTP publique

        Args:
            file_path: Chemin local (ex: /var/spool/asterisk/recording/file.wav
                                      ou assembled_audio/full_call_assembled_*.wav)

        Returns:
            URL HTTP publique (ex: http://VPS_IP:8000/calls/recordings/file.wav
                                ou https://domaine.com/calls/assembled/file.wav)
            Utilise PUBLIC_API_URL depuis .env (config.PUBLIC_API_URL)
        """
        if not file_path:
            return ""

        # Extraire juste le nom du fichier
        filename = os.path.basename(file_path)

        # Si c'est un fichier assemblé, utiliser l'endpoint /assembled/
        if 'assembled' in file_path or 'assembled' in filename:
            return f"{self.api_base_url}/calls/assembled/{filename}"

        # Sinon, endpoint classique /recordings/
        return f"{self.api_base_url}/calls/recordings/{filename}"

    def get_transcript_text(self, call_id):
        """
        Lit le fichier de transcription JSON complète post-appel et retourne le texte formaté

        Args:
            call_id: ID de l'appel

        Returns:
            Texte de conversation formaté (BOT: ... | CLIENT: ...)
        """
        # Chemin vers le répertoire transcripts (nouveau format post-call)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Essayer d'abord le nouveau format (post-call complet)
        complete_transcript_path = os.path.join(base_dir, "transcripts", f"complete_call_{call_id}.json")
        
        if os.path.exists(complete_transcript_path):
            try:
                with open(complete_transcript_path, 'r', encoding='utf-8') as f:
                    transcript = json.load(f)

                # Nouveau format: conversation_analysis.turns
                conversation_text = []
                turns = transcript.get("conversation_analysis", {}).get("turns", [])
                
                for turn in turns:
                    speaker = turn.get("speaker", "UNKNOWN")
                    text = turn.get("text", "")
                    start_time = turn.get("start_time", 0)
                    
                    if text.strip():  # Ignorer les segments vides
                        conversation_text.append(f"[{start_time:05.1f}s] {speaker}: {text}")

                return " | ".join(conversation_text) if conversation_text else "[Conversation analysée mais vide]"
                
            except Exception as e:
                return f"[Erreur lecture transcription complète: {e}]"
        
        # Fallback: ancien format si le nouveau n'existe pas
        old_transcript_path = os.path.join(base_dir, "transcripts", f"transcript_{call_id}.json")
        
        if os.path.exists(old_transcript_path):
            try:
                with open(old_transcript_path, 'r', encoding='utf-8') as f:
                    transcript = json.load(f)

                conversation_text = []
                for turn in transcript.get("conversation", []):
                    if turn["speaker"] == "BOT":
                        conversation_text.append(f"BOT: {turn['text']}")
                    else:
                        conversation_text.append(f"CLIENT: {turn['transcription']}")

                return " | ".join(conversation_text)
                
            except Exception as e:
                return f"[Erreur lecture ancienne transcription: {e}]"
        
        return "[Transcription non disponible - Aucun fichier trouvé]"

    def export_contacts(self, output_file, campaign=None, status=None, include_calls=False):
        """
        Exporte les contacts vers un fichier CSV

        Args:
            output_file: Fichier de sortie
            campaign: Filtrer par campagne
            status: Filtrer par statut (new, called, interested, not_interested)
            include_calls: Inclure les résultats d'appels
        """
        logger.info("=" * 60)
        logger.info("📤 EXPORT DE CONTACTS")
        logger.info(f"   Fichier: {output_file}")
        logger.info(f"   Campagne: {campaign or 'Toutes'}")
        logger.info(f"   Statut: {status or 'Tous'}")
        logger.info(f"   Inclure appels: {'Oui' if include_calls else 'Non'}")
        logger.info("=" * 60)

        try:
            # Construire la requête
            query = self.db.query(Contact)

            # Filtres
            # Note: Le modèle Contact n'a pas de champ campaign pour l'instant
            # Le filtrage par campagne se fait via la table calls
            if status:
                query = query.filter(Contact.status == status)

            contacts = query.all()
            logger.info(f"📊 {len(contacts)} contacts trouvés")

            # Préparer les colonnes
            fieldnames = [
                'lead_id',  # Numéro de lead auto-généré
                'phone_number',
                'first_name',
                'last_name',
                'email',
                'company',
                'status',
                'priority',
                'attempts',
                'last_attempt',
                'imported_at',
                'audio_recording_path'
            ]

            if include_calls:
                fieldnames.extend([
                    'last_call_date',
                    'last_call_duration',
                    'last_call_result',
                    'amd_result',
                    'final_sentiment',
                    'is_interested',
                    'total_calls',
                    'transcription_complete'
                ])

            # Écrire le CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for contact in contacts:
                    # Récupérer le dernier appel pour obtenir l'audio assemblé
                    last_call = self.db.query(Call).filter(
                        Call.phone_number == contact.phone
                    ).order_by(Call.started_at.desc()).first()

                    # Utiliser assembled_audio_path si disponible, sinon recording_path
                    audio_path = ""
                    if last_call:
                        audio_path = last_call.assembled_audio_path if hasattr(last_call, 'assembled_audio_path') and last_call.assembled_audio_path else last_call.recording_path

                    row = {
                        'lead_id': contact.id,  # Numéro de lead auto-généré
                        'phone_number': contact.phone,
                        'first_name': contact.first_name or '',
                        'last_name': contact.last_name or '',
                        'email': contact.email or '',
                        'company': contact.company or '',
                        'status': contact.status or '',
                        'priority': contact.priority or 1,
                        'attempts': contact.attempts or 0,
                        'last_attempt': contact.last_attempt.strftime('%Y-%m-%d %H:%M:%S') if contact.last_attempt else '',
                        'imported_at': contact.created_at.strftime('%Y-%m-%d %H:%M:%S') if contact.created_at else '',
                        'audio_recording_path': self.path_to_url(audio_path)
                    }

                    if include_calls:
                        if last_call:
                            row.update({
                                'last_call_date': last_call.started_at.strftime('%Y-%m-%d %H:%M:%S') if last_call.started_at else '',
                                'last_call_duration': last_call.duration or 0,
                                'last_call_result': last_call.status or '',
                                'amd_result': last_call.amd_result or '',
                                'final_sentiment': last_call.final_sentiment or '',
                                'is_interested': 'Oui' if last_call.is_interested else 'Non',
                            })

                            # Compter le total d'appels
                            total = self.db.query(Call).filter(
                                Call.phone_number == contact.phone
                            ).count()
                            row['total_calls'] = total

                            # Ajouter la transcription complète
                            row['transcription_complete'] = self.get_transcript_text(last_call.call_id)
                        else:
                            row.update({
                                'last_call_date': '',
                                'last_call_duration': 0,
                                'last_call_result': '',
                                'amd_result': '',
                                'final_sentiment': '',
                                'is_interested': '',
                                'total_calls': 0,
                                'transcription_complete': ''
                            })

                    writer.writerow(row)

            logger.info(f"✅ Export terminé: {len(contacts)} contacts")
            logger.info(f"📁 Fichier créé: {output_file}")

            return True

        except Exception as e:
            logger.error(f"❌ Erreur export: {e}")
            return False
        finally:
            self.db.close()

    def export_call_results(self, output_file, date_from=None, date_to=None):
        """
        Exporte uniquement les résultats d'appels

        Args:
            output_file: Fichier de sortie
            date_from: Date de début (format: YYYY-MM-DD)
            date_to: Date de fin (format: YYYY-MM-DD)
        """
        logger.info("=" * 60)
        logger.info("📤 EXPORT DES RÉSULTATS D'APPELS")
        logger.info(f"   Fichier: {output_file}")
        logger.info(f"   Période: {date_from or 'Début'} à {date_to or 'Fin'}")
        logger.info("=" * 60)

        try:
            # Requête
            query = self.db.query(Call)

            # Filtres de date
            if date_from:
                date_obj = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(Call.started_at >= date_obj)
            if date_to:
                date_obj = datetime.strptime(date_to, '%Y-%m-%d')
                query = query.filter(Call.started_at <= date_obj)

            calls = query.order_by(Call.started_at.desc()).all()
            logger.info(f"📊 {len(calls)} appels trouvés")

            # Colonnes
            fieldnames = [
                'call_id',
                'phone_number',
                'campaign_id',
                'started_at',
                'ended_at',
                'duration',
                'status',
                'amd_result',
                'final_sentiment',
                'is_interested',
                'recording_path',
                'transcription_complete'
            ]

            # Écrire le CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for call in calls:
                    # Utiliser assembled_audio_path si disponible, sinon recording_path
                    audio_path = call.assembled_audio_path if hasattr(call, 'assembled_audio_path') and call.assembled_audio_path else call.recording_path

                    row = {
                        'call_id': call.call_id,
                        'phone_number': call.phone_number,
                        'campaign_id': call.campaign_id or '',
                        'started_at': call.started_at.strftime('%Y-%m-%d %H:%M:%S') if call.started_at else '',
                        'ended_at': call.ended_at.strftime('%Y-%m-%d %H:%M:%S') if call.ended_at else '',
                        'duration': call.duration or 0,
                        'status': call.status or '',
                        'amd_result': call.amd_result or '',
                        'final_sentiment': call.final_sentiment or '',
                        'is_interested': 'Oui' if call.is_interested else 'Non',
                        'recording_path': self.path_to_url(audio_path),
                        'transcription_complete': self.get_transcript_text(call.call_id)
                    }
                    writer.writerow(row)

            logger.info(f"✅ Export terminé: {len(calls)} appels")
            logger.info(f"📁 Fichier créé: {output_file}")

            return True

        except Exception as e:
            logger.error(f"❌ Erreur export: {e}")
            return False
        finally:
            self.db.close()

def main():
    """Script principal"""
    parser = argparse.ArgumentParser(description="Export de contacts et résultats")

    subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')

    # Export contacts
    contacts_parser = subparsers.add_parser('contacts', help='Exporter les contacts')
    contacts_parser.add_argument('output', help='Fichier CSV de sortie')
    contacts_parser.add_argument('--campaign', '-c', help='Filtrer par campagne')
    contacts_parser.add_argument('--status', '-s', choices=['new', 'called', 'interested', 'not_interested'],
                                help='Filtrer par statut')
    contacts_parser.add_argument('--with-calls', action='store_true', help='Inclure les résultats d\'appels')

    # Export appels
    calls_parser = subparsers.add_parser('calls', help='Exporter les résultats d\'appels')
    calls_parser.add_argument('output', help='Fichier CSV de sortie')
    calls_parser.add_argument('--from', dest='date_from', help='Date de début (YYYY-MM-DD)')
    calls_parser.add_argument('--to', dest='date_to', help='Date de fin (YYYY-MM-DD)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    exporter = ContactExporter()

    # Chemin de sortie - par défaut dans le dossier contacts/
    if not os.path.isabs(args.output):
        # Dossier contacts à la racine du projet
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_path = os.path.join(base_dir, "contacts", args.output)

        # Créer le dossier contacts/ s'il n'existe pas
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    else:
        output_path = args.output

    logger.info(f"📁 Fichier de sortie: {output_path}")

    if args.command == 'contacts':
        success = exporter.export_contacts(
            output_path,
            campaign=args.campaign,
            status=args.status,
            include_calls=args.with_calls
        )
    elif args.command == 'calls':
        success = exporter.export_call_results(
            output_path,
            date_from=args.date_from,
            date_to=args.date_to
        )

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()