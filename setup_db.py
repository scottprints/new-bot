import sqlite3

# Connect to the SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('db/warnings.db')

# Create a cursor object to execute SQL commands
cursor = conn.cursor()

# Create the warnings table if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    reason TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    moderator_id INTEGER
)
''')

# Create the verifications table
cursor.execute('''
CREATE TABLE IF NOT EXISTS verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    moderator_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Create the tags table
cursor.execute('''
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    message TEXT
)
''')

# Create the mute/ban actions table
cursor.execute('''
CREATE TABLE IF NOT EXISTS mod_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    moderator_id INTEGER,
    action TEXT,
    reason TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Add the moderator_id column to the warnings table
try:
    cursor.execute('ALTER TABLE warnings ADD COLUMN moderator_id INTEGER')
    print("Column 'moderator_id' added to 'warnings' table.")
except sqlite3.OperationalError as e:
    print(f"Error: {e}")

# Commit the changes and close the connection
conn.commit()
conn.close()

print("Database and table setup complete.") 