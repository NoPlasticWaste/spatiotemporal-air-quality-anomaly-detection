
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

Repository Structure

crea-anomaly-detection/
├── data/
├── notebooks/
├── src/
├── config/
├── reports/
├── figures/
├── requirements.txt
└── README.md

Environment Setup

1. Clone the Repository

git clone https://github.com/endarlani/crea-anomaly-detection.git
cd crea-anomaly-detection

2. Create a Virtual Environment

python -m venv venv
source venv/bin/activate

3. Install Dependencies

pip install -r requirements.txt

4. Prepare the Data

Download and place the required datasets in the data/ directory.

Refer to data/README.md for detailed instructions.

5. Launch Jupyter Notebook

jupyter notebook

Analysis Workflow

The project follows a notebook-based analytical pipeline:

Notebook	Description
01_data_preparation_EDA	Data cleaning, validation, and exploratory analysis
02_baseline_zscore	Baseline anomaly detection using Z-score methods
03_isolation_forest	Machine learning anomaly detection using Isolation Forest
04_spatial_analysis	Geographic analysis of pollution events
05_china_timeslices	Temporal analysis of pollution patterns in China

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
