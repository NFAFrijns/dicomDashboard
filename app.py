import streamlit as st
import pydicom
import pandas as pd
import plotly.express as px
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re


def parse_dicom_date(date_str: str) -> datetime | None:
    """Parse DICOM date format (YYYYMMDD) to datetime."""
    if not date_str:
        return None
    try:
        # DICOM date format is typically YYYYMMDD
        date_str = str(date_str).strip()
        if len(date_str) >= 8:
            return datetime.strptime(date_str[:8], "%Y%m%d")
    except Exception:
        pass
    return None


def parse_age(age_str: str) -> int | None:
    """Parse DICOM age string (e.g., '065Y') to integer years."""
    if not age_str:
        return None
    try:
        age_str = str(age_str).strip()
        # Format is typically 065Y (3 digits + unit)
        match = re.match(r"(\d+)([YMWD])?", age_str)
        if match:
            value = int(match.group(1))
            unit = match.group(2) or "Y"
            if unit == "Y":
                return value
            elif unit == "M":
                return value // 12
            elif unit == "W":
                return value // 52
            elif unit == "D":
                return value // 365
    except Exception:
        pass
    return None


def scan_ct_folders(folder_path: str) -> list[dict]:
    """
    Scan folder structure for CT folders only.
    Expected structure: Patient/Timepoint/CT_Patient_Timepoint/
    Only reads FIRST slice for metadata (fast!).
    """
    dicom_data = []
    folder = Path(folder_path)

    if not folder.exists():
        return []

    # Find all CT_ folders (skip MASK_ folders)
    for ct_folder in folder.rglob("CT_*"):
        if not ct_folder.is_dir():
            continue

        # Get all DICOM files in this CT folder
        dcm_files = list(ct_folder.glob("*.dcm"))
        if not dcm_files:
            continue

        # Sort to get consistent first slice
        dcm_files.sort()
        first_slice = dcm_files[0]

        try:
            ds = pydicom.dcmread(str(first_slice), stop_before_pixels=True)

            # Extract folder structure: Patient/Timepoint/CT_...
            relative_path = ct_folder.relative_to(folder)
            parts = relative_path.parts

            # Parse patient and timepoint from folder structure
            patient = parts[0] if len(parts) >= 1 else "unknown"
            timepoint = parts[1] if len(parts) >= 2 else "unknown"

            record = {
                "Patient": patient,
                "Timepoint": timepoint,
                "Sex": getattr(ds, "PatientSex", None),
                "Age": parse_age(getattr(ds, "PatientAge", None)),
                "SliceThickness": float(ds.SliceThickness) if hasattr(ds, "SliceThickness") else None,
                "SliceCount": len(dcm_files),
                "Modality": getattr(ds, "Modality", None),
                "StudyDate": parse_dicom_date(getattr(ds, "StudyDate", None)),
                "_ct_folder": str(ct_folder),
            }

            dicom_data.append(record)

        except Exception as e:
            st.warning(f"Could not read {first_slice}: {e}")

    return dicom_data


def calculate_time_between_scans(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate time between 1YR and 5YR scans for each patient."""
    time_data = []

    patients = df["Patient"].unique()

    for patient in patients:
        patient_df = df[df["Patient"] == patient]

        # Find 1YR and 5YR records
        yr1 = patient_df[patient_df["Timepoint"] == "1YR"]
        yr5 = patient_df[patient_df["Timepoint"] == "5YR"]

        if len(yr1) > 0 and len(yr5) > 0:
            date1 = yr1.iloc[0]["StudyDate"]
            date5 = yr5.iloc[0]["StudyDate"]

            if date1 and date5:
                delta = relativedelta(date5, date1)
                total_months = delta.years * 12 + delta.months

                time_data.append({
                    "Patient": patient,
                    "1YR_Date": date1.strftime("%Y-%m-%d"),
                    "5YR_Date": date5.strftime("%Y-%m-%d"),
                    "Years": delta.years,
                    "Months": delta.months,
                    "Total_Months": total_months,
                    "Time_Diff": f"{delta.years}y {delta.months}m",
                })

    return pd.DataFrame(time_data)


def render_donut_chart(df: pd.DataFrame, field: str):
    """Render a donut chart for categorical data."""
    counts = df[field].value_counts().reset_index()
    counts.columns = [field, "count"]

    fig = px.pie(
        counts,
        values="count",
        names=field,
        hole=0.4,
        title=f"Distribution of {field}",
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)


def render_count_table(df: pd.DataFrame, field: str):
    """Render a table with n (%) for categorical data."""
    counts = df[field].value_counts()
    total = len(df)

    table_data = []
    for value, count in counts.items():
        percentage = (count / total) * 100
        table_data.append({
            field: value,
            "n": count,
            "%": f"{percentage:.1f}%",
            "n (%)": f"{count} ({percentage:.1f}%)",
        })

    result_df = pd.DataFrame(table_data)
    st.dataframe(result_df, use_container_width=True, hide_index=True)


def render_stats_table(df: pd.DataFrame, field: str):
    """Render a table with mean (SD) for numerical data."""
    # Try to convert to numeric
    numeric_values = pd.to_numeric(df[field], errors="coerce")
    valid_count = numeric_values.notna().sum()

    if valid_count == 0:
        st.warning(f"No numeric values found in '{field}'")
        return

    mean_val = numeric_values.mean()
    std_val = numeric_values.std()
    min_val = numeric_values.min()
    max_val = numeric_values.max()
    median_val = numeric_values.median()

    stats_df = pd.DataFrame({
        "Statistic": ["n", "Mean", "SD", "Mean (SD)", "Median", "Min", "Max"],
        "Value": [
            valid_count,
            f"{mean_val:.2f}",
            f"{std_val:.2f}",
            f"{mean_val:.2f} ({std_val:.2f})",
            f"{median_val:.2f}",
            f"{min_val:.2f}",
            f"{max_val:.2f}",
        ],
    })
    st.dataframe(stats_df, use_container_width=True, hide_index=True)


def main():
    st.set_page_config(
        page_title="DICOM CT Metadata Dashboard",
        page_icon="",
        layout="wide",
    )

    st.title("DICOM CT Metadata Dashboard")
    st.markdown("Fast metadata extraction from CT scans (reads only first slice per scan).")

    # Folder selection
    folder_path = st.text_input(
        "Enter the path to your DICOM folder:",
        placeholder="e.g., C:/data/dicom or /home/user/dicom",
    )

    if not folder_path:
        st.info("Expected folder structure: Patient/Timepoint/CT_Patient_Timepoint/")
        return

    # Scan CT folders only (fast - reads only first slice)
    with st.spinner("Scanning CT folders..."):
        dicom_data = scan_ct_folders(folder_path)

    if not dicom_data:
        st.error("No CT folders found. Expected structure: Patient/Timepoint/CT_*/")
        return

    df = pd.DataFrame(dicom_data)
    st.success(f"Found {len(df)} CT scans across {df['Patient'].nunique()} patients")

    # ===================
    # STANDARD METRICS
    # ===================
    st.divider()
    st.header("Standard Metrics")

    col1, col2 = st.columns(2)

    with col1:
        # Sex distribution
        st.subheader("Sex")
        if df["Sex"].notna().any():
            render_count_table(df, "Sex")
            render_donut_chart(df, "Sex")
        else:
            st.warning("No sex data available")

        # Modality
        st.subheader("Modality")
        if df["Modality"].notna().any():
            render_count_table(df, "Modality")
        else:
            st.warning("No modality data available")

    with col2:
        # Age statistics
        st.subheader("Age (years)")
        if df["Age"].notna().any():
            render_stats_table(df, "Age")
        else:
            st.warning("No age data available")

        # Slice Thickness
        st.subheader("Slice Thickness (mm)")
        if df["SliceThickness"].notna().any():
            render_stats_table(df, "SliceThickness")
        else:
            st.warning("No slice thickness data available")

        # Slice Count
        st.subheader("Slice Count")
        render_stats_table(df, "SliceCount")

    # ===================
    # TIME BETWEEN SCANS
    # ===================
    st.divider()
    st.header("Time Between 1YR and 5YR CT Scans")

    time_df = calculate_time_between_scans(df)

    if len(time_df) > 0:
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Patients with both scans", len(time_df))
        with col2:
            mean_months = time_df["Total_Months"].mean()
            st.metric("Mean time difference", f"{mean_months / 12:.1f} years ({mean_months:.0f} months)")
        with col3:
            std_months = time_df["Total_Months"].std()
            st.metric("SD", f"{std_months:.1f} months")

        # Detailed table
        st.subheader("Per-Patient Time Differences")
        display_df = time_df[["Patient", "1YR_Date", "5YR_Date", "Time_Diff"]].copy()
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Histogram of time differences
        fig = px.histogram(
            time_df,
            x="Total_Months",
            nbins=20,
            title="Distribution of Time Between Scans (months)",
            labels={"Total_Months": "Months between scans"},
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No patients found with both 1YR and 5YR scans")

    # ===================
    # RAW DATA
    # ===================
    st.divider()
    st.header("Raw Data")

    # Show summary table
    display_cols = ["Patient", "Timepoint", "Sex", "Age", "SliceThickness", "SliceCount", "Modality"]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

    # Export options
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Download CT metadata as CSV",
            data=df[display_cols].to_csv(index=False),
            file_name="ct_metadata.csv",
            mime="text/csv",
        )
    with col2:
        if len(time_df) > 0:
            st.download_button(
                label="Download time differences as CSV",
                data=time_df.to_csv(index=False),
                file_name="time_between_scans.csv",
                mime="text/csv",
            )


if __name__ == "__main__":
    main()
