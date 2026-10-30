"""Streamlit-интерфейс управления справочником персонала."""

import json
import re

import pandas as pd
import streamlit as st

from services.db import (
    get_personnel_dict,
    reset_personnel_to_default,
    save_personnel_dict,
)


CALCULATION_TYPES = [
    "per_checkpoint",
    "per_shift",
    "per_lane",
    "per_cabin",
    "per_direction",
    "per_inspection_group",
    "per_inspection_personnel",
    "manual",
]


def render_personnel_editor() -> None:
    """Отображает редактор должностей, нормативов и пользовательских ролей."""
    st.header("👥 Управление справочником персонала")
    st.caption(
        "Здесь настраиваются должности и нормативы, используемые при расчете "
        "штата КПП. Системные записи нельзя удалить из этого интерфейса."
    )

    personnel = get_personnel_dict(include_inactive=True)
    groups = sorted(
        {item["functional_group"] for item in personnel if item["functional_group"]}
        | {"other"}
    )

    edit_tab, add_tab, reset_tab = st.tabs(
        ["📋 Должности и нормативы", "➕ Добавить должность", "🔄 Сброс"]
    )

    with edit_tab:
        st.info(
            "Код роли и признак системной записи защищены от редактирования. "
            "Чтобы исключить должность из новых расчетов, снимите флаг «Активна»."
        )
        table = pd.DataFrame(personnel)
        table["rule_params"] = table["rule_params"].apply(
            lambda value: json.dumps(value, ensure_ascii=False)
        )
        version = st.session_state.get("personnel_editor_version", 0)
        edited = st.data_editor(
            table,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "category": st.column_config.TextColumn("Категория"),
                "position_name": st.column_config.TextColumn(
                    "Наименование должности", width="large"
                ),
                "role_code": st.column_config.TextColumn("Код роли", disabled=True),
                "functional_group": st.column_config.SelectboxColumn(
                    "Функциональная группа", options=groups
                ),
                "calculation_type": st.column_config.SelectboxColumn(
                    "Тип норматива", options=CALCULATION_TYPES
                ),
                "quantity": st.column_config.NumberColumn(
                    "Количество", min_value=0.0, step=1.0
                ),
                "apply_shift_factor": st.column_config.CheckboxColumn(
                    "Учитывать сменность"
                ),
                "condition_key": st.column_config.TextColumn("Условие включения"),
                "rule_params": st.column_config.TextColumn(
                    "Параметры правила (JSON)", width="large"
                ),
                "is_active": st.column_config.CheckboxColumn("Активна"),
                "is_system": st.column_config.CheckboxColumn(
                    "Системная", disabled=True
                ),
                "note": st.column_config.TextColumn("Примечание", width="large"),
                "sort_order": st.column_config.NumberColumn("Порядок"),
            },
            disabled=["id", "role_code", "is_system"],
            num_rows="fixed",
            width="stretch",
            key=f"personnel_editor_{version}",
        )

        save_col, cancel_col = st.columns(2)
        with save_col:
            if st.button("💾 Сохранить справочник", type="primary"):
                try:
                    save_personnel_dict(edited)
                    st.session_state["personnel_editor_version"] = version + 1
                    st.success("Справочник персонала сохранен.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Не удалось сохранить справочник: {exc}")
        with cancel_col:
            if st.button("↩️ Отменить изменения"):
                st.session_state["personnel_editor_version"] = version + 1
                st.rerun()

    with add_tab:
        st.subheader("Новая должность")
        st.caption(
            "Новая роль будет участвовать в расчете по выбранной функциональной группе. "
            "Для типа «manual» укажите в JSON параметр input_key, соответствующий "
            "ключу исходных данных. Условия включения должны использовать ключи, "
            "которые уже поддерживает расчетный модуль."
        )
        with st.form("add_personnel_form", clear_on_submit=True):
            category = st.text_input("Категория", value="Дополнительный персонал")
            position = st.text_input("Наименование должности")
            role_code = st.text_input(
                "Уникальный код роли",
                help="Латинские буквы, цифры и _. Код после создания не меняется.",
            )
            group = st.selectbox("Функциональная группа", options=groups)
            calculation_type = st.selectbox(
                "Тип норматива", options=CALCULATION_TYPES
            )
            quantity_col, shift_col = st.columns(2)
            with quantity_col:
                quantity = st.number_input(
                    "Количество по нормативу", min_value=0.0, value=1.0, step=1.0
                )
            with shift_col:
                apply_shift = st.checkbox(
                    "Учитывать коэффициент сменности", value=True
                )
            condition = st.text_input(
                "Условие включения (необязательно)",
                help="Например: has_idk, has_rpm или k9_staff_enabled.",
            )
            rule_params_text = st.text_input(
                "Параметры правила (JSON)", value="{}"
            )
            note = st.text_input("Примечание")
            submitted = st.form_submit_button("➕ Добавить должность")

        if submitted:
            normalized_code = role_code.strip()
            if not category.strip() or not position.strip() or not normalized_code:
                st.warning("Заполните категорию, должность и код роли.")
            elif not re.fullmatch(r"[A-Za-z0-9_]+", normalized_code):
                st.warning("Код роли должен содержать латинские буквы, цифры и _.")
            else:
                try:
                    params = json.loads(rule_params_text or "{}")
                    if not isinstance(params, dict):
                        raise ValueError("Параметры правила должны быть JSON-объектом.")
                    new_item = {
                        "id": None,
                        "category": category.strip(),
                        "position_name": position.strip(),
                        "role_code": normalized_code,
                        "functional_group": group,
                        "calculation_type": calculation_type,
                        "quantity": quantity,
                        "apply_shift_factor": apply_shift,
                        "condition_key": condition.strip() or None,
                        "rule_params": params,
                        "is_active": True,
                        "is_system": False,
                        "note": note.strip(),
                        "sort_order": max(
                            (int(item["sort_order"]) for item in personnel),
                            default=0,
                        ) + 1,
                    }
                    save_personnel_dict(personnel + [new_item])
                    st.session_state["personnel_editor_version"] = (
                        st.session_state.get("personnel_editor_version", 0) + 1
                    )
                    st.success(f"Должность «{position}» добавлена.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Не удалось добавить должность: {exc}")

    with reset_tab:
        st.warning(
            "Сброс восстановит стандартный шаблон и удалит пользовательские "
            "записи и все изменения справочника персонала."
        )
        if st.session_state.get("personnel_reset_confirm"):
            st.error("Подтвердите сброс справочника.")
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("Да, сбросить справочник", type="primary"):
                    try:
                        reset_personnel_to_default()
                        st.session_state["personnel_reset_confirm"] = False
                        st.session_state["personnel_editor_version"] = (
                            st.session_state.get("personnel_editor_version", 0) + 1
                        )
                        st.success("Стандартный шаблон восстановлен.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Ошибка при сбросе: {exc}")
            with cancel_col:
                if st.button("Отмена"):
                    st.session_state["personnel_reset_confirm"] = False
                    st.rerun()
        elif st.button("🔄 Сбросить к стандартному шаблону"):
            st.session_state["personnel_reset_confirm"] = True
            st.rerun()
