# Natural Language Business Data Chatbot

This project implements a sophisticated natural language to SQL chatbot capable of answering complex business questions by converting plain English into accurate database queries and returning the results. This README is intended to provide technical leadership and developers with an in-depth understanding of the system's architecture, underlying logic, and the intelligent methods used to bridge the gap between unstructured questions and structured relational data.

---

## 1. Detailed Workflow and Architecture

The system operates using a **3-Phase LLM Pipeline architecture**. Relying on a single LLM prompt to both understand a user's intent and write perfect SQL often leads to hallucinations. Our multi-phase approach isolates tasks for maximum accuracy and safety.

### Architecture Components:
- **`config.py`**: Centralized configuration management for database paths, model parameters (e.g., setting LLM temperature to `0.1` for deterministic, highly reproducible outputs), and Azure OpenAI credentials.
- **`db_manager.py`**: An automated, intelligent ingestion engine that converts raw `/Data` CSVs into a structured SQLite database without requiring manual schema definitions.
- **`schema_analyzer.py`**: A specialized script that scans the live database to generate a rich, context-aware schema payload (`schema_context.json`) for the LLM.
- **`query_orchestrator.py`**: The core AI engine implementing the 3-phase LLM pipeline for processing user questions.
- **`validator.py`**: A strict security layer ensuring SQL injection prevention and enforcing query constraints.
- **`chatbot.py`**: The interactive CLI application that loops user input into the orchestrator.

### The 3-Phase Workflow Pipeline:
1. **User Input:** The user asks a natural language question (e.g., "How many accountants are currently on the bench?").
2. **Phase 1 - Intent Analysis:** The LLM is provided the user's question and a high-level summary of the database schema and business concepts. The goal here is **not** to write SQL yet, but to identify *intent*: Which tables are relevant? What columns do we need? What is the filtering logic?
3. **Phase 2 - SQL Generation:** The LLM takes its own intent analysis from Phase 1, combined with the comprehensive `schema_context.json` (which includes sample data and exact column names), to generate a precise SQLite query.
4. **Validation (Security Check):** The generated SQL string is intercepted by `validator.py`. This script ensures:
   - No destructive commands are present (e.g., `DROP`, `DELETE`, `UPDATE`, `INSERT`).
   - `LIMIT` clauses are explicitly blocked (to guarantee the user gets the *complete* dataset, not just the top 5 rows).
   - Valid SQL comments (like `--`) are allowed, which prevents query breakage.
5. **Execution:** The sanitized SQL query is executed directly against the local `business_data.db` SQLite database.
6. **Phase 3 - Result Formatting:** The raw dataset fetched from the database is passed back to the LLM (or formatted via code if the dataset is too large). The LLM synthesizes the exact rows returned into a human-readable, natural language summary (e.g., "We currently have 12 accountants on the bench.").

---

## 2. Core Concept and Approach Implemented

**Concept:** LLM Context Enrichment using **"Live Sample Data & Explicit Business Concepts"**.

**The "Why":** Standard Text-to-SQL models fail in enterprise environments for two main reasons:
1. **Blindness to Data Values:** An LLM might know a column is named `Company_Category`, but it doesn't know if the database stores "Active", "active_customer", or "Customer".
2. **Business Jargon Disconnect:** If a user asks for "job titles", an LLM will naturally look for a table named `Position`. However, in this specific business data, the `position` table represents open job requisitions, while actual employee job titles are stored in the `entity_placement.POSITION` column.

**Our Approach:** 
To solve this, we implemented dynamic context enrichment. 
- **Sample Data Injection:** We extract actual cell values from the database and feed them into the LLM prompt. The LLM now sees: `Company_Category (Examples: 'Prospect', 'Referral Partner')`. It no longer has to guess string formatting.
- **Business Concept Mapping:** We manually map out confusing business rules in `schema_analyzer.py`. We explicitly tell the LLM: *"POSITION column in entity_placement = job title (e.g. Accountant). The 'position' table is NOT for job titles."* By feeding the LLM the exact business context, hallucination rates drop to near zero.

---

## 3. The End-to-End Data Fetching Process

Let's walk through the exact lifecycle of data fetching:

1. **Initialization:** The chatbot loads `schema/schema_context.json` into memory. This file is the "brain" that maps the user's plain English to the database reality.
2. **Prompt Construction:** `query_orchestrator.py` wraps the user's question with the schema JSON payload and system instructions (e.g., "Write SQLite-compatible SQL, do not use LIMIT clauses").
3. **AI Processing:** Azure OpenAI processes the prompt and returns a raw SQL string.
4. **Regex Extraction:** The orchestrator uses regular expressions to extract *just* the SQL code from the LLM's response (stripping away markdown like ```sql).
5. **Database Interfacing:** Python's built-in `sqlite3` library is used to open a cursor to `database/business_data.db`.
6. **Query Execution:** `cursor.execute(sql_query)` runs the query.
7. **Data Hydration:** `cursor.fetchall()` pulls every matching record into a Python list of tuples.
8. **Final Presentation:** The rows, along with their corresponding column headers (`cursor.description`), are either printed as a formatted table in the CLI or summarized by the LLM in Phase 3.

---

## 4. How `schema_context.json` is Made (Handling PK/FK and DB Introspection)

The `schema_context.json` is not hand-typed; it is dynamically and programmatically generated by `schema_analyzer.py` acting as a database reflection tool. Yes, it actively looks at the DB, including Primary Keys (PK) and Foreign Keys (FK)!

**The Introspection Process:**
1. **Database Connection:** The script connects to the live `business_data.db` SQLite database.
2. **Schema Reflection:** It iterates over every table using SQLite's internal metadata commands (e.g., `PRAGMA table_info(table_name)`). This command returns exactly how the database is structured: every column name, its specific data type (`INTEGER`, `TEXT`), and a boolean flag indicating if it is a Primary Key.
3. **Data Sampling (The Secret Sauce):** For every table, the script executes `SELECT * FROM table LIMIT 3`. It takes these 3 rows and associates the actual cell values with their respective columns. This is how the JSON payload gets populated with live sample data for the LLM to read.
4. **Foreign Key (FK) Inference:** Because the original CSVs did not have explicit Foreign Key constraints, the script deduces them intelligently. It scans column names for specific suffixes like `_EXD_OBJECT_ID` or `_ID`. If a column (that is not a Primary Key) is named `COMPANY_EXD_OBJECT_ID`, the script cross-references this against other tables and infers a relationship with `Entity_Company.Entity_ID`. It documents these inferred JOIN paths in the JSON.
5. **Appending Business Logic:** Finally, the script merges the automatically deduced schema with a hardcoded dictionary of `business_concepts` (like definitions for "Bench resources" or "Active Cases"), outputting the final `schema_context.json`.

---

## 5. Automated Database Implementation from `/Data` CSVs (Most Important)

The `/Data` folder contains raw CSV exports from various enterprise systems. Manually writing `CREATE TABLE` scripts for 21 different files (with thousands of rows and messy headers) is incredibly time-consuming. 

We completely automated this via **`db_manager.py`**, which acts as an intelligent ETL (Extract, Transform, Load) pipeline:

1. **Dynamic File Scanning:** The manager scans the `/Data` directory, identifying all `.csv` files.
2. **Intelligent Column Cleaning:** CSV headers exported from CRMs are notoriously bad for SQL databases (e.g., "1st Order Date", "Address (Line 1)").
   - `pandas` is used to load the CSV into memory.
   - A regex engine (`[^a-zA-Z0-9_]`) strips out parentheses, hyphens, and spaces, replacing them with underscores.
   - If a column name starts with a number (which breaks SQL), it automatically prefixes it with `col_` (e.g., `col_1st_Order_Date`).
   - Duplicate column names in the CSV are automatically numbered to avoid collisions.
3. **Data Type and Primary Key Inference:** 
   - The script inspects the `pandas` dataframe `dtype` for each column, mapping `int` to SQLite `INTEGER`, `float` to `REAL`, and `datetime/string` to `TEXT`.
   - It intelligently guesses the Primary Key by looking for column names that match `ID`, `table_name_ID`, or end in `Id`.
4. **Automated DDL (Data Definition Language):** Based on the inferences, it dynamically constructs a `CREATE TABLE` SQL string for each CSV and executes it.
5. **Bulk Data Insertion:** It uses the optimized `df.to_sql()` method to rapidly dump the entire CSV dataset into the newly created SQLite table.
6. **Automatic Indexing:** To ensure JOIN queries perform instantly, the script runs a final pass over the new database. It finds any column ending in `ID` (which it assumes is a Foreign Key) and automatically runs a `CREATE INDEX` command on it.

**The Result:** If the business exports a brand new CSV and drops it into `/Data`, a developer simply runs `python db_manager.py`, and the system will automatically clean it, infer its structure, build the table, insert the data, index the keys, and make it instantly queryable by the AI chatbot.
