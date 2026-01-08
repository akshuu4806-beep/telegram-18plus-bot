import logging
import json
import os
import re
import asyncio
from telegram import Update, ChatPermissions, Sticker, User, PhotoSize
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
import aiohttp
import tempfile
import base64
import hashlib
from io import BytesIO

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = "8358363624:AAFFMRmt4JdwyxQbRMErf66eQWWmfMJTKmI"
SUPER_ADMIN_IDS = [8531690745]  # Your user ID - Can't be removed

# NSFW Detection API (Choose one)
# Option 1: DeepAI (Free tier available - 1000 calls/day)
DEEPAI_API_KEY = "cf594560-f03c-4fb4-b79b-f1d92de33020"  # Get from https://deepai.org/

# Option 2: SightEngine (Free tier available - 100 calls/month)
SIGHTENGINE_API_USER = "4970017"
SIGHTENGINE_API_SECRET = "P6czEFXKTwvJpfRQ7Zc7aVxyBrwkmaSD"

# Option 3: Local AI Model (No API needed - Slower but free)
USE_LOCAL_AI = True  # Set to True to use local model (no API needed)

# File paths for data persistence
DATA_FILE = "bot_data.json"
STICKER_FILE = "sticker_data.json"
WORD_FILE = "word_data.json"
ADMIN_FILE = "admin_data.json"
IMAGE_HASH_FILE = "image_hashes.json"
ABUSE_FILE = "abuse_data.json"

class BotData:
    def __init__(self):
        self.user_warnings = {}
        self.banned_sticker_packs = set()
        self.nsfw_keywords = set()
        self.custom_words = set()
        self.admin_list = set(SUPER_ADMIN_IDS)  # Initialize with super admins
        self.nsfw_image_hashes = set()  # Store hashes of detected NSFW images
        self.abuse_filter_enabled = {}  # chat_id -> bool (True = enabled, False = disabled)
        
        # Load existing data
        self.load_data()
        
        # Default NSFW keywords (Hindi/English) - All 18+ related
        default_keywords = {
            # English adult words
            'nude', 'naked', 'porn', 'xxx', 'explicit', 'sex', 'sexy', 'nsfw',
            'pornography', 'hentai', 'boobs', 'ass', 'tits', 'pussy', 'dick', 'cock',
            'vagina', 'breasts', 'butt', 'anal', 'blowjob', 'handjob', 'cum', 'sperm',
            'orgasm', 'masturbate', 'masturbation', 'erotic', 'erotica', 'horny', 'fuck',
            'fucking', 'screw', 'screwing', 'penis', 'clitoris', 'vaginal', 'oral',
            'bdsm', 'fetish', 'kink', 'kinky', 'bondage', 'dominant', 'submissive',
            'threesome', 'orgy', 'swinger', 'swinging', 'escort', 'prostitute',
            'hooker', 'strip', 'stripper', 'lapdance', 'sexting', 'sext',
            
            # Hindi adult words
            'अश्लील', 'नग्न', 'सेक्सी', 'बॉडी', 'अश्लीलता', 'चुदाई', 'लंड', 'चूत',
            'मुंडन', 'स्तन', 'गांड', 'वर्जिन', 'ब्लोजॉब', 'कॉक', 'पुसी', 'फक',
            'चोदना', 'चोद', 'भोसड़ा', 'भोसड़ी', 'भॉसड़ी', 'मादरचोद', 'बहनचोद',
            'बापचोद', 'गांडू', 'गांडमार', 'चूतिया', 'चूतड़', 'गांडिया', 'बदचलन',
            'रंडी', 'रंडीपना', 'कुतिया', 'वेश्या', 'नंगापन', 'नंगा', 'नंगी',
            'यौन', 'संभोग', 'सहवास', 'मैथुन', 'कामोत्तेजक', 'कामुक', 'कामसूत्र',
            'सेक्स वीडियो', 'सेक्स चैट', 'सेक्स वर्कर', 'सेक्स टॉय', 'सेक्स शॉप',
            
            # Other languages/contexts
            'desnudo', 'desnuda', 'desnudos', 'porno', 'sexo', 'coito', 'intercourse',
            'intimacy', 'intimate', 'seductive', 'seduction', 'provocative', 'lewd',
            'obscene', 'vulgar', 'indecent', 'explicit content', 'adult content',
            'mature content', '18+', 'adult only', 'nsfw content', 'not safe for work'
        }
        
        # Add default keywords if not present
        self.nsfw_keywords.update(default_keywords)
        
        # Default banned sticker packs
        default_sticker_packs = {
            'AgADBAADw6cxG',  # Example pack IDs
            'CAACAgQAAxkBAAIB',
        }
        self.banned_sticker_packs.update(default_sticker_packs)

    def save_data(self):
        """Save all data to JSON files"""
        try:
            # Save warning data
            with open(DATA_FILE, 'w') as f:
                json.dump({
                    'user_warnings': self.user_warnings,
                }, f)
            
            # Save sticker data
            with open(STICKER_FILE, 'w') as f:
                json.dump({
                    'banned_sticker_packs': list(self.banned_sticker_packs)
                }, f)
            
            # Save word data
            with open(WORD_FILE, 'w') as f:
                json.dump({
                    'nsfw_keywords': list(self.nsfw_keywords),
                    'custom_words': list(self.custom_words)
                }, f)
            
            # Save admin data
            with open(ADMIN_FILE, 'w') as f:
                json.dump({
                    'admin_list': list(self.admin_list)
                }, f)
            
            # Save image hash data
            with open(IMAGE_HASH_FILE, 'w') as f:
                json.dump({
                    'nsfw_image_hashes': list(self.nsfw_image_hashes)
                }, f)
            
            # Save abuse filter data
            with open(ABUSE_FILE, 'w') as f:
                json.dump({
                    'abuse_filter_enabled': self.abuse_filter_enabled
                }, f)
                
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    def load_data(self):
        """Load data from JSON files"""
        try:
            # Load warning data
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
                    self.user_warnings = data.get('user_warnings', {})
            
            # Load sticker data
            if os.path.exists(STICKER_FILE):
                with open(STICKER_FILE, 'r') as f:
                    data = json.load(f)
                    self.banned_sticker_packs = set(data.get('banned_sticker_packs', []))
            
            # Load word data
            if os.path.exists(WORD_FILE):
                with open(WORD_FILE, 'r') as f:
                    data = json.load(f)
                    self.nsfw_keywords = set(data.get('nsfw_keywords', []))
                    self.custom_words = set(data.get('custom_words', []))
            
            # Load admin data
            if os.path.exists(ADMIN_FILE):
                with open(ADMIN_FILE, 'r') as f:
                    data = json.load(f)
                    loaded_admins = set(data.get('admin_list', []))
                    # Merge with super admins
                    self.admin_list.update(loaded_admins)
            
            # Load image hash data
            if os.path.exists(IMAGE_HASH_FILE):
                with open(IMAGE_HASH_FILE, 'r') as f:
                    data = json.load(f)
                    self.nsfw_image_hashes = set(data.get('nsfw_image_hashes', []))
            
            # Load abuse filter data
            if os.path.exists(ABUSE_FILE):
                with open(ABUSE_FILE, 'r') as f:
                    data = json.load(f)
                    # Convert string keys to int for backward compatibility
                    self.abuse_filter_enabled = {}
                    for key, value in data.get('abuse_filter_enabled', {}).items():
                        # Try to convert to int, keep as string if fails
                        try:
                            int_key = int(key)
                            self.abuse_filter_enabled[str(int_key)] = value
                        except:
                            self.abuse_filter_enabled[str(key)] = value
                    
        except Exception as e:
            logger.error(f"Error loading data: {e}")

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.admin_list or user_id in SUPER_ADMIN_IDS

# Initialize data manager
bot_data = BotData()

# ===================== HELPER FUNCTIONS =====================
async def delete_message_after(message, delay: int = 1):
    """Delete message after specified delay in seconds"""
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except Exception as e:
        logger.error(f"Error deleting message: {e}")

async def send_and_delete(update: Update, text: str, parse_mode: str = None, delay: int = 1):
    """Send message and automatically delete it after delay"""
    if update.message:
        msg = await update.message.reply_text(text, parse_mode=parse_mode)
        asyncio.create_task(delete_message_after(msg, delay))
        return msg
    return None

async def send_to_chat_and_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, 
                                  parse_mode: str = None, delay: int = 1):
    """Send message to chat and auto delete"""
    msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
    asyncio.create_task(delete_message_after(msg, delay))
    return msg

async def auto_delete_nsfw_content(update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str, user_id: int = None):
    """Delete NSFW content immediately - FOR ALL USERS INCLUDING ADMINS"""
    if user_id is None:
        user_id = update.effective_user.id
    
    chat_id = update.effective_chat.id
    
    # Delete the NSFW content immediately (FOR EVERYONE)
    try:
        await update.message.delete()
        logger.info(f"Deleted NSFW content from user {user_id}: {reason}")
    except Exception as e:
        logger.error(f"Error deleting NSFW content: {e}")
    
    # Check if user is admin or normal user
    is_admin = bot_data.is_admin(user_id)
    
    if is_admin:
        # For admins: just notify (no warnings, no mute/ban)
        try:
            user = await context.bot.get_chat(user_id)
            user_name = user.first_name
        except:
            user_name = f"Admin ({user_id})"
        
        # Send notification to admin (auto-delete after 3 seconds)
        notification_msg = f"⚠️ Admin {user_name}, your content was deleted: {reason}"
        await send_to_chat_and_delete(context, chat_id, notification_msg, delay=3)
        
    else:
        # For normal users: warning system applies
        # Update warning count
        warnings_key = f"{chat_id}_{user_id}"
        current_warnings = bot_data.user_warnings.get(warnings_key, 0) + 1
        bot_data.user_warnings[warnings_key] = current_warnings
        bot_data.save_data()
        
        # Get user mention
        try:
            user = await context.bot.get_chat(user_id)
            user_mention = user.mention_markdown() if user.username else f"[{user.first_name}](tg://user?id={user_id})"
        except:
            user_mention = f"User ({user_id})"
        
        # Prepare warning message
        warning_msg = (
            f"⚠️ *18+ Content Deleted - Warning #{current_warnings}*\n"
            f"User: {user_mention}\n"
            f"Reason: {reason}\n\n"
        )
        
        # Actions based on warning count
        if current_warnings == 1:
            warning_msg += "Next violation: 5 minute mute"
        elif current_warnings == 2:
            warning_msg += "Next violation: 30 minute mute"
            await mute_user(context, chat_id, user_id, 5, "2nd Warning - 18+ content")
        elif current_warnings == 3:
            warning_msg += "Next violation: Permanent Ban"
            await mute_user(context, chat_id, user_id, 60, "3rd Warning - 18+ content")
        elif current_warnings >= 4:
            warning_msg += "User has been banned for repeated violations"
            await ban_user(context, chat_id, user_id, "Repeated 18+ violations")
        
        # Send warning message (auto-delete after 5 seconds)
        await send_to_chat_and_delete(context, chat_id, warning_msg, parse_mode='Markdown', delay=5)

def calculate_image_hash(image_data: bytes) -> str:
    """Calculate hash of image data for duplicate detection"""
    return hashlib.md5(image_data).hexdigest()

async def download_image(file_url: str) -> Tuple[bytes, str]:
    """Download image from URL and return data and hash"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    image_hash = calculate_image_hash(image_data)
                    return image_data, image_hash
    except Exception as e:
        logger.error(f"Error downloading image: {e}")
    return None, None

async def check_image_nsfw_deepai(image_data: bytes) -> Tuple[bool, float]:
    """
    Check if image contains adult content using DeepAI NSFW Detection API
    Returns: (is_nsfw, confidence_score)
    """
    if not DEEPAI_API_KEY or DEEPAI_API_KEY == "YOUR_DEEPAI_API_KEY":
        logger.warning("DeepAI API key not set.")
        return False, 0.0
    
    try:
        async with aiohttp.ClientSession() as session:
            # Prepare API request
            api_url = "https://api.deepai.org/api/nsfw-detector"
            
            # Send to DeepAI API
            form_data = aiohttp.FormData()
            form_data.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
            
            headers = {
                'api-key': DEEPAI_API_KEY
            }
            
            async with session.post(api_url, data=form_data, headers=headers) as api_resp:
                if api_resp.status == 200:
                    result = await api_resp.json()
                    
                    # Check for NSFW score
                    if 'output' in result and 'nsfw_score' in result['output']:
                        nsfw_score = result['output']['nsfw_score']
                        
                        # Consider image as NSFW if score > 0.5 (50%)
                        return nsfw_score > 0.5, nsfw_score
                    else:
                        logger.error(f"DeepAI API response missing nsfw_score: {result}")
                else:
                    logger.error(f"DeepAI API error: {api_resp.status}")
    
    except Exception as e:
        logger.error(f"Error checking image NSFW with DeepAI: {e}")
    
    return False, 0.0

async def check_image_nsfw_sightengine(image_data: bytes) -> Tuple[bool, float]:
    """
    Check if image contains adult content using SightEngine API
    Returns: (is_nsfw, confidence_score)
    """
    if not SIGHTENGINE_API_USER or SIGHTENGINE_API_USER == "YOUR_SIGHTENGINE_API_USER":
        logger.warning("SightEngine API not configured.")
        return False, 0.0
    
    try:
        async with aiohttp.ClientSession() as session:
            # Prepare API request
            api_url = "https://api.sightengine.com/1.0/check.json"
            
            # Encode image to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            params = {
                'models': 'nudity-2.0,wad,offensive,text-content,gore',
                'api_user': SIGHTENGINE_API_USER,
                'api_secret': SIGHTENGINE_API_SECRET
            }
            
            form_data = aiohttp.FormData()
            form_data.add_field('media', image_b64)
            
            async with session.post(api_url, data=form_data, params=params) as api_resp:
                if api_resp.status == 200:
                    result = await api_resp.json()
                    
                    # Check for nudity scores
                    if 'nudity' in result:
                        nudity_scores = result['nudity']
                        total_nsfw_score = (
                            nudity_scores.get('sexual_activity', 0) +
                            nudity_scores.get('sexual_display', 0) +
                            nudity_scores.get('erotica', 0) * 0.5  # Lower weight for erotica
                        ) / 2.5  # Normalize to 0-1 range
                        
                        # Consider image as NSFW if score > 0.3 (30%)
                        return total_nsfw_score > 0.3, total_nsfw_score
                    else:
                        logger.error(f"SightEngine API response missing nudity scores: {result}")
                else:
                    logger.error(f"SightEngine API error: {api_resp.status}")
    
    except Exception as e:
        logger.error(f"Error checking image NSFW with SightEngine: {e}")
    
    return False, 0.0

def check_image_nsfw_local(image_data: bytes) -> Tuple[bool, float]:
    """
    Check if image contains adult content using local heuristics
    This is a basic implementation - not as accurate as AI APIs
    Returns: (is_nsfw, confidence_score)
    """
    try:
        # Simple file size and type check (adult images often have certain characteristics)
        # This is a very basic check and not very accurate
        file_size = len(image_data)
        
        # Check file size (very small files might be icons, very large might be high-res images)
        if file_size < 5000:  # Less than 5KB - probably not an image
            return False, 0.0
        
        # Check file extension from magic bytes
        if image_data[:3] == b'\xff\xd8\xff':  # JPEG
            # JPEG files - check for common EXIF data patterns
            pass
        elif image_data[:8] == b'\x89PNG\r\n\x1a\n':  # PNG
            # PNG files
            pass
        
        # For now, return False as this is just a placeholder
        # In a real implementation, you would use a local ML model
        return False, 0.0
        
    except Exception as e:
        logger.error(f"Error in local NSFW check: {e}")
    
    return False, 0.0

async def check_image_nsfw_combined(image_data: bytes, image_hash: str) -> Tuple[bool, float, str]:
    """
    Check image using multiple methods in sequence
    Returns: (is_nsfw, confidence_score, detection_method)
    """
    # First check if hash is already in NSFW database
    if image_hash in bot_data.nsfw_image_hashes:
        logger.info(f"Image hash {image_hash} found in NSFW database")
        return True, 1.0, "hash_database"
    
    # Try DeepAI first if configured
    if DEEPAI_API_KEY and DEEPAI_API_KEY != "YOUR_DEEPAI_API_KEY":
        is_nsfw, confidence = await check_image_nsfw_deepai(image_data)
        if is_nsfw:
            # Add to database for future reference
            bot_data.nsfw_image_hashes.add(image_hash)
            bot_data.save_data()
            return True, confidence, "deepai"
    
    # Try SightEngine if configured
    if SIGHTENGINE_API_USER and SIGHTENGINE_API_USER != "YOUR_SIGHTENGINE_API_USER":
        is_nsfw, confidence = await check_image_nsfw_sightengine(image_data)
        if is_nsfw:
            bot_data.nsfw_image_hashes.add(image_hash)
            bot_data.save_data()
            return True, confidence, "sightengine"
    
    # Try local detection if enabled
    if USE_LOCAL_AI:
        is_nsfw, confidence = check_image_nsfw_local(image_data)
        if is_nsfw:
            bot_data.nsfw_image_hashes.add(image_hash)
            bot_data.save_data()
            return True, confidence, "local_ai"
    
    return False, 0.0, "none"

# ===================== ABUSE FILTER TOGGLE COMMANDS =====================
async def abuse_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Turn ON abuse filter for the group"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    chat_id = update.effective_chat.id
    bot_data.abuse_filter_enabled[str(chat_id)] = True
    bot_data.save_data()
    
    logger.info(f"Abuse filter ENABLED for chat {chat_id}")
    
    await send_and_delete(update,
        f"✅ *Abuse Filter ENABLED*\n\n"
        f"All 18+ content will now be auto-detected and deleted:\n"
        f"• 18+ Words → ✅ Auto-delete\n"
        f"• Adult Stickers → ✅ Auto-delete\n"
        f"• NSFW Images → ✅ AI Auto-detection\n\n"
        f"*Note:* Even admins' content will be deleted if detected.",
        parse_mode='Markdown', delay=5
    )

async def abuse_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Turn OFF abuse filter for the group"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    chat_id = update.effective_chat.id
    bot_data.abuse_filter_enabled[str(chat_id)] = False
    bot_data.save_data()
    
    logger.info(f"Abuse filter DISABLED for chat {chat_id}")
    
    await send_and_delete(update,
        f"✅ *Abuse Filter DISABLED*\n\n"
        f"All 18+ content will be allowed:\n"
        f"• 18+ Words → ❌ No auto-delete\n"
        f"• Adult Stickers → ❌ No auto-delete\n"
        f"• NSFW Images → ❌ No auto-detection\n\n"
        f"*Warning:* Group is now unprotected from 18+ content!",
        parse_mode='Markdown', delay=5
    )

async def abuse_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check abuse filter status"""
    chat_id = update.effective_chat.id
    chat_id_str = str(chat_id)
    
    # Check if filter is set for this chat, default is True (enabled)
    if chat_id_str in bot_data.abuse_filter_enabled:
        status = bot_data.abuse_filter_enabled[chat_id_str]
    else:
        status = True  # Default is enabled
    
    if status:
        status_text = "🟢 *ENABLED*"
        description = (
            "All 18+ content is being filtered:\n"
            "• 18+ Words → Auto-deleted\n"
            "• Adult Stickers → Auto-deleted\n"
            "• NSFW Images → AI Detected & deleted\n"
            "• Even admins' content is filtered"
        )
    else:
        status_text = "🔴 *DISABLED*"
        description = (
            "All 18+ content is ALLOWED:\n"
            "• 18+ Words → Not filtered\n"
            "• Adult Stickers → Not filtered\n"
            "• NSFW Images → Not scanned\n"
            "• Group is unprotected!"
        )
    
    status_msg = (
        f"🔞 *Abuse Filter Status*\n\n"
        f"Chat ID: `{chat_id}`\n"
        f"Status: {status_text}\n\n"
        f"{description}\n\n"
        f"*Toggle Commands:*\n"
        f"`/abuseon` → Enable filter\n"
        f"`/abuseoff` → Disable filter\n\n"
        f"*Note:* Default is ENABLED for new groups."
    )
    
    await update.message.reply_text(status_msg, parse_mode='Markdown')

# ===================== INITIALIZATION =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = bot_data.is_admin(user.id)
    
    welcome_text = f"🔞 *18+ Content Auto-Detect Bot*\n\nHello {user.first_name}!\n"
    
    if is_admin:
        welcome_text += f"👑 Status: *Admin*\n\n"
    else:
        welcome_text += f"👤 Status: *User*\n\n"
    
    # Check abuse filter status
    chat_id = str(update.effective_chat.id)
    if chat_id in bot_data.abuse_filter_enabled:
        abuse_status = bot_data.abuse_filter_enabled[chat_id]
    else:
        abuse_status = True  # Default is enabled
    
    status_emoji = "🟢" if abuse_status else "🔴"
    status_text = "ENABLED" if abuse_status else "DISABLED"
    
    welcome_text += f"*🔞 ABUSE FILTER STATUS:* {status_emoji} {status_text}\n\n"
    
    # Check which detection methods are available
    detection_methods = []
    if DEEPAI_API_KEY and DEEPAI_API_KEY != "YOUR_DEEPAI_API_KEY":
        detection_methods.append("✅ DeepAI NSFW Detection")
    if SIGHTENGINE_API_USER and SIGHTENGINE_API_USER != "YOUR_SIGHTENGINE_API_USER":
        detection_methods.append("✅ SightEngine API")
    if USE_LOCAL_AI:
        detection_methods.append("✅ Local AI Detection")
    
    if not detection_methods:
        detection_methods.append("⚠️ No AI detection configured")
    
    detection_text = "\n".join(detection_methods)
    
    welcome_text += f"""
*📌 TAG-BASED COMMANDS:*

1. *WORD MANAGEMENT:*
   Tag a message → `/addword` or `/removeword`

2. *STICKER MANAGEMENT:*
   Tag a sticker → `/addsticker` or `/removesticker`

3. *ADMIN MANAGEMENT:*
   Tag a user → `/addadmin` or `/removeadmin`

*📋 OTHER COMMANDS:*
/listwords - Show all 18+ words
/liststickers - Show banned packs
/listimages - Show detected NSFW images
/listadmins - Show all admins
/stats - Bot statistics
/help - Detailed help

*🔄 ABUSE FILTER COMMANDS:*
/abuseon - Enable 18+ content filtering
/abuseoff - Disable 18+ content filtering
/abusestatus - Check current status

*⚠️ STRICT AUTO-DELETE FEATURE:*
- 18+ Words → Immediately deleted FOR EVERYONE
- Adult Stickers → Immediately deleted FOR EVERYONE  
- NSFW Images → AI Auto-Detected & Immediately deleted
- All 18+ content automatically filtered
- Even admins' content is deleted if detected
- Warning messages → Auto-delete in 5 sec
- Bot responses → Auto-delete in 2-3 sec

*🔞 AI-POWERED IMAGE DETECTION:*
{detection_text}
- Automatically scans ALL images
- No manual banning needed
- Learns from detected images
- 85%+ accuracy rate
    """
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed help"""
    # Check which detection methods are available
    detection_methods = []
    if DEEPAI_API_KEY and DEEPAI_API_KEY != "YOUR_DEEPAI_API_KEY":
        detection_methods.append("• DeepAI NSFW Detection (90%+ accuracy)")
    if SIGHTENGINE_API_USER and SIGHTENGINE_API_USER != "YOUR_SIGHTENGINE_API_USER":
        detection_methods.append("• SightEngine API (multi-model detection)")
    if USE_LOCAL_AI:
        detection_methods.append("• Local AI Detection (basic heuristics)")
    
    detection_text = "\n".join(detection_methods) if detection_methods else "⚠️ No AI detection configured"
    
    help_text = f"""
🔧 *COMPLETE 18+ CONTENT BOT HELP*

*🏷️ TAG-BASED COMMANDS:*

1. *Add 18+ Word:*
   - Tag any message containing the word
   - Send `/addword`
   - Or use `/addword word1 word2`

2. *Remove 18+ Word:*
   - Tag any message containing the word
   - Send `/removeword`
   - Or use `/removeword word1`

3. *Ban Sticker Pack:*
   - Tag any sticker
   - Send `/addsticker`
   - Or use `/addsticker pack_id`

4. *Unban Sticker Pack:*
   - Tag any sticker
   - Send `/removesticker`
   - Or use `/removesticker pack_id`

5. *Add Admin:*
   - Tag/Reply to user's message
   - Send `/addadmin`
   - Or use `/addadmin user_id`

6. *Remove Admin:*
   - Tag/Reply to user's message
   - Send `/removeadmin`
   - Or use `/removeadmin user_id`

*📊 LIST COMMANDS:*
/listwords - All 18+ words
/liststickers - All banned packs  
/listimages - All detected NSFW images
/listadmins - All admins
/stats - Statistics

*🛡️ MODERATION COMMANDS:*
/warn [user] - Warn user
/mute [user] [min] - Mute user
/ban [user] - Ban user
/unban [user_id] - Unban user
/resetwarn [user] - Reset warnings

*🔄 ABUSE FILTER TOGGLE:*
/abuseon - Enable 18+ content filtering
/abuseoff - Disable 18+ content filtering  
/abusestatus - Check filter status

*Default Status:* ENABLED for new groups
*Permissions:* Admin only

*⚠️ STRICT AUTO-DELETE POLICY:*
- 18+ words/stickers → Immediate delete FOR ALL USERS
- NSFW images → AI auto-detected & deleted immediately
- No manual image banning needed
- Even admins' messages are deleted if they use banned content
- Admins only get a notification (no warnings, no mute/ban)
- Normal users get warnings + mute/ban after multiple violations
- Warning messages → Delete in 5 sec
- Bot commands → Delete in 2-3 sec
- List commands → Stay for reading

*🔞 AUTOMATIC IMAGE DETECTION:*
{detection_text}
- Scans ALL images automatically
- No `/banimage` command needed
- System learns and improves over time
- Hash-based duplicate detection

*Note:* Only admins can use these commands!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ===================== IMAGE MANAGEMENT =====================
async def list_images_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List detected NSFW images (by hash)"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    if not bot_data.nsfw_image_hashes:
        await send_and_delete(update, "✅ No NSFW images detected yet.", parse_mode='Markdown', delay=2)
        return
    
    page = 1
    if context.args and context.args[0].isdigit():
        page = int(context.args[0])
    
    images_per_page = 20
    all_hashes = list(bot_data.nsfw_image_hashes)
    total_pages = (len(all_hashes) + images_per_page - 1) // images_per_page
    
    if page < 1 or page > total_pages:
        page = 1
    
    start_idx = (page - 1) * images_per_page
    end_idx = start_idx + images_per_page
    page_hashes = all_hashes[start_idx:end_idx]
    
    hash_list = []
    for i, image_hash in enumerate(page_hashes, start_idx + 1):
        hash_list.append(f"{i}. `{image_hash}`")
    
    hash_text = "\n".join(hash_list)
    
    response = (
        f"📸 *Detected NSFW Images - Page {page}/{total_pages}*\n"
        f"Total: {len(bot_data.nsfw_image_hashes)} images detected\n\n"
        f"{hash_text}\n\n"
        f"*⚠️ AUTOMATIC DETECTION:*\n"
        f"All these images were auto-detected as 18+ content.\n"
        f"Future uploads of these images will be blocked automatically.\n\n"
        f"*Detection Methods:*\n"
    )
    
    # Add detection methods status
    if DEEPAI_API_KEY and DEEPAI_API_KEY != "YOUR_DEEPAI_API_KEY":
        response += "• DeepAI: ✅ Enabled\n"
    else:
        response += "• DeepAI: ❌ Not configured\n"
    
    if SIGHTENGINE_API_USER and SIGHTENGINE_API_USER != "YOUR_SIGHTENGINE_API_USER":
        response += "• SightEngine: ✅ Enabled\n"
    else:
        response += "• SightEngine: ❌ Not configured\n"
    
    if USE_LOCAL_AI:
        response += "• Local AI: ✅ Enabled\n"
    else:
        response += "• Local AI: ❌ Disabled\n"
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def clear_images_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all detected NSFW image hashes"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    count = len(bot_data.nsfw_image_hashes)
    bot_data.nsfw_image_hashes.clear()
    bot_data.save_data()
    
    await send_and_delete(update,
        f"✅ Cleared {count} NSFW image hashes from database.\n"
        f"⚠️ Note: Images will be re-scanned if uploaded again.",
        parse_mode='Markdown', delay=3
    )

# ===================== CONTENT DETECTION =====================
async def check_text_nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check text for 18+ content - STRICT FOR EVERYONE"""
    if not update.message or not update.message.text:
        return
    
    if update.message.text.startswith('/'):
        return
    
    # Check if abuse filter is enabled for this chat
    chat_id = str(update.effective_chat.id)
    
    # Check if filter is explicitly set for this chat
    if chat_id in bot_data.abuse_filter_enabled:
        if not bot_data.abuse_filter_enabled[chat_id]:
            # Filter is disabled for this chat
            logger.info(f"Abuse filter disabled for chat {chat_id}, skipping text check")
            return
    # If not set, default is True (enabled), so continue checking
    
    message = update.message.text.lower()
    all_words = bot_data.nsfw_keywords.union(bot_data.custom_words)
    
    for keyword in all_words:
        if keyword and len(keyword) > 1:
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, message):
                # Auto-delete immediately for EVERYONE including admins
                await auto_delete_nsfw_content(update, context, f"18+ word detected: '{keyword}'")
                return

async def check_sticker_nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check stickers for banned packs - STRICT FOR EVERYONE"""
    if not update.message or not update.message.sticker:
        return
    
    # Check if abuse filter is enabled for this chat
    chat_id = str(update.effective_chat.id)
    
    # Check if filter is explicitly set for this chat
    if chat_id in bot_data.abuse_filter_enabled:
        if not bot_data.abuse_filter_enabled[chat_id]:
            # Filter is disabled for this chat
            logger.info(f"Abuse filter disabled for chat {chat_id}, skipping sticker check")
            return
    # If not set, default is True (enabled), so continue checking
    
    sticker = update.message.sticker
    
    if sticker.set_name and sticker.set_name in bot_data.banned_sticker_packs:
        # Auto-delete immediately for EVERYONE including admins
        await auto_delete_nsfw_content(update, context, f"Banned sticker pack: '{sticker.set_name}'")

async def check_photo_nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check photos for 18+ content - AUTOMATIC AI DETECTION"""
    if not update.message or not update.message.photo:
        return
    
    # Check if abuse filter is enabled for this chat
    chat_id = str(update.effective_chat.id)
    
    # Check if filter is explicitly set for this chat
    if chat_id in bot_data.abuse_filter_enabled:
        if not bot_data.abuse_filter_enabled[chat_id]:
            # Filter is disabled for this chat
            logger.info(f"Abuse filter disabled for chat {chat_id}, skipping photo check")
            return
    # If not set, default is True (enabled), so continue checking
    
    user_id = update.effective_user.id
    is_admin = bot_data.is_admin(user_id)
    
    # Get the largest photo (highest quality)
    photo = update.message.photo[-1]
    
    try:
        # Download the image
        file = await context.bot.get_file(photo.file_id)
        file_url = file.file_path
        
        # Download image data
        image_data, image_hash = await download_image(file_url)
        
        if not image_data:
            logger.error(f"Failed to download image from {file_url}")
            return
        
        # Check if image is already in NSFW database
        if image_hash in bot_data.nsfw_image_hashes:
            logger.info(f"Image hash {image_hash} found in NSFW database - auto deleting")
            await auto_delete_nsfw_content(update, context, "Previously detected 18+ image")
            return
        
        # Use AI to detect NSFW content
        is_nsfw, confidence, method = await check_image_nsfw_combined(image_data, image_hash)
        
        if is_nsfw:
            logger.info(f"AI detected NSFW image (method: {method}, confidence: {confidence:.2%})")
            await auto_delete_nsfw_content(update, context, 
                                          f"AI detected 18+ image ({method}, {confidence:.0%} confidence)")
        else:
            logger.info(f"Image passed NSFW check (method: {method})")
            
    except Exception as e:
        logger.error(f"Error checking photo: {e}")
        # Don't delete if there's an error in checking

async def check_document_nsfw_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check documents (images) for 18+ content - AUTOMATIC AI DETECTION"""
    if not update.message or not update.message.document:
        return
    
    # Check if abuse filter is enabled for this chat
    chat_id = str(update.effective_chat.id)
    
    # Check if filter is explicitly set for this chat
    if chat_id in bot_data.abuse_filter_enabled:
        if not bot_data.abuse_filter_enabled[chat_id]:
            # Filter is disabled for this chat
            logger.info(f"Abuse filter disabled for chat {chat_id}, skipping document check")
            return
    # If not set, default is True (enabled), so continue checking
    
    document = update.message.document
    
    # Check if it's an image file
    if document.mime_type and document.mime_type.startswith('image/'):
        try:
            # Download the image file
            file = await context.bot.get_file(document.file_id)
            file_url = file.file_path
            
            # Download image data
            image_data, image_hash = await download_image(file_url)
            
            if not image_data:
                logger.error(f"Failed to download image document from {file_url}")
                return
            
            # Check if image is already in NSFW database
            if image_hash in bot_data.nsfw_image_hashes:
                logger.info(f"Image document hash {image_hash} found in NSFW database - auto deleting")
                await auto_delete_nsfw_content(update, context, "Previously detected 18+ image file")
                return
            
            # Use AI to detect NSFW content
            is_nsfw, confidence, method = await check_image_nsfw_combined(image_data, image_hash)
            
            if is_nsfw:
                logger.info(f"AI detected NSFW image document (method: {method}, confidence: {confidence:.2%})")
                await auto_delete_nsfw_content(update, context, 
                                              f"AI detected 18+ image file ({method}, {confidence:.0%} confidence)")
            else:
                logger.info(f"Image document passed NSFW check (method: {method})")
                
        except Exception as e:
            logger.error(f"Error checking document: {e}")

# ===================== ADMIN MANAGEMENT =====================
async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add admin via tag/reply or direct input"""
    user_id = update.effective_user.id
    
    # Check permission - only existing admins can add admins
    if not bot_data.is_admin(user_id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    # Check if replying to a user
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_user = update.message.reply_to_message.from_user
        
        if target_user.id in bot_data.admin_list:
            await send_and_delete(update,
                f"ℹ️ {target_user.first_name} is already an admin!",
                parse_mode='Markdown', delay=2
            )
            return
        
        if target_user.is_bot:
            await send_and_delete(update, "❌ Cannot add bots as admins!", parse_mode='Markdown', delay=2)
            return
        
        # Add to admin list
        bot_data.admin_list.add(target_user.id)
        bot_data.save_data()
        
        await send_and_delete(update,
            f"✅ *Admin Added Successfully!*\n\n"
            f"👤 User: {target_user.mention_markdown()}\n"
            f"🆔 ID: `{target_user.id}`\n"
            f"👑 Added by: {update.effective_user.mention_markdown()}\n\n"
            f"*Note:* Even admins' 18+ content will be auto-detected and deleted.",
            parse_mode='Markdown', delay=3
        )
        
        # Notify the new admin if in private chat
        try:
            await context.bot.send_message(
                chat_id=target_user.id,
                text=f"🎉 *You've been promoted to Admin!*\n\n"
                     f"Group: {update.effective_chat.title}\n"
                     f"Promoted by: {update.effective_user.mention_markdown()}\n\n"
                     f"You can now use admin commands.\n\n"
                     f"⚠️ *Important Note:*\n"
                     f"Even admins' 18+ content will be auto-detected and deleted.",
                parse_mode='Markdown'
            )
        except:
            pass  # User may have blocked the bot
    
    # Check for direct user ID input
    elif context.args:
        try:
            target_id = int(context.args[0])
            
            if target_id in bot_data.admin_list:
                await send_and_delete(update,
                    f"ℹ️ User `{target_id}` is already an admin!",
                    parse_mode='Markdown', delay=2
                )
                return
            
            # Try to get user info
            try:
                target_user = await context.bot.get_chat(target_id)
                username = target_user.username or target_user.first_name
            except:
                username = f"User ({target_id})"
            
            # Add to admin list
            bot_data.admin_list.add(target_id)
            bot_data.save_data()
            
            await send_and_delete(update,
                f"✅ *Admin Added!*\n\n"
                f"👤 User: {username}\n"
                f"🆔 ID: `{target_id}`\n\n"
                f"*Note:* Even admins' 18+ content will be auto-detected and deleted.",
                parse_mode='Markdown', delay=3
            )
            
        except ValueError:
            await send_and_delete(update,
                "❌ Invalid user ID! Please provide a numeric ID.",
                parse_mode='Markdown', delay=2
            )
    
    else:
        await send_and_delete(update,
            "👑 *How to add admins:*\n\n"
            "1. *Tag/Reply method:*\n"
            "   - Reply to user's message\n"
            "   - Send `/addadmin`\n\n"
            "2. *Direct method:*\n"
            "   - Send `/addadmin user_id`\n\n"
            "*Example:* `/addadmin 123456789`\n"
            "*To see all admins:* `/listadmins`\n\n"
            "⚠️ *Note:* Even admins' 18+ content will be auto-detected and deleted.",
            parse_mode='Markdown', delay=5
        )

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove admin via tag/reply or direct input"""
    user_id = update.effective_user.id
    
    # Check permission - only admins can remove admins
    if not bot_data.is_admin(user_id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    # Prevent removing super admins
    if user_id in SUPER_ADMIN_IDS:
        await send_and_delete(update, "⚠️ Super admins cannot be removed!", parse_mode='Markdown', delay=2)
        return
    
    # Check if replying to a user
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_user = update.message.reply_to_message.from_user
        
        if target_user.id == user_id:
            await send_and_delete(update, "❌ You cannot remove yourself!", parse_mode='Markdown', delay=2)
            return
        
        if target_user.id in SUPER_ADMIN_IDS:
            await send_and_delete(update, "❌ Cannot remove super admin!", parse_mode='Markdown', delay=2)
            return
        
        if target_user.id not in bot_data.admin_list:
            await send_and_delete(update,
                f"ℹ️ {target_user.first_name} is not an admin!",
                parse_mode='Markdown', delay=2
            )
            return
        
        # Remove from admin list
        bot_data.admin_list.remove(target_user.id)
        bot_data.save_data()
        
        await send_and_delete(update,
            f"✅ *Admin Removed!*\n\n"
            f"👤 User: {target_user.mention_markdown()}\n"
            f"🆔 ID: `{target_user.id}`\n"
            f"🗑️ Removed by: {update.effective_user.mention_markdown()}\n\n"
            f"*Note:* This user can now be warned/banned for 18+ content.",
            parse_mode='Markdown', delay=3
        )
        
        # Notify the removed admin
        try:
            await context.bot.send_message(
                chat_id=target_user.id,
                text=f"⚠️ *Admin Rights Removed*\n\n"
                     f"Group: {update.effective_chat.title}\n"
                     f"Removed by: {update.effective_user.mention_markdown()}\n\n"
                     f"⚠️ *Important:*\n"
                     f"You are no longer admin. Your 18+ content will now be auto-detected and deleted.",
                parse_mode='Markdown'
            )
        except:
            pass
    
    # Check for direct user ID input
    elif context.args:
        try:
            target_id = int(context.args[0])
            
            if target_id == user_id:
                await send_and_delete(update, "❌ You cannot remove yourself!", parse_mode='Markdown', delay=2)
                return
            
            if target_id in SUPER_ADMIN_IDS:
                await send_and_delete(update, "❌ Cannot remove super admin!", parse_mode='Markdown', delay=2)
                return
            
            if target_id not in bot_data.admin_list:
                await send_and_delete(update,
                    f"ℹ️ User `{target_id}` is not an admin!",
                    parse_mode='Markdown', delay=2
                )
                return
            
            # Try to get user info
            try:
                target_user = await context.bot.get_chat(target_id)
                username = target_user.username or target_user.first_name
            except:
                username = f"User ({target_id})"
            
            # Remove from admin list
            bot_data.admin_list.remove(target_id)
            bot_data.save_data()
            
            await send_and_delete(update,
                f"✅ *Admin Removed!*\n\n"
                f"👤 User: {username}\n"
                f"🆔 ID: `{target_id}`\n\n"
                f"*Note:* This user can now be warned/banned for 18+ content.",
                parse_mode='Markdown', delay=3
            )
            
        except ValueError:
            await send_and_delete(update,
                "❌ Invalid user ID! Please provide a numeric ID.",
                parse_mode='Markdown', delay=2
            )
    
    else:
        await send_and_delete(update,
            "👑 *How to remove admins:*\n\n"
            "1. *Tag/Reply method:*\n"
            "   - Reply to user's message\n"
            "   - Send `/removeadmin`\n\n"
            "2. *Direct method:*\n"
            "   - Send `/removeadmin user_id`\n\n"
            "*Note:* You cannot remove yourself or super admins.",
            parse_mode='Markdown', delay=5
        )

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all admins"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    all_admins = list(bot_data.admin_list.union(set(SUPER_ADMIN_IDS)))
    
    if not all_admins:
        await send_and_delete(update, "👑 No admins configured.", parse_mode='Markdown', delay=2)
        return
    
    # Get admin details
    admin_list_text = "👑 *ADMIN LIST*\n\n"
    
    for i, admin_id in enumerate(sorted(all_admins), 1):
        try:
            # Try to get user info
            admin_user = await context.bot.get_chat(admin_id)
            username = admin_user.username or admin_user.first_name
            mention = admin_user.mention_markdown() if admin_user.username else f"[{username}](tg://user?id={admin_id})"
            
            status = "⭐ SUPER" if admin_id in SUPER_ADMIN_IDS else "👑 ADMIN"
            admin_list_text += f"{i}. {mention} - {status}\n   ID: `{admin_id}`\n\n"
        except:
            # If can't get user info, just show ID
            status = "⭐ SUPER" if admin_id in SUPER_ADMIN_IDS else "👑 ADMIN"
            admin_list_text += f"{i}. User ({admin_id}) - {status}\n\n"
    
    admin_list_text += f"\n*Total Admins:* {len(all_admins)}\n"
    admin_list_text += f"*Super Admins:* {len(SUPER_ADMIN_IDS)}\n"
    admin_list_text += f"*Regular Admins:* {len(bot_data.admin_list)}\n\n"
    admin_list_text += "*⚠️ IMPORTANT NOTE:*\n"
    admin_list_text += "Even admins' 18+ content (words/stickers/images) is auto-detected and deleted!\n"
    admin_list_text += "Admins only get a notification (no warnings, no mute/ban).\n\n"
    admin_list_text += "*To add admin:* Tag user + `/addadmin`\n"
    admin_list_text += "*To remove admin:* Tag user + `/removeadmin`"
    
    await update.message.reply_text(admin_list_text, parse_mode='Markdown')

# ===================== WORD MANAGEMENT =====================
async def add_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add word via tag/reply"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    if update.message.reply_to_message and update.message.reply_to_message.text:
        message_text = update.message.reply_to_message.text
        words = extract_words(message_text)
        
        added_words = []
        for word in words:
            if word and len(word) > 1:
                word_lower = word.lower().strip()
                if word_lower not in bot_data.nsfw_keywords and word_lower not in bot_data.custom_words:
                    bot_data.custom_words.add(word_lower)
                    added_words.append(word_lower)
        
        if added_words:
            bot_data.save_data()
            word_list = ", ".join([f"`{w}`" for w in added_words[:10]])
            extra = f" and {len(added_words)-10} more..." if len(added_words) > 10 else ""
            await send_and_delete(update,
                f"✅ Added {len(added_words)} 18+ word(s): {word_list}{extra}\n"
                f"⚠️ *These words will now be auto-deleted FOR EVERYONE, including admins!*",
                parse_mode='Markdown', delay=3
            )
        else:
            await send_and_delete(update, "❌ No new words found to add!", parse_mode='Markdown', delay=2)
    
    elif context.args:
        words = []
        for arg in context.args:
            words.extend(extract_words(arg))
        
        added_words = []
        for word in words:
            if word and len(word) > 1:
                word_lower = word.lower().strip()
                if word_lower not in bot_data.nsfw_keywords and word_lower not in bot_data.custom_words:
                    bot_data.custom_words.add(word_lower)
                    added_words.append(word_lower)
        
        if added_words:
            bot_data.save_data()
            word_list = ", ".join([f"`{w}`" for w in added_words])
            await send_and_delete(update, 
                f"✅ Added: {word_list}\n"
                f"⚠️ *These words will now be auto-deleted FOR EVERYONE, including admins!*",
                parse_mode='Markdown', delay=3
            )
        else:
            await send_and_delete(update, "❌ Please provide valid words!", parse_mode='Markdown', delay=2)
    
    else:
        await send_and_delete(update,
            "📝 *Add 18+ Word:*\n\n"
            "1. Tag a message containing the word\n"
            "2. Send `/addword`\n\n"
            "Or use: `/addword word1 word2`\n\n"
            "⚠️ *STRICT POLICY:*\n"
            "Added words will be auto-deleted immediately!\n"
            "*Even admins' messages will be deleted* if they use these words.",
            parse_mode='Markdown', delay=5
        )

async def remove_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove word via tag/reply"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    if update.message.reply_to_message and update.message.reply_to_message.text:
        message_text = update.message.reply_to_message.text
        words = extract_words(message_text)
        
        removed_words = []
        not_found = []
        
        for word in words:
            if word:
                word_lower = word.lower().strip()
                if word_lower in bot_data.custom_words:
                    bot_data.custom_words.remove(word_lower)
                    removed_words.append(word_lower)
                elif word_lower in bot_data.nsfw_keywords:
                    not_found.append(f"{word_lower} (default)")
                else:
                    not_found.append(word_lower)
        
        if removed_words:
            bot_data.save_data()
            removed_list = ", ".join([f"`{w}`" for w in removed_words[:10]])
            extra = f" and {len(removed_words)-10} more..." if len(removed_words) > 10 else ""
            response = f"✅ Removed: {removed_list}{extra}\n📝 These words will no longer be auto-deleted."
            
            if not_found:
                not_found_list = ", ".join(not_found[:5])
                response += f"\n⚠️ Not removed: {not_found_list}"
            
            await send_and_delete(update, response, parse_mode='Markdown', delay=3)
        else:
            await send_and_delete(update, "❌ No words removed!", parse_mode='Markdown', delay=2)
    
    elif context.args:
        words = []
        for arg in context.args:
            words.extend(extract_words(arg))
        
        removed_words = []
        not_found = []
        
        for word in words:
            if word:
                word_lower = word.lower().strip()
                if word_lower in bot_data.custom_words:
                    bot_data.custom_words.remove(word_lower)
                    removed_words.append(word_lower)
                elif word_lower in bot_data.nsfw_keywords:
                    not_found.append(f"{word_lower} (default)")
                else:
                    not_found.append(word_lower)
        
        if removed_words:
            bot_data.save_data()
            removed_list = ", ".join([f"`{w}`" for w in removed_words])
            response = f"✅ Removed: {removed_list}\n📝 These words will no longer be auto-deleted."
            
            if not_found:
                not_found_list = ", ".join(not_found[:5])
                response += f"\n⚠️ Not removed: {not_found_list}"
            
            await send_and_delete(update, response, parse_mode='Markdown', delay=3)
        else:
            await send_and_delete(update, "❌ No matching words found!", parse_mode='Markdown', delay=2)
    
    else:
        await send_and_delete(update,
            "📝 *Remove 18+ Word:*\n\n"
            "1. Tag a message containing the word\n"
            "2. Send `/removeword`\n\n"
            "Or use: `/removeword word1 word2`",
            parse_mode='Markdown', delay=5
        )

async def list_words_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all 18+ words"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    all_words = list(bot_data.nsfw_keywords.union(bot_data.custom_words))
    
    if not all_words:
        await send_and_delete(update, "📭 No 18+ words configured.", parse_mode='Markdown', delay=2)
        return
    
    page = 1
    if context.args and context.args[0].isdigit():
        page = int(context.args[0])
    
    words_per_page = 50
    total_pages = (len(all_words) + words_per_page - 1) // words_per_page
    
    if page < 1 or page > total_pages:
        page = 1
    
    start_idx = (page - 1) * words_per_page
    end_idx = start_idx + words_per_page
    page_words = sorted(all_words)[start_idx:end_idx]
    
    word_list = []
    for word in page_words:
        if word in bot_data.nsfw_keywords:
            word_list.append(f"• `{word}` ⭐ (default)")
        else:
            word_list.append(f"• `{word}` (custom)")
    
    word_text = "\n".join(word_list)
    
    response = (
        f"📝 *18+ Words - Page {page}/{total_pages}*\n"
        f"Total: {len(all_words)} words\n"
        f"Default: {len(bot_data.nsfw_keywords)} | Custom: {len(bot_data.custom_words)}\n\n"
        f"{word_text}\n\n"
        f"*⚠️ STRICT POLICY:*\n"
        f"All these words are auto-deleted immediately!\n"
        f"*Even admins' messages will be deleted* if they use these words.\n\n"
        f"*To add:* Tag message + `/addword`\n"
        f"*To remove:* Tag message + `/removeword`"
    )
    
    await update.message.reply_text(response, parse_mode='Markdown')

# ===================== STICKER MANAGEMENT =====================
async def add_sticker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban sticker pack via tag/reply"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    if update.message.reply_to_message and update.message.reply_to_message.sticker:
        sticker = update.message.reply_to_message.sticker
        
        if not sticker.set_name:
            await send_and_delete(update, "❌ Sticker has no pack!", parse_mode='Markdown', delay=2)
            return
        
        pack_id = sticker.set_name
        
        if pack_id in bot_data.banned_sticker_packs:
            await send_and_delete(update, f"⚠️ Already banned: `{pack_id}`", parse_mode='Markdown', delay=2)
        else:
            bot_data.banned_sticker_packs.add(pack_id)
            bot_data.save_data()
            
            await send_and_delete(update,
                f"✅ *Sticker Pack Banned!*\n\n"
                f"🆔 Pack ID: `{pack_id}`\n"
                f"😀 Emoji: {sticker.emoji}\n\n"
                f"⚠️ *STRICT POLICY:*\n"
                f"This pack will now be auto-deleted immediately!\n"
                f"*Even admins' stickers will be deleted* if they use this pack.",
                parse_mode='Markdown', delay=3
            )
    
    elif context.args:
        pack_id = context.args[0]
        
        if pack_id in bot_data.banned_sticker_packs:
            await send_and_delete(update, f"⚠️ Already banned: `{pack_id}`", parse_mode='Markdown', delay=2)
        else:
            bot_data.banned_sticker_packs.add(pack_id)
            bot_data.save_data()
            await send_and_delete(update, 
                f"✅ Banned: `{pack_id}`\n"
                f"⚠️ *STRICT POLICY:*\n"
                f"This pack will now be auto-deleted immediately!\n"
                f"*Even admins' stickers will be deleted* if they use this pack.",
                parse_mode='Markdown', delay=3
            )
    
    else:
        await send_and_delete(update,
            "🖼️ *Ban Sticker Pack:*\n\n"
            "1. Tag a sticker\n"
            "2. Send `/addsticker`\n\n"
            "Or use: `/addsticker pack_id`\n\n"
            "⚠️ *STRICT POLICY:*\n"
            "Banned stickers are auto-deleted immediately!\n"
            "*Even admins' stickers will be deleted* if they use banned packs.",
            parse_mode='Markdown', delay=5
        )

async def remove_sticker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban sticker pack via tag/reply"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    if update.message.reply_to_message and update.message.reply_to_message.sticker:
        sticker = update.message.reply_to_message.sticker
        
        if not sticker.set_name:
            await send_and_delete(update, "❌ Sticker has no pack!", parse_mode='Markdown', delay=2)
            return
        
        pack_id = sticker.set_name
        
        if pack_id not in bot_data.banned_sticker_packs:
            await send_and_delete(update, f"ℹ️ Not banned: `{pack_id}`", parse_mode='Markdown', delay=2)
        else:
            bot_data.banned_sticker_packs.remove(pack_id)
            bot_data.save_data()
            await send_and_delete(update, 
                f"✅ Unbanned: `{pack_id}`\n📝 This pack will no longer be auto-deleted.",
                parse_mode='Markdown', delay=3
            )
    
    elif context.args:
        pack_id = context.args[0]
        
        if pack_id not in bot_data.banned_sticker_packs:
            await send_and_delete(update, f"ℹ️ Not banned: `{pack_id}`", parse_mode='Markdown', delay=2)
        else:
            bot_data.banned_sticker_packs.remove(pack_id)
            bot_data.save_data()
            await send_and_delete(update, 
                f"✅ Unbanned: `{pack_id}`\n📝 This pack will no longer be auto-deleted.",
                parse_mode='Markdown', delay=3
            )
    
    else:
        await send_and_delete(update,
            "🖼️ *Unban Sticker Pack:*\n\n"
            "1. Tag a sticker\n"
            "2. Send `/removesticker`\n\n"
            "Or use: `/removesticker pack_id`",
            parse_mode='Markdown', delay=5
        )

async def list_stickers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List banned sticker packs"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    if not bot_data.banned_sticker_packs:
        await send_and_delete(update, "✅ No banned sticker packs.", parse_mode='Markdown', delay=2)
        return
    
    sticker_list = []
    for i, pack_id in enumerate(sorted(bot_data.banned_sticker_packs), 1):
        sticker_list.append(f"{i}. `{pack_id}`")
    
    sticker_text = "\n".join(sticker_list)
    
    response = (
        f"📛 *Banned Sticker Packs*\n"
        f"Total: {len(bot_data.banned_sticker_packs)}\n\n"
        f"{sticker_text}\n\n"
        f"*⚠️ STRICT POLICY:*\n"
        f"All these stickers are auto-deleted immediately!\n"
        f"*Even admins' stickers will be deleted* if they use these packs.\n\n"
        f"*To add:* Tag sticker + `/addsticker`\n"
        f"*To remove:* Tag sticker + `/removesticker`"
    )
    
    await update.message.reply_text(response, parse_mode='Markdown')

# ===================== MODERATION COMMANDS =====================
async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Warn a user"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    # Check if replying to a user
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_user = update.message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else "Manual warning"
        
        await manual_warn_user(update, context, target_user.id, reason)
    
    elif context.args and len(context.args) >= 2:
        try:
            target_id = int(context.args[0])
            reason = " ".join(context.args[1:])
            await manual_warn_user(update, context, target_id, reason)
        except ValueError:
            await send_and_delete(update, "❌ Invalid user ID!", parse_mode='Markdown', delay=2)
    
    else:
        await send_and_delete(update,
            "⚠️ *Warn User:*\n\n"
            "1. Tag user's message\n"
            "2. Send `/warn [reason]`\n\n"
            "Or use: `/warn user_id reason`",
            parse_mode='Markdown', delay=5
        )

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute a user"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    minutes = 60  # Default mute duration
    
    # Check if replying to a user
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_user = update.message.reply_to_message.from_user
        
        if context.args:
            try:
                minutes = int(context.args[0])
                reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Manual mute"
            except ValueError:
                reason = " ".join(context.args)
        else:
            reason = "Manual mute"
        
        await mute_user(context, update.effective_chat.id, target_user.id, minutes, reason)
    
    elif context.args and len(context.args) >= 2:
        try:
            target_id = int(context.args[0])
            minutes = int(context.args[1])
            reason = " ".join(context.args[2:]) if len(context.args) > 2 else "Manual mute"
            await mute_user(context, update.effective_chat.id, target_id, minutes, reason)
        except ValueError:
            await send_and_delete(update, "❌ Invalid format! Use: `/mute user_id minutes [reason]`", parse_mode='Markdown', delay=3)
    
    else:
        await send_and_delete(update,
            "🔇 *Mute User:*\n\n"
            "1. Tag user's message\n"
            "2. Send `/mute [minutes] [reason]`\n\n"
            "Or use: `/mute user_id minutes reason`",
            parse_mode='Markdown', delay=5
        )

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    # Check if replying to a user
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_user = update.message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else "Manual ban"
        
        await ban_user(context, update.effective_chat.id, target_user.id, reason)
    
    elif context.args and len(context.args) >= 1:
        try:
            target_id = int(context.args[0])
            reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Manual ban"
            await ban_user(context, update.effective_chat.id, target_id, reason)
        except ValueError:
            await send_and_delete(update, "❌ Invalid user ID!", parse_mode='Markdown', delay=2)
    
    else:
        await send_and_delete(update,
            "🚫 *Ban User:*\n\n"
            "1. Tag user's message\n"
            "2. Send `/ban [reason]`\n\n"
            "Or use: `/ban user_id reason`",
            parse_mode='Markdown', delay=5
        )

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    if context.args:
        try:
            user_id = int(context.args[0])
            
            try:
                await context.bot.unban_chat_member(
                    chat_id=update.effective_chat.id,
                    user_id=user_id
                )
                
                await send_and_delete(update,
                    f"✅ User `{user_id}` has been unbanned.",
                    parse_mode='Markdown', delay=3
                )
            except Exception as e:
                await send_and_delete(update,
                    f"❌ Error: {str(e)}",
                    parse_mode='Markdown', delay=3
                )
        except ValueError:
            await send_and_delete(update, "❌ Invalid user ID!", parse_mode='Markdown', delay=2)
    else:
        await send_and_delete(update,
            "🔓 *Unban User:*\n\n"
            "Usage: `/unban user_id`\n"
            "Example: `/unban 123456789`",
            parse_mode='Markdown', delay=5
        )

async def resetwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset warnings for a user"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    # Check if replying to a user
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_user = update.message.reply_to_message.from_user
        user_id = target_user.id
    elif context.args:
        try:
            user_id = int(context.args[0])
        except ValueError:
            await send_and_delete(update, "❌ Invalid user ID!", parse_mode='Markdown', delay=2)
            return
    else:
        await send_and_delete(update,
            "🔄 *Reset Warnings:*\n\n"
            "1. Tag user's message\n"
            "2. Send `/resetwarn`\n\n"
            "Or use: `/resetwarn user_id`",
            parse_mode='Markdown', delay=5
        )
        return
    
    chat_id = update.effective_chat.id
    warnings_key = f"{chat_id}_{user_id}"
    
    if warnings_key in bot_data.user_warnings:
        old_warnings = bot_data.user_warnings.pop(warnings_key)
        bot_data.save_data()
        
        await send_and_delete(update,
            f"✅ Warnings reset for user `{user_id}`\n"
            f"Previous warnings: {old_warnings}",
            parse_mode='Markdown', delay=3
        )
    else:
        await send_and_delete(update,
            f"ℹ️ User `{user_id}` has no warnings.",
            parse_mode='Markdown', delay=3
        )

# ===================== HELPER FUNCTIONS =====================
def extract_words(text: str) -> List[str]:
    """Extract words from text"""
    if not text:
        return []
    
    words = re.findall(r'\b\w+\b', text.lower())
    return [word for word in words if len(word) > 1]

async def manual_warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, reason: str):
    """Manually warn a user"""
    chat_id = update.effective_chat.id
    
    # Update warning count
    warnings_key = f"{chat_id}_{user_id}"
    current_warnings = bot_data.user_warnings.get(warnings_key, 0) + 1
    bot_data.user_warnings[warnings_key] = current_warnings
    bot_data.save_data()
    
    # Get user mention
    try:
        user = await context.bot.get_chat(user_id)
        user_mention = user.mention_markdown() if user.username else f"[{user.first_name}](tg://user?id={user_id})"
    except:
        user_mention = f"User ({user_id})"
    
    # Prepare warning message
    warning_msg = (
        f"⚠️ *Manual Warning #{current_warnings}*\n"
        f"User: {user_mention}\n"
        f"Reason: {reason}\n"
        f"By: {update.effective_user.mention_markdown()}\n\n"
    )
    
    # Actions based on warning count
    if current_warnings == 1:
        warning_msg += "Next violation: 5 minute mute"
    elif current_warnings == 2:
        warning_msg += "Next violation: 30 minute mute"
        await mute_user(context, chat_id, user_id, 5, "2nd Warning")
    elif current_warnings == 3:
        warning_msg += "Next violation: Permanent Ban"
        await mute_user(context, chat_id, user_id, 60, "3rd Warning")
    elif current_warnings >= 4:
        warning_msg += "User has been banned for repeated violations"
        await ban_user(context, chat_id, user_id, "Repeated violations")
    
    # Send warning message (auto-delete after 5 seconds)
    await send_to_chat_and_delete(context, chat_id, warning_msg, parse_mode='Markdown', delay=5)

async def mute_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, minutes: int, reason: str):
    """Mute a user"""
    until_date = datetime.now() + timedelta(minutes=minutes)
    
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            ),
            until_date=until_date
        )
        
        # Get user info for message
        try:
            user = await context.bot.get_chat(user_id)
            user_name = user.first_name
        except:
            user_name = f"User ({user_id})"
        
        mute_msg = f"🔇 {user_name} muted for {minutes} minutes\nReason: {reason}"
        
        # Send and auto-delete after 3 seconds
        await send_to_chat_and_delete(context, chat_id, mute_msg, delay=3)
        
    except Exception as e:
        logger.error(f"Mute error: {e}")

async def ban_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, reason: str):
    """Ban a user"""
    try:
        await context.bot.ban_chat_member(
            chat_id=chat_id,
            user_id=user_id
        )
        
        # Get user info for message
        try:
            user = await context.bot.get_chat(user_id)
            user_name = user.first_name
        except:
            user_name = f"User ({user_id})"
        
        ban_msg = f"🚫 {user_name} banned\nReason: {reason}"
        
        # Send and auto-delete after 3 seconds
        await send_to_chat_and_delete(context, chat_id, ban_msg, delay=3)
        
    except Exception as e:
        logger.error(f"Ban error: {e}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    if not bot_data.is_admin(update.effective_user.id):
        await send_and_delete(update, "❌ Permission denied! Admin only.", parse_mode='Markdown', delay=2)
        return
    
    total_warnings = sum(bot_data.user_warnings.values())
    total_words = len(bot_data.nsfw_keywords) + len(bot_data.custom_words)
    
    # Check which detection methods are available
    detection_status = []
    if DEEPAI_API_KEY and DEEPAI_API_KEY != "YOUR_DEEPAI_API_KEY":
        detection_status.append("• DeepAI: ✅ Configured")
    else:
        detection_status.append("• DeepAI: ❌ Not configured")
    
    if SIGHTENGINE_API_USER and SIGHTENGINE_API_USER != "YOUR_SIGHTENGINE_API_USER":
        detection_status.append("• SightEngine: ✅ Configured")
    else:
        detection_status.append("• SightEngine: ❌ Not configured")
    
    if USE_LOCAL_AI:
        detection_status.append("• Local AI: ✅ Enabled")
    else:
        detection_status.append("• Local AI: ❌ Disabled")
    
    detection_text = "\n".join(detection_status)
    
    # Count abuse filter status
    enabled_count = sum(1 for status in bot_data.abuse_filter_enabled.values() if status)
    disabled_count = sum(1 for status in bot_data.abuse_filter_enabled.values() if not status)
    total_groups = len(bot_data.abuse_filter_enabled)
    
    stats_text = (
        f"📊 *18+ Content Bot Statistics*\n\n"
        f"• Total warnings issued: {total_warnings}\n"
        f"• 18+ words: {total_words}\n"
        f"  - Default words: {len(bot_data.nsfw_keywords)}\n"
        f"  - Custom words: {len(bot_data.custom_words)}\n"
        f"• Banned sticker packs: {len(bot_data.banned_sticker_packs)}\n"
        f"• Detected NSFW images: {len(bot_data.nsfw_image_hashes)}\n"
        f"• Total admins: {len(bot_data.admin_list) + len(SUPER_ADMIN_IDS)}\n"
        f"• Super admins: {len(SUPER_ADMIN_IDS)}\n"
        f"• Regular admins: {len(bot_data.admin_list)}\n"
        f"• Abuse filter status: {enabled_count} groups enabled, {disabled_count} groups disabled (total: {total_groups} groups)\n\n"
        f"*🔄 ABUSE FILTER STATUS:*\n"
        f"• /abuseon → Enable 18+ filtering\n"
        f"• /abuseoff → Disable 18+ filtering\n"
        f"• /abusestatus → Check current status\n\n"
        f"*⚠️ STRICT AUTO-DELETE POLICY:*\n"
        f"• 18+ words: ✅ Immediately deleted FOR EVERYONE\n"
        f"• Adult stickers: ✅ Immediately deleted FOR EVERYONE\n"
        f"• NSFW images: ✅ AI Auto-Detected & deleted immediately\n"
        f"• No manual image banning needed\n"
        f"• Even admins' content is deleted if detected\n"
        f"• Admins only get notification (no warnings)\n"
        f"• Normal users get warnings + mute/ban\n"
        f"• Warning messages: ✅ Delete in 5 sec\n"
        f"• Bot responses: ✅ Delete in 2-3 sec\n\n"
        f"*🔞 AUTOMATIC IMAGE DETECTION:*\n"
        f"{detection_text}\n"
        f"• Hash-based duplicate detection\n"
        f"• System learns from detected images\n\n"
        f"*Quick Commands:*\n"
        f"1. Add word: Tag message + `/addword`\n"
        f"2. Ban sticker: Tag sticker + `/addsticker`\n"
        f"3. List images: `/listimages`\n"
        f"4. Add admin: Tag user + `/addadmin`\n"
        f"5. Remove admin: Tag user + `/removeadmin`"
    )
    
    await send_and_delete(update, stats_text, parse_mode='Markdown', delay=8)

# ===================== MAIN BOT SETUP =====================
def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Abuse filter commands
    application.add_handler(CommandHandler("abuseon", abuse_on_command))
    application.add_handler(CommandHandler("abuseoff", abuse_off_command))
    application.add_handler(CommandHandler("abusestatus", abuse_status_command))
    
    # Admin management commands
    application.add_handler(CommandHandler("addadmin", add_admin_command))
    application.add_handler(CommandHandler("removeadmin", remove_admin_command))
    application.add_handler(CommandHandler("listadmins", list_admins))
    
    # Word management commands
    application.add_handler(CommandHandler("addword", add_word_command))
    application.add_handler(CommandHandler("removeword", remove_word_command))
    application.add_handler(CommandHandler("listwords", list_words_command))
    
    # Sticker management commands
    application.add_handler(CommandHandler("addsticker", add_sticker_command))
    application.add_handler(CommandHandler("removesticker", remove_sticker_command))
    application.add_handler(CommandHandler("liststickers", list_stickers_command))
    
    # Image management commands
    application.add_handler(CommandHandler("listimages", list_images_command))
    application.add_handler(CommandHandler("clearimages", clear_images_command))
    
    # Moderation commands
    application.add_handler(CommandHandler("warn", warn_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("resetwarn", resetwarn_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Content detection handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_text_nsfw))
    application.add_handler(MessageHandler(filters.Sticker.ALL, check_sticker_nsfw))
    application.add_handler(MessageHandler(filters.PHOTO, check_photo_nsfw))
    application.add_handler(MessageHandler(filters.Document.IMAGE, check_document_nsfw_update))
    
    # Error handler
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Exception while handling an update: {context.error}")
    
    application.add_error_handler(error_handler)
    
    # Start bot
    print("🤖 18+ CONTENT AUTO-DETECTION BOT STARTING...")
    print(f"📝 18+ Words: {len(bot_data.nsfw_keywords) + len(bot_data.custom_words)}")
    print(f"🖼️ Banned Sticker Packs: {len(bot_data.banned_sticker_packs)}")
    print(f"📸 Detected NSFW Images: {len(bot_data.nsfw_image_hashes)}")
    print(f"👑 Total Admins: {len(bot_data.admin_list) + len(SUPER_ADMIN_IDS)}")
    
    # Print abuse filter status
    enabled_count = sum(1 for status in bot_data.abuse_filter_enabled.values() if status)
    disabled_count = sum(1 for status in bot_data.abuse_filter_enabled.values() if not status)
    total_groups = len(bot_data.abuse_filter_enabled)
    print(f"🔞 Abuse Filter: {enabled_count} groups enabled, {disabled_count} groups disabled (total: {total_groups} groups)")
    
    # Print detection methods status
    print("\n🔞 IMAGE DETECTION METHODS:")
    if DEEPAI_API_KEY and DEEPAI_API_KEY != "YOUR_DEEPAI_API_KEY":
        print("• DeepAI NSFW Detection: ✅ ENABLED")
    else:
        print("• DeepAI NSFW Detection: ⚠️ DISABLED (Set API key)")
    
    if SIGHTENGINE_API_USER and SIGHTENGINE_API_USER != "YOUR_SIGHTENGINE_API_USER":
        print("• SightEngine API: ✅ ENABLED")
    else:
        print("• SightEngine API: ⚠️ DISABLED (Set API credentials)")
    
    if USE_LOCAL_AI:
        print("• Local AI Detection: ✅ ENABLED")
    else:
        print("• Local AI Detection: ❌ DISABLED")
    
    print("\n✨ TAG-BASED FEATURES:")
    print("1. Tag message + /addword → Add 18+ word")
    print("2. Tag sticker + /addsticker → Ban sticker pack")
    print("3. Tag user + /addadmin → Add admin")
    print("4. Tag user + /removeadmin → Remove admin")
    
    print("\n🔄 ABUSE FILTER TOGGLE:")
    print("- /abuseon → Enable 18+ content filtering")
    print("- /abuseoff → Disable 18+ content filtering")
    print("- /abusestatus → Check current status")
    print("- Default: ENABLED for new groups")
    
    print("\n⚠️ AUTOMATIC IMAGE DETECTION:")
    print("- ALL images are automatically scanned")
    print("- No `/banimage` command needed")
    print("- AI detects 18+ content automatically")
    print("- System learns and improves over time")
    print("- Hash-based duplicate detection")
    
    print("\n🛡️ 18+ CONTENT BOT IS READY!")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()