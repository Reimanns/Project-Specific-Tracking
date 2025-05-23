import streamlit as st
import pandas as pd
import datetime
import altair as alt
import plotly.express as px

st.set_page_config(layout="wide")
# ---------------------------
# Helper Functions
# ---------------------------
def normalize_date(dt):
    """Set time components to zero."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

def get_weekly_dates(start_date, end_date):
    """Return a list of weekly dates (Mondays) between start_date and end_date."""
    current = start_date
    # Back up to the most recent Monday
    while current.weekday() != 0:  # Monday = 0
        current -= datetime.timedelta(days=1)
    dates = []
    while current <= end_date:
        dates.append(current)
        current += datetime.timedelta(days=7)
    return dates

def format_date(dt):
    return dt.strftime("%Y-%m-%d")

# ---------------------------
# Hard-Coded Status Data
# ---------------------------
status_data = {
    "All":       {"Canceled":16, "Released":73, "In Check":1, "Not Started":27, "Redlines":2, "In Progress":15},
    "BDDS":      {"Canceled":6,  "Released":27,  "In Check":0, "Not Started":3,  "Redlines":0, "In Progress":5},
    "Maverick":  {"Canceled":3,  "Released":27, "In Check":2, "Not Started":3,  "Redlines":0, "In Progress":0},
    "Elisen":    {"Canceled":0,  "Released":16,  "In Check":0, "Not Started":0,  "Redlines":0, "In Progress":3},
    "Cotney":    {"Canceled":5,  "Released":1,  "In Check":1, "Not Started":12, "Redlines":1, "In Progress":4},
    "Citadel":   {"Canceled":2,  "Released":11,  "In Check":0, "Not Started":0,  "Redlines":0, "In Progress":1}
}

status_labels = ["Canceled", "Released", "In Check", "Not Started", "Redlines", "In Progress"]

# ---------------------------
# Sidebar Navigation
# ---------------------------
page = st.sidebar.radio("Select Dashboard", ["Engineering Dashboard", "Material Dashboard"])

# ---------------------------
# Engineering Dashboard
# ---------------------------
if page == "Engineering Dashboard":
    st.image("citadel_logo.png", width=300)
    st.title("Engineering Burndown and Status Distribution: Parallel")

    # Load the CSV data (cache to speed up reloads)
    @st.cache_data
    @st.cache_data
    def load_data():
        df = pd.read_csv("drawings.csv", parse_dates=["EstimatedCompletionDate", "ReleasedDate"])
        # Remove rows with missing/blank DrawingNumber
        df = df[df["DrawingNumber"].notna() & (df["DrawingNumber"].str.strip() != "")]
        if "EstimatedCompletionDate" in df.columns:
            df["EstimatedCompletionDate"] = pd.to_datetime(df["EstimatedCompletionDate"], errors='coerce')
            df["EstimatedCompletionDate"] = df["EstimatedCompletionDate"].apply(normalize_date)
        if "ReleasedDate" in df.columns:
            df["ReleasedDate"] = pd.to_datetime(df["ReleasedDate"], errors='coerce')
            df["ReleasedDate"] = df["ReleasedDate"].apply(normalize_date)
        return df


    df = load_data()

    # Combine owners from CSV and our hard-coded status data
    csv_owners = df["DrawingOwner"].dropna().unique().tolist()
    combined_owners = sorted(set(csv_owners + list(status_data.keys())))
    # Default to "All" if available
    default_idx = combined_owners.index("All") if "All" in combined_owners else 0
    owner = st.selectbox("Select Owner", combined_owners, index=default_idx)

    # Filter data for selected owner
    if owner != "All":
        df_filtered = df[df["DrawingOwner"] == owner]
    else:
        df_filtered = df.copy()

    # ---------------------------
    # Burndown Chart Calculation
    # ---------------------------
    if df_filtered.empty:
        st.warning(f"No data available for owner '{owner}'.")
    else:
        total_tasks = len(df_filtered)
        valid_ecd = df_filtered["EstimatedCompletionDate"].dropna()
        valid_rd = df_filtered["ReleasedDate"].dropna()
        if valid_ecd.empty:
            st.error("No valid EstimatedCompletionDate found for the selected owner.")
        else:
            earliest = valid_ecd.min()
            # Combine dates from both columns to find the overall latest date
            all_dates = pd.concat([valid_ecd, valid_rd])
            latest = all_dates.max() if not all_dates.empty else earliest
            latest = latest + pd.Timedelta(days=7)  # extend the range a bit

            weekly_dates = get_weekly_dates(earliest, latest)
            planned_remaining = []
            actual_remaining = []
            today = normalize_date(datetime.datetime.now())
            # Determine the Monday of the current week
            current_monday = today
            while current_monday.weekday() != 0:
                current_monday -= datetime.timedelta(days=1)
            max_actual_week = current_monday + datetime.timedelta(days=7)

            actual_completed_today = df_filtered[df_filtered["ReleasedDate"] <= today].shape[0]
            for week in weekly_dates:
                # Calculate planned remaining tasks as before
                planned_completed = df_filtered[df_filtered["EstimatedCompletionDate"] <= week].shape[0]
                planned_remaining.append(total_tasks - planned_completed)
    
                # For the actual remaining extending a week out:
                if week > max_actual_week:
                    # Terminate the actual remaining line after one week past the current week
                    actual_remaining.append(None)
                elif week > today:
                    # For weeks between today and max_actual_week, use today's data
                    actual_remaining.append(total_tasks - actual_completed_today)
                else:
                     # For weeks up to today, calculate the actual completed count
                    actual_completed = df_filtered[df_filtered["ReleasedDate"] <= week].shape[0]
                    actual_remaining.append(total_tasks - actual_completed)
    
                # For the actual remaining tasks, only compute up to today:
                #if week > today:
                    #actual_remaining.append(None)
                #else:
                    #actual_completed = df_filtered[df_filtered["ReleasedDate"] <= week].shape[0]
                    #actual_remaining.append(total_tasks - actual_completed)


            burndown_df = pd.DataFrame({
                "Week": [format_date(d) for d in weekly_dates],
                "Planned Remaining": planned_remaining,
                "Actual Remaining": actual_remaining
            })
            burndown_melt = burndown_df.melt("Week", var_name="Type", value_name="Remaining")

            st.subheader(f"Weekly Burndown: Planned vs. Actual ({owner})")
            burndown_chart = alt.Chart(burndown_melt).mark_line(point=True).encode(
                x=alt.X("Week:N", title="Week Start (Monday)"),
                y=alt.Y("Remaining:Q", title="Drawings Remaining"),
                color="Type:N"
            ).properties(width=700, height=400, title=f"Weekly Burndown: Planned vs Actual ({owner})")
            st.altair_chart(burndown_chart)

    # ---------------------------
    # Status Distribution Bar Chart
    # ---------------------------
    st.subheader(f"Status Distribution ({owner})")
    owner_status = status_data.get(owner, {label: 0 for label in status_labels})
    status_df = pd.DataFrame({
        "Status": status_labels,
        "Count": [owner_status.get(label, 0) for label in status_labels]
    })
    bar_chart = alt.Chart(status_df).mark_bar().encode(
        x=alt.X("Status:N", sort=None, title="Status Category"),
        y=alt.Y("Count:Q", title="Number of Drawings"),
        color=alt.Color("Status:N")
    ).properties(width=700, height=400, title=f"Drawings by Status: {owner}")
    st.altair_chart(bar_chart)

# ---------------------------
# Material Dashboard
# ---------------------------
elif page == "Material Dashboard":
    st.image("citadel_logo.png", width=300)
    st.title("Material Dashboard: Parallel")

    # Navigation link (here you could use the sidebar to switch pages)
    st.info("Use the sidebar to switch back to the Engineering Dashboard.")

    # ---------------------------
    # Dashboard Cards
    # ---------------------------
    st.subheader("Dashboard Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Demands", 165)
        st.metric("Total Unapproved Reqs", 7)
    with col2:
        st.metric("Total Services", 53)
        st.metric("Total Approved Reqs", 158)
    with col3:
        st.metric("Total On P.O.", 130)
        st.metric("% Material On Site", "80%")
    st.metric("Total Parts Expected Late", 53)

    # ---------------------------
    # Donut Chart: Late vs. On-Time Parts
    # ---------------------------
    st.subheader("Parts: Late vs. On-Time")
    total_parts = 152
    late_parts = 53
    on_time_parts = total_parts - late_parts
    donut_data = pd.DataFrame({
        "Status": ["Late Parts", "On-Time Parts"],
        "Count": [late_parts, on_time_parts]
    })
    fig = px.pie(donut_data, names="Status", values="Count", hole=0.5,
                 color_discrete_sequence=["#FF6384", "#36A2EB"])
    fig.update_layout(
        title_text="Late vs. On-Time Parts",
        annotations=[dict(text='Parts', x=0.5, y=0.5, font_size=20, showarrow=False)]
    )
    st.plotly_chart(fig)
