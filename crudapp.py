import streamlit as st
import sqlite3
import re
import datetime

DB_NAME = "patients.db"

# ----------------- Database Functions -----------------

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            address TEXT,
            email TEXT UNIQUE NOT NULL,
            phone TEXT
        )
    """)
    conn.commit()
    # Run migrations to ensure new columns exist
    migrate_db()
    conn.close()

def migrate_db():
    """Ensure schema has new date columns; add them if missing and backfill where reasonable."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("PRAGMA table_info(patients)")
    existing_cols = {row[1] for row in c.fetchall()}

    if "date_of_birth" not in existing_cols:
        c.execute("ALTER TABLE patients ADD COLUMN date_of_birth TEXT")
    if "date_of_entry" not in existing_cols:
        # Store dates as ISO strings (YYYY-MM-DD)
        c.execute("ALTER TABLE patients ADD COLUMN date_of_entry TEXT")

    # Backfill date_of_entry with today's date where NULL
    today_iso = datetime.date.today().isoformat()
    try:
        c.execute("UPDATE patients SET date_of_entry = ? WHERE date_of_entry IS NULL", (today_iso,))
    except Exception:
        # Ignore if column didn't exist prior to this run; safe to continue
        pass

    conn.commit()
    conn.close()

def add_patient(first_name, last_name, address, email, phone, date_of_birth, date_of_entry):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO patients (first_name, last_name, address, email, phone, date_of_birth, date_of_entry)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (first_name, last_name, address, email, phone, date_of_birth, date_of_entry))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: patients.email" in str(e):
            return False, "Email already exists."
        return False, str(e)
    finally:
        conn.close()

def get_all_patients():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM patients ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_patient_by_id(patient_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM patients WHERE id=?", (patient_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_patient(patient_id, first_name, last_name, address, email, phone, date_of_birth, date_of_entry):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE patients
            SET first_name=?, last_name=?, address=?, email=?, phone=?, date_of_birth=?, date_of_entry=?
            WHERE id=?
        """, (first_name, last_name, address, email, phone, date_of_birth, date_of_entry, patient_id))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: patients.email" in str(e):
            return False, "Email already exists."
        return False, str(e)
    finally:
        conn.close()

def delete_patient(patient_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM patients WHERE id=?", (patient_id,))
    conn.commit()
    conn.close()

def search_patients(query="", last_name_filter=None, email_domain_filter=None):
    conn = get_connection()
    c = conn.cursor()
    sql = "SELECT * FROM patients WHERE 1=1"
    params = []
    if query:
        sql += " AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ? OR phone LIKE ?)"
        like_query = f"%{query}%"
        params.extend([like_query, like_query, like_query, like_query])
    if last_name_filter and last_name_filter != "All":
        sql += " AND last_name = ?"
        params.append(last_name_filter)
    if email_domain_filter and email_domain_filter != "All":
        sql += " AND email LIKE ?"
        params.append(f"%@{email_domain_filter}")
    sql += " ORDER BY id DESC"
    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_last_names():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT last_name FROM patients ORDER BY last_name")
    rows = c.fetchall()
    conn.close()
    return [row["last_name"] for row in rows if row["last_name"]]

def get_all_email_domains():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT email FROM patients")
    emails = [row["email"] for row in c.fetchall()]
    domains = set()
    for email in emails:
        if "@" in email:
            domains.add(email.split("@")[1])
    return sorted(domains)

# ----------------- Validation Functions -----------------

def is_valid_email(email):
    # Simple regex for email validation
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return re.match(pattern, email) is not None

def is_valid_phone(phone):
    # Allows optional + at start, then 10-15 digits
    pattern = r"^\+?\d{10,15}$"
    return re.match(pattern, phone) is not None

# ----------------- Streamlit UI -----------------

st.set_page_config(page_title="Patient Management", layout="centered")
st.title("Patient Management System")

init_db()

menu = st.sidebar.radio("Navigation", ["Add Patient", "View/Search Patients"])

if menu == "Add Patient":
    st.header("Add New Patient")
    with st.form("add_patient_form", clear_on_submit=True):
        first_name = st.text_input("First Name *")
        last_name = st.text_input("Last Name *")
        address = st.text_input("Address")
        email = st.text_input("Email *")
        phone = st.text_input("Phone")
        col_a, col_b = st.columns(2)
        with col_a:
            dob_date = st.date_input("Date of Birth", value=None, format="YYYY-MM-DD")
        with col_b:
            doe_date = st.date_input("Date of Entry", value=datetime.date.today(), format="YYYY-MM-DD")
        submitted = st.form_submit_button("Add Patient")
        if submitted:
            errors = []
            if not first_name.strip():
                errors.append("First name is required.")
            if not last_name.strip():
                errors.append("Last name is required.")
            if not email.strip():
                errors.append("Email is required.")
            elif not is_valid_email(email.strip()):
                errors.append("Invalid email format.")
            if phone.strip():
                if not is_valid_phone(phone.strip()):
                    errors.append("Phone must be 10–15 digits, optional '+' at start.")
            # Validate dates (optional DOB, required DOE)
            dob_str = dob_date.isoformat() if dob_date else None
            doe_str = doe_date.isoformat() if doe_date else None
            if not doe_str:
                errors.append("Date of Entry is required.")
            if errors:
                for err in errors:
                    st.error(err)
            else:
                success, error = add_patient(
                    first_name.strip(), last_name.strip(), address.strip(), email.strip(), phone.strip(), dob_str, doe_str
                )
                if success:
                    st.success("Patient added successfully!")
                else:
                    st.error(f"Error adding patient: {error}")

elif menu == "View/Search Patients":
    st.header("View & Search Patients")

    # --- Search and Filter Controls ---
    col1, col2, col3 = st.columns([2,2,2])
    with col1:
        search_query = st.text_input("Search (name, email, phone)", key="search_query")
    with col2:
        last_names = ["All"] + get_all_last_names()
        last_name_filter = st.selectbox("Filter by Last Name", last_names, key="last_name_filter")
    with col3:
        email_domains = ["All"] + get_all_email_domains()
        email_domain_filter = st.selectbox("Filter by Email Domain", email_domains, key="email_domain_filter")

    patients = search_patients(
        query=search_query.strip(),
        last_name_filter=last_name_filter,
        email_domain_filter=email_domain_filter
    )

    # --- Data Table ---
    st.subheader("Patient List")
    if patients:
        import pandas as pd
        df = pd.DataFrame([{
            "ID": row["id"],
            "First Name": row["first_name"],
            "Last Name": row["last_name"],
            "Address": row["address"],
            "Email": row["email"],
            "Phone": row["phone"],
            "Date of Birth": row["date_of_birth"],
            "Date of Entry": row["date_of_entry"]
        } for row in patients])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No patients found.")

    # --- Select Patient for Edit/Delete ---
    st.markdown("---")
    st.subheader("Edit or Delete Patient")
    patient_options = [
        f"{row['first_name']} {row['last_name']} (ID: {row['id']})"
        for row in patients
    ]
    selected_patient = st.selectbox(
        "Select a patient to edit or delete", [""] + patient_options, key="select_patient"
    )
    if selected_patient:
        selected_id = int(selected_patient.split("ID: ")[1].replace(")", ""))
        patient = get_patient_by_id(selected_id)
        if patient:
            with st.form(f"edit_patient_form_{selected_id}"):
                new_first_name = st.text_input("First Name *", value=patient["first_name"], key=f"edit_fn_{selected_id}")
                new_last_name = st.text_input("Last Name *", value=patient["last_name"], key=f"edit_ln_{selected_id}")
                new_address = st.text_input("Address", value=patient["address"], key=f"edit_addr_{selected_id}")
                new_email = st.text_input("Email *", value=patient["email"], key=f"edit_email_{selected_id}")
                new_phone = st.text_input("Phone", value=patient["phone"], key=f"edit_phone_{selected_id}")
                col_da, col_db = st.columns(2)
                existing_dob = patient["date_of_birth"]
                existing_doe = patient["date_of_entry"]
                with col_da:
                    new_dob = st.date_input(
                        "Date of Birth",
                        value=datetime.date.fromisoformat(existing_dob) if existing_dob else None,
                        format="YYYY-MM-DD",
                        key=f"edit_dob_{selected_id}"
                    )
                with col_db:
                    new_doe = st.date_input(
                        "Date of Entry",
                        value=datetime.date.fromisoformat(existing_doe) if existing_doe else datetime.date.today(),
                        format="YYYY-MM-DD",
                        key=f"edit_doe_{selected_id}"
                    )
                colu1, colu2 = st.columns(2)
                update_btn = colu1.form_submit_button("Update")
                delete_btn = colu2.form_submit_button("Delete")
                if update_btn:
                    errors = []
                    if not new_first_name.strip():
                        errors.append("First name is required.")
                    if not new_last_name.strip():
                        errors.append("Last name is required.")
                    if not new_email.strip():
                        errors.append("Email is required.")
                    elif not is_valid_email(new_email.strip()):
                        errors.append("Invalid email format.")
                    if new_phone.strip():
                        if not is_valid_phone(new_phone.strip()):
                            errors.append("Phone must be 10–15 digits, optional '+' at start.")
                    new_dob_str = new_dob.isoformat() if new_dob else None
                    new_doe_str = new_doe.isoformat() if new_doe else None
                    if not new_doe_str:
                        errors.append("Date of Entry is required.")
                    if errors:
                        for err in errors:
                            st.error(err)
                    else:
                        success, error = update_patient(
                            selected_id,
                            new_first_name.strip(),
                            new_last_name.strip(),
                            new_address.strip(),
                            new_email.strip(),
                            new_phone.strip(),
                            new_dob_str,
                            new_doe_str
                        )
                        if success:
                            st.success("Patient updated successfully!")
                        else:
                            st.error(f"Error updating patient: {error}")
                if delete_btn:
                    delete_patient(selected_id)
                    st.success("Patient deleted successfully!")

