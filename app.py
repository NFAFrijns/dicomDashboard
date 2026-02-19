import streamlit as st
import pydicom
import pandas as pd
import plotly.express as px
from pathlib import Path
import os


def scan_dicom_folder(folder_path: str) -> list[dict]:
    """Recursively scan folder for DICOM files and extract metadata."""
    dicom_data = []
    folder = Path(folder_path)

    if not folder.exists():
        return []

    # Find all .dcm files recursively
    for dcm_file in folder.rglob("*.dcm"):
        try:
            ds = pydicom.dcmread(str(dcm_file), stop_before_pixels=True)

            # Extract folder structure info (patient/year)
            relative_path = dcm_file.relative_to(folder)
            parts = relative_path.parts

            record = {
                "_file_path": str(dcm_file),
                "_patient": parts[0] if len(parts) > 1 else "unknown",
                "_timepoint": parts[1] if len(parts) > 2 else "unknown",
            }

            # Extract all metadata elements
            for elem in ds:
                if elem.VR != "SQ" and elem.keyword:  # Skip sequences and empty keywords
                    try:
                        value = elem.value
                        # Convert to string for consistent handling
                        if hasattr(value, "__iter__") and not isinstance(value, str):
                            value = str(value)
                        record[elem.keyword] = value
                    except Exception:
                        pass

            dicom_data.append(record)
        except Exception as e:
            st.warning(f"Could not read {dcm_file}: {e}")

    return dicom_data


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
        page_title="DICOM Metadata Analyzer",
        page_icon="🏥",
        layout="wide",
    )

    st.title("DICOM Metadata Analyzer")
    st.markdown("Analyze metadata from multiple DICOM files organized in patient/timepoint folders.")

    # Folder selection
    folder_path = st.text_input(
        "Enter the path to your DICOM folder:",
        placeholder="e.g., C:/data/dicom or /home/user/dicom",
    )

    if not folder_path:
        st.info("Please enter a folder path containing DICOM files organized as patient/timepoint subfolders.")
        return

    # Scan and load DICOM files
    with st.spinner("Scanning for DICOM files..."):
        dicom_data = scan_dicom_folder(folder_path)

    if not dicom_data:
        st.error("No DICOM files found in the specified folder.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(dicom_data)

    st.success(f"Loaded {len(df)} DICOM files")

    # Show folder structure summary
    with st.expander("Folder structure summary"):
        structure_df = df.groupby(["_patient", "_timepoint"]).size().reset_index(name="file_count")
        st.dataframe(structure_df, use_container_width=True, hide_index=True)

    # Get available metadata fields (exclude internal fields starting with _)
    metadata_fields = [col for col in df.columns if not col.startswith("_")]

    st.divider()
    st.subheader("Available Metadata Fields")
    st.write(f"Found {len(metadata_fields)} metadata fields across all files.")

    # Field selection
    selected_fields = st.multiselect(
        "Select fields to analyze:",
        options=sorted(metadata_fields),
        default=[],
    )

    if not selected_fields:
        st.info("Select one or more fields above to generate visualizations.")

        # Show all metadata fields as a reference
        with st.expander("View all available fields"):
            st.write(sorted(metadata_fields))
        return

    st.divider()
    st.subheader("Visualizations")

    # For each selected field, let user choose visualization type
    for field in selected_fields:
        st.markdown(f"### {field}")

        # Count unique values to suggest visualization type
        unique_count = df[field].nunique()
        non_null_count = df[field].notna().sum()

        col1, col2 = st.columns([1, 3])

        with col1:
            st.caption(f"Unique values: {unique_count}")
            st.caption(f"Non-null: {non_null_count}/{len(df)}")

            viz_type = st.radio(
                f"Visualization for {field}:",
                options=["Donut chart", "Table n (%)", "Table mean (SD)"],
                key=f"viz_{field}",
                label_visibility="collapsed",
            )

        with col2:
            if viz_type == "Donut chart":
                render_donut_chart(df, field)
            elif viz_type == "Table n (%)":
                render_count_table(df, field)
            else:
                render_stats_table(df, field)

        st.divider()

    # Option to export raw data
    with st.expander("Export raw data"):
        st.download_button(
            label="Download as CSV",
            data=df.to_csv(index=False),
            file_name="dicom_metadata.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
