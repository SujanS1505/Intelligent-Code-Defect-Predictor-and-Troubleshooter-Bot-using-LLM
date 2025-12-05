function getUser(db, id) {
  const query = "SELECT * FROM users WHERE id='" + id + "'"; // SQL injection
  db.execute(query);
}
