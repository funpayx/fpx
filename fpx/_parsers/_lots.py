from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup, Tag

from fpx.utils import errors as fpx_err

from ._base import BaseParser

logger = logging.getLogger("fpx.lot_parser")


class LotParser(BaseParser):
    @classmethod
    def parse_lot_menu(cls, html_content: str) -> str:
        """Парсит страницу pay.com/lots/.../trade"""
        soup = BeautifulSoup(html_content, "html.parser")
        button = soup.find("button", class_="js-lot-raise")
        if not button:
            button = soup.find("button", attrs={"data-game": True})
        if button:
            data_game = cls._get_str_attr(button, "data-game")
            if data_game:
                return data_game
            raise fpx_err.FpxParseError("Атрибут data-game не найден внутри кнопки поднятия")
        raise fpx_err.FpxNullDataError(
            "На странице лотов не найдена кнопка для поднятия.Возможно у вас нет созданных лотов в этой категории"
        )

    @classmethod
    def parse_current_lot_menu(cls, html_content: str) -> dict[str, Any]:
        """https://funpay.com/lots/offer?id=..."""
        result: dict[str, Any] = {}
        soup = BeautifulSoup(html_content, "html.parser")
        param_items: list[Tag] = soup.find_all("div", class_="param-item")
        if not param_items:
            param_items = [parent for h5 in soup.find_all("h5") if (parent := h5.find_parent("div")) is not None]
        if not param_items:
            raise fpx_err.FpxNullDataError(
                "Страница лота не найдена. Возможно, указана инвалидная ссылка или лот был удалён."
            )
        descriptions: dict[str, str] = {}
        for item in param_items:
            try:
                header_tag = item.find(["h5", "h4", "label"])
                content_tag = item.find("div") or item.find("textarea")
                if header_tag and content_tag:
                    header = header_tag.get_text(strip=True)
                    text = content_tag.get_text(separator="\n", strip=True)
                    descriptions[header] = text
            except Exception as e:
                logger.debug(f"При парсинге конкретного объекта произошла ошибка: {e}")
        result["short_desc"] = (
            descriptions.get("Краткое описание")
            or descriptions.get("Short description")
            or descriptions.get("Короткий опис")
        )
        result["description"] = (
            descriptions.get("Подробное описание")
            or descriptions.get("Detailed description")
            or descriptions.get("Докладний опис")
        )
        option = soup.find("option", value="21") or soup.find("option", attrs={"data-content": True})
        if option:
            inner_html = cls._get_str_attr(option, "data-content")
            if inner_html:
                inner_soup = BeautifulSoup(inner_html, "html.parser")
                price_span = inner_soup.find("span", class_="payment-value")
                raw_price = price_span.get_text(strip=True) if price_span else inner_soup.get_text(strip=True)
                raw_price = raw_price.replace(",", ".")
                cleaned_price = "".join(c for c in raw_price if c.isdigit() or c == ".")
                try:
                    result["price"] = float(cleaned_price) if cleaned_price else 0.0
                except ValueError:
                    result["price"] = 0.0
                return result
        raise fpx_err.FpxNullDataError("Не удалось найти цену в скрытых атрибутах выбора оплаты.")

    @classmethod
    def parse_edit_lot_page(cls, html_content: str) -> dict[str, Any]:
        """https://funpay.com/lots/offerEdit?node=...&offer=..."""
        soup = BeautifulSoup(html_content, "html.parser")
        hidden_inputs = soup.find_all("input", type="hidden")
        if not hidden_inputs:
            raise fpx_err.FpxNullDataError("Не найдено вводных данных в редакторе лота. Возможно слетела сессия")
        result: dict[str, Any] = {
            name: cls._get_str_attr(tag, "value") for tag in hidden_inputs if (name := cls._get_str_attr(tag, "name"))
        }
        selects = soup.find_all("select")
        if not selects:
            raise fpx_err.FpxNullDataError(
                "Ни одна выборка в редакторе лотов не найдена. Проверьте актуальность сессии"
            )
        for s in selects:
            try:
                name = cls._get_str_attr(s, "name")
                if not name:
                    continue
                selected_option = s.find("option", selected=True)
                if selected_option:
                    result[name] = cls._get_str_attr(selected_option, "value")
                else:
                    first_opt = s.find("option")
                    result[name] = cls._get_str_attr(first_opt, "value") if first_opt else ""
            except Exception as e:
                logger.debug(f"При парсинге конкретной выборки произошла ошибка: {e}")
        inputs: list[Tag] = soup.find_all("input", class_="form-control")
        if not inputs:
            inputs = [
                i
                for i in soup.find_all("input")
                if cls._get_str_attr(i, "name")
                and i.get("type") in ["text", "number", None]
                and i.get("type") != "hidden"
            ]
        if not inputs:
            logger.debug("Ни одно поле для ввода в редакторе лотов не найдено. Возможно всё в порядке")
        else:
            for i in inputs:
                try:
                    name = cls._get_str_attr(i, "name")
                    if name:
                        result[name] = cls._get_str_attr(i, "value")
                except Exception as e:
                    logger.debug(f"При парсинге конкретного поля для ввода произошла ошибка: {e}")
        textareas = soup.find_all("textarea")
        if not textareas:
            logger.debug("При парсинге редактора лотов не найдено ни одного текстового поля. Возможно всё в порядке")
        else:
            for t in textareas:
                try:
                    name = cls._get_str_attr(t, "name")
                    if name:
                        result[name] = t.get_text().strip()
                except Exception as e:
                    logger.debug(f"При парсинге конкретного текстового поля произошла ошибка: {e}")
        # Чекбоксы («Активное», «Автовыдача», «Деактивировать после продажи»)
        form = soup.select_one("form.form-offer-editor") or soup
        for checkbox in form.find_all("input", attrs={"type": "checkbox"}):
            name = cls._get_str_attr(checkbox, "name")
            if name and checkbox.has_attr("checked"):
                result[name] = cls._get_str_attr(checkbox, "value") or "on"
        return result

    @classmethod
    def parse_create_lot_page(cls, html_content: str) -> dict[str, Any]:
        """https://funpay.com/lots/offerEdit?node=..."""
        soup = BeautifulSoup(html_content, "html.parser")
        hidden_inputs = soup.find_all("input", type="hidden")
        if not hidden_inputs:
            raise fpx_err.FpxNullDataError("Не найдено вводных данных в редакторе лота. Возможно слетела сессия")
        result: dict[str, Any] = {
            name: cls._get_str_attr(tag, "value") for tag in hidden_inputs if (name := cls._get_str_attr(tag, "name"))
        }
        selects = soup.find_all("select")
        if not selects:
            raise fpx_err.FpxNullDataError(
                "Ни одна выборка в редакторе лотов не найдена. Проверьте актуальность сессии"
            )
        for s in selects:
            try:
                name = cls._get_str_attr(s, "name")
                options = s.find_all("option")
                value_list: list[dict[str, str]] = []
                for option in options:
                    value_name = option.get_text(strip=True)
                    value = cls._get_str_attr(option, "value")
                    if value_name and value:
                        value_list.append({value_name: value})
                result[name] = value_list
            except Exception as e:
                logger.debug(f"При парсинге конкретной выборки произошла ошибка: {e}")
        inputs: list[Tag] = soup.find_all("input", class_="form-control")
        if not inputs:
            inputs = [
                i
                for i in soup.find_all("input")
                if cls._get_str_attr(i, "name")
                and i.get("type") in ["text", "number", None]
                and i.get("type") != "hidden"
            ]
        if not inputs:
            logger.debug("Ни одно поле для ввода в редакторе лотов не найдено. Возможно всё в порядке")
        else:
            for i in inputs:
                try:
                    name = cls._get_str_attr(i, "name")
                    if name:
                        result[name] = cls._get_str_attr(i, "value")
                except Exception as e:
                    logger.debug(f"При парсинге конкретного поля для ввода произошла ошибка: {e}")
        textareas = soup.find_all("textarea")
        if not textareas:
            logger.debug("При парсинге редактора лотов не найдено ни одного текстового поля. Возможно всё в порядке")
        else:
            for t in textareas:
                try:
                    name = cls._get_str_attr(t, "name")
                    if name:
                        result[name] = t.get_text().strip()
                except Exception as e:
                    logger.debug(f"При парсинге конкретного текстового поля произошла ошибка: {e}")
        return result
