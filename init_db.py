import sqlite3

# Connect to the database (or create it if it doesn't exist)
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

# Create the users table
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0
)
''')

# Create the questions table
cursor.execute('''
CREATE TABLE IF NOT EXISTS questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text TEXT,
    option_a TEXT,
    option_b TEXT,
    correct_answer TEXT,
    time_limit TEXT,
    is_active BOOLEAN DEFAULT TRUE
)
''')

# Create the participants table
cursor.execute('''
CREATE TABLE IF NOT EXISTS participants (
    participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    question_id INTEGER,
    selected_answer TEXT,
    entry_fee INTEGER,
    status TEXT DEFAULT 'pending',
    timestamp TEXT
)
''')

# Create the transactions table
cursor.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    type TEXT,
    description TEXT,
    timestamp TEXT
)
''')

# Save changes and close the connection
conn.commit()
conn.close()

print("Database initialized successfully!")
