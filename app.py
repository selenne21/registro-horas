import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pandas as pd

# =============================
# CONFIG
# =============================
st.set_page_config(page_title="Registro de horas", layout="centered")
st.title("⏰ Registro de horas")

# =============================
# GOOGLE SHEETS
# =============================
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)

client = gspread.authorize(creds)

archivo = client.open_by_key("1MDS9f1cLCe99VgNcqJzOZwp3Rbql5H7LTjqigJZWb9o")

sheet_eventos = archivo.sheet1
sheet_semanas = archivo.worksheet("semanas")


# =============================
# ASEGURAR ENCABEZADOS
# =============================
encabezado = [
    "Trabajo","Tipo_semana","Semana_inicio",
    "Día","Fecha","Entrada","Inicio break","Fin break","Salida","Horas"
]

valores = sheet_semanas.get_all_values()
if valores == [] or valores[0] != encabezado:
    sheet_semanas.clear()
    sheet_semanas.append_row(encabezado)

# =============================
# FUNCIONES
# =============================
def obtener_trabajos():
    filas = sheet_eventos.get_all_values()
    if len(filas) < 2:
        return []
    return sorted(set(f[1] for f in filas[1:] if len(f) > 1 and f[1]))

def borrar_trabajo(trabajo):
    # borrar de hoja principal (trabajos)
    filas_eventos = sheet_eventos.get_all_values()
    for i in range(len(filas_eventos)-1, 0, -1):
        if len(filas_eventos[i]) > 1 and filas_eventos[i][1] == trabajo:
            sheet_eventos.delete_rows(i+1)

    # borrar todas las semanas asociadas
    filas_semanas = sheet_semanas.get_all_values()
    for i in range(len(filas_semanas)-1, 0, -1):
        if filas_semanas[i][0] == trabajo:
            sheet_semanas.delete_rows(i+1)

def borrar_semana(trabajo, tipo, inicio):
    filas = sheet_semanas.get_all_values()
    for i in range(len(filas)-1, 0, -1):
        if (
            filas[i][0] == trabajo and
            filas[i][1] == tipo and
            filas[i][2] == inicio
        ):
            sheet_semanas.delete_rows(i+1)

def cargar_semana_guardada(trabajo, tipo, inicio):
    valores = sheet_semanas.get_all_values()
    if len(valores) < 2:
        return None

    df = pd.DataFrame(valores[1:], columns=valores[0])

    df = df[
        (df["Trabajo"] == trabajo) &
        (df["Tipo_semana"] == tipo) &
        (df["Semana_inicio"] == inicio)
    ]

    if df.empty:
        return None

    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df["Horas"] = pd.to_numeric(df["Horas"], errors="coerce").fillna(0)

    return df[["Día","Fecha","Entrada","Inicio break","Fin break","Salida","Horas"]]

def calcular_horas(row):
    try:
        if not row["Entrada"] or not row["Salida"]:
            return 0

        fecha = pd.to_datetime(row["Fecha"]).date()

        e = pd.to_datetime(
            f"{fecha} {row['Entrada']}",
            format="%Y-%m-%d %I:%M %p",
            errors="coerce"
        )
        s = pd.to_datetime(
            f"{fecha} {row['Salida']}",
            format="%Y-%m-%d %I:%M %p",
            errors="coerce"
        )

        if pd.isna(e) or pd.isna(s):
            return 0

        if s < e:
            s += pd.Timedelta(days=1)

        total = (s - e).total_seconds() / 3600

        if row["Inicio break"] and row["Fin break"]:
            b1 = pd.to_datetime(
                f"{fecha} {row['Inicio break']}",
                format="%Y-%m-%d %I:%M %p",
                errors="coerce"
            )
            b2 = pd.to_datetime(
                f"{fecha} {row['Fin break']}",
                format="%Y-%m-%d %I:%M %p",
                errors="coerce"
            )

            if not pd.isna(b1) and not pd.isna(b2):
                if b2 < b1:
                    b2 += pd.Timedelta(days=1)
                total -= (b2 - b1).total_seconds() / 3600

        return round(max(total, 0), 2)

    except:
        return 0

# =============================
# TRABAJOS
# =============================
trabajos = obtener_trabajos()
opciones = trabajos + ["➕ Crear nuevo trabajo"]

trabajo_sel = st.selectbox("Selecciona el trabajo", opciones)

if trabajo_sel == "➕ Crear nuevo trabajo":
    nuevo = st.text_input("Nombre del nuevo trabajo")
    if st.button("Guardar trabajo") and nuevo.strip():
        sheet_eventos.append_row(["", nuevo.strip()])
        st.success("Trabajo creado")
        st.rerun()

# =============================
# TRABAJO ACTIVO
# =============================
if "trabajo_activo" not in st.session_state:
    st.session_state.trabajo_activo = None

st.subheader("📝 Tus trabajos")
cols = st.columns(3)

for i, t in enumerate(trabajos):
    with cols[i % 3]:
        if st.button(t, key=f"btn_{i}"):
            st.session_state.trabajo_activo = t
            st.session_state.confirmar_borrado = False

# =============================
# ELIMINAR TRABAJO
# =============================
if st.session_state.trabajo_activo:
    st.markdown("---")
    st.warning(f"⚠️ Eliminar el trabajo **{st.session_state.trabajo_activo}**")

    if st.button("🗑️ Eliminar este trabajo"):
        st.session_state.confirmar_borrado = True

if st.session_state.get("confirmar_borrado", False):
    st.error("❗ Esta acción eliminará TODAS las semanas registradas")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("❌ Cancelar"):
            st.session_state.confirmar_borrado = False

    with col2:
        if st.button("✅ Sí, eliminar definitivamente"):
            borrar_trabajo(st.session_state.trabajo_activo)
            st.session_state.trabajo_activo = None
            st.session_state.confirmar_borrado = False
            st.success("🗑️ Trabajo eliminado correctamente")
            st.rerun()

# =============================
# REGISTRO SEMANAL
# =============================
if st.session_state.trabajo_activo:
    tipo = st.radio("Inicio de semana", ["Lunes a domingo", "Sábado a viernes"])
    hoy = datetime.today().date()

    if tipo == "Lunes a domingo":
        inicio = hoy - timedelta(days=hoy.weekday())
        dias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    else:
        inicio = hoy - timedelta(days=(hoy.weekday()+2) % 7)
        dias = ["Sábado","Domingo","Lunes","Martes","Miércoles","Jueves","Viernes"]

    inicio_str = inicio.strftime("%Y-%m-%d")
    fechas = [inicio + timedelta(days=i) for i in range(7)]

    key = f"{st.session_state.trabajo_activo}_{tipo}_{inicio_str}"

    if key not in st.session_state:
        guardado = cargar_semana_guardada(
            st.session_state.trabajo_activo, tipo, inicio_str
        )
        if guardado is not None:
            st.session_state[key] = guardado
        else:
            st.session_state[key] = pd.DataFrame({
                "Día": dias,
                "Fecha": fechas,
                "Entrada": ["" for _ in range(7)],
                "Inicio break": ["" for _ in range(7)],
                "Fin break": ["" for _ in range(7)],
                "Salida": ["" for _ in range(7)]
            })

    df = st.data_editor(st.session_state[key], num_rows="fixed", use_container_width=True)
    df["Horas"] = df.apply(calcular_horas, axis=1)
    st.session_state[key] = df

    st.success(f"🟢 Total semanal: {round(df['Horas'].sum(),2)} h")

    if st.button("💾 Guardar semana"):
        borrar_semana(st.session_state.trabajo_activo, tipo, inicio_str)
        for _, r in df.iterrows():
            sheet_semanas.append_row([
                st.session_state.trabajo_activo,
                tipo,
                inicio_str,
                r["Día"],
                r["Fecha"].strftime("%Y-%m-%d"),
                r["Entrada"],
                r["Inicio break"],
                r["Fin break"],
                r["Salida"],
                r["Horas"]
            ])
        st.success("✅ Semana guardada correctamente")








# seguridad
st.success("✅ Conexión segura establecida con Google Sheets")


