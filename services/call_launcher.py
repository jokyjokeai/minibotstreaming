import requests
import config
import uuid
from datetime import datetime
from logger_config import get_logger

logger = get_logger(__name__)

def launch_call(phone_number: str, scenario: str = "basique", campaign_id: str = None) -> str:
    """
    Launch a call via Asterisk ARI
    
    Args:
        phone_number: The phone number to call
        scenario: The scenario to execute (basique, avancee, rdv)
        campaign_id: Optional campaign ID
        
    Returns:
        str: The generated call ID
        
    Raises:
        Exception: If the call launch fails
    """
    
    try:
        # Generate unique call ID
        call_id = f"robot_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
        
        logger.info(f"🚀 Launching call to {phone_number} with scenario {scenario}")
        
        # Prepare ARI request
        ari_url = f"{config.ARI_URL}/ari/channels"
        
        # Build channel endpoint - this will create an outbound call
        endpoint = f"PJSIP/{phone_number}@bitcall"  # Use bitcall endpoint from pjsip.conf
        
        # Prepare the request data for ARI channel creation
        # IMPORTANT: We DON'T specify the app here, we let the dialplan handle it
        # The dialplan will do AMD detection and then send to Stasis
        data = {
            "endpoint": endpoint,
            "context": "outbound-robot",  # Use the dialplan context
            "extension": phone_number,     # Extension to dial
            "priority": 1,                 # Start at priority 1
            "variables": {
                "ARG1": phone_number,
                "ARG2": scenario,
                "ARG3": campaign_id or ""
            }
        }
        
        # Make the ARI request with authentication
        auth = (config.ARI_USERNAME, config.ARI_PASSWORD)
        
        logger.info(f"📡 Making ARI request to: {ari_url}")
        logger.debug(f"📡 Request data: {data}")
        
        response = requests.post(
            ari_url,
            json=data,
            auth=auth,
            timeout=10
        )
        
        # Check response
        if response.status_code == 200 or response.status_code == 201:
            response_data = response.json()
            asterisk_call_id = response_data.get("id", call_id)
            
            logger.info(f"✅ Call launched successfully: {asterisk_call_id}")
            logger.info(f"📞 Asterisk will call {phone_number} and execute {scenario}")
            
            return asterisk_call_id
            
        else:
            error_msg = f"ARI request failed: {response.status_code} - {response.text}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error launching call: {e}"
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Failed to launch call: {e}"
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)

def test_ari_connection() -> bool:
    """
    Test connection to Asterisk ARI
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        ari_url = f"{config.ARI_URL}/ari/asterisk/info"
        auth = (config.ARI_USERNAME, config.ARI_PASSWORD)
        
        logger.info(f"🔍 Testing ARI connection to: {ari_url}")
        
        response = requests.get(ari_url, auth=auth, timeout=5)
        
        if response.status_code == 200:
            info = response.json()
            logger.info(f"✅ ARI connection successful - Asterisk version: {info.get('version', 'unknown')}")
            return True
        else:
            logger.error(f"❌ ARI connection failed: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ ARI connection test failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error testing ARI connection: {e}")
        return False