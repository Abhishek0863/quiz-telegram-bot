import nest_asyncio
nest_asyncio.apply()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import sqlite3
from datetime import datetime
import asyncio
import shlex

# Database setup
conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()

# Admin configuration
ADMIN_USER_ID = 1538695675  # Replace with your actual user_id

# Helper function to check if a user is an admin
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID  # Hardcoded admin

# Helper function to log transactions
def log_transaction(user_id, amount, type, description):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO transactions (user_id, amount, type, description, timestamp) VALUES (?, ?, ?, ?, ?)',
                   (user_id, amount, type, description, timestamp))
    conn.commit()

# Helper function to add new users
async def add_new_user(user_id: int, username: str):
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    if cursor.fetchone() is None:
        # Add the user to the database with ₹1 free money
        cursor.execute('INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)', (user_id, username, 1))
        log_transaction(user_id, 1, "credit", "Welcome bonus of ₹1")
        conn.commit()

# Helper function to get all users
def get_all_users():
    cursor.execute('SELECT user_id FROM users')
    return [row[0] for row in cursor.fetchall()]

# Admin command to add balance
async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, target_user_id))
        log_transaction(target_user_id, amount, "credit", f"Admin added ₹{amount}")
        conn.commit()
        await update.message.reply_text(f"Added ₹{amount} to user {target_user_id}'s balance.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /addbalance <user_id> <amount>")

# Admin command to withdraw balance
async def withdraw_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, target_user_id))
        log_transaction(target_user_id, amount, "debit", f"Admin withdrew ₹{amount}")
        conn.commit()
        await update.message.reply_text(f"Withdrew ₹{amount} from user {target_user_id}'s balance.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /withdrawbalance <user_id> <amount>")

# User command to check balance
async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"

    # Add the user if they don't exist
    await add_new_user(user_id, username)

    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if result is None:
        await update.message.reply_text("Your wallet has been created with a balance of ₹0.")
    else:
        balance = result[0]
        await update.message.reply_text(f"Your current balance is ₹{balance}.")

# Admin command to ask a question
async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    try:
        # Split the command arguments using shlex to handle quoted strings
        args = shlex.split(update.message.text)[1:]  # Skip the command itself
        if len(args) < 4:
            raise IndexError("Not enough arguments")

        question_text = args[0]
        option_a = args[1]
        option_b = args[2]
        time_limit = args[3]  # Format: "YYYY-MM-DD HH:MM"

        # Insert the question into the database
        cursor.execute('INSERT INTO questions (question_text, option_a, option_b, time_limit) VALUES (?, ?, ?, ?)',
                       (question_text, option_a, option_b, time_limit))
        conn.commit()
        question_id = cursor.lastrowid

        # Create a keyboard with the two options
        keyboard = [
            [InlineKeyboardButton(option_a, callback_data=f'A_{question_id}')],
            [InlineKeyboardButton(option_b, callback_data=f'B_{question_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send the question to the admin
        await update.message.reply_text(f"Question {question_id}: {question_text}", reply_markup=reply_markup)

        # Forward the question to all users
        all_users = get_all_users()
        for user in all_users:
            try:
                await context.bot.send_message(chat_id=user, text=f"New Question: {question_text}", reply_markup=reply_markup)
            except Exception as e:
                print(f"Failed to send message to user {user}: {e}")
    except IndexError:
        await update.message.reply_text("Usage: /askquestion \"<question_text>\" \"<option_a>\" \"<option_b>\" \"<time_limit>\"")
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {str(e)}")

# Handle answer selection
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Acknowledge the callback query

    user_id = query.from_user.id
    selected_answer, question_id = query.data.split('_')
    question_id = int(question_id)

    # Store the selected answer and question_id in the user's context
    context.user_data['selected_answer'] = selected_answer
    context.user_data['question_id'] = question_id

    # Ask the user to choose a bet amount
    keyboard = [
        [InlineKeyboardButton("₹1", callback_data="1")],
        [InlineKeyboardButton("₹2", callback_data="2")],
        [InlineKeyboardButton("₹5", callback_data="5")],
        [InlineKeyboardButton("₹10", callback_data="10")],
        [InlineKeyboardButton("₹20", callback_data="20")],
        [InlineKeyboardButton("₹40", callback_data="40")],
        [InlineKeyboardButton("₹80", callback_data="80")],
        [InlineKeyboardButton("₹160", callback_data="160")],
        [InlineKeyboardButton("₹320", callback_data="320")],
        [InlineKeyboardButton("₹640", callback_data="640")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Please choose your bet amount:", reply_markup=reply_markup)

# Handle bet amount selection
async def handle_bet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Acknowledge the callback query

    user_id = query.from_user.id
    bet_amount = int(query.data)  # Get the selected bet amount

    # Retrieve the selected answer and question_id from the user's context
    selected_answer = context.user_data.get('selected_answer')
    question_id = context.user_data.get('question_id')

    if not selected_answer or not question_id:
        await query.edit_message_text("Error: No question or answer selected. Please try again.")
        return

    # Check if the user has sufficient balance
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result is None:
        await query.edit_message_text("Error: Your wallet does not exist. Please use /balance to create one.")
        return

    balance = result[0]
    if balance < bet_amount:
        await query.edit_message_text("Insufficient balance to place this bet.")
        return

    # Deduct the bet amount from the user's balance
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (bet_amount, user_id))
    log_transaction(user_id, bet_amount, "debit", f"Placed bet on question {question_id}")

    # Record the user's participation
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO participants (user_id, question_id, selected_answer, entry_fee, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
                   (user_id, question_id, selected_answer, bet_amount, 'pending', timestamp))
    conn.commit()

    # Notify the user
    await query.edit_message_text(f"Your bet of ₹{bet_amount} on option {selected_answer} has been submitted. Good luck!")

# User command to view quiz history
async def view_quiz_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"

    # Add the user if they don't exist
    await add_new_user(user_id, username)

    # Fetch the user's quiz history
    cursor.execute('SELECT question_id, selected_answer, entry_fee, status, timestamp FROM participants WHERE user_id = ? ORDER BY timestamp DESC', (user_id,))
    quiz_history = cursor.fetchall()

    if not quiz_history:
        await update.message.reply_text("No quiz history found.")
        return

    # Format the quiz history
    response = "Your quiz history:\n"
    for question_id, selected_answer, entry_fee, status, timestamp in quiz_history:
        response += f"{timestamp}: Question {question_id}, Selected {selected_answer}, Entry Fee ₹{entry_fee}, Status: {status}\n"

    await update.message.reply_text(response)

# User command to view transaction history
async def view_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"

    # Add the user if they don't exist
    await add_new_user(user_id, username)

    # Fetch the user's transaction history
    cursor.execute('SELECT amount, type, description, timestamp FROM transactions WHERE user_id = ? ORDER BY timestamp DESC', (user_id,))
    transactions = cursor.fetchall()

    if not transactions:
        await update.message.reply_text("No transactions found.")
        return

    # Format the transaction history
    response = "Your transaction history:\n"
    for amount, type, description, timestamp in transactions:
        response += f"{timestamp}: {type} ₹{amount} ({description})\n"

    await update.message.reply_text(response)

# Admin command to announce the correct answer
async def announce_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    try:
        # Parse arguments
        question_id = int(context.args[0])
        correct_answer = context.args[1]

        # Mark the question as inactive and set the correct answer
        cursor.execute('UPDATE questions SET is_active = FALSE, correct_answer = ? WHERE question_id = ?', (correct_answer, question_id))
        conn.commit()

        # Fetch all participants for this question
        cursor.execute('SELECT user_id, selected_answer, entry_fee FROM participants WHERE question_id = ?', (question_id,))
        participants = cursor.fetchall()

        if not participants:
            await update.message.reply_text(f"No participants for question {question_id}.")
            return

        # Separate winners and losers
        winners = [p for p in participants if p[1] == correct_answer]
        losers = [p for p in participants if p[1] != correct_answer]

        if not winners:
            await update.message.reply_text(f"No winners for question {question_id}.")
            return

        # Calculate the total pool of losers' entry fees
        losers_pool = sum(loser[2] for loser in losers)

        # Calculate the total entry fees of all winners
        total_winners_entry_fees = sum(winner[2] for winner in winners)

        # Distribute the losers' pool among the winners
        for winner in winners:
            user_id, _, entry_fee = winner
            reward = (losers_pool * (entry_fee / total_winners_entry_fees)) + entry_fee
            cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (reward, user_id))
            log_transaction(user_id, reward, "credit", f"Reward for question {question_id}")

            # Update the participant's status to 'won'
            cursor.execute('UPDATE participants SET status = ? WHERE user_id = ? AND question_id = ?', ('won', user_id, question_id))

            # Notify the winner
            try:
                await context.bot.send_message(chat_id=user_id, text=f"Congratulations! You won ₹{reward:.2f} on question {question_id}.")
            except Exception as e:
                print(f"Failed to notify winner {user_id}: {e}")

        # Update the status for losers
        for loser in losers:
            user_id, _, _ = loser
            cursor.execute('UPDATE participants SET status = ? WHERE user_id = ? AND question_id = ?', ('lost', user_id, question_id))

            # Notify the loser
            try:
                await context.bot.send_message(chat_id=user_id, text=f"Sorry, you lost on question {question_id}. Better luck next time!")
            except Exception as e:
                print(f"Failed to notify loser {user_id}: {e}")

        conn.commit()
        await update.message.reply_text(f"Correct answer for question {question_id} is {correct_answer}. Rewards distributed!")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /announceanswer <question_id> <correct_answer>")
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {str(e)}")

# Main function
async def main():
    application = Application.builder().token("6675246793:AAFWpJ0jdalZ4l2gaTBDYkQVt0KR6l6U1Hg").build()

    # Add command handlers
    application.add_handler(CommandHandler("addbalance", add_balance))
    application.add_handler(CommandHandler("withdrawbalance", withdraw_balance))
    application.add_handler(CommandHandler("balance", check_balance))
    application.add_handler(CommandHandler("askquestion", ask_question))
    application.add_handler(CommandHandler("quizhistory", view_quiz_history))
    application.add_handler(CommandHandler("transactions", view_transactions))
    application.add_handler(CommandHandler("announceanswer", announce_answer))
    application.add_handler(CallbackQueryHandler(handle_answer, pattern=r'^[AB]_\d+$'))
    application.add_handler(CallbackQueryHandler(handle_bet_amount, pattern=r'^\d+$'))

    # Start the bot
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
