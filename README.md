
CREA PM2.5 Anomaly Detection

An end-to-end data analytics project focused on detecting anomalies in PM2.5 air quality measurements using OpenAQ data.

This repository reproduces and extends the methodology proposed in the CREA Anomaly Detection Challenge, combining exploratory data analysis, statistical anomaly detection, and spatial analysis techniques to identify unusual pollution patterns across monitoring stations.

Project Objectives

* Analyze large-scale air quality monitoring data.
* Detect abnormal PM2.5 observations using time-series anomaly detection methods.
* Comparing different statistical approaches.
* Investigate spatial and temporal pollution patterns.
* Build a reproducible research workflow suitable for environmental data analysis.

Dataset

The project uses OpenAQ air quality measurements and monitoring station metadata.

Main files:

* measurements.csv — PM2.5 observations
* locations.csv — Monitoring station information

For data acquisition and storage instructions, see data/README.md.

## Repository Structure

```
crea-anomaly-detection/
├── data/
│   ├── raw/                # Raw CSV files from CREA
│   ├── processed/          # Cleaned & merged data
│   └── README.md
├── notebooks/              # Jupyter notebooks
├── src/                    # Python scripts (utils.py, etc.)
├── config/                 # Configuration files
├── reports/                # Analysis reports
├── figures/                # Visualization outputs
├── requirements.txt
└── README.md
```

## Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/endarlani/crea-anomaly-detection.git
cd crea-anomaly-detection
```

### 2. Create a Virtual Environment

```bash
conda create -n crea python=3.12
conda activate crea
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Prepare the Data

Place the required datasets in the `data/raw/` directory:
- `anomaly_sample_measurements.csv`
- `anomaly_sample_locations.csv`

Refer to `data/README.md` for detailed instructions.

### 5. Launch Jupyter Notebook

```bash
jupyter notebook
```

## Analysis Workflow

The project follows a notebook-based analytical pipeline:

| Notebook | Description |
|---|---|
| `01_EDA_data_preparation_and_cleaning` | Data cleaning, validation, and exploratory analysis |
| `02_TSAD_spatial_analysis` | Spatial anomaly detection using TSAD method (ADF framework) |
| `03_TSAD_china_all_timeslices` | TSAD applied across all time slices for China stations |
| `04_decompose_anomaly_china` | Temporal anomaly detection via seasonal decomposition (statsmodels) |
| `05_multimetrics_anomaly_china` | Multi-method detection: Z-Score, IQR, and Isolation Forest |

Key Skills Demonstrated

* Data Cleaning & Preprocessing
* Exploratory Data Analysis (EDA)
* Time Series Analytics
* Anomaly Detection
* Feature Engineering
* Geospatial Analysis
* Python Data Stack (Pandas, NumPy, Scikit-learn)
* Research Reproducibility
* Git & Version Control

Results

Key findings, visualizations, and model performance evaluations are documented within the notebooks and summarized in the reports/ directory.

Reproducibility

This repository is structured following reproducible research principles:

* Version-controlled code and notebooks
* Documented data sources
* Configurable parameters
* Reproducible analytical workflow
* Clear project organization

References

* CREA Anomaly Detection Challenge
* OpenAQ Air Quality Platform
* see report/methodology.md
