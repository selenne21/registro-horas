import streamlit as st
import pandas as pd
import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials



from google.oauth2.service_account import Credentials

st.title("Registro de horas de trabajo 🕒")

hoja = conectar_sheets_local()
st.success("Conectado a Google Sheets ✅")
