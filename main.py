from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import sqlite3
from datetime import datetime

# Database setup
conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()

# Helper function to log transactions
def log_transaction(user_id, amount, type, description):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO transactions (user_id, amount, type, description, timestamp) VALUES (?, ?, ?, ?, ?)',
                   (user_id, amount, type, description, timestamp))
    conn.commit()

# Admin command to add balance
def add_balance(update: Update, context: CallbackContext):
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        log_transaction(user_id, amount, "credit", f"Admin added ₹{amount}")
        conn.commit()
        update.message.reply_text(f"Added ₹{amount} to user {user_id}'s balance.")
    except (IndexError, ValueError):
        update.message.reply_text("Usage: /addbalance <user_id> <amount>")

# Admin command to withdraw balance
def withdraw_balance(update: Update, context: CallbackContext):
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
        log_transaction(user_id, amount, "debit", f"Admin withdrew ₹{amount}")
        conn.commit()
        update.message.reply_text(f"Withdrew ₹{amount} from user {user_id}'s balance.")
    except (IndexError, ValueError):
        update.message.reply_text("Usage: /withdrawbalance <user_id> <amount>")

# Admin command to ask a question
def ask_question(update: Update, context: CallbackContext):
    try:
        question_text = context.args[0]
        option_a = context.args[1]
        option_b = context.args[2]
        time_limit = context.args[3]  # Format: "YYYY-MM-DD HH:MM"
        cursor.execute('INSERT INTO questions (question_text, option_a, option_b, time_limit) VALUES (?, ?, ?, ?)',
                       (question_text, option_a, option_b, time_limit))
        conn.commit()
        question_id = cursor.lastrowid
        keyboard = [[InlineKeyboardButton(option_a, callback_data=f'A_{question_id}'),
                     InlineKeyboardButton(option_b, callback_data=f'B_{question_id}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(f"Question {question_id}: {question_text}", reply_markup=reply_markup)
    except (IndexError, ValueError):
        update.message.reply_text("Usage: /askquestion <question_text> <option_a> <option_b> <time_limit>")

# User selects an answer
def handle_answer(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    selected_answer, question_id = query.data.split('_')
    question_id = int(question_id)

    # Check if the question is active and time limit is not reached
    cursor.execute('SELECT time_limit, is_active FROM questions WHERE question_id = ?', (question_id,))
    time_limit, is_active = cursor.fetchone()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not is_active:
        query.answer("This question is no longer active.")
        return
    if current_time > time_limit:
        cursor.execute('UPDATE questions SET is_active = FALSE WHERE question_id = ?', (question_id,))
        conn.commit()
        query.answer("Time limit reached for this question.")
        return

    # Deduct entry fee (example: ₹10)
    entry_fee = 10
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    if balance < entry_fee:
        query.answer("Insufficient balance to participate.")
        return
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (entry_fee, user_id))
    log_transaction(user_id, entry_fee, "debit", f"Paid entry fee for question {question_id}")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO participants (user_id, question_id, selected_answer, entry_fee, timestamp) VALUES (?, ?, ?, ?, ?)',
                   (user_id, question_id, selected_answer, entry_fee, timestamp))
    conn.commit()
    query.answer("Thank you for participating!")

# Admin command to announce the correct answer
def announce_answer(update: Update, context: CallbackContext):
    try:
        question_id = int(context.args[0])
        correct_answer = context.args[1]
        cursor.execute('UPDATE questions SET is_active = FALSE, correct_answer = ? WHERE question_id = ?',
                       (correct_answer, question_id))
        cursor.execute('SELECT user_id, entry_fee FROM participants WHERE question_id = ? AND selected_answer = ?',
                       (question_id, correct_answer))
        winners = cursor.fetchall()
        total_pool = sum(winner[1] for winner in winners)
        for winner in winners:
            user_id, entry_fee = winner
            reward = (entry_fee / total_pool) * total_pool  # Simplified calculation
            cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (reward, user_id))
            log_transaction(user_id, reward, "credit", f"Reward for question {question_id}")
        conn.commit()
        update.message.reply_text(f"Correct answer for question {question_id} is {correct_answer}. Rewards distributed!")
    except (IndexError, ValueError):
        update.message.reply_text("Usage: /announceanswer <question_id> <correct_answer>")

# User command to check balance
def check_balance(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    update.message.reply_text(f"Your current balance is ₹{balance}.")

# User command to view transaction history
def view_transactions(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    cursor.execute('SELECT amount, type, description, timestamp FROM transactions WHERE user_id = ? ORDER BY timestamp DESC', (user_id,))
    transactions = cursor.fetchall()
    if not transactions:
        update.message.reply_text("No transactions found.")
        return
    response = "Your transaction history:\n"
    for amount, type, description, timestamp in transactions:
        response += f"{timestamp}: {type} ₹{amount} ({description})\n"
    update.message.reply_text(response)

# User command to view quiz history
def view_quiz_history(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    cursor.execute('SELECT question_id, selected_answer, entry_fee, timestamp FROM participants WHERE user_id = ? ORDER BY timestamp DESC', (user_id,))
    quiz_history = cursor.fetchall()
    if not quiz_history:
        update.message.reply_text("No quiz history found.")
        return
    response = "Your quiz history:\n"
    for question_id, selected_answer, entry_fee, timestamp in quiz_history:
        response += f"{timestamp}: Question {question_id}, Selected {selected_answer}, Entry Fee ₹{entry_fee}\n"
    update.message.reply_text(response)

# Main function
def main():
    updater = Updater("YOUR_TELEGRAM_BOT_TOKEN", use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("addbalance", add_balance))
    dp.add_handler(CommandHandler("withdrawbalance", withdraw_balance))
    dp.add_handler(CommandHandler("askquestion", ask_question))
    dp.add_handler(CallbackQueryHandler(handle_answer))
    dp.add_handler(CommandHandler("announceanswer", announce_answer))
    dp.add_handler(CommandHandler("balance", check_balance))
    dp.add_handler(CommandHandler("transactions", view_transactions))
    dp.add_handler(CommandHandler("quizhistory", view_quiz_history))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
