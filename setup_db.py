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

# Create the bans table
cursor.execute('''
CREATE TABLE IF NOT EXISTS bans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    moderator_id INTEGER,
    reason TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Create the mutes table
cursor.execute('''
CREATE TABLE IF NOT EXISTS mutes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    moderator_id INTEGER,
    reason TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Create the tickets table
cursor.execute('''
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    moderator_id INTEGER,
    type TEXT,
    status TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Modify the roles_backup table to set user_id as a primary key
cursor.execute('''
CREATE TABLE IF NOT EXISTS roles_backup (
    user_id INTEGER PRIMARY KEY,
    roles TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
''')

# Commit the changes and close the connection
conn.commit()
conn.close()

print("Database and table setup complete.") 