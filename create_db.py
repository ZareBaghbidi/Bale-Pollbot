import sqlite3

# Connect to a new SQLite database (this will create the file if it doesn't exist)
connection = sqlite3.connect('new_database.db')
cursor = connection.cursor()

# Create the 'users' table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        name TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

# Create the 'classes' table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

# Create the 'sqlite_sequence' table (used by SQLite to track auto-increment values)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sqlite_sequence(name, seq)
''')

# Create the 'user_classes' table (many-to-many relationship between users and classes)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_classes (
        user_id INTEGER,
        class_id INTEGER,
        PRIMARY KEY (user_id, class_id),
        FOREIGN KEY (user_id) REFERENCES users(chat_id) ON DELETE CASCADE,
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
    )
''')

# Create the 'polls' table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS polls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        class TEXT,
        active INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

# Create the 'questions' table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        poll_id INTEGER NOT NULL,
        `index` INTEGER NOT NULL,
        text TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE,
        UNIQUE (poll_id, `index`)
    )
''')

# Create the 'votes' table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        poll_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        value TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        username TEXT,
        name TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
    )
''')

# Create the 'tasks' table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_at DATETIME NOT NULL,
        poll_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

# Commit the changes and close the connection
connection.commit()
connection.close()

print("Database structure created successfully!")
