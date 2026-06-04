from typing import Any
from datetime import datetime
import os
import sys
import logging
import psycopg2
import pandas as pd
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
import yfinance as yf

# Load environment variables
load_dotenv(override=True)

# Database connection string
conn_string = os.getenv("DATABASE_URL")
port = int(os.getenv("PORT", 8000))
# Initialize FastMCP server
mcp = FastMCP("mcp-db", host="0.0.0.0", port=port)

@mcp.tool()
def get_current_date() -> str:
    """
    Retrieves the current local date formatted as YYYY-MM-DD.
    
    Returns:
        str: The current date.
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    return f"The current date is: {current_date}"

@mcp.tool()
def get_market_prices(
    name: str,
    start_date: str,
    end_date: str,
):
    """
    Fetch historical market data for a financial asset from the data warehouse.

    Supported asset categories:
    - Stocks
    - Commodities
    - Currencies (Forex)
    - Bonds

    Args:
        name (str):
            Exact asset name stored in gold.dim_asset.asset_name.

        start_date (str):
            Start date in YYYY-MM-DD format.

        end_date (str):
            End date in YYYY-MM-DD format.

    Returns:
        pd.DataFrame:
            Historical market data.

            Columns:
                - asset_name
                - asset_type
                - base_currency
                - stock_sector
                - commodity_group
                - observed_at
                - price_value
                - day_change_pct
                - volume
                - market_cap
                - pe_ratio

            Returns an empty DataFrame if no data is found.
    """

    # -----------------------------
    # Validate dates
    # -----------------------------
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Dates must be in YYYY-MM-DD format.")

    # -----------------------------
    # SQL Query
    # -----------------------------
    query = """
        SELECT
            da.asset_name,
            da.asset_type,
            da.base_currency,
            da.stock_sector,
            da.commodity_group,
            fmh.observed_at,
            fmh.price_value,
            fmh.day_change_pct,
            fmh.volume,
            fmh.market_cap,
            fmh.pe_ratio
        FROM gold.fact_market_history fmh
        INNER JOIN gold.dim_asset da
            ON da.asset_key = fmh.asset_key
        WHERE da.asset_name = %s
          AND DATE(fmh.observed_at) BETWEEN %s AND %s
        ORDER BY fmh.observed_at ASC
    """

    conn = None
    cursor = None

    try:
        # -----------------------------
        # Connect to PostgreSQL
        # -----------------------------
        conn = psycopg2.connect(conn_string)
        cursor = conn.cursor()

        # -----------------------------
        # Execute query
        # -----------------------------
        cursor.execute(
            query,
            (
                name,
                start_date,
                end_date,
            ),
        )

        # -----------------------------
        # Fetch data
        # -----------------------------
        rows = cursor.fetchall()

        # Extract column names
        columns = [desc[0] for desc in cursor.description]

        # Create DataFrame
        df = pd.DataFrame(rows, columns=columns)

    except Exception as e:
        logging.info(f"Database error: {e}")

        # Return empty DataFrame on failure
        df = pd.DataFrame(
            columns=[
                "asset_name",
                "asset_type",
                "base_currency",
                "stock_sector",
                "commodity_group",
                "observed_at",
                "price_value",
                "day_change_pct",
                "volume",
                "market_cap",
                "pe_ratio",
            ]
        )

    finally:
        # -----------------------------
        # Clean up resources
        # -----------------------------
        if cursor:
            cursor.close()

        if conn:
            conn.close()

    return df


@mcp.tool()
def get_asset_sentiment(
    name: str,
    start_date: str,
    end_date: str,
):
    """
    Fetch sentiment analysis/news data for a financial asset.

    Supported asset categories:
    - Stocks
    - Commodities
    - Currencies (Forex)
    - Bonds

    Args:
        name (str):
            Exact asset name stored in gold.dim_asset.asset_name.

        start_date (str):
            Start date in YYYY-MM-DD format.

        end_date (str):
            End date in YYYY-MM-DD format.

    Returns:
        pd.DataFrame:
            Sentiment records.

            Columns:
                - asset_name
                - asset_type
                - headline
                - sentiment_label
                - sentiment_score
                - source
                - published_at
                - created_at

            Returns an empty DataFrame if no data is found.
    """

    # -----------------------------
    # Validate dates
    # -----------------------------
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Dates must be in YYYY-MM-DD format.")

    # -----------------------------
    # SQL Query
    # -----------------------------
    query = """
        SELECT
            da.asset_name,
            da.asset_type,
            ds.headline,
            ds.sentiment_label,
            ds.sentiment_score,
            ds.source,
            ds.published_at,
            ds.created_at
        FROM gold.dim_sentiment ds
        INNER JOIN gold.dim_asset da
            ON da.asset_key = ds.asset_key
        WHERE da.asset_name = %s
          AND DATE(ds.published_at) BETWEEN %s AND %s
        ORDER BY ds.published_at DESC
    """

    conn = None
    cursor = None

    try:
        # -----------------------------
        # Connect to PostgreSQL
        # -----------------------------
        conn = psycopg2.connect(conn_string)
        cursor = conn.cursor()

        # -----------------------------
        # Execute query
        # -----------------------------
        cursor.execute(
            query,
            (
                name,
                start_date,
                end_date,
            ),
        )

        # -----------------------------
        # Fetch results
        # -----------------------------
        rows = cursor.fetchall()

        # Extract column names
        columns = [desc[0] for desc in cursor.description]

        # Convert to DataFrame
        df = pd.DataFrame(rows, columns=columns)

    except Exception as e:
        logging.info(f"Database error: {e}")

        # Return empty DataFrame safely
        df = pd.DataFrame(
            columns=[
                "asset_name",
                "asset_type",
                "headline",
                "sentiment_label",
                "sentiment_score",
                "source",
                "published_at",
                "created_at",
            ]
        )

    finally:
        # -----------------------------
        # Clean up resources
        # -----------------------------
        if cursor:
            cursor.close()

        if conn:
            conn.close()

    return df




@mcp.tool()
def get_hist_data(
    ticker: str,
    start_date: str,
    end_date: str,
    interval: str ,
):
    """
    Fetch historical market data for a financial asset using Yahoo Finance.

    Supported assets:
    - Stocks
    - ETFs
    - Commodities
    - Forex pairs
    - Indices
    - Cryptocurrencies

    Args:
        ticker (str):
            Yahoo Finance ticker symbol.

            Examples:
                - "AAPL"      -> Apple
                - "NVDA"      -> NVIDIA
                - "GC=F"      -> Gold Futures
                - "EURUSD=X"  -> EUR/USD Forex
                - "BTC-USD"   -> Bitcoin

        start_date (str, optional):
            Start date in YYYY-MM-DD format.

        end_date (str, optional):
            End date in YYYY-MM-DD format.

        interval (str, optional):
            Data interval.

            Examples:
                - "1m"
                - "5m"
                - "15m"
                - "1h"
                - "1d"
                - "1wk"
                - "1mo"

    Returns:
        pd.DataFrame:
            Historical OHLCV market data.

            Columns typically include:
                - Open
                - High
                - Low
                - Close
                - Volume
                - Dividends
                - Stock Splits

            Returns an empty DataFrame if no data is found.

    Example:
        >>> df = get_hist_data(
        ...     ticker="NVDA",
        ...     start_date="2025-01-01",
        ...     end_date="2025-02-01",
        ...     interval="1d"
        ... )

        >>> print(df.head())

    Notes:
        - Data source: Yahoo Finance
        - Returned DataFrame can directly be exported to Excel:

              df.to_excel("market_data.xlsx", index=True)
    """

    # -----------------------------
    # Validate dates
    # -----------------------------
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            "Dates must be in YYYY-MM-DD format."
        )

    try:
        # -----------------------------
        # Initialize ticker
        # -----------------------------
        tick = yf.Ticker(ticker)

        # -----------------------------
        # Fetch historical data
        # -----------------------------
        hist = tick.history(
            start=start_date,
            end=end_date,
            interval=interval,
            repair=True,
        )
        # -----------------------------
        # Handle empty data
        # -----------------------------
        if hist.empty:
            df = pd.DataFrame(
                    columns=[
                        "asset_name",
                        "asset_type",
                        "base_currency",
                        "stock_sector",
                        "commodity_group",
                        "observed_at",
                        "price_value",
                        "day_change_pct",
                        "volume",
                        "market_cap",
                        "pe_ratio",
                    ]
                )
            return df

        # -----------------------------
        # Clean DataFrame
        # -----------------------------
        hist = hist.fillna(0)

  
        return  hist.to_json()
    except Exception as e:
        print(f"Yahoo Finance error: {e}")
        df = pd.DataFrame(
                    columns=[
                        "asset_name",
                        "asset_type",
                        "base_currency",
                        "stock_sector",
                        "commodity_group",
                        "observed_at",
                        "price_value",
                        "day_change_pct",
                        "volume",
                        "market_cap",
                        "pe_ratio",
                    ]
                )
        return df # Return empty DataFrame on failure
        


def main():
    print("========== MCP STARTING ==========")
    print(f"PORT={os.getenv('PORT')}")
    print(f"DATABASE_URL exists={bool(os.getenv('DATABASE_URL'))}")
    print("==================================")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()