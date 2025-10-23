import streamlit as st
import pandas as pd
from datetime import date
# --- FIX: Explicitly import the Google Sheets connection class to ensure registration ---
from st_gsheets_connection import GSheetsConnection 

# --- CONFIGURATION AND INSTRUCTIONS ---

# ! IMPORTANT: Replace this with your actual Google Sheet URL or ID
# You need to ensure your Sheet is shared with the service account email 
# provided in your Streamlit secrets.
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1dL-nn9YirbzRRTxSQDREnO7xo5mdGKqZuzToqKAij5A/edit"
SHEET_NAME = "Sheet1" # The name of the tab containing the data

# Define the columns (for structure integrity)
COLUMNS = [
    'Group_Association', 'President_Name', 'President_Email', 'President_Contact',
    'Secretary_Name', 'Secretary_Email', 'Secretary_Contact', 'Treasurer_Name',
    'Treasurer_Email', 'Treasurer_Contact', 'Last_Fee_Paid_Year', 'Web_Data_Updated'
]

# --- 1. LIVE DATA CONNECTION & LOADING ---

@st.cache_data(ttl=600) # Cache data for 10 minutes to avoid hitting Sheet limits frequently
def load_data():
    """
    Connects to the Google Sheet using st.connection and reads the data.
    Requires Google Sheets credentials configured in Streamlit secrets.toml.
    """
    try:
        # 1. Initialize the Google Sheets connection (requires 'gsheets' config in secrets.toml)
        # Note: The 'type' parameter is now optional/implied due to the explicit import above.
        conn = st.connection('gsheets', type='sheets')
        
        # 2. Query the data from the specified Sheet Name
        df = conn.read(spreadsheet=GOOGLE_SHEET_URL, worksheet=SHEET_NAME, ttl=600)
        
        # 3. Data Cleaning and Type Conversion
        # Ensure correct data types (especially for 'Year' fields)
        df['Last_Fee_Paid_Year'] = df['Last_Fee_Paid_Year'].fillna(0).astype(int)
        # Convert date to standard string format
        df['Web_Data_Updated'] = pd.to_datetime(df['Web_Data_Updated'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Ensure all required columns are present, filling missing ones with empty strings
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ''
        
        return df[COLUMNS] # Return with defined column order
    
    except Exception as e:
        st.error("🚨 Error connecting to Database. Please ensure the Google Sheet URL is correct and `secrets.toml` is configured.")
        st.exception(e)
        # Return an empty DataFrame structure on failure
        return pd.DataFrame(columns=COLUMNS)

def write_data(df_to_write):
    """
    Writes the entire DataFrame back to the Google Sheet.
    NOTE: Writing the entire sheet is simple but less efficient than targeted updates.
    """
    try:
        conn = st.connection('gsheets', type='sheets')
        # This function writes the DataFrame back, overwriting the entire sheet content
        # starting at the top-left cell (A1).
        conn.write(df_to_write, spreadsheet=GOOGLE_SHEET_URL, worksheet=SHEET_NAME)
        return True
    except Exception as e:
        st.error("🚨 Error writing data back to Google Sheets. Please check permissions.")
        st.exception(e)
        return False

# Initialize session state for the DataFrame if it's not already there
if 'df_orgaco' not in st.session_state:
    st.session_state.df_orgaco = load_data()

# --- 2. STREAMLIT APP CONFIGURATION ---

st.set_page_config(
    page_title="ORGACO Database Manager (Live GS)",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏛️ ORGACO Database Manager (Live Google Sheets)")
st.markdown("---")

# --- 3. TAB STRUCTURE ---

tab1, tab2 = st.tabs(["🔍 Search & Update Group", "➕ Add New Group"])

# --- 4. SEARCH & UPDATE LOGIC (TAB 1) ---

with tab1:
    st.header("Search and Update Details")

    df = st.session_state.df_orgaco

    # Get the list of all groups for the dropdown
    group_options = df['Group_Association'].sort_values().unique().tolist()
    
    selected_group_name = st.selectbox(
        "Select a Group or Association to view/edit:",
        options=group_options,
        index=0 if group_options else None, # Handle case where no data is loaded
        help="Start typing the name to quickly find the group."
    )

    if selected_group_name:
        # Filter the DataFrame for the selected group
        selected_row = df[df['Group_Association'] == selected_group_name].copy()

        if not selected_row.empty:
            st.subheader(f"Details for: {selected_group_name}")
            
            # Use st.data_editor to allow inline editing of the single row
            # Drop the 'Group_Association' column from the editor so the key cannot be changed
            df_display = selected_row.drop(columns=['Group_Association', 'Web_Data_Updated']).reset_index(drop=True)
            
            # Manually construct the data for the editor
            data_to_edit = df_display.to_dict('records')

            edited_data = st.data_editor(
                data_to_edit,
                column_config={
                    "Last_Fee_Paid_Year": st.column_config.NumberColumn(
                        "Last Fee Paid Year",
                        format="%d",
                        min_value=1900,
                        max_value=date.today().year + 1,
                        step=1,
                        help="Year the last membership fee was paid."
                    ),
                },
                hide_index=True,
                num_rows="fixed", # Ensure only one row is editable
                key="update_editor"
            )
            
            if st.button("Save Changes", type="primary"):
                try:
                    # 1. Get the current index of the selected group in the main DataFrame
                    idx_to_update = st.session_state.df_orgaco[st.session_state.df_orgaco['Group_Association'] == selected_group_name].index[0]
                    
                    # 2. Extract the edited row data
                    edited_series = pd.Series(edited_data[0])

                    # 3. Update all editable columns in the session state
                    for col in edited_series.index:
                        st.session_state.df_orgaco.loc[idx_to_update, col] = edited_series[col]

                    # 4. Update the Web_Data_Updated timestamp
                    st.session_state.df_orgaco.loc[idx_to_update, 'Web_Data_Updated'] = date.today().strftime('%Y-%m-%d')
                    
                    # 5. Write the ENTIRE updated DataFrame back to Google Sheets
                    if write_data(st.session_state.df_orgaco):
                        st.success(f"Successfully updated details for **{selected_group_name}** and saved to Google Sheets. Last updated: {date.today().strftime('%Y-%m-%d')}")
                        
                        # Clear the cache for the next load
                        load_data.clear()
                        # Rerun to refresh the display
                        st.rerun()

                except Exception as e:
                    st.error(f"An error occurred while preparing to save: {e}")
                    
        else:
            st.warning("No data found for the selected group.")

    else:
        st.info("Please select a group from the list.")

# --- 5. ADD NEW GROUP LOGIC (TAB 2) ---

with tab2:
    st.header("Add a New Group or Association")

    # Use st.form for atomic submission
    with st.form("new_group_form", clear_on_submit=True):
        st.subheader("Group/Association Details")
        new_group_name = st.text_input("Group/Association Name (Required)", max_chars=100)
        
        col_p, col_s, col_t = st.columns(3)
        
        # President Details
        with col_p:
            st.subheader("President")
            p_name = st.text_input("Name (President)", key="p_name")
            p_email = st.text_input("Email (President)", key="p_email")
            p_contact = st.text_input("Contact (President)", key="p_contact", max_chars=20)
        
        # Secretary Details
        with col_s:
            st.subheader("Secretary")
            s_name = st.text_input("Name (Secretary)", key="s_name")
            s_email = st.text_input("Email (Secretary)", key="s_email")
            s_contact = st.text_input("Contact (Secretary)", key="s_contact", max_chars=20)
            
        # Treasurer Details
        with col_t:
            st.subheader("Treasurer")
            t_name = st.text_input("Name (Treasurer)", key="t_name")
            t_email = st.text_input("Email (Treasurer)", key="t_email")
            t_contact = st.text_input("Contact (Treasurer)", key="t_contact", max_chars=20)

        st.markdown("---")
        
        col_fee, _ = st.columns(2)
        with col_fee:
            fee_year = st.number_input(
                "Last Fee Paid Year", 
                min_value=1900, 
                max_value=date.today().year, 
                value=date.today().year, 
                step=1
            )
        
        submitted = st.form_submit_button("Add New Group", type="primary")

        if submitted:
            if not new_group_name:
                st.error("The Group/Association Name is required.")
            elif new_group_name in st.session_state.df_orgaco['Group_Association'].tolist():
                st.error(f"The group **{new_group_name}** already exists. Please use the Search & Update tab.")
            else:
                # 1. Create a dictionary for the new row
                new_data = {
                    'Group_Association': new_group_name,
                    'President_Name': p_name,
                    'President_Email': p_email,
                    'President_Contact': p_contact,
                    'Secretary_Name': s_name,
                    'Secretary_Email': s_email,
                    'Secretary_Contact': s_contact,
                    'Treasurer_Name': t_name,
                    'Treasurer_Email': t_email,
                    'Treasurer_Contact': t_contact,
                    'Last_Fee_Paid_Year': fee_year,
                    'Web_Data_Updated': date.today().strftime('%Y-%m-%d')
                }
                
                # 2. Convert to DataFrame and append to session state
                new_df_row = pd.DataFrame([new_data], columns=COLUMNS)
                st.session_state.df_orgaco = pd.concat([st.session_state.df_orgaco, new_df_row], ignore_index=True)
                
                # 3. Write the ENTIRE updated DataFrame back to Google Sheets
                if write_data(st.session_state.df_orgaco):
                    st.success(f"Successfully added new group: **{new_group_name}** and saved to Google Sheets.")
                    st.balloons()
                    # Clear the cache for the next load
                    load_data.clear()
                    # Rerun to refresh the search list
                    st.rerun()

# --- 6. SIDEBAR AND INSTRUCTIONS ---
with st.sidebar:
    st.header("Configuration Required")
    st.warning("You MUST complete the steps below for the app to work.")
    st.markdown("""
        1.  **Replace Placeholder URL:** Update the `GOOGLE_SHEET_URL` variable in the code with your actual Google Sheet link.
        2.  **Configure Secrets:** Add a `.streamlit/secrets.toml` file in your Streamlit repository's root directory with your Google Sheets service account credentials.
    """)
    st.code("""
# .streamlit/secrets.toml
[gsheets]
service_account_email = "your-service-account@xxx.iam.gserviceaccount.com"
private_key = "---BEGIN PRIVATE KEY---\\n..."
# The 'url' parameter is optional if you use the full URL in the Python code
# url = "YOUR_SPREADSHEET_ID_HERE"
    """)
    st.write("---")
    st.header("Database Status")
    st.write(f"Total Records: **{len(st.session_state.df_orgaco)}**")
    
    if st.checkbox("Show Raw Live Data Table (for debugging)"):
        st.dataframe(st.session_state.df_orgaco)
