import io
import json

import pandas as pd
import streamlit as st

from services.calc import calculate_personnel, calculate_tspk
from services.personnel_ui import render_personnel_editor
from services.db import (
  delete_calculation,
  get_all_calculations,
  get_connection,
  get_tspk_dict,
  init_db,
  reset_tspk_to_default,
  save_calculation,
  save_tspk_dict,
)

# Инициализация БД
init_db()

st.set_page_config(
    page_title="Смена-Т | ГПС КР",
    page_icon="🦅",
    layout="wide",
)

# Сведения о разработчике — отображаются только в интерфейсе приложения.
st.sidebar.markdown("---")
st.sidebar.caption(
    "**Разработано Оперативной пограничной группой ФСБ России "
    "в Кыргызской Республике**"
)


def generate_excel_report(input_data: dict) -> bytes:
  """Генерирует форматированный Excel-отчет с итоговыми строками."""
  res_personnel = calculate_personnel(input_data)
  res_tspk = calculate_tspk(input_data, res_personnel)

  all_personnel = (
      res_personnel["management_table"] + res_personnel["duty_table"]
  )
  df_personnel = pd.DataFrame(all_personnel)
  df_tspk = pd.DataFrame(res_tspk)
  df_params_excel = pd.DataFrame([
      {"Параметр": "Автомобильный пункт пропуска", "Значение": input_data.get("app_name", "—")},
      {"Параметр": "Пропускная способность", "Значение": input_data.get("capacity_category", "—")},
      {"Параметр": "Режим работы", "Значение": input_data.get("work_mode", "—")},
      {"Параметр": "Количество смен", "Значение": input_data.get("shift_hours", "—")},
  ])

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

  # Итоговые строки: текстовые значения не суммируем, числовые поля складываем.
  personnel_total = {column: "" for column in df_personnel_excel.columns}
  if len(df_personnel_excel.columns):
      personnel_total[df_personnel_excel.columns[0]] = "ИТОГО"
  if "В смене (чел)" in df_personnel_excel:
      shift_values = pd.to_numeric(df_personnel_excel["В смене (чел)"], errors="coerce")
      shift_sum = shift_values.sum()
      personnel_total["В смене (чел)"] = int(shift_sum) if float(shift_sum).is_integer() else shift_sum
      if shift_values.notna().sum() == 0:
          personnel_total["В смене (чел)"] = "—"
  if "Всего штат (чел)" in df_personnel_excel:
      personnel_total["Всего штат (чел)"] = int(df_personnel_excel["Всего штат (чел)"].sum())

  tspk_total = {column: "" for column in df_tspk_excel.columns}
  if len(df_tspk_excel.columns):
      tspk_total[df_tspk_excel.columns[0]] = "ИТОГО"
  for column in ("Потребность", "НЗ (10%)", "Всего", "Итого стоимость ($)"):
      if column in df_tspk_excel:
          total_value = pd.to_numeric(df_tspk_excel[column], errors="coerce").sum()
          tspk_total[column] = (
              round(float(total_value), 2)
              if column == "Итого стоимость ($)"
              else int(total_value)
          )

  output = io.BytesIO()
  with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    workbook = writer.book

    title_format = workbook.add_format({
        "bold": True, "font_size": 16, "font_color": "#FFFFFF",
        "bg_color": "#1F4E78", "align": "center", "valign": "vcenter",
    })
    subtitle_format = workbook.add_format({
        "italic": True, "font_size": 10, "font_color": "#44546A",
        "align": "center", "valign": "vcenter",
    })
    header_format = workbook.add_format({
        "border": 1, "bold": True, "bg_color": "#D9EAF7",
        "font_color": "#17365D", "valign": "vcenter",
        "align": "center", "text_wrap": True,
    })
    cell_format = workbook.add_format({
        "border": 1, "valign": "vcenter",
    })
    total_format = workbook.add_format({
        "border": 1, "bold": True, "bg_color": "#E2F0D9",
        "top": 2, "valign": "vcenter",
    })
    money_format = workbook.add_format({
        "border": 1, "valign": "vcenter", "num_format": '$#,##0.00',
    })
    total_money_format = workbook.add_format({
        "border": 1, "bold": True, "bg_color": "#E2F0D9",
        "top": 2, "valign": "vcenter", "num_format": '$#,##0.00',
    })

    sheets_data = [
        (
            "Исходные данные", df_params_excel,
            "ИСХОДНЫЕ ДАННЫЕ РАСЧЁТА",
            f"Автомобильный пункт пропуска: {input_data.get('app_name', '—')} | {input_data.get('capacity_category', '—')}",
            None,
        ),
        (
            "Штат КПП", df_personnel_excel,
            "РАСЧЁТ ОРГАНИЗАЦИОННО-ШТАТНОЙ СТРУКТУРЫ",
            f"Автомобильный пункт пропуска: {input_data.get('app_name', '—')} | Смен: {input_data.get('shift_hours', '—')}",
            personnel_total,
        ),
        (
            "Спецификация ТСПК", df_tspk_excel,
            "ВЕДОМОСТЬ ПОТРЕБНОСТИ В ТЕХНИЧЕСКИХ СРЕДСТВАХ",
            f"Автомобильный пункт пропуска: {input_data.get('app_name', '—')} | Стоимость указана в долларах США",
            tspk_total,
        ),
    ]

    for sheet_name, df, title, subtitle, total_row in sheets_data:
      worksheet = workbook.add_worksheet(sheet_name)
      last_col = max(len(df.columns) - 1, 0)
      worksheet.merge_range(0, 0, 0, last_col, title, title_format)
      worksheet.merge_range(1, 0, 1, last_col, subtitle, subtitle_format)
      worksheet.set_row(0, 30)
      worksheet.set_row(1, 22)
      header_row = 3

      for col_idx, col_name in enumerate(df.columns):
        worksheet.write(header_row, col_idx, col_name, header_format)

      for row_idx, row in df.iterrows():
        for col_idx, val in enumerate(row):
          if pd.isna(val):
            val = ""
          fmt = money_format if df.columns[col_idx] == "Итого стоимость ($)" else cell_format
          worksheet.write(header_row + row_idx + 1, col_idx, val, fmt)

      if total_row is not None:
        total_excel_row = header_row + len(df) + 1
        for col_idx, col_name in enumerate(df.columns):
          value = total_row.get(col_name, "")
          fmt = total_money_format if col_name == "Итого стоимость ($)" else total_format
          worksheet.write(total_excel_row, col_idx, value, fmt)

      for idx, col in enumerate(df.columns):
        values = df[col].astype(str).tolist()
        max_len = max([len(str(col))] + [len(value) for value in values] + [12])
        worksheet.set_column(idx, idx, min(max(max_len + 3, 14), 48))

      worksheet.freeze_panes(header_row + 1, 0)
      if not df.empty:
        worksheet.autofilter(header_row, 0, header_row + len(df), last_col)
      worksheet.hide_gridlines(2)

  return output.getvalue()


# ==========================================
# 2. НАВИГАЦИЯ
# ==========================================
st.title("🦅 Смена-Т | Расчет потребностей пункта пропуска (ГПС КР)")

# Горизонтальное меню в виде переключателя
app_mode = st.radio(
    "Режим работы",
    [
        "🧮 Расчет пункта пропуска",
        "📜 История расчетов",
        "⚙️ Справочник ТСПК",
        "👥 Справочник персонала",
    ],
    horizontal=True,
    label_visibility="collapsed",
)

st.markdown("---")

# Если выбрана история — показываем архив и останавливаем выполнение калькулятора
if app_mode == "📜 История расчетов":
  st.header("📜 История сохраненных расчетов")
  st.caption("Архив всех ранее сохраненных конфигураций пунктов пропуска.")

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
            st.write(f"- **Автомобильный пункт пропуска:** {input_data.get('app_name', '—')}")
            st.write(
                f"- **Пропускная способность:**"
                f" {input_data.get('capacity_category', '—')}"
            )
          with col2:
            st.write(f"- **Режим работы:** {input_data.get('work_mode', '—')}")
            st.write(
                f"- **Количество смен:** {input_data.get('shift_hours', '—')}"
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
# РЕЖИМ: СПРАВОЧНИК ТСПК
# ==========================================
elif app_mode == "⚙️ Справочник ТСПК":
    st.header("⚙️ Управление справочником ТСПК")
    st.caption(
        "Здесь вы можете просматривать справочник, изменять цены и модели, "
        "а также добавлять новые позиции или удалять старые."
    )

    tspk_data = get_tspk_dict()
    df_tspk_editable = pd.DataFrame(tspk_data)

    # Создаем вкладки, чтобы не сваливать всё в одну кучу
    tab_edit, tab_add, tab_delete = st.tabs(["📋 Таблица и цены", "➕ Добавить позицию", "🗑️ Удалить позицию"])

    with tab_edit:
        if st.session_state.pop("tspk_reset_done", False):
            st.success("Справочник сброшен к исходным значениям.")

        st.subheader("Редактирование цен и моделей")
        st.info("Измените нужные ячейки в таблице и нажмите кнопку сохранения внизу.")

        edited_df = st.data_editor(
            df_tspk_editable,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "category": st.column_config.TextColumn("Категория", disabled=True),
                "equipment_name": st.column_config.TextColumn("Наименование ТСПК", width="large", disabled=True),
                "selected_model": st.column_config.TextColumn("Модель / Марка"),
                "unit_price_usd": st.column_config.NumberColumn("Цена за ед. ($)", format="$ %.2f"),
                "unit": st.column_config.TextColumn("Ед. изм.", disabled=True),
                "norm_type": None,
                "ratio": None,
                "note": st.column_config.TextColumn("Примечание"),
            },
            disabled=["id", "category", "equipment_name", "unit"],
            num_rows="fixed",  # Фиксируем строки, чтобы не ломать таблицу случайно
            width='content',
            key=f"tspk_editor_{st.session_state.get('tspk_editor_version', 0)}",
        )

        col_save, col_reset = st.columns(2)
        with col_save:
            if st.button("💾 Сохранить изменения цен", type="primary"):
                try:
                    save_tspk_dict(edited_df)
                    st.success("Цены и модели успешно обновлены!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка при сохранении: {e}")

        with col_reset:
            if st.button("🔄 Сбросить к исходным значениям"):
                try:
                    reset_tspk_to_default()
                    st.session_state["tspk_editor_version"] = (
                        st.session_state.get("tspk_editor_version", 0) + 1
                    )
                    st.session_state["tspk_reset_done"] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка при сбросе: {e}")

    with tab_add:
        added_item = st.session_state.pop("tspk_add_done", None)
        if added_item:
            st.success(f"Оборудование «{added_item}» успешно добавлено в справочник.")

        st.subheader("Добавление нового оборудования")
        with st.form("add_tspk_form", clear_on_submit=True):  # clear_on_submit=True автоматически очистит все поля формы после успешной отправки!
            new_cat = st.selectbox("Категория", [
                "Паспортный контроль", 
                "Досмотровые средства", 
                "Обнаружение оружия, ВВ и НВ", 
                "Аудио-, видео- и фотодокументирование", 
                "Эксплуатационные / технологические средства", 
                "Учебно-материальная база"
            ])
            new_name = st.text_input("Наименование оборудования")
            new_model = st.text_input("Модель / Марка")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                new_price = st.number_input("Цена за единицу ($)", min_value=0.0, value=100.0, step=10.0)
                new_unit = st.selectbox("Единица измерения", ["шт.", "компл."])
            with col_f2:
                norm_mapping = {
                    "На весь пункт пропуска (фиксировано)": "per_checkpoint",
                    "На каждое рабочее место (1:1)": "per_workstation",
                    "На каждую досмотровую группу": "per_inspection_group",
                    "На каждого контроллера / инспектора": "per_controller",
                    "На комнату специальной проверки": "per_spec_room",
                    "Количество выбирается оператором": "manual"
                }
                selected_norm_label = st.selectbox("Как рассчитывается норма?", options=list(norm_mapping.keys()))
                new_norm_type = norm_mapping[selected_norm_label]
            
            new_note = st.text_input("Примечание (например, 1 на пункт пропуска)")
            
            submitted = st.form_submit_button("➕ Добавить в справочник")
            if submitted:
                if new_name:
                    try:
                        # Объединяем контекст спиннера и подключения к БД через запятую
                        with st.spinner("Сохранение нового оборудования в базу..."), get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO dict_tspk (category, equipment_name, selected_model, norm_type, ratio, unit, unit_price_usd, note)
                                VALUES (?, ?, ?, ?, 1.0, ?, ?, ?)
                            """, (new_cat, new_name, new_model, new_norm_type, new_unit, new_price, new_note))
                            conn.commit()
                        
                        # Обновляем данные справочника и все вкладки
                        st.session_state["tspk_add_done"] = new_name
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Ошибка при добавлении: {e}")
                else:
                    st.warning("Пожалуйста, заполните наименование оборудования.")

    with tab_delete:
        deleted_item = st.session_state.pop("tspk_delete_done", None)
        if deleted_item:
            st.success(f"Позиция «{deleted_item}» успешно удалена.")

        st.subheader("Удаление позиции из справочника")
        st.warning("Будьте аккуратны: удаленная позиция пропадет из расчетов.")
        
        # Выбор позиции для удаления
        tspk_items = {
            f"{row['id']} | {row['category']} — {row['equipment_name']} ({row['selected_model']})": row
            for row in tspk_data
        }

        selected_item_label = st.selectbox(
            "Выберите оборудование для удаления",
            options=list(tspk_items.keys()),
            key=f"delete_select_{st.session_state.get('tspk_delete_version', 0)}",
        )
        selected_item = tspk_items[selected_item_label]
        item_id_to_delete = selected_item["id"]

        # Если пользователь переключил позицию, старое подтверждение больше не действует
        pending_delete_id = st.session_state.get("tspk_delete_confirm_id")
        if pending_delete_id is not None and pending_delete_id != item_id_to_delete:
            st.session_state.pop("tspk_delete_confirm_id", None)
            pending_delete_id = None

        st.markdown("#### Параметры выбранной позиции")
        detail_col1, detail_col2 = st.columns(2)
        with detail_col1:
            st.write(f"**Категория:** {selected_item.get('category') or '—'}")
            st.write(f"**Наименование:** {selected_item.get('equipment_name') or '—'}")
            st.write(f"**Модель / Марка:** {selected_item.get('selected_model') or '—'}")
        with detail_col2:
            st.write(f"**Единица измерения:** {selected_item.get('unit') or '—'}")
            st.write(f"**Цена за единицу:** $ {float(selected_item.get('unit_price_usd') or 0):,.2f}")
            st.write(f"**Примечание:** {selected_item.get('note') or '—'}")

        if pending_delete_id == item_id_to_delete:
            st.warning(
                f"Вы действительно хотите удалить позицию «{selected_item['equipment_name']}»? "
                "После удаления она перестанет учитываться в новых расчётах."
            )
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("Да, удалить", type="primary", key="confirm_tspk_delete"):
                    try:
                        with st.spinner("Удаление позиции из базы..."), get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "DELETE FROM dict_tspk WHERE id = ?",
                                (item_id_to_delete,),
                            )
                            if cursor.rowcount == 0:
                                raise ValueError("Выбранная позиция уже отсутствует в справочнике.")
                            conn.commit()

                        st.session_state.pop("tspk_delete_confirm_id", None)
                        st.session_state["tspk_delete_done"] = selected_item["equipment_name"]
                        st.session_state["tspk_delete_version"] = (
                            st.session_state.get("tspk_delete_version", 0) + 1
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка при удалении: {e}")
            with cancel_col:
                if st.button("Отмена", key="cancel_tspk_delete"):
                    st.session_state.pop("tspk_delete_confirm_id", None)
                    st.rerun()
        else:
            if st.button("🗑️ Удалить выбранную позицию", type="primary"):
                st.session_state["tspk_delete_confirm_id"] = item_id_to_delete
                st.rerun()

    st.stop()

# ==========================================
# РЕЖИМ: СПРАВОЧНИК ПЕРСОНАЛА
# ==========================================
elif app_mode == "👥 Справочник персонала":
    render_personnel_editor()
    st.stop()

# ==========================================
# ДАЛЬШЕ ИДЕТ КОД КАЛЬКУЛЯТОРА (Шаги 1, 2, 3)
# ==========================================

CAPACITY_PRESETS = {
    "Низкая (до 3 000 лиц/сутки)": {
        "cabins_in": 2,
        "cabins_out": 2,
        "lanes_auto_in": 1,
        "lanes_auto_out": 1,
        "lanes_truck_in": 1,
        "lanes_truck_out": 1,
        "lanes_bus_in": 0,
        "lanes_bus_out": 0,
    },
    "Средняя (3 000–7 000 лиц/сутки)": {
        "cabins_in": 4,
        "cabins_out": 4,
        "lanes_auto_in": 2,
        "lanes_auto_out": 2,
        "lanes_truck_in": 1,
        "lanes_truck_out": 1,
        "lanes_bus_in": 1,
        "lanes_bus_out": 1,
    },
    "Высокая I (7 000–10 000 лиц/сутки)": {
        "cabins_in": 8,
        "cabins_out": 8,
        "lanes_auto_in": 2,
        "lanes_auto_out": 2,
        "lanes_truck_in": 2,
        "lanes_truck_out": 2,
        "lanes_bus_in": 1,
        "lanes_bus_out": 1,
    },
    "Высокая II (10 000–20 000 лиц/сутки)": {
        "cabins_in": 12,
        "cabins_out": 12,
        "lanes_auto_in": 3,
        "lanes_auto_out": 3,
        "lanes_truck_in": 2,
        "lanes_truck_out": 2,
        "lanes_bus_in": 1,
        "lanes_bus_out": 1,
    },
    "Высокая III (20 000–25 000 лиц/сутки)": {
        "cabins_in": 19,
        "cabins_out": 19,
        "lanes_auto_in": 3,
        "lanes_auto_out": 3,
        "lanes_truck_in": 2,
        "lanes_truck_out": 2,
        "lanes_bus_in": 1,
        "lanes_bus_out": 1,
    },
}

if "step" not in st.session_state:
  st.session_state.step = 1

DEFAULT_CALC_DATA = {
    "app_name": "",
    "capacity_category": "Высокая III (20 000–25 000 лиц/сутки)",
    "work_mode": "24/7 (Круглосуточно)",
    "shift_hours": 3,
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
    "is_mixed_lanes": False,
    "lanes_mixed_in": 2,
    "lanes_mixed_out": 2,
}

if "calc_data" not in st.session_state:
  st.session_state.calc_data = DEFAULT_CALC_DATA.copy()


def go_step(step_number: int):
  st.session_state.step = step_number


def start_new_calculation():
  # Сбрасываем параметры и состояние виджетов, не затрагивая сохранённую историю и справочники.
  st.session_state.clear()


st.caption(f"Шаг {st.session_state.step} из 3")
top_new_col, _ = st.columns([1, 5])
with top_new_col:
  st.button(
      "🆕 Новый расчёт",
      key=f"new_calculation_top_step_{st.session_state.step}",
      on_click=start_new_calculation,
  )
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
        placeholder="Например: Мамыр, Кызыл-Кия, Достук",
        help="Введите название пункта пропуска. Оно будет указано в результатах и Excel-отчёте.",
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
        "Количество смен",
        options=[2, 3, 4],
        index=[2, 3, 4].index(
            int(st.session_state.calc_data.get("shift_hours", 3))
        ),
        format_func=lambda x: f"{x}",
        horizontal=True,
    )

  st.markdown("---")
  if st.button("Далее: Инфраструктура ➡️", type="primary"):
    if not app_name.strip():
        st.warning("Укажите наименование пункта пропуска.")
    else:
        preset = CAPACITY_PRESETS.get(
            capacity, CAPACITY_PRESETS["Высокая III (20 000–25 000 лиц/сутки)"]
        )

        st.session_state.calc_data.update({
            "app_name": app_name.strip(),
            "capacity_category": capacity,
            "work_mode": work_mode,
            "shift_hours": shift_hours,
            **preset,
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
        
        # Ручной выбор автоматизированных кабин
        st.subheader("Автоматизированные кабины (E-Gate)")
        manual_auto_cabins = st.number_input(
            "Количество кабин E-Gate",
            min_value=0,
            value=st.session_state.calc_data.get("manual_auto_cabins", 0),
            help="Количество автоматизированных кабин пограничного контроля (E-Gate) задается вручную.",
        )
        
        st.subheader("Специальные помещения")
        spec_rooms_count = st.number_input(
            "Количество комнат специальной проверки",
            min_value=0,
            value=st.session_state.calc_data.get("spec_rooms_count", 1),
            help="Количество оборудованных комнат специальной проверки документов в пункте пропуска.",
        )

        st.subheader("Полосы движения")
        
        # Переключатель для универсальных полос
        is_mixed_lanes = st.checkbox(
            "Все полосы для всех видов транспорта (универсальные)",
            value=st.session_state.calc_data.get("is_mixed_lanes", False),
            help="При активации полосы не делятся по типам ТС, а рассчитываются как единые универсальные полосы движения.",
        )

        if is_mixed_lanes:
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                lanes_mixed_in = st.number_input(
                    "Универсальные полосы (Въезд)",
                    min_value=1,
                    value=max(1, int(st.session_state.calc_data.get("lanes_mixed_in", 2))),
                )
            with c_m2:
                lanes_mixed_out = st.number_input(
                    "Универсальные полосы (Выезд)",
                    min_value=1,
                    value=max(1, int(st.session_state.calc_data.get("lanes_mixed_out", 2))),
                )

            # Для совместимости со старой логикой грузовых/легковых полос присваиваем универсальные значения:
            lanes_auto_in = lanes_mixed_in
            lanes_auto_out = lanes_mixed_out
            lanes_truck_in = lanes_mixed_in
            lanes_truck_out = lanes_mixed_out
            lanes_bus_in = 0
            lanes_bus_out = 0

            st.caption("🔒 Специализированные полосы заблокированы, так как выбран универсальный режим.")
            c_l1, c_l2 = st.columns(2)
            with c_l1:
                st.number_input("Легковые (Въезд)", value=lanes_auto_in, disabled=True, key="dis_auto_in")
                st.number_input("Грузовые (Въезд)", value=lanes_truck_in, disabled=True, key="dis_truck_in")
                st.number_input("Автобусы (Въезд)", value=0, disabled=True, key="dis_bus_in")
            with c_l2:
                st.number_input("Легковые (Выезд)", value=lanes_auto_out, disabled=True, key="dis_auto_out")
                st.number_input("Грузовые (Выезд)", value=lanes_truck_out, disabled=True, key="dis_truck_out")
                st.number_input("Автобусы (Выезд)", value=0, disabled=True, key="dis_bus_out")

        else:
            lanes_mixed_in = 0
            lanes_mixed_out = 0
            c_l1, c_l2 = st.columns(2)
            with c_l1:
                lanes_auto_in = st.number_input(
                    "Легковые (Въезд)",
                    min_value=1,
                    value=st.session_state.calc_data.get("lanes_auto_in", 2),
                )
                lanes_truck_in = st.number_input(
                    "Грузовые (Въезд)",
                    min_value=0,
                    value=st.session_state.calc_data.get("lanes_truck_in", 1),
                )
                lanes_bus_in = st.number_input(
                    "Автобусы (Въезд)",
                    min_value=0,
                    value=st.session_state.calc_data.get("lanes_bus_in", 0),
                )

            with c_l2:
                lanes_auto_out = st.number_input(
                    "Легковые (Выезд)",
                    min_value=1,
                    value=st.session_state.calc_data.get("lanes_auto_out", 2),
                )
                lanes_truck_out = st.number_input(
                    "Грузовые (Выезд)",
                    min_value=0,
                    value=st.session_state.calc_data.get("lanes_truck_out", 1),
                )
                lanes_bus_out = st.number_input(
                    "Автобусы (Выезд)",
                    min_value=0,
                    value=st.session_state.calc_data.get("lanes_bus_out", 0),
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
            help="При досмотре автотранспорта наличие кинологов обязательно.",
        )

        st.subheader("Руководящий состав КПП")
        dep_general = st.checkbox(
            "Заместитель начальника КПП",
            value=st.session_state.calc_data.get("deputies", {}).get(
                "deputy_general", True
            ),
        )
        dep_political = st.checkbox(
            "Заместитель по воспитательной работе",
            value=st.session_state.calc_data.get("deputies", {}).get(
                "deputy_political", False
            ),
        )
        dep_tspk = st.checkbox(
            "Заместитель по ТСПК",
            value=st.session_state.calc_data.get("deputies", {}).get(
                "deputy_tspk", True
            ),
        )
        dep_operational = st.checkbox(
            "Заместитель по оперативной деятельности",
            value=st.session_state.calc_data.get("deputies", {}).get(
                "deputy_operational", True
            ),
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
                "manual_auto_cabins": manual_auto_cabins,
                "spec_rooms_count": spec_rooms_count,
                "is_mixed_lanes": is_mixed_lanes,
                "lanes_mixed_in": lanes_mixed_in,
                "lanes_mixed_out": lanes_mixed_out,
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

  st.subheader(f"🚗 Автомобильный пункт пропуска «{data['app_name']}» ({data['capacity_category']})")
  st.caption(
      f"Режим работы: {data.get('work_mode', '—')} | "
      f"Количество смен: {data.get('shift_hours', '—')}"
  )

  m1, m2, m3, m4 = st.columns(4)
  m1.metric("Состав смены", f"{res_personnel['shift_total']} чел.")
  m2.metric("Общий штат смен", f"{res_personnel['total_duty']} чел.")
  m3.metric("Руководство", f"{res_personnel['management_count']} чел.")
  m4.metric("ИТОГО штат КПП", f"{res_personnel['total_full_staff']} чел.")

  st.markdown("---")

  st.subheader("👥 Расчетная оргштатная структура пункта пропуска")
  st.info(
      "💡 **Примечание:** Приведенные данные являются ориентировочным расчетным"
      " штатом. Окончательная оргштатная структура утверждается в"
      " соответствии с ведомственными приказами."
  )

  all_personnel = (
      res_personnel["management_table"] + res_personnel["duty_table"]
  )
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
      width="stretch",
      hide_index=True,
  )

  st.markdown("---")

  st.subheader("📦 Нормативная потребность в ТСПК и стоимость")
  df_tspk = pd.DataFrame(res_tspk)

  grand_total_usd = (
      df_tspk["total_price"].sum() if "total_price" in df_tspk.columns else 0
  )

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
          "unit_price": st.column_config.NumberColumn(
              "Цена за ед.", format="$ %,.2f"
          ),
          "total_price": st.column_config.NumberColumn(
              "Итого стоимость", format="$ %,.2f"
          ),
          "note": "Примечание",
      },
      width="stretch",
      hide_index=True,
  )

  st.subheader(
      f"💰 Общая стоимость оборудования ТСПК: **$ {grand_total_usd:,.2f}**"
  )

  st.markdown("---")
  c1, c3, c4 = st.columns([1.2, 2, 2])

  with c1:
    if st.button("⬅️ Изменить параметры"):
      go_step(2)
      st.rerun()

  with c3:
    processed_data = generate_excel_report(data)

    st.download_button(
        label="📥 Скачать отчёт (Excel)",
        data=processed_data,
        file_name=f"Смена_Т_{data['app_name']}.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        key="download_excel_report",
    )

  with c4:
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

      st.success(
          f"Расчет успешно сохранен в базе данных! (ID записи: {calc_id})"
      )