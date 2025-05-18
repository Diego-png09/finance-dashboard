# Must be first Streamlit call
import streamlit as st
st.set_page_config(page_title="Financial Dashboard", layout="wide")

# All other imports AFTER
import pandas as pd
import yfinance as yf
import requests
import numpy as np
from datetime import datetime
import plotly.express as px
from fredapi import Fred

# Main app title (AFTER set_page_config)
st.title("📈 Financial Markets Dashboard")

# -------------------
# CETES from Banxico API
# -------------------
def get_cetes_data():
    token = "406c8f6c4f71c2d9f8ca296f526028877c4a45a57d15342bbc52d69f8b1a9fb6"  # Replace with your real token
    series_id = "SF43936"  # CETES 28 days
    url = f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{series_id}/datos"
    headers = {"Bmx-Token": token}
    r = requests.get(url, headers=headers)
    try:
        data = r.json()['bmx']['series'][0]['datos']
        df = pd.DataFrame(data)
        df['fecha'] = pd.to_datetime(df['fecha'], format='%d/%m/%Y')
        df['valor'] = pd.to_numeric(df['dato'], errors='coerce')
        df = df[['fecha', 'valor']].dropna()
        return df
    except Exception as e:
        st.error("Error loading CETES data. Check your Banxico token.")
        return pd.DataFrame(columns=['fecha', 'valor'])

# -------------------
# US Bonds (FRED)
# -------------------
def get_us_bond_data():
    fred = Fred(api_key='48d9921340c775a2aa6ac13f88016298')  # Replace with real key
    data = fred.get_series('GS10')
    df = pd.DataFrame({'fecha': data.index, 'US10Y': data.values})
    df = df[df['US10Y'].notna()]
    return df

# -------------------
# Exchange Rates
# -------------------
def get_fx_data():
    usd_mxn = yf.download("USDMXN=X", period="10y")['Close'].dropna()
    eur_usd = yf.download("EURUSD=X", period="10y")['Close'].dropna()
    df = pd.DataFrame(index=usd_mxn.index)
    df['USD/MXN'] = usd_mxn
    df['USD/EUR'] = 1 / eur_usd
    df = df.dropna().reset_index()
    df.rename(columns={'Date': 'fecha'}, inplace=True)
    return df

# -------------------
# Stock Prices
# -------------------
big_seven = ['AAPL', 'MSFT', 'NVDA', 'GOOG', 'META', 'TSLA']
extra_stocks = ['NFLX', 'AMD', 'INTC', 'KO', 'AMZN']
all_stocks = big_seven + extra_stocks

@st.cache_data(ttl=86400)
def get_stock_data(tickers):
    data = yf.download(tickers, start="2015-01-01", group_by='ticker', auto_adjust=True)
    frames = []
    for ticker in tickers:
        df = data[ticker].reset_index()[['Date', 'Close']]
        df['ticker'] = ticker
        df.rename(columns={'Date': 'fecha', 'Close': 'price'}, inplace=True)
        frames.append(df)
    return pd.concat(frames)

# -------------------
# Load Data
# -------------------
with st.spinner("📥 Loading data..."):
    cetes_df = get_cetes_data()
    bond_df = get_us_bond_data()
    fx_df = get_fx_data()
    stocks_df = get_stock_data(all_stocks)

st.success("✅ Data loaded!")

# -------------------
# Date Filter
# -------------------
min_date = max([
    cetes_df['fecha'].min(),
    bond_df['fecha'].min(),
    fx_df['fecha'].min(),
    stocks_df['fecha'].min()
])
max_date = datetime.today()

st.sidebar.header("📅 Date Filter")
date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date], min_value=min_date, max_value=max_date)

if len(date_range) == 2:
    start_date, end_date = pd.to_datetime(date_range)
    cetes_df = cetes_df[(cetes_df['fecha'] >= start_date) & (cetes_df['fecha'] <= end_date)]
    bond_df = bond_df[(bond_df['fecha'] >= start_date) & (bond_df['fecha'] <= end_date)]
    fx_df = fx_df[(fx_df['fecha'] >= start_date) & (fx_df['fecha'] <= end_date)]
    stocks_df = stocks_df[(stocks_df['fecha'] >= start_date) & (stocks_df['fecha'] <= end_date)]

# -------------------
# KPIs
# -------------------
st.header("📌 Key Performance Indicators")
col1, col2, col3 = st.columns(3)

latest_cetes = round(cetes_df['valor'].iloc[-1], 2)
latest_bond = round(bond_df['US10Y'].iloc[-1], 2)
latest_usdmxn = round(fx_df['USD/MXN'].iloc[-1], 2)

col1.metric("CETES Rate", f"{latest_cetes}%", f"{latest_cetes - cetes_df['valor'].iloc[-2]:.2f}")
col2.metric("US 10Y Yield", f"{latest_bond}%", f"{latest_bond - bond_df['US10Y'].iloc[-2]:.2f}")
col3.metric("USD/MXN", f"${latest_usdmxn}", f"{latest_usdmxn - fx_df['USD/MXN'].iloc[-2]:.2f}")

if latest_cetes > 10:
    st.error(f"🚨 ALERT: CETES rate is critically high ({latest_cetes}%)")

# Alerts
alerts_triggered = False

if latest_cetes > 10:
    st.error(f"🚨 ALERT: CETES rate is critically high ({latest_cetes}%)")
    alerts_triggered = True

if latest_bond > 5:
    st.warning(f"⚠️ Warning: US 10Y yield is above 5% ({latest_bond}%)")
    alerts_triggered = True

if latest_usdmxn > 20:
    st.warning(f"⚠️ Warning: USD/MXN exchange rate is above 20 ({latest_usdmxn})")
    alerts_triggered = True

if not alerts_triggered:
    st.success("✅ All indicators are within normal range.")

# -------------------
# Macro Charts
# -------------------
st.header("📉 Macro Trends")

col1, col2 = st.columns(2)
with col1:
    st.subheader("🇲🇽 CETES 28-Day")
    st.plotly_chart(px.line(cetes_df, x='fecha', y='valor', title="CETES (%)"), use_container_width=True)

with col2:
    st.subheader("🇺🇸 US 10Y Yield")
    st.plotly_chart(px.line(bond_df, x='fecha', y='US10Y', title="US 10-Year Treasury (%)"), use_container_width=True)

st.subheader("💱 Exchange Rates")
st.plotly_chart(px.line(fx_df, x='fecha', y=['USD/MXN', 'USD/EUR'], title="Exchange Rates"), use_container_width=True)

# -------------------
# Stock Trends
# -------------------
st.header("📊 Stock Market: Big Seven")
selected_big = st.multiselect("Select Big 7 Companies", big_seven, default=big_seven)
if selected_big:
    fig = px.line(stocks_df[stocks_df['ticker'].isin(selected_big)], x='fecha', y='price', color='ticker')
    st.plotly_chart(fig, use_container_width=True)

st.header("📈 Stock Market: Extra Companies")
selected_extra = st.multiselect("Select Extra Companies", extra_stocks, default=extra_stocks)
if selected_extra:
    fig2 = px.line(stocks_df[stocks_df['ticker'].isin(selected_extra)], x='fecha', y='price', color='ticker')
    st.plotly_chart(fig2, use_container_width=True)