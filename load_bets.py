import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_batch


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "betting_analytics",
    "user": "postgres",
    "password": "8017"
}

CSV_PATH = "data/bets.csv"


REQUIRED_COLUMNS = [
    "date",
    "time",
    "sport",
    "match",
    "selection",
    "status",
    "stake",
    "odds",
    "sportsbook"
]

OPTIONAL_COLUMNS = [
    "tag",
    "closing_odds"
]

ALLOWED_STATUS = {"win", "loss", "void"}


def load_csv(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    df.columns = [col.strip().lower() for col in df.columns]

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Colunas obrigatórias ausentes no CSV: {missing_cols}")

    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df


def validate_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Remove espaços extras de colunas texto
    text_columns = [
        "sport",
        "match",
        "selection",
        "tag",
        "status",
        "sportsbook"
    ]
    for col in text_columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "": None})

    # Padroniza status
    df["status"] = df["status"].str.lower()

    invalid_status = df.loc[~df["status"].isin(ALLOWED_STATUS), "status"].dropna().unique()
    if len(invalid_status) > 0:
        raise ValueError(f"Status inválidos encontrados: {list(invalid_status)}")

    # Converte datas e horas
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["time"] = pd.to_datetime(df["time"], format="%H:%M", errors="coerce").dt.time

    if df["date"].isnull().any():
        raise ValueError("Existem valores inválidos na coluna 'date'.")

    if df["time"].isnull().any():
        raise ValueError("Existem valores inválidos na coluna 'time'. Use o formato HH:MM.")

    # Converte números
    numeric_columns = ["stake", "odds", "closing_odds"]
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df["stake"].isnull().any():
        raise ValueError("Existem valores inválidos na coluna 'stake'.")

    if df["odds"].isnull().any():
        raise ValueError("Existem valores inválidos na coluna 'odds'.")

    if (df["stake"] <= 0).any():
        raise ValueError("Todos os valores de 'stake' devem ser maiores que 0.")

    if (df["odds"] <= 1).any():
        raise ValueError("Todos os valores de 'odds' devem ser maiores que 1.")

    if df["closing_odds"].notnull().any() and (df.loc[df["closing_odds"].notnull(), "closing_odds"] <= 1).any():
        raise ValueError("Todos os valores de 'closing_odds' devem ser maiores que 1.")

    # Garante obrigatórios preenchidos
    for col in REQUIRED_COLUMNS:
        if df[col].isnull().any():
            raise ValueError(f"Existem valores nulos na coluna obrigatória '{col}'.")

    return df


def insert_data(df: pd.DataFrame) -> None:
    insert_query = """
        INSERT INTO bets (
            date,
            time,
            sport,
            match,
            selection,
            tag,
            status,
            closing_odds,
            stake,
            odds,
            sportsbook
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    rows = [
        (
            row["date"],
            row["time"],
            row["sport"],
            row["match"],
            row["selection"],
            row["tag"],
            row["status"],
            row["closing_odds"],
            row["stake"],
            row["odds"],
            row["sportsbook"],
        )
        for _, row in df.iterrows()
    ]

    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        execute_batch(cursor, insert_query, rows)
        conn.commit()

        print(f"{len(rows)} apostas inseridas com sucesso na tabela 'bets'.")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Erro ao inserir dados no banco: {e}")
        raise

    finally:
        if conn:
            conn.close()


def main():
    try:
        print("Lendo CSV...")
        df = load_csv(CSV_PATH)

        print("Validando e limpando dados...")
        df = validate_and_clean(df)

        print("Inserindo dados no PostgreSQL...")
        insert_data(df)

        print("Processo finalizado com sucesso.")

    except Exception as e:
        print(f"Falha no processo: {e}")


if __name__ == "__main__":
    main()