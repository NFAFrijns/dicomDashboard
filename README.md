# dicomDashboard

A browser-based tool to analyze metadata from multiple DICOM files used for deep learning.

## Features

- Recursive scanning of DICOM files in patient/timepoint folder structures
- Extracts all available metadata fields from DICOM headers
- Three visualization options for each metadata field:
  - **Donut chart** - Interactive pie chart for categorical data
  - **Table n (%)** - Count and percentage breakdown
  - **Table mean (SD)** - Statistical summary for numerical data
- Export metadata to CSV

## Expected Folder Structure

```
data/
├── p1/
│   ├── Y1/
│   │   └── *.dcm
│   └── Y5/
│       └── *.dcm
├── p2/
│   ├── Y1/
│   │   └── *.dcm
│   └── Y5/
│       └── *.dcm
└── ...
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
streamlit run app.py
```

Then open the browser and enter the path to your DICOM folder.

## Dependencies

- streamlit
- pydicom
- pandas
- plotly
