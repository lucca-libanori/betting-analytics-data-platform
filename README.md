# Betting Analytics Data Platform

## Overview

This project is a data analytics platform designed to track, process, and analyze sports investment performance. It simulates a real-world data pipeline, transforming raw betting data into meaningful insights through a structured workflow.

The system allows users to evaluate their betting performance using key metrics such as profit, ROI, and hit rate, as well as interactive filtering and visualization.

You can adapt this platform for any kind of investment with just a few changes.

---

## Tech Stack

* **Python** (Pandas, SQLAlchemy)
* **PostgreSQL**
* **SQL**
* **Streamlit**
* **CSV (data ingestion)**

---

## Features

* Data ingestion from CSV files
* Automated ETL pipeline using Python
* Structured relational database (PostgreSQL)

* KPI calculations:

  * Total Profit
  * ROI (%)
  * Hit Rate (%)
  * Total Stake

* Interactive dashboard with filters:

  * Sport
  * Sportsbook
  * Status
  * Tag
  * Date range

* Analytical views:

  * Profit by Sport
  * Profit by Sportsbook
  * Profit by Tag
  * ROI by Sport
  * ROI by Sportsbook
  * Bankroll evolution over time

---

## Project Structure
```
betting-data-platform/
│
├── data/
│   └── bets.csv
│
├── database/
│   └── schema.sql
│
├── sql/
│   └── metrics.sql
│
├── dashboard/
│   └── app.py
│
├── load_bets.py
├── requirements.txt
└── README.md
```

---

## How to Run

### 1. Clone the repository

```
git clone <your-repo-url>
cd betting-data-platform
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Set up PostgreSQL

* Create a database named:

```
betting_analytics
```

* Run the SQL schema:

```
database/schema.sql
```

### 4. Load the data

```
python load_bets.py
```

### 5. Run the dashboard

```
streamlit run dashboard/app.py
if this command doesn't work, try:
python -m streamlit run dashboard/app.py
```

---

## Dashboard Metrics

The dashboard provides:

* Total number of bets
* Total profit
* ROI (%)
* Hit rate (%)
* Total stake

It also includes breakdowns by:

* Sport
* Sportsbook
* Tag

And visualizations such as:

* Profit by category
* ROI comparison
* Bankroll evolution over time

---

## Future Improvements

* Integration with external APIs for automated data ingestion
* Closing Line Value (CLV) analysis
* Perhaps some personal adjustments that fit in my situation.
