import io

import pandas as pd
import streamlit as st

from services.calc import calculate_personnel, calculate_tspk
from services.db import (
  delete_calculation,
  get_all_calculations,
  init_db,
  save_calculation,
)

# Инициализация БД
init_db()

st.set_page_config(
    page_title="Смена-Т | ГПС КР",
    page_icon="🦅",
    layout="wide",
)

def generate_excel_report(input_data: dict) -> bytes:
  """Генерирует форматированный Excel-отчет на основе входных данных расчета."""
  res_personnel = calculate_personnel(input_data)
  res_tspk = calculate_tspk(input_data, res_personnel)

  all_personnel = (
      res_personnel["management_table"] + res_personnel["duty_table"]
  )
  df_personnel = pd.DataFrame(all_personnel)
  df_tspk = pd.DataFrame(res_tspk)

  df_personnel_excel = df_personnel.rename(
      columns={
          "category": "Категория",
          "position": "Должность",
          "in_shift": "В смене (чел)",
          "total": "Всего штат (чел)",
          "note": "Основание / Примечание",
      }
  )

  df_tspk_excel = df_tspk.rename(
      columns={
          "category": "Категория",
          "name": "Наименование ТСПК",
          "selected_model": "Модель / Марка",
          "required": "Потребность",
          "reserve": "НЗ (10%)",
          "total": "Всего",
          "unit": "Ед. изм.",
          "unit_price": "Цена за ед. ($)",
          "total_price": "Итого стоимость ($)",
          "note": "Примечание",
      }
  )

  output = io.BytesIO()
  with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    workbook = writer.book

    border_format = workbook.add_format(
        {"border": 1, "valign": "vcenter"}
    )
    header_format = workbook.add_format({
        "border": 1,
        "bold": True,
        "bg_color": "#D9E1F2",
        "valign": "vcenter",
        "align": "center",
    })

    sheets_data = {
        "Штат КПП": df_personnel_excel,
        "Спецификация ТСПК": df_tspk_excel,
    }

    for sheet_name, df in sheets_data.items():
      worksheet = workbook.add_worksheet(sheet_name)

      for col_idx, col_name in enumerate(df.columns):
        worksheet.write(0, col_idx, col_name, header_format)

      for row_idx, row in df.iterrows():
        for col_idx, val in enumerate(row):
          if pd.isna(val):
            val = ""
          worksheet.write(row_idx + 1, col_idx, val, border_format)

      for idx, col in enumerate(df.columns):
        max_len = (
            max(df[col].astype(str).map(len).max(), len(str(col))) + 3
        )
        worksheet.set_column(idx, idx, max(max_len, 12))

  return output.getvalue()

# ==========================================
# 2. НАВИГАЦИЯ
# ==========================================
st.title("🦅 Смена-Т | Расчет потребностей пункта пропуска (ГПС КР)")

# Горизонтальное меню в виде переключателя
app_mode = st.radio(
    "Режим работы",
    ["🧮 Расчет пункта пропуска", "📜 История расчетов"],
    horizontal=True,
    label_visibility="collapsed",
)

st.markdown("---")

# Если выбрана история — показываем архив и останавливаем выполнение калькулятора
if app_mode == "📜 История расчетов":
  st.header("📜 История сохраненных расчетов")
  st.caption("Архив всех ранее сохраненных конфигураций пунктов пропуска.")

  import json

  history_items = get_all_calculations()

  if not history_items:
    st.info(
        "В базе данных пока нет сохраненных расчетов. Сделайте расчет и нажмите"
        " кнопку «Сохранить в историю» на третьем шаге."
    )
  else:
    for item in history_items:
      try:
        res_data = (
            json.loads(item["results"])
            if isinstance(item["results"], str)
            else item["results"]
        )
        total_usd = res_data.get("grand_total_usd", 0)
      except Exception:
        total_usd = 0

      with st.expander(
          f"📍 {item['app_name']} | {item['category']} (от"
          f" {item['created_at']})"
      ):
        st.write(f"**ID записи в базе:** {item['id']}")
       # st.write(f"**Общая стоимость ТСПК:** $ {total_usd:,.2f}")

        # Безопасно парсим входные параметры
        try:
          input_data = (
              json.loads(item["input_params"])
              if isinstance(item["input_params"], str)
              else item["input_params"]
          )
        except Exception:
          input_data = {}

        # Выводим основные входные параметры, если они есть
        if input_data:
          st.markdown("#### 📋 Параметры расчета:")
          col1, col2 = st.columns(2)
          with col1:
            st.write(
                f"- **Наименование:** {input_data.get('app_name', '—')}"
            )
            st.write(
                f"- **Пропускная способность:**"
                f" {input_data.get('capacity_category', '—')}"
            )
          with col2:
            st.write(f"- **Режим работы:** {input_data.get('work_mode', '—')}")
            st.write(
                f"- **Смена:** {input_data.get('shift_hours', '—')} часов"
            )

        # Человекопонятное отображение деталей вместо сырого JSON
        with st.expander("📊 Детали сохраненной конфигурации"):
          st.markdown("##### 🚗 Инфраструктура и полосы движения")
          col_inf1, col_inf2 = st.columns(2)
          with col_inf1:
            st.write(
                f"- **Кабины въезд / выезд:**"
                f" {input_data.get('cabins_in', 0)} /"
                f" {input_data.get('cabins_out', 0)}"
            )
            st.write(
                f"- **Легковые полосы (в/в):**"
                f" {input_data.get('lanes_car_in', 0)} /"
                f" {input_data.get('lanes_car_out', 0)}"
            )
            st.write(
                f"- **Грузовые полосы (в/в):**"
                f" {input_data.get('lanes_truck_in', 0)} /"
                f" {input_data.get('lanes_truck_out', 0)}"
            )
          with col_inf2:
            st.write(
                f"- **Автобусные полосы (в/в):**"
                f" {input_data.get('lanes_bus_in', 0)} /"
                f" {input_data.get('lanes_bus_out', 0)}"
            )
            st.write(
                "- **Наличие ИДК:**"
                f" {'✅ Да' if input_data.get('has_idk') else '❌ Нет'}"
            )
            st.write(
                "- **Система РПМ:**"
                f" {'✅ Да' if input_data.get('has_rpm') else '❌ Нет'}"
            )

          # Если в результатах есть данные по оборудованию или штату, выведем их тоже красиво
          if res_data:
            st.markdown("##### 💰 Финансовые и ресурсные итоги")
            st.write(
                f"- **Итоговая стоимость ТСПК:** **$**"
                f" **{res_data.get('grand_total_usd', 0):,.2f}**"
            )

        st.markdown("---")

        # Генерируем Excel-отчет "на лету" из сохраненных входных параметров
        excel_bytes = generate_excel_report(input_data)

        # Делаем две аккуратные колонки: слева — скачать, справа — удалить
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
          st.download_button(
              label="📥 Скачать отчёт (Excel)",
              data=excel_bytes,
              file_name=(
                  f"Смена_Т_{input_data.get('app_name', 'Пункт_пропуска')}.xlsx"
              ),
              mime=(
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              ),
              key=f"dl_excel_{item['id']}",
          )
        with col_btn2:
          if st.button(
              f"🗑️ Удалить расчет (ID: {item['id']})",
              key=f"del_calc_{item['id']}",
          ):
            delete_calculation(item["id"])
            st.success(f"Расчет ID {item['id']} успешно удален!")
            st.rerun()

  st.stop()  # Останавливает отрисовку шагов калькулятора, когда открыта история

# ==========================================
# ДАЛЬШЕ ИДЕТ КОД КАЛЬКУЛЯТОРА (Шаги 1, 2, 3)
# ==========================================

st.set_page_config(
    page_title="Смена-Т | ГПС КР",
    page_icon="🦅",
    layout="wide",
)

CAPACITY_PRESETS = {
    "Низкая (до 3 000 лиц/сутки)": {
        "cabins_in": 2, "cabins_out": 2,
        "lanes_auto_in": 1, "lanes_auto_out": 1,
        "lanes_truck_in": 1, "lanes_truck_out": 1,
        "lanes_bus_in": 0, "lanes_bus_out": 0,
    },
    "Средняя (3 000–7 000 лиц/сутки)": {
        "cabins_in": 4, "cabins_out": 4,
        "lanes_auto_in": 2, "lanes_auto_out": 2,
        "lanes_truck_in": 1, "lanes_truck_out": 1,
        "lanes_bus_in": 1, "lanes_bus_out": 1,
    },
    "Высокая I (7 000–10 000 лиц/сутки)": {
        "cabins_in": 8, "cabins_out": 8,
        "lanes_auto_in": 2, "lanes_auto_out": 2,
        "lanes_truck_in": 2, "lanes_truck_out": 2,
        "lanes_bus_in": 1, "lanes_bus_out": 1,
    },
    "Высокая II (10 000–20 000 лиц/сутки)": {
        "cabins_in": 12, "cabins_out": 12,
        "lanes_auto_in": 3, "lanes_auto_out": 3,
        "lanes_truck_in": 2, "lanes_truck_out": 2,
        "lanes_bus_in": 1, "lanes_bus_out": 1,
    },
    "Высокая III (20 000–25 000 лиц/сутки)": {
        "cabins_in": 19, "cabins_out": 19,
        "lanes_auto_in": 3, "lanes_auto_out": 3,
        "lanes_truck_in": 2, "lanes_truck_out": 2,
        "lanes_bus_in": 1, "lanes_bus_out": 1,
    },
}

if "step" not in st.session_state:
    st.session_state.step = 1

if "calc_data" not in st.session_state:
    st.session_state.calc_data = {
        "app_name": "Пункт пропуска 'Мамыр'",
        "capacity_category": "Высокая III (20 000–25 000 лиц/сутки)",
        "work_mode": "24/7 (Круглосуточно)",
        "shift_hours": 12,
        "cabins_in": 19,
        "cabins_out": 19,
        "lanes_auto_in": 3,
        "lanes_auto_out": 3,
        "lanes_truck_in": 2,
        "lanes_truck_out": 2,
        "lanes_bus_in": 1,
        "lanes_bus_out": 1,
        "has_idk": True,
        "has_rpm": True,
        "k9_service": "Приданные силы",
    }


def go_step(step_number: int):
    st.session_state.step = step_number


# st.title("🦅 Смена-Т — Расчет потребностей пункта пропуска (ГПС КР)")
st.caption(f"Шаг {st.session_state.step} из 3")
st.progress(st.session_state.step / 3)

# ==========================================
# ШАГ 1: БАЗОВЫЕ ПАРАМЕТРЫ
# ==========================================
if st.session_state.step == 1:
    st.header("1. Общие сведения и пропускная способность")

    col1, col2 = st.columns(2)

    with col1:
        app_name = st.text_input(
            "Наименование пункта пропуска",
            value=st.session_state.calc_data["app_name"],
        )

        capacity = st.selectbox(
            "Пропускная способность (лиц/сутки)",
            options=[
                "Низкая (до 3 000 лиц/сутки)",
                "Средняя (3 000–7 000 лиц/сутки)",
                "Высокая I (7 000–10 000 лиц/сутки)",
                "Высокая II (10 000–20 000 лиц/сутки)",
                "Высокая III (20 000–25 000 лиц/сутки)",
            ],
            index=4,
        )

    with col2:
        work_mode = st.selectbox(
            "Режим работы",
            options=["24/7 (Круглосуточно)", "12 часов (Дневной)"],
            index=0,
        )

        shift_hours = st.radio(
            "Продолжительность смены",
            options=[12, 8, 24],
            format_func=lambda x: f"{x} часов",
            horizontal=True,
        )

    st.markdown("---")
    if st.button("Далее: Инфраструктура ➡️", type="primary"):
        # Получаем пресет под выбранную категорию
        preset = CAPACITY_PRESETS.get(capacity, CAPACITY_PRESETS["Высокая III (20 000–25 000 лиц/сутки)"])
        
        # Обновляем данные, включая автоматические параметры для кабин и полос
        st.session_state.calc_data.update({
            "app_name": app_name,
            "capacity_category": capacity,
            "work_mode": work_mode,
            "shift_hours": shift_hours,
            **preset,  # Распаковываем дефолтные кабины и полосы выбранной категории
        })
        go_step(2)
        st.rerun()

# ==========================================
# ШАГ 2: ИНФРАСТРУКТУРА И СПЕЦ-ОСНАЩЕНИЕ
# ==========================================
elif st.session_state.step == 2:
    st.header("2. Инфраструктура и технические оснащения")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Кабины паспортного контроля (ПД)")
        cabins_in = st.number_input(
            "Кабин на въезд",
            min_value=1,
            value=st.session_state.calc_data["cabins_in"],
        )
        cabins_out = st.number_input(
            "Кабин на выезд",
            min_value=1,
            value=st.session_state.calc_data["cabins_out"],
        )

        st.subheader("Полосы движения (Въезд / Выезд)")
        c_l1, c_l2 = st.columns(2)
        with c_l1:
            lanes_auto_in = st.number_input(
                "Легковые (Въезд)",
                min_value=1,
                value=st.session_state.calc_data["lanes_auto_in"],
            )
            lanes_truck_in = st.number_input(
                "Грузовые (Въезд)",
                min_value=0,
                value=st.session_state.calc_data["lanes_truck_in"],
            )
            lanes_bus_in = st.number_input(
                "Автобусы (Въезд)",
                min_value=0,
                value=st.session_state.calc_data["lanes_bus_in"],
            )

        with c_l2:
            lanes_auto_out = st.number_input(
                "Легковые (Выезд)",
                min_value=1,
                value=st.session_state.calc_data.get("lanes_auto_out", 3),
            )
            lanes_truck_out = st.number_input(
                "Грузовые (Выезд)",
                min_value=0,
                value=st.session_state.calc_data.get("lanes_truck_out", 2),
            )
            lanes_bus_out = st.number_input(
                "Автобусы (Выезд)",
                min_value=0,
                value=st.session_state.calc_data["lanes_bus_out"],
            )

    with col2:
        st.subheader("Специальные комплексы")
        has_idk = st.checkbox(
            "Наличие ИДК",
            value=st.session_state.calc_data["has_idk"],
        )
        has_rpm = st.checkbox(
            "Система РПМ (въезд/выезд)",
            value=st.session_state.calc_data["has_rpm"],
        )

        st.subheader("Кинологическое обеспечение")
        k9_service = st.radio(
            "Формат кинологического обеспечения",
            options=["В штате КПП", "Приданные силы"],
            index=0,
            help="При досмотре автотранспорта наличие кинологов обязательно."
        )

        # -------------------------------------------------------------
        # ДОБАВЛЯЕМ БЛОК РУКОВОДСТВА СЮДА:
        # -------------------------------------------------------------
        st.subheader("Руководящий состав КПП")
        dep_general = st.checkbox(
            "Заместитель начальника КПП", 
            value=st.session_state.calc_data.get("deputies", {}).get("deputy_general", True)
        )
        dep_political = st.checkbox(
            "Заместитель по воспитательной работе", 
            value=st.session_state.calc_data.get("deputies", {}).get("deputy_political", False)
        )
        dep_tspk = st.checkbox(
            "Заместитель по ТСПК", 
            value=st.session_state.calc_data.get("deputies", {}).get("deputy_tspk", True)
        )
        dep_operational = st.checkbox(
            "Заместитель по оперативной деятельности", 
            value=st.session_state.calc_data.get("deputies", {}).get("deputy_operational", True)
        )

    st.markdown("---")
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("⬅️ Назад"):
            go_step(1)
            st.rerun()
    with c2:
        if st.button("Рассчитать 📊", type="primary"):
            st.session_state.calc_data.update({
                "cabins_in": cabins_in,
                "cabins_out": cabins_out,
                "lanes_auto_in": lanes_auto_in,
                "lanes_auto_out": lanes_auto_out,
                "lanes_truck_in": lanes_truck_in,
                "lanes_truck_out": lanes_truck_out,
                "lanes_bus_in": lanes_bus_in,
                "lanes_bus_out": lanes_bus_out,
                "has_idk": has_idk,
                "has_rpm": has_rpm,
                "k9_service": k9_service,
                "deputies": {
                    "deputy_general": dep_general,
                    "deputy_political": dep_political,
                    "deputy_tspk": dep_tspk,
                    "deputy_operational": dep_operational,
                },
            })
            go_step(3)
            st.rerun()

# ==========================================
# ШАГ 3: РЕЗУЛЬТАТЫ
# ==========================================
elif st.session_state.step == 3:
    st.header("3. Результаты расчета")

    data = st.session_state.calc_data

    res_personnel = calculate_personnel(data)
    res_tspk = calculate_tspk(data, res_personnel)

    st.subheader(f"📌 {data['app_name']} ({data['capacity_category']})")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Состав смены", f"{res_personnel['shift_total']} чел.")
    m2.metric("Общий штат смен", f"{res_personnel['total_duty']} чел.")
    m3.metric("Руководство", f"{res_personnel['management_count']} чел.")
    m4.metric("ИТОГО штат КПП", f"{res_personnel['total_full_staff']} чел.")

    st.markdown("---")

    st.subheader("👥 Расчетная оргштатная структура пункта пропуска")
    st.info(
        "💡 **Примечание:** Приведенные данные являются ориентировочным расчетным штатом. "
        "Окончательная оргштатная структура утверждается в соответствии с ведомственными приказами."
    )

    all_personnel = res_personnel["management_table"] + res_personnel["duty_table"]
    df_personnel = pd.DataFrame(all_personnel)

    st.dataframe(
        df_personnel,
        column_config={
            "category": "Подразделение / Группа",
            "position": "Должность",
            "in_shift": "В смене (чел)",
            "total": "Всего штат (чел)",
            "note": "Основание / Примечание",
        },
        width='stretch',
        hide_index=True,
    )

    st.markdown("---")

    st.subheader("📦 Нормативная потребность в ТСПК и стоимость")
    df_tspk = pd.DataFrame(res_tspk)

    grand_total_usd = df_tspk["total_price"].sum() if "total_price" in df_tspk.columns else 0

    st.dataframe(
        df_tspk,
        column_config={
            "category": "Категория",
            "name": "Наименование ТСПК",
            "selected_model": "Модель / Марка",
            "required": "Потребность",
            "reserve": "НЗ (10%)",
            "total": "Всего",
            "unit": "Ед. изм.",
            "unit_price": st.column_config.NumberColumn("Цена за ед.", format="$ %,.2f"),
            "total_price": st.column_config.NumberColumn("Итого стоимость", format="$ %,.2f"),
            "note": "Примечание",
        },
        width='stretch',
        hide_index=True,
    )

    st.subheader(f"💰 Общая стоимость оборудования ТСПК: **$ {grand_total_usd:,.2f}**")

    st.markdown("---")
    c1, c2, c3 = st.columns([1, 2, 4])
    
    with c1:
        if st.button("⬅️ Изменить параметры"):
            go_step(2)
            st.rerun()
            
    with c2:
      processed_data = generate_excel_report(data)

      st.download_button(
          label="📥 Скачать отчет (Excel)",
          data=processed_data,
          file_name=f"Смена_Т_{data['app_name']}.xlsx",
          mime=(
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          ),
          type="primary",
          key="download_excel_report",
      )

    with c3:
        if st.button("💾 Сохранить в историю"):
            combined_results = {
                "personnel": res_personnel,
                "tspk": res_tspk,
                "grand_total_usd": grand_total_usd,
            }
            calc_id = save_calculation(
                app_name=data["app_name"],
                app_code=None,
                category=data["capacity_category"],
                input_params=data,
                results=combined_results,
            )

            st.success(f"Расчет успешно сохранен в базе данных! (ID записи: {calc_id})")