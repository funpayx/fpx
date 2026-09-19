from __future__ import annotations

import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from fpx.models.account import Balance
from fpx.utils import errors as fpx_err

from ._base import BaseParser

logger = logging.getLogger("fpx.profile_parser")


class ProfileParser(BaseParser):
    # Кнопки на /security/twoFactorSetting: если 2FA выключена — «включить»,
    # если включена — «отключить». Проверяем ru/en/uk локали FunPay.
    _2FA_ENABLE_MARKERS = (
        "включить 2fa",
        "enable 2fa",
        "увімкнути 2fa",
    )
    _2FA_DISABLE_MARKERS = (
        "отключить 2fa",
        "disable 2fa",
        "вимкнути 2fa",
    )

    @classmethod
    def parse_2fa_status(cls, html_content: str) -> bool:
        """Парсит https://funpay.com/security/twoFactorSetting"""
        if not html_content or not str(html_content).strip():
            raise fpx_err.FpxNullDataError("Страница настроек 2FA пустая")
        text = html_content.lower()
        has_disable = any(marker in text for marker in cls._2FA_DISABLE_MARKERS)
        has_enable = any(marker in text for marker in cls._2FA_ENABLE_MARKERS)
        if has_disable and not has_enable:
            return True
        if has_enable and not has_disable:
            return False
        raise fpx_err.FpxParseError(
            "Не удалось определить статус 2FA: на странице нет однозначных маркеров включения или отключения."
        )

    @classmethod
    def parse_finanses(cls, html_content: str) -> Balance:
        """Парсит https://funpay.com/account/balance"""
        soup = BeautifulSoup(html_content, "html.parser")
        balances_container = soup.find("span", class_="balances-list")
        if not balances_container:
            raise fpx_err.FpxNullDataError("На странице финансов не найдено модуля баланса")
        values = balances_container.find_all("span", class_="balances-value")
        if not values:
            raise fpx_err.FpxNullDataError("На странице финансов не найдено баланса")
        clean_values = [cls.clean_text(v) for v in values]
        data: dict[str, float] = {}
        for i in clean_values:
            try:
                value = i.replace("₽", "").replace("$", "").replace("€", "").replace(",", ".").strip()
                num = float(value)
                if "₽" in i:
                    data["rub"] = num
                elif "$" in i:
                    data["usd"] = num
                elif "€" in i:
                    data["eur"] = num
            except Exception as e:
                logger.debug(f"Ошибка парсинга отдельной валюты: {e}. Пропускаем")
                continue
        if not data:
            raise fpx_err.FpxParseError(
                "Не удалось распарсить ни одну валюту, верстка полностью изменилась или что-то сломалось."
            )
        return Balance(**data)

    @classmethod
    def parse_profile(cls, html_content: str) -> dict[str, Any]:
        """Парсит https://funpay.com/users/.../"""
        soup = BeautifulSoup(html_content, "html.parser")
        offer_list = soup.find_all("div", class_="offer") or soup.find_all("div", attrs={"data-id": True})
        review_list = soup.find_all("div", class_="review-compiled-review") or soup.find_all(
            "div", class_="review-item"
        )
        if not offer_list or not review_list:
            logger.debug(
                "На странице профиля не найден блок категорий или блок отзывов."
                "Возможно ошибка или их просто не существует"
            )
        category_ids: set[str] = set()
        lots: list[dict[str, str]] = []
        for offer in offer_list:
            links = offer.find_all("a", href=True)
            if not links:
                logger.debug("В блоке категории не найдено лотов. Возможно ошибка/Их просто не существует")
            for link in links:
                try:
                    href = str(link["href"])
                    if "/lots/" in href and "id=" not in href:
                        cat_id = href.strip("/").split("/")[-1]
                        if cat_id.isdigit():
                            category_ids.add(cat_id)
                    if "id=" in href:
                        lot_id = href.split("id=")[-1].split("&")[0]
                        name_tag = link.find("div", class_="tc-desc-text")
                        name = name_tag.get_text(strip=True) if name_tag else "Unknown"
                        lots.append({"name": name, "id": lot_id})
                except Exception as e:
                    logger.debug(f"Ошибка парсинга отдельной категории: {e}")
                    continue
        if not lots:
            logger.debug("Не удалось распарсить ни один лот. Возможно изменилась вёрстка/у вас просто нет лотов.")
        reviews: list[dict[str, Any]] = []
        for review in review_list:
            try:
                rev: dict[str, Any] = {}
                text_tag = review.find("div", class_="review-item-text") or review.find("div")
                rev["text"] = cls.clean_text(text_tag)
                rate_div = review.find("div", class_="rating")
                if rate_div:
                    inner_div = rate_div.find("div", class_=True)
                    if inner_div:
                        classes_str = cls._get_str_attr(inner_div, "class")
                        match = re.search(r"\d+", classes_str)
                        rev["stars"] = int(match.group()) if match else 0
                    else:
                        rev["stars"] = 0
                else:
                    rev["stars"] = 0
                author_tag = review.find("div", class_="media-user-name") or review.find("span", class_="pseudo-a")
                rev["author"] = cls.clean_text(author_tag) if author_tag else "Unknown"
                detail_tag = review.find("div", class_="review-item-detail")
                rev["detail"] = cls.clean_text(detail_tag)
                order_div = review.find("div", class_="review-item-order")
                if order_div:
                    a_tag = order_div.find("a", href=True)
                    rev["order_id"] = cls._get_str_attr(a_tag, "href").strip("/").split("/")[-1] if a_tag else ""
                else:
                    rev["order_id"] = ""
                reviews.append(rev)
            except Exception as e:
                logger.debug(f"При парсинге конкретного отзыва возникла ошибка: {e}")
                continue
        if not reviews:
            logger.debug("Не удалось распарсить ни один отзыв, возможно их просто нет/возникла какая-то ошибка")
        return {"category-ids": list(category_ids), "lots": lots, "reviews": reviews}

    @classmethod
    def parse_my_sells(cls, html_content: str) -> dict[str, Any]:
        """Парсит https://funpay.com/orders/trade"""
        result: dict[str, Any] = {}
        result["sells"] = []
        soup = BeautifulSoup(html_content, "html.parser")
        tc_items = soup.find_all("a", class_="tc-item")
        if not tc_items:
            tc_items = soup.find_all("a", href=lambda h: h and "/orders/" in h)
        if not tc_items:
            raise fpx_err.FpxNullDataError("На странице продаж не найдено объектов(tc-item)")
        for item in tc_items:
            try:
                pre_result: dict[str, Any] = {}
                order_tag = item.find("div", class_="tc-order") or item.find("div", class_=lambda c: c and "order" in c)
                pre_result["order-id"] = order_tag.get_text(strip=True).replace("#", "") if order_tag else "Unknown"
                time_tag = item.find("div", class_="tc-date-time")
                pre_result["order-time"] = time_tag.get_text(strip=True) if time_tag else ""
                status_tag = item.find("div", class_="tc-status")
                pre_result["status"] = status_tag.get_text(strip=True) if status_tag else "Unknown"
                client_tag = (
                    item.find("span", class_="pseudo-a")
                    or item.find("div", class_="tc-user")
                    or item.find("div", class_=lambda c: c and "user" in c)
                )
                pre_result["client-name"] = client_tag.get_text(strip=True) if client_tag else "Unknown"
                price_tag = item.find("div", class_="tc-price")
                if price_tag:
                    raw_price = price_tag.get_text(strip=True).replace(",", ".")
                    cleaned_price = "".join(c for c in raw_price if c.isdigit() or c == ".")
                    pre_result["price"] = float(cleaned_price) if cleaned_price else 0.0
                else:
                    pre_result["price"] = 0.0
                order_desc = item.find("div", class_="order-desc")
                if order_desc:
                    divs: list[Any] = order_desc.find_all(["div", "span", "p"], recursive=False)
                    if not divs:
                        divs = [order_desc]
                    raw_name = divs[0].get_text(strip=True) if len(divs) > 0 else "Unknown"
                    pre_result["name"] = raw_name
                    pre_result["category"] = divs[1].get_text(strip=True) if len(divs) > 1 else "Unknown"
                    match = re.search(r"(\d+)\s*(?:шт\.?|pcs\.?)\s*,\s*(.+)$", raw_name, re.IGNORECASE)
                    if match:
                        try:
                            pre_result["amount"] = int(match.group(1))
                        except ValueError:
                            pre_result["amount"] = 1
                        extracted_data = match.group(2).strip()
                        pre_result["topup_data"] = extracted_data if extracted_data else None
                    else:
                        pre_result["topup_data"] = None
                        amount_match = re.search(r"(\d+)\s*(?:шт\.?|pcs\.?)", raw_name, re.IGNORECASE)
                        pre_result["amount"] = int(amount_match.group(1)) if amount_match else 1
                else:
                    pre_result["name"] = "Unknown"
                    pre_result["category"] = "Unknown"
                    pre_result["amount"] = 1
                    pre_result["topup_data"] = None
                result["sells"].append(pre_result)
            except Exception as e:
                logger.debug(f"При парсинге конкретного объекта произошла ошибка: {e}")
                continue
        if not result["sells"]:
            raise fpx_err.FpxParseError("При парсинге не найдено ни одной продажи")
        form_class = soup.find("form", class_="dyn-table-form")
        if form_class:
            input_tag = form_class.find("input")
            result["next_page"] = cls._get_str_attr(input_tag, "value") if input_tag else None
        return result

    @classmethod
    def parse_main_menu(cls, html_content: str) -> dict[str, Any]:
        """Парсит funpay.com"""
        soup = BeautifulSoup(html_content, "html.parser")
        user_link = soup.find("a", class_="user-link-dropdown")
        if not user_link:
            user_link = soup.find("a", href=lambda h: h and "/users/" in h)
        result: dict[str, Any] = {}
        if user_link:
            href = cls._get_str_attr(user_link, "href")
            user_id = href.strip("/").split("/")[-1] if href else None
            if user_id and user_id.isdigit():
                result["user-id"] = user_id
                name_tag = soup.find("div", class_="user-link-name") or user_link.find("div") or user_link
                result["username"] = cls.clean_text(name_tag) if name_tag else "Unknown"
            else:
                raise fpx_err.FpxParseError(
                    "Не удалось извлечь цифровой ID юзера, возможно слетела сессия или изменилась вёрстка"
                )
        else:
            raise fpx_err.FpxNullDataError("На главной странице не найдено информации о юзере. Возможно слетела сессия")
        body = soup.find("body")
        if not body:
            raise fpx_err.FpxNullDataError("Тело главной страницы (body) не найдено")
        try:
            app_data_str = cls._get_str_attr(body, "data-app-data", "{}")
            app_data = json.loads(app_data_str)
            result["csrf-token"] = app_data.get("csrf-token", "")
        except Exception as e:
            raise fpx_err.FpxParseError("Не удалось распарсить csrf_token из data-app-data.") from e
        return result
