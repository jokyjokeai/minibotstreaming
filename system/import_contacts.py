#!/usr/bin/env python3
"""
Import contacts from CSV to MiniBotPanel v2 database
Usage: python3 import_contacts.py contacts.csv
"""

import sys
import os
import csv
import logging
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, Contact

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def format_name(name: str) -> str:
    """
    Formate un nom/prénom correctement:
    - Première lettre en majuscule, reste en minuscule
    - Gère les noms composés avec espaces: "jean pIERRe" → "Jean Pierre"
    - Gère les noms composés avec trait d'union: "jean-PIERRE" → "Jean-Pierre"
    - Gère les espaces multiples

    Examples:
        "jean pIERRe" → "Jean Pierre"
        "marie-claire DUPONT" → "Marie-Claire Dupont"
        "MARTIN" → "Martin"
        "jean  pierre" → "Jean Pierre" (espaces multiples)
    """
    if not name or not name.strip():
        return ""

    # Nettoyer les espaces multiples
    name = ' '.join(name.split())

    # Traiter chaque partie séparée par des espaces
    parts = []
    for part in name.split():
        # Traiter les traits d'union dans chaque partie
        sub_parts = []
        for sub in part.split('-'):
            # Capitaliser: première lettre maj, reste min
            if sub:
                sub_parts.append(sub.capitalize())

        parts.append('-'.join(sub_parts))

    return ' '.join(parts)

def create_tables():
    """Create database tables if they don't exist"""
    logger.info("🔧 Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created")

def import_contacts_from_csv(csv_file: str):
    """Import contacts from CSV file"""
    if not csv_file:
        logger.error("❌ CSV file path required")
        return False
    
    db: Session = SessionLocal()
    
    try:
        logger.info(f"📥 Importing contacts from {csv_file}")
        
        imported = 0
        updated = 0
        errors = 0
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            # Detect CSV format
            sample = file.read(1024)
            file.seek(0)
            
            # Try different delimiters
            if ';' in sample:
                delimiter = ';'
            elif ',' in sample:
                delimiter = ','
            else:
                delimiter = ','
            
            reader = csv.DictReader(file, delimiter=delimiter)
            
            logger.info(f"📋 CSV columns detected: {reader.fieldnames}")
            
            for row_num, row in enumerate(reader, 1):
                try:
                    # Map CSV columns (flexible mapping)
                    phone = (row.get('phone') or row.get('Phone') or 
                            row.get('telephone') or row.get('Telephone') or '').strip()
                    
                    if not phone:
                        logger.warning(f"⚠️  Row {row_num}: No phone number")
                        errors += 1
                        continue
                    
                    # Clean phone number
                    phone = ''.join(filter(str.isdigit, phone))
                    if len(phone) < 8:
                        logger.warning(f"⚠️  Row {row_num}: Invalid phone {phone}")
                        errors += 1
                        continue
                    
                    # Extract other fields
                    first_name = (row.get('first_name') or row.get('FirstName') or
                                 row.get('prenom') or row.get('Prenom') or '').strip()
                    first_name = format_name(first_name)  # Formatage propre

                    last_name = (row.get('last_name') or row.get('LastName') or
                                row.get('nom') or row.get('Nom') or '').strip()
                    last_name = format_name(last_name)  # Formatage propre
                    
                    email = (row.get('email') or row.get('Email') or 
                            row.get('mail') or row.get('Mail') or '').strip()
                    
                    company = (row.get('company') or row.get('Company') or 
                              row.get('entreprise') or row.get('Entreprise') or '').strip()
                    
                    priority = 1
                    try:
                        priority = int(row.get('priority') or row.get('Priority') or 1)
                    except:
                        priority = 1
                    
                    # Check if contact exists
                    existing = db.query(Contact).filter(Contact.phone == phone).first()
                    
                    if existing:
                        # Update existing contact
                        existing.first_name = first_name or existing.first_name
                        existing.last_name = last_name or existing.last_name
                        existing.email = email or existing.email
                        existing.company = company or existing.company
                        existing.priority = priority
                        existing.updated_at = datetime.now()
                        updated += 1
                        logger.debug(f"📝 Updated contact: {phone}")
                    else:
                        # Create new contact
                        contact = Contact(
                            phone=phone,
                            first_name=first_name,
                            last_name=last_name,
                            email=email,
                            company=company,
                            priority=priority,
                            status="New"
                        )
                        db.add(contact)
                        imported += 1
                        logger.debug(f"➕ Added contact: {phone}")
                
                except Exception as e:
                    logger.error(f"❌ Error processing row {row_num}: {e}")
                    errors += 1
        
        # Commit all changes
        db.commit()
        
        logger.info(f"""
📊 Import Summary:
  ➕ New contacts: {imported}
  📝 Updated contacts: {updated}
  ❌ Errors: {errors}
  ✅ Total processed: {imported + updated}
""")
        
        return True
        
    except FileNotFoundError:
        logger.error(f"❌ File not found: {csv_file}")
        return False
    except Exception as e:
        logger.error(f"❌ Import error: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python3 import_contacts.py <csv_file>")
        print("Example: python3 import_contacts.py contacts.csv")
        print("Note: Le fichier sera cherché dans le dossier contacts/ par défaut")
        sys.exit(1)

    csv_filename = sys.argv[1]

    # Si le chemin n'est pas absolu, chercher dans le dossier contacts/
    if not os.path.isabs(csv_filename):
        # Dossier contacts à la racine du projet
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_file = os.path.join(base_dir, "contacts", csv_filename)

        # Si le fichier n'existe pas dans contacts/, chercher à la racine
        if not os.path.exists(csv_file):
            csv_file_root = os.path.join(base_dir, csv_filename)
            if os.path.exists(csv_file_root):
                csv_file = csv_file_root
            else:
                logger.error(f"❌ Fichier introuvable: {csv_filename}")
                logger.error(f"   Cherché dans: contacts/{csv_filename}")
                logger.error(f"   Et aussi dans: {csv_filename}")
                sys.exit(1)
    else:
        csv_file = csv_filename

    logger.info(f"📁 Fichier CSV: {csv_file}")

    # Create tables first
    create_tables()

    # Import contacts
    if import_contacts_from_csv(csv_file):
        logger.info("✅ Import completed successfully")
    else:
        logger.error("❌ Import failed")
        sys.exit(1)

if __name__ == "__main__":
    main()