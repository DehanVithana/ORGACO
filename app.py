import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# 1. Configuration and Connection
# --------------------------------

# ⚠️ SECURITY WARNING: Never hardcode secrets in production code.
# Use Streamlit Secrets for deployment!
# For local testing, you can define the URL here or use an .env file.
# For Streamlit Cloud deployment, you MUST use st.secrets.
DATABASE_URL = "postgresql://postgres:orepa@2025@db.exxeppgsduhrvvlkyplj.supabase.co:5432/postgres"
TABLE_NAME = "dbORGACO"  # ⚠️ Replace with your actual table name

# --- Function to get a database engine/connection ---
@st.cache_resource
def init_connection():
    # Use st.secrets in Streamlit Cloud deployment
    if "db_url" in st.secrets:
        return create_engine(st.secrets["db_url"])
    # Fallback for local testing (replace with actual URL if testing locally)
    return create_engine(DATABASE_URL)

engine = init_connection()

# 2. Helper Functions for Database Operations
# ---------------------------------------------

def fetch_group_associations():
    """Fetches all distinct Group_Association values for the search filter."""
    query = text(f"SELECT DISTINCT \"Group_Association\" FROM {TABLE_NAME} ORDER BY \"Group_Association\";")
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df['Group_Association'].tolist()

def fetch_data_by_group(group_name):
    """Fetches all records for a specific Group_Association."""
    # Note: Using double quotes around column/table names for case sensitivity in PostgreSQL
    query = text(f"SELECT * FROM {TABLE_NAME} WHERE \"Group_Association\" = :group_name;")
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={'group_name': group_name})
    return df

def update_record(record_id, column_name, new_value):
    """Updates a single field for a given record ID."""
    try:
        # Sanitize column_name to prevent SQL Injection in the column name part
        # Assuming record_id is the primary key (PK). Replace 'id' with your PK column name.
        pk_column = "id" # ⚠️ Replace 'id' with your actual Primary Key column name
        
        # Prepare the query using parameter binding for the value
        # Column name is safe if you are sure about the allowed columns
        query = text(f"UPDATE {TABLE_NAME} SET \"{column_name}\" = :new_value WHERE \"{pk_column}\" = :record_id;")
        
        with engine.connect() as conn:
            conn.execute(query, {'new_value': new_value, 'record_id': record_id})
            conn.commit()
        st.success(f"Successfully updated {column_name} for record ID {record_id}.")
    except Exception as e:
        st.error(f"Error updating record: {e}")

def add_new_group(new_group_name):
    """Adds a new Group_Association record (only filling the group name)."""
    try:
        # Insert statement for a new group. Assumes other columns are nullable or have defaults.
        query = text(f"INSERT INTO {TABLE_NAME} (\"Group_Association\") VALUES (:new_group);")
        with engine.connect() as conn:
            conn.execute(query, {'new_group': new_group_name})
            conn.commit()
        st.success(f"Successfully added new Group_Association: **{new_group_name}** 🎉")
        # Rerun to update the selection list
        st.experimental_rerun()
    except Exception as e:
        st.error(f"Error adding new group: {e}")

# 3. Streamlit App Layout
# -----------------------------
st.title("Supabase Group Data Manager 📊")

group_associations = fetch_group_associations()

# --- Feature 1: Search, View, and Update ---
st.header("Search and Update Existing Data")

selected_group = st.selectbox(
    "Select a Group_Association to view and edit:",
    options=[''] + group_associations,
    index=0,
    help="Start typing to quickly find a group."
)

if selected_group:
    data_df = fetch_data_by_group(selected_group)
    
    if data_df.empty:
        st.warning(f"No data found for Group_Association: **{selected_group}**")
    else:
        st.subheader(f"Data for: {selected_group}")
        st.write(f"Showing **{len(data_df)}** record(s).")
        
        # Display editable data table
        # NOTE: st.data_editor is the easiest way, but sometimes complex for direct DB update.
        # We will use st.columns and input fields for a more controlled update.
        
        pk_column = "id" # ⚠️ Replace 'id' with your actual Primary Key column name
        non_editable_cols = [pk_column, 'Group_Association'] # Columns users shouldn't change
        
        for index, row in data_df.iterrows():
            record_id = row[pk_column]
            
            with st.expander(f"Record ID: {record_id} (Group: {row['Group_Association']})"):
                cols = st.columns(3)
                col_index = 0
                
                # Iterate over columns to create editable input fields
                for col in data_df.columns:
                    current_value = row[col]
                    
                    if col in non_editable_cols:
                        cols[col_index % 3].info(f"{col}: {current_value}")
                    else:
                        new_value = cols[col_index % 3].text_input(
                            f"Update {col} (ID: {record_id})",
                            value=str(current_value),
                            key=f"input_{record_id}_{col}"
                        )
                        
                        # Check if value has changed and update button is pressed
                        if str(new_value) != str(current_value):
                            if cols[col_index % 3].button(f"Save {col}", key=f"btn_save_{record_id}_{col}"):
                                update_record(record_id, col, new_value)
                                # Rerun to show updated data
                                st.experimental_rerun()
                    
                    col_index += 1

st.markdown("---")

# --- Feature 2: Add New Group_Association ---
st.header("Add New Group_Association")

with st.form("new_group_form"):
    new_group_input = st.text_input("New Group_Association Name", max_chars=100)
    submitted = st.form_submit_button("Add New Group")
    
    if submitted and new_group_input:
        add_new_group(new_group_input.strip())
    elif submitted and not new_group_input:
        st.warning("Please enter a name for the new Group_Association.")
