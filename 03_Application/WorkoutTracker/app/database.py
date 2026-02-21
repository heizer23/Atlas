import os
import psycopg
from psycopg.rows import dict_row

def get_connection():
    """
    Establishes a connection to the Postgres database using environment variables.
    Returns a connection object.
    """
    try:
        conn = psycopg.connect(
            dbname=os.environ["ATLAS_PG_DB"],
            user=os.environ["ATLAS_PG_USER"],
            password=os.environ["ATLAS_PG_PASSWORD"],
            host="127.0.0.1", # Assuming running on host accessing docker port
            port=os.environ.get("ATLAS_PG_PORT", "5432"),
            row_factory=dict_row,
            autocommit=True # Simplified for this app
        )
        return conn
    except KeyError as e:
        raise RuntimeError(f"Missing database environment variable: {e}")
    except psycopg.Error as e:
        raise RuntimeError(f"Database connection failed: {e}")
