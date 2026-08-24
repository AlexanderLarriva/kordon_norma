import pandas as pd
import streamlit as st

from services.calc import calculate_personnel, calculate_tspk
from services.db import (
    get_admin_password,
    get_calculation_history,
    get_connection,
    get_tspk_classes,
    init_db,
    save_calculation,
    set_admin_password,
)

# Инициализируем БД при старте (создаст таблицы и дефолтный пароль 'admin123', если их нет)
init_db()

st.set_page_config(
    page_title="Расчет штата и ТСПК АПП",
    page_icon="🦅",
    layout="wide"
)

st.title("🦅 Расчет штатной численности и потребности в ТСПК")

# ---------------------------------------------------------
# Боковая панель: Ввод исходных данных
# ---------------------------------------------------------
st.sidebar.header("Параметры АПП")

app_name = st.sidebar.text_input("Наименование АПП", value="АПП 'Мамыр'")
app_code = st.sidebar.text_input("Код АПП", value="100100")
is_high_category = st.sidebar.checkbox("Высокая категория АПП", value=False)
has_tspk_complex = st.sidebar.checkbox("Комплекс ТСПК/АСПК", value=True)
has_idk = st.sidebar.checkbox("Наличие ИДК", value=True)
has_rpm = st.sidebar.checkbox("Система РПМ (въезд/выезд)", value=True)
has_k9 = st.sidebar.checkbox("Кинологическая служба", value=False)

st.sidebar.markdown("---")
st.sidebar.subheader("Режим работы и коэффициенты")
shift_type = st.sidebar.selectbox(
    "График сменности",
    options=["12h", "8h", "24h"],
    format_func=lambda x: "12-часовой (4 смены)" if x == "12h" else ("8-часовой (3 смены)" if x == "8h" else "24-часовой (4 смены)")
)
k_substitute = st.sidebar.number_input("Коэффициент подмены", value=1.15, step=0.01)

st.sidebar.markdown("---")
st.sidebar.subheader("Инфраструктура и посты")

# Кабины ПД
pd_pedestrian = st.sidebar.number_input("Кабины ПД (пешеходка)", min_value=0, value=2)
pd_auto = st.sidebar.number_input("Кабины/АРМ ПД (авто)", min_value=0, value=4)
pd_extra = st.sidebar.checkbox("Доп. пост ПД на территории", value=False)
spec_rooms = st.sidebar.number_input("Комнаты спецпроверки", min_value=0, value=1)

# Шлагбаумы и полосы
barriers_in = st.sidebar.number_input("Посты шлагбаумов (въезд)", min_value=0, value=1)
barriers_out = st.sidebar.number_input("Посты шлагбаумов (выезд)", min_value=0, value=1)

lanes_auto_in = st.sidebar.number_input("Полосы легковых (въезд)", min_value=0, value=2)
lanes_auto_out = st.sidebar.number_input("Полосы легковых (выезд)", min_value=0, value=2)
lanes_truck_in = st.sidebar.number_input("Полосы грузовых (въезд)", min_value=0, value=2)
lanes_truck_out = st.sidebar.number_input("Полосы грузовых (выезд)", min_value=0, value=2)
lanes_bus_in = st.sidebar.number_input("Полосы автобусов (въезд)", min_value=0, value=1)
lanes_bus_out = st.sidebar.number_input("Полосы автобусов (выезд)", min_value=0, value=1)

# Досмотр
inspection_in = st.sidebar.number_input("Площадки осмотра (въезд)", min_value=0, value=1)
inspection_out = st.sidebar.number_input("Площадки осмотра (выезд)", min_value=0, value=1)
dts_boxes = st.sidebar.number_input("Боксы ДТС", min_value=0, value=1)

# Упаковка входных данных
input_data = {
    "shift_type": shift_type,
    "k_substitute": k_substitute,
    "has_tspk_complex": has_tspk_complex,
    "is_high_category": is_high_category,
    "has_idk": has_idk,
    "has_rpm": has_rpm,
    "has_k9": has_k9,
    "pd_cabins_pedestrian": pd_pedestrian,
    "pd_cabins_auto": pd_auto,
    "pd_extra_site": pd_extra,
    "spec_rooms": spec_rooms,
    "barriers_in": barriers_in,
    "barriers_out": barriers_out,
    "lanes_auto_in": lanes_auto_in,
    "lanes_auto_out": lanes_auto_out,
    "lanes_truck_in": lanes_truck_in,
    "lanes_truck_out": lanes_truck_out,
    "lanes_bus_in": lanes_bus_in,
    "lanes_bus_out": lanes_bus_out,
    "inspection_sites_in": inspection_in,
    "inspection_sites_out": inspection_out,
    "dts_boxes": dts_boxes,
}

# ---------------------------------------------------------
# Выполнение расчетов
# ---------------------------------------------------------
res_personnel = calculate_personnel(input_data)
res_tspk = calculate_tspk(input_data, res_personnel)

# Метрики сверху
col1, col2, col3, col4 = st.columns(4)
col1.metric("Итого штат КПП", f"{res_personnel['total_full_staff']} чел.")
col2.metric("В том числе руководство", f"{res_personnel['total_leadership']} чел.")
col3.metric("Оперативный штат", f"{res_personnel['total_operational']} чел.")
col4.metric("Наряд в одну смену", f"{res_personnel['total_per_shift']} чел.")

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "👥 Штатное расписание", 
    "🛠️ Потребность в ТСПК", 
    "📜 История расчетов",
    "⚙️ Справочники"
])

# ---------------------------------------------------------
# TAB 1: Штатное расписание
# ---------------------------------------------------------
with tab1:
    st.subheader("1. Руководящий состав")
    df_lead = pd.DataFrame(list(res_personnel["leadership"].items()), columns=["Должность", "Количество (чел.)"])
    st.dataframe(df_lead, use_container_width=True)

    st.subheader("2. Состав дежурной смены")
    df_shift = pd.DataFrame(list(res_personnel["shift_duty"].items()), columns=["Наряд / Должность", "Количество в смену (чел.)"])
    st.dataframe(df_shift, use_container_width=True)

# ---------------------------------------------------------
# TAB 2: Потребность в ТСПК
# ---------------------------------------------------------
# ---------------------------------------------------------
# TAB 2: Потребность в ТСПК
# ---------------------------------------------------------
with tab2:
    st.subheader("🛠️ Расчет потребности в ТСПК")
    st.caption("Данные упорядочены по приоритету и важности (сверху вниз). Вы можете выбрать модель техники прямо в таблице.")

    if res_tspk:
        # 1. Порядок приоритета категорий (от высшего к низшему)
        category_order = {
            "Технические средства паспортного контроля": 1,
            "Средства досмотра ТС и грузов": 2,
            "Средства обнаружения оружия, ВВ и НВ": 3,
            "Средства аудио, видео и фото документирования": 4,
            "Средства обеспечения, технологическое оборудование": 5,
            "Специальные технические средства обучения": 6
        }

        # 2. Сортируем полученные результаты по важности категорий и ID класса
        sorted_tspk = sorted(
            res_tspk,
            key=lambda x: (category_order.get(x["category"], 99), x["class_id"])
        )

        # 3. Формируем структуру данных для единой таблицы
        table_data = []
        for item in sorted_tspk:
            models = item["available_models"]
            selected_default = models[0] if models else "Стандартное (не указана)"
            
            table_data.append({
                "Категория": item["category"],
                "Класс ТСПК / Название": item["class_name"],
                "Модель техники": selected_default,
                "Основная норма": item["base_count"],
                "НЗ (10%)": item["reserve"],
                "Итого (потребность)": item["total_required"],
                "Ед. изм.": item["unit"],
                "Примечание / Расчет": item["note"]
            })

        df_tspk = pd.DataFrame(table_data)

        # 4. Отображаем таблицу с выпадающим списком моделей для тех классов, где они есть
        edited_tspk_df = st.data_editor(
            df_tspk,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Категория": st.column_config.TextColumn("Категория", disabled=True),
                "Класс ТСПК / Название": st.column_config.TextColumn("Класс ТСПК / Название", disabled=True),
                "Модель техники": st.column_config.SelectboxColumn(
                    "Модель техники",
                    help="Выберите конкретную модель из справочника",
                    options=[
                        "Регула 4305", "ST-30 (Газпром)", "Ультрамаг-A6",
                        "Каскад-2", "ЭТ-230", "СФИНКС ВМ-611",
                        "Garrett Super Scanner", "Янтарь-1П", "С T-SCAN",
                        "Стандартное (не указана)"
                    ],
                    required=True
                ),
                "Основная норма": st.column_config.NumberColumn("Основная норма", disabled=True),
                "НЗ (10%)": st.column_config.NumberColumn("НЗ (10%)", disabled=True),
                "Итого (потребность)": st.column_config.NumberColumn("Итого (потребность)", disabled=True),
                "Ед. изм.": st.column_config.TextColumn("Ед. изм.", disabled=True),
                "Примечание / Расчет": st.column_config.TextColumn("Примечание / Расчет", disabled=True)
            }
        )

    else:
        st.info("Потребность в ТСПК не рассчитана.")

# ---------------------------------------------------------
# TAB 3: История расчетов
# ---------------------------------------------------------
with tab3:
    st.subheader("Сохраненные расчеты")
    if st.button("💾 Сохранить текущий расчет в базу"):
        save_calculation(app_name, app_code, "Стандартная", input_data, {"personnel": res_personnel, "tspk": res_tspk})
        st.success("Расчет успешно сохранен!")

    history = get_calculation_history()
    if history:
        df_hist = pd.DataFrame(history, columns=["ID", "Дата/Время", "Наименование АПП", "Код", "Категория"])
        st.dataframe(df_hist, use_container_width=True)

# ---------------------------------------------------------
# TAB 4: Справочники и редактирование
# ---------------------------------------------------------
with tab4:
    st.subheader("⚙️ Управление классификатором ТСПК")
    
    raw_classes = get_tspk_classes()
    df_raw_classes = pd.DataFrame(
        raw_classes, 
        columns=["ID", "Категория", "Класс ТСПК", "Тип нормирования", "Коэффициент", "Ед. изм.", "Примечание"]
    )

    admin_mode = st.toggle("🔒 Режим администратора (редактирование)")

    if admin_mode:
        current_password = get_admin_password()
        admin_password = st.text_input("Введите пароль администратора", type="password")
        
        if admin_password == current_password:
            st.success("Режим редактирования активен.")

            # Смена пароля
            with st.expander("🔑 Сменить пароль администратора"):
                with st.form("change_pass_form"):
                    new_pass = st.text_input("Новый пароль", type="password")
                    confirm_pass = st.text_input("Подтвердите новый пароль", type="password")
                    submit_pass = st.form_submit_button("Сохранить новый пароль")
                    
                    if submit_pass:
                        if new_pass and new_pass == confirm_pass:
                            set_admin_password(new_pass)
                            st.success("Пароль успешно изменен!")
                            st.rerun()
                        else:
                            st.error("Пароли не совпадают или поле пустое!")

            st.caption("Вы можете редактировать классы и нормативные коэффициенты ниже.")
            
            edited_df = st.data_editor(
                df_raw_classes,
                num_rows="dynamic",
                use_container_width=True,
                key="tspk_classes_editor"
            )
            
            if st.button("💾 Сохранить изменения в базе", type="primary"):
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM dict_tspk_classes")
                for _, row in edited_df.iterrows():
                    if pd.notna(row["Класс ТСПК"]) and str(row["Класс ТСПК"]).strip():
                        cursor.execute("""
                            INSERT INTO dict_tspk_classes (category, class_name, norm_type, ratio, unit, note)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            row["Категория"], 
                            row["Класс ТСПК"], 
                            row["Тип нормирования"], 
                            float(row["Коэффициент"]), 
                            row["Ед. изм."], 
                            row["Примечание"]
                        ))
                conn.commit()
                conn.close()
                st.success("Классификатор успешно обновлен!")
                st.rerun()
        elif admin_password:
            st.error("Неверный пароль!")
    else:
        st.dataframe(df_raw_classes.drop(columns=["ID"]), use_container_width=True)