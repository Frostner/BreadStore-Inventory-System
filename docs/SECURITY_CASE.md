# Cybersecurity case study — Preventing SQL injection in BreadStore

This is an **educational, defensive example** related to the BSIT guideline's cybersecurity case requirement. Confirm the behavior in your own tests before turning it in as personal project evidence.

## 1. What is the vulnerability?

SQL injection occurs when untrusted user-supplied text is interpreted as part of a SQL command instead of as a **data value**. An attacker might try to interfere with records, bypass a filter or retrieve unauthorized data.

## 2. How can it happen?

An unsafe app might build a SQL statement by directly concatenating a search term or login input into the SQL text. That would mix SQL syntax and user input. An application should instead use the database driver's SQL parameters.

## 3. What are the risks?

Unauthorized access, inaccurate inventory, disclosure of business records, and loss of trust in data.

## 4. How does this project reduce the risk?

BreadStore uses SQLite parameter placeholders (`?`) with values supplied separately, e.g.:

```python
row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
```

For inventory filtering, the user-supplied search is added to an array of parameter values, while sortable column names are chosen from an **explicit allowlist** in the backend. SQL injection-like SKU values are also rejected by input validation, though parameterization—not input screening alone—is the key defense.

## 5. Recommended additional practices

- Require authentication for inventory, sale and reporting routes.
- Validate field types, monetary ranges and stock amounts server-side.
- Use TLS/HTTPS and secure cookies when hosted publicly.
- Store salted password hashes, not passwords.
- Restrict DB and environment-file permissions.
- Back up the database and monitor errors.
- Keep dependencies and operating system patches up to date.

## Responsible test example

Use the supplied `tests/test_api.py` integration tests against a **temporary database**. One test submits a deliberately malformed SKU and confirms the application rejects it without changing the product table. Do not test arbitrary third-party systems without authorization.
