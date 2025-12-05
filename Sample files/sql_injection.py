def get_user(cursor, uid):
    query = f"SELECT * FROM users WHERE id = '{uid}'"  # Vulnerable!
    cursor.execute(query)
