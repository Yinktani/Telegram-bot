import json
import os
from google.oauth2.service_account import Credentials

# Google Sheets setup for production
def setup_google_sheets():
    if 'GOOGLE_CREDENTIALS' in os.environ:
        # Production: Read from environment variable
        creds_json = json.loads(os.environ['GOOGLE_CREDENTIALS'])
        credentials = Credentials.from_service_account_info(creds_json)
        gc = gspread.authorize(credentials)
    else:
        # Development: Read from local file
        gc = gspread.service_account(filename='credentials.json')
    
    return gc

# Replace your current gc = gspread.service_account(filename='credentials.json') with:
gc = setup_google_sheets()



import os
import logging
from datetime import datetime, date
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SGIBot:
    def __init__(self, spreadsheet_id, admin_user_ids):
        self.spreadsheet_id = spreadsheet_id
        self.admin_user_ids = set(map(int, admin_user_ids.split(',')))
        self.sheet = None
        self.challenge_active = True
        self.setup_google_sheets()
    
    def setup_google_sheets(self):
        """Initialize Google Sheets connection"""
        try:
            # Try environment variables first (for deployment)
            if os.getenv("GOOGLE_TYPE"):
                creds_dict = {
                    "type": os.getenv("GOOGLE_TYPE"),
                    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
                    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
                    "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),
                    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
                    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_X509_CERT_URL")
                }
                creds = Credentials.from_service_account_info(
                    creds_dict,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
            else:
                # Use local credentials file for development
                creds = Credentials.from_service_account_file(
                    'credentials.json',
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
            
            gc = gspread.authorize(creds)
            self.sheet = gc.open_by_key(self.spreadsheet_id).sheet1
            logger.info("Google Sheets connection established")
            
        except Exception as e:
            logger.error(f"Failed to setup Google Sheets: {e}")
            raise
    
    def is_admin(self, user_id):
        """Check if user is an admin"""
        return user_id in self.admin_user_ids
    
    def get_current_date_string(self):
        """Get current date as string in YYYY-MM-DD format"""
        return date.today().strftime("%Y-%m-%d")
    
    def get_current_week_string(self):
        """Get current week as string in YYYY-W## format"""
        today = date.today()
        year, week, _ = today.isocalendar()
        return f"{year}-W{week:02d}"
    
    def find_challenger(self, user_id):
        """Find challenger by Telegram user ID"""
        try:
            records = self.sheet.get_all_records()
            
            for i, record in enumerate(records, start=2):
                if str(record.get('User_ID', '')) == str(user_id):
                    return i, record
            
            return None, None
            
        except Exception as e:
            logger.error(f"Error finding challenger {user_id}: {e}")
            return None, None
    
    def register_challenger(self, user_id, first_name, group):
        """Register a new challenger"""
        try:
            # Check if already registered
            row_num, existing = self.find_challenger(user_id)
            if existing:
                return False, "You are already registered for the challenge"
            
            # Add new challenger with updated column structure
            new_row = [
                first_name,           # Name
                str(user_id),        # User_ID
                group,               # Group (Senior/Junior)
                0,                   # Current_Points
                0,                   # Strikes
                "Active",            # Status
                "",                  # Daily1_Last (last completion date)
                "",                  # Daily2_Last (last completion date)
                "",                  # Daily3_Last (last completion date)
                "",                  # Weekly1_Week (week when completed)
                ""                   # Weekly2_Week (week when completed)
            ]
            
            self.sheet.append_row(new_row)
            logger.info(f"Registered new challenger: {first_name} (ID: {user_id})")
            return True, f"Welcome {first_name}! You're registered in the {group} group"
            
        except Exception as e:
            logger.error(f"Error registering challenger: {e}")
            return False, "Unable to register. Please try again"
    
    def update_task_completion(self, user_id, task_type):
        """Update task completion for a challenger"""
        try:
            if not self.challenge_active:
                return False, "Challenge is being reset. Try again in a few minutes"
            
            row_num, challenger = self.find_challenger(user_id)
            
            if not challenger:
                return False, "You are not registered. Use /register to join the challenge"
            
            if challenger.get('Status') != 'Active':
                return False, "You have been eliminated from the challenge"
            
            current_date = self.get_current_date_string()
            current_week = self.get_current_week_string()
            
            # Map task types to new column names
            task_column_mapping = {
                'Daily1': 'Daily1_Last',
                'Daily2': 'Daily2_Last',
                'Daily3': 'Daily3_Last',
                'Weekly1': 'Weekly1_Week',
                'Weekly2': 'Weekly2_Week'
            }
            
            if task_type not in task_column_mapping:
                return False, "Invalid task type"
            
            column_name = task_column_mapping[task_type]
            last_completion = challenger.get(column_name, '')
            
            # Check if task can be completed
            if 'Daily' in task_type:
                # Daily tasks: check if completed today
                if last_completion == current_date:
                    return False, f"You already completed {task_type.lower()} today"
                points_to_add = 3
                new_completion_value = current_date
            else:
                # Weekly tasks: check if completed this week
                if last_completion == current_week:
                    return False, f"You already completed {task_type.lower()} this week"
                points_to_add = 5
                new_completion_value = current_week
            
            # Find column indices
            headers = self.sheet.row_values(1)
            task_col = None
            points_col = None
            
            for i, header in enumerate(headers, start=1):
                if header == column_name:
                    task_col = i
                elif header == 'Current_Points':
                    points_col = i
            
            if not task_col or not points_col:
                return False, "System error. Please contact admin"
            
            # Update task completion date/week
            self.sheet.update_cell(row_num, task_col, new_completion_value)
            
            # Calculate and update points
            current_points = int(challenger.get('Current_Points', 0))
            new_points = current_points + points_to_add
            self.sheet.update_cell(row_num, points_col, new_points)
            
            logger.info(f"User {user_id} completed {task_type}, added {points_to_add} points")
            return True, f"Task completed. +{points_to_add} points. Total: {new_points}"
            
        except Exception as e:
            logger.error(f"Error updating task for {user_id}: {e}")
            return False, "Unable to connect to database. Please try again in a moment"
    
    def get_challenger_status(self, user_id):
        """Get challenger's current status"""
        try:
            row_num, challenger = self.find_challenger(user_id)
            
            if not challenger:
                return "You are not registered. Use /register to join the challenge"
            
            name = challenger.get('Name', 'Unknown')
            group = challenger.get('Group', 'Unknown')
            points = challenger.get('Current_Points', 0)
            strikes = challenger.get('Strikes', 0)
            status = challenger.get('Status', 'Active')
            
            current_date = self.get_current_date_string()
            current_week = self.get_current_week_string()
            
            # Check task completion status for today/this week
            daily1_done = challenger.get('Daily1_Last') == current_date
            daily2_done = challenger.get('Daily2_Last') == current_date
            daily3_done = challenger.get('Daily3_Last') == current_date
            weekly1_done = challenger.get('Weekly1_Week') == current_week
            weekly2_done = challenger.get('Weekly2_Week') == current_week
            
            status_msg = f"""Your Progress:

Name: {name}
Group: {group}
Points: {points}
Strikes: {strikes}/2
Status: {status}

Today's Tasks (3 pts each):
Daily 1: {'Done' if daily1_done else 'Pending'}
Daily 2: {'Done' if daily2_done else 'Pending'}
Daily 3: {'Done' if daily3_done else 'Pending'}

This Week's Tasks (5 pts each):
Weekly 1: {'Done' if weekly1_done else 'Pending'}
Weekly 2: {'Done' if weekly2_done else 'Pending'}"""
            
            return status_msg
            
        except Exception as e:
            logger.error(f"Error getting status for {user_id}: {e}")
            return "Unable to connect to database. Please try again in a moment"
    
    def get_leaderboard(self):
        """Generate leaderboard"""
        try:
            records = self.sheet.get_all_records()
            
            # Separate by groups and filter active users
            senior_users = []
            junior_users = []
            
            for record in records:
                if record.get('Status') != 'Active':
                    continue
                    
                user_data = {
                    'name': record.get('Name', 'Unknown'),
                    'points': int(record.get('Current_Points', 0))
                }
                
                if record.get('Group') == 'Senior':
                    senior_users.append(user_data)
                else:
                    junior_users.append(user_data)
            
            # Sort by points
            senior_users.sort(key=lambda x: x['points'], reverse=True)
            junior_users.sort(key=lambda x: x['points'], reverse=True)
            
            # Build leaderboard message
            msg = "SGI Challenge Leaderboard:\n\n"
            
            if senior_users:
                msg += "Senior Group:\n"
                for i, user in enumerate(senior_users[:10], 1):
                    msg += f"{i}. {user['name']}: {user['points']} pts\n"
                msg += "\n"
            
            if junior_users:
                msg += "Junior Group:\n"
                for i, user in enumerate(junior_users[:10], 1):
                    msg += f"{i}. {user['name']}: {user['points']} pts\n"
            
            return msg if senior_users or junior_users else "No active challengers found"
            
        except Exception as e:
            logger.error(f"Error generating leaderboard: {e}")
            return "Unable to connect to database. Please try again in a moment"
    
    def add_strike(self, user_id, reason):
        """Add strike to a user (admin only)"""
        try:
            row_num, challenger = self.find_challenger(user_id)
            
            if not challenger:
                return False, "User not found"
            
            current_strikes = int(challenger.get('Strikes', 0))
            new_strikes = current_strikes + 1
            
            # Find column indices
            headers = self.sheet.row_values(1)
            strikes_col = None
            status_col = None
            
            for i, header in enumerate(headers, start=1):
                if header == 'Strikes':
                    strikes_col = i
                elif header == 'Status':
                    status_col = i
            
            # Update strikes
            self.sheet.update_cell(row_num, strikes_col, new_strikes)
            
            # Check for elimination
            if new_strikes >= 2:
                self.sheet.update_cell(row_num, status_col, 'Eliminated')
                status_msg = f"Strike added. User eliminated (2/2 strikes). Reason: {reason}"
            else:
                status_msg = f"Strike added ({new_strikes}/2). Reason: {reason}"
            
            logger.info(f"Strike added to user {user_id}: {reason}")
            return True, status_msg
            
        except Exception as e:
            logger.error(f"Error adding strike: {e}")
            return False, "Unable to connect to database. Please try again in a moment"
    
    def remove_strike(self, user_id):
        """Remove strike from a user (admin only)"""
        try:
            row_num, challenger = self.find_challenger(user_id)
            
            if not challenger:
                return False, "User not found"
            
            current_strikes = int(challenger.get('Strikes', 0))
            
            if current_strikes <= 0:
                return False, "User has no strikes to remove"
            
            new_strikes = current_strikes - 1
            
            # Find column indices
            headers = self.sheet.row_values(1)
            strikes_col = None
            status_col = None
            
            for i, header in enumerate(headers, start=1):
                if header == 'Strikes':
                    strikes_col = i
                elif header == 'Status':
                    status_col = i
            
            # Update strikes
            self.sheet.update_cell(row_num, strikes_col, new_strikes)
            
            # If user was eliminated but now has less than 2 strikes, reactivate
            if challenger.get('Status') == 'Eliminated' and new_strikes < 2:
                self.sheet.update_cell(row_num, status_col, 'Active')
                status_msg = f"Strike removed ({new_strikes}/2). User reactivated"
            else:
                status_msg = f"Strike removed ({new_strikes}/2)"
            
            logger.info(f"Strike removed from user {user_id}")
            return True, status_msg
            
        except Exception as e:
            logger.error(f"Error removing strike: {e}")
            return False, "Unable to connect to database. Please try again in a moment"
    
    def get_user_stats(self, user_id):
        """Get detailed stats for a specific user (admin only)"""
        try:
            row_num, challenger = self.find_challenger(user_id)
            
            if not challenger:
                return "User not found"
            
            name = challenger.get('Name', 'Unknown')
            group = challenger.get('Group', 'Unknown')
            points = challenger.get('Current_Points', 0)
            strikes = challenger.get('Strikes', 0)
            status = challenger.get('Status', 'Active')
            
            current_date = self.get_current_date_string()
            current_week = self.get_current_week_string()
            
            # Check task completion status
            daily1_done = challenger.get('Daily1_Last') == current_date
            daily2_done = challenger.get('Daily2_Last') == current_date
            daily3_done = challenger.get('Daily3_Last') == current_date
            weekly1_done = challenger.get('Weekly1_Week') == current_week
            weekly2_done = challenger.get('Weekly2_Week') == current_week
            
            stats_msg = f"""User Statistics:

User ID: {user_id}
Name: {name}
Group: {group}
Points: {points}
Strikes: {strikes}/2
Status: {status}

Today's Tasks:
Daily 1: {'Completed' if daily1_done else 'Pending'}
Daily 2: {'Completed' if daily2_done else 'Pending'}
Daily 3: {'Completed' if daily3_done else 'Pending'}

This Week's Tasks:
Weekly 1: {'Completed' if weekly1_done else 'Pending'}
Weekly 2: {'Completed' if weekly2_done else 'Pending'}

Last Completions:
Daily 1: {challenger.get('Daily1_Last', 'Never')}
Daily 2: {challenger.get('Daily2_Last', 'Never')}
Daily 3: {challenger.get('Daily3_Last', 'Never')}
Weekly 1: {challenger.get('Weekly1_Week', 'Never')}
Weekly 2: {challenger.get('Weekly2_Week', 'Never')}"""
            
            return stats_msg
            
        except Exception as e:
            logger.error(f"Error getting user stats for {user_id}: {e}")
            return "Unable to connect to database. Please try again in a moment"
    
    def adjust_points(self, user_id, points, action):
        """Add or remove points from a user (admin only)"""
        try:
            row_num, challenger = self.find_challenger(user_id)
            
            if not challenger:
                return False, "User not found"
            
            current_points = int(challenger.get('Current_Points', 0))
            
            if action == "add":
                new_points = current_points + points
                action_text = "added"
            elif action == "remove":
                new_points = max(0, current_points - points)  # Don't allow negative points
                action_text = "removed"
            else:
                return False, "Invalid action. Use 'add' or 'remove'"
            
            # Find points column
            headers = self.sheet.row_values(1)
            points_col = None
            
            for i, header in enumerate(headers, start=1):
                if header == 'Current_Points':
                    points_col = i
                    break
            
            if not points_col:
                return False, "System error. Please contact admin"
            
            # Update points
            self.sheet.update_cell(row_num, points_col, new_points)
            
            logger.info(f"Points {action_text} for user {user_id}: {points} points")
            return True, f"Points {action_text}: {points}. New total: {new_points}"
            
        except Exception as e:
            logger.error(f"Error adjusting points for user {user_id}: {e}")
            return False, "Unable to connect to database. Please try again in a moment"
    
    def get_admin_stats(self):
        """Get admin statistics"""
        try:
            records = self.sheet.get_all_records()
            
            total_users = len(records)
            active_users = len([r for r in records if r.get('Status') == 'Active'])
            eliminated_users = len([r for r in records if r.get('Status') == 'Eliminated'])
            senior_users = len([r for r in records if r.get('Group') == 'Senior'])
            junior_users = len([r for r in records if r.get('Group') == 'Junior'])
            
            current_date = self.get_current_date_string()
            current_week = self.get_current_week_string()
            
            # Task completion stats for today/this week
            daily1_today = len([r for r in records if r.get('Daily1_Last') == current_date])
            daily2_today = len([r for r in records if r.get('Daily2_Last') == current_date])
            daily3_today = len([r for r in records if r.get('Daily3_Last') == current_date])
            weekly1_this_week = len([r for r in records if r.get('Weekly1_Week') == current_week])
            weekly2_this_week = len([r for r in records if r.get('Weekly2_Week') == current_week])
            
            # Average points
            total_points = sum(int(r.get('Current_Points', 0)) for r in records)
            avg_points = round(total_points / total_users, 1) if total_users > 0 else 0
            
            stats_msg = f"""Admin Statistics:

Users:
Total: {total_users}
Active: {active_users}
Eliminated: {eliminated_users}
Senior: {senior_users}
Junior: {junior_users}

Today's Completions:
Daily 1: {daily1_today}
Daily 2: {daily2_today}
Daily 3: {daily3_today}

This Week's Completions:
Weekly 1: {weekly1_this_week}
Weekly 2: {weekly2_this_week}

Points:
Total Points: {total_points}
Average: {avg_points} pts/user"""
            
            return stats_msg
            
        except Exception as e:
            logger.error(f"Error getting admin stats: {e}")
            return "Unable to connect to database. Please try again in a moment"
    
    def reset_challenge(self):
        """Reset all user progress (admin only)"""
        try:
            self.challenge_active = False
            
            records = self.sheet.get_all_records()
            
            # Reset all users
            for i, record in enumerate(records, start=2):
                # Reset points and tasks, keep strikes and status for eliminated users
                if record.get('Status') == 'Eliminated':
                    continue
                
                # Find column indices
                headers = self.sheet.row_values(1)
                updates = []
                
                for j, header in enumerate(headers, start=1):
                    if header == 'Current_Points':
                        updates.append((i, j, 0))
                    elif header in ['Daily1_Last', 'Daily2_Last', 'Daily3_Last', 'Weekly1_Week', 'Weekly2_Week']:
                        updates.append((i, j, ''))
                
                # Batch update
                for row, col, value in updates:
                    self.sheet.update_cell(row, col, value)
            
            self.challenge_active = True
            logger.info("Challenge reset completed")
            return True, "Challenge reset completed. All active users back to 0 points"
            
        except Exception as e:
            logger.error(f"Error resetting challenge: {e}")
            self.challenge_active = True
            return False, "Unable to reset challenge. Please try again"

# Global bot instance
bot_instance = None

# Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_msg = """Welcome to SGI Challenge Tracker!

Commands:
/register - Join the challenge
/done daily1 - Mark daily task 1 complete
/done daily2 - Mark daily task 2 complete  
/done daily3 - Mark daily task 3 complete
/done weekly1 - Mark weekly task 1 complete
/done weekly2 - Mark weekly task 2 complete
/mystatus - Check your progress
/leaderboard - View rankings

Challenge Info:
30-day challenge
Daily tasks: 3 points each (can complete every day)
Weekly tasks: 5 points each (can complete once per week)
2 strikes = elimination
6 days per week (Sunday is rest day)

Good luck!"""
    
    await update.message.reply_text(welcome_msg)

async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /register command"""
    user = update.effective_user
    
    # Check for group argument
    if not context.args or context.args[0].lower() not in ['senior', 'junior']:
        await update.message.reply_text(
            "Please specify your group:\n"
            "/register senior (for existing members)\n"
            "/register junior (for new members)"
        )
        return
    
    group = context.args[0].capitalize()
    success, message = bot_instance.register_challenger(user.id, user.first_name, group)
    
    await update.message.reply_text(message)

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /done command"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "Please specify the task:\n"
            "Example: /done daily1 or /done weekly2"
        )
        return
    
    task = context.args[0].lower()
    
    # Map to column names
    task_mapping = {
        'daily1': 'Daily1',
        'daily2': 'Daily2', 
        'daily3': 'Daily3',
        'weekly1': 'Weekly1',
        'weekly2': 'Weekly2'
    }
    
    if task not in task_mapping:
        await update.message.reply_text(
            "Invalid task. Valid options: daily1, daily2, daily3, weekly1, weekly2"
        )
        return
    
    success, message = bot_instance.update_task_completion(user.id, task_mapping[task])
    await update.message.reply_text(message)

async def mystatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mystatus command"""
    user = update.effective_user
    status_msg = bot_instance.get_challenger_status(user.id)
    await update.message.reply_text(status_msg)

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /leaderboard command"""
    leaderboard_msg = bot_instance.get_leaderboard()
    await update.message.reply_text(leaderboard_msg)

# Admin Commands
async def admin_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_help command"""
    user = update.effective_user
    
    if not bot_instance.is_admin(user.id):
        await update.message.reply_text("You are not authorized to use admin commands")
        return
    
    help_msg = """Admin Commands:

/admin_help - Show this help message
/admin_stats - Show challenge statistics
/admin_strike <user_id> <reason> - Add strike to user
/admin_remove_strike <user_id> - Remove strike from user
/admin_user_stats <user_id> - Get detailed user stats
/admin_add_points <user_id> <points> - Add points to user
/admin_remove_points <user_id> <points> - Remove points from user
/admin_reset - Reset entire challenge (use with caution!)

Examples:
/admin_strike 123456789 Missed daily tasks
/admin_add_points 123456789 15
/admin_user_stats 123456789

Note: user_id is the Telegram User ID (number), not username."""
    
    await update.message.reply_text(help_msg)

async def admin_strike_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_strike command"""
    user = update.effective_user
    
    if not bot_instance.is_admin(user.id):
        await update.message.reply_text("You are not authorized to use admin commands")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /admin_strike <user_id> <reason>\n"
            "Example: /admin_strike 123456789 Missed deadline"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        reason = ' '.join(context.args[1:])
        
        success, message = bot_instance.add_strike(target_user_id, reason)
        await update.message.reply_text(message)
        
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number")

async def admin_remove_strike_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_remove_strike command"""
    user = update.effective_user
    
    if not bot_instance.is_admin(user.id):
        await update.message.reply_text("You are not authorized to use admin commands")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /admin_remove_strike <user_id>\n"
            "Example: /admin_remove_strike 123456789"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        
        success, message = bot_instance.remove_strike(target_user_id)
        await update.message.reply_text(message)
        
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number")

async def admin_user_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_user_stats command"""
    user = update.effective_user
    
    if not bot_instance.is_admin(user.id):
        await update.message.reply_text("You are not authorized to use admin commands")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /admin_user_stats <user_id>\n"
            "Example: /admin_user_stats 123456789"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        
        stats_msg = bot_instance.get_user_stats(target_user_id)
        await update.message.reply_text(stats_msg)
        
    except ValueError:
        await update.message.reply_text("Invalid user ID. Must be a number")

async def admin_add_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_add_points command"""
    user = update.effective_user
    
    if not bot_instance.is_admin(user.id):
        await update.message.reply_text("You are not authorized to use admin commands")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /admin_add_points <user_id> <points>\n"
            "Example: /admin_add_points 123456789 15"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        points_to_add = int(context.args[1])
        
        if points_to_add <= 0:
            await update.message.reply_text("Points must be a positive number")
            return
        
        success, message = bot_instance.adjust_points(target_user_id, points_to_add, "add")
        await update.message.reply_text(message)
        
    except ValueError:
        await update.message.reply_text("Invalid input. Both user ID and points must be numbers")

async def admin_remove_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_remove_points command"""
    user = update.effective_user
    
    if not bot_instance.is_admin(user.id):
        await update.message.reply_text("You are not authorized to use admin commands")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /admin_remove_points <user_id> <points>\n"
            "Example: /admin_remove_points 123456789 10"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        points_to_remove = int(context.args[1])
        
        if points_to_remove <= 0:
            await update.message.reply_text("Points must be a positive number")
            return
        
        success, message = bot_instance.adjust_points(target_user_id, points_to_remove, "remove")
        await update.message.reply_text(message)
        
    except ValueError:
        await update.message.reply_text("Invalid input. Both user ID and points must be numbers")

async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_stats command"""
    user = update.effective_user
    
    if not bot_instance.is_admin(user.id):
        await update.message.reply_text("You are not authorized to use admin commands")
        return
    
    stats_msg = bot_instance.get_admin_stats()
    await update.message.reply_text(stats_msg)

async def admin_reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_reset command"""
    user = update.effective_user
    
    if not bot_instance.is_admin(user.id):
        await update.message.reply_text("You are not authorized to use admin commands")
        return
    
    success, message = bot_instance.reset_challenge()
    await update.message.reply_text(message)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def main():
    """Run the bot"""
    global bot_instance
    
    # Get configuration from environment variables
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID') 
    ADMIN_USER_IDS = os.getenv('ADMIN_USER_IDS')
    
    if not all([BOT_TOKEN, SPREADSHEET_ID, ADMIN_USER_IDS]):
        logger.error("Missing required environment variables")
        return
    
    try:
        # Initialize bot instance
        bot_instance = SGIBot(SPREADSHEET_ID, ADMIN_USER_IDS)
        
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("register", register_command))
        application.add_handler(CommandHandler("done", done_command))
        application.add_handler(CommandHandler("mystatus", mystatus_command))
        application.add_handler(CommandHandler("leaderboard", leaderboard_command))
        
        # Admin commands
        application.add_handler(CommandHandler("admin_help", admin_help_command))
        application.add_handler(CommandHandler("admin_strike", admin_strike_command))
        application.add_handler(CommandHandler("admin_remove_strike", admin_remove_strike_command))
        application.add_handler(CommandHandler("admin_user_stats", admin_user_stats_command))
        application.add_handler(CommandHandler("admin_add_points", admin_add_points_command))
        application.add_handler(CommandHandler("admin_remove_points", admin_remove_points_command))
        application.add_handler(CommandHandler("admin_stats", admin_stats_command))
        application.add_handler(CommandHandler("admin_reset", admin_reset_command))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        # Run the bot
        logger.info("SGI Bot starting...")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()