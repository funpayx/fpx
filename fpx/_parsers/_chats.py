from __future__ import annotations

import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from fpx.models.chat import Chat
from fpx.utils import errors as fpx_err

from ._base import BaseParser

logger = logging.getLogger("fpx.chat_parser")


class ChatParser(BaseParser):
    @classmethod
    def _parse_contact_item(cls, item: Tag) -> Chat:
        """Парсит элемент списка чатов (a.contact-item)."""
        href = cls._get_str_attr(item, "href")
        node_msg_id = int(cls._get_str_attr(item, "data-node-msg", "0"))
        chat_id = href.split("node=")[-1] if "node=" in href else ""
        username = cls.clean_text(item.find("div", class_="media-user-name"))
        last_msg = cls.clean_text(item.find("div", class_="contact-item-message"))
        date = cls.clean_text(item.find("div", class_="contact-item-time"))
        is_unread = "unread" in cls._get_class_list(item)
        return Chat(
            id=chat_id,
            node_msg_id=node_msg_id,
            username=username,
            last_msg=last_msg,
            date=date,
            link=href,
            is_unread=is_unread,
        )

    @classmethod
    def _message_text(cls, item: Tag) -> str:
        """Текст сообщения чата, у картинки без подписи - ссылка на неё."""
        msg_tag = item.find("div", class_="chat-msg-text")
        if not msg_tag:
            return ""
        message = msg_tag.get_text(separator="\n").strip()
        if not message:
            img_link = msg_tag.find("a", class_="chat-img-link")
            message = cls._get_str_attr(img_link, "href") if img_link else ""
        return message

    @classmethod
    def parse_chats_list(cls, html_content: str) -> list[Chat]:
        """Парсит страницу https://funpay.com/chat/"""
        soup = BeautifulSoup(html_content, "html.parser")
        items: list[Tag] = soup.find_all("a", class_="contact-item")
        if not items:
            items = cls._safe_parse_links(html_content, r"node=\d+")
        if not items:
            raise fpx_err.FpxNullDataError("На странице не найдено ни одного чата")
        chats: list[Chat] = []
        for item in items:
            try:
                chats.append(cls._parse_contact_item(item))
            except Exception as e:
                logger.debug(f"Ошибка парсинга отдельного чата: {e}. Пропускаем элемент.")
                continue
        if not chats:
            raise fpx_err.FpxParseError(
                "Не удалось распарсить ни один чат, верстка полностью изменилась, или что-то сломалось."
            )
        return chats

    @classmethod
    def parse_chat_bookmarks(cls, html_content: str) -> list[Chat]:
        """
        Парсит список чатов из объекта chat_bookmarks ответа /runner/.

        Разметка та же, что на https://funpay.com/chat/, но пустой список здесь
        не ошибка: у аккаунта может ещё не быть чатов.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        chats: list[Chat] = []
        for item in soup.find_all("a", class_="contact-item"):
            try:
                chat = cls._parse_contact_item(item)
            except Exception as e:
                logger.debug(f"Ошибка парсинга отдельного чата: {e}. Пропускаем элемент.")
                continue
            if chat.id:
                chats.append(chat)
        return chats

    @classmethod
    def parse_runner_messages(cls, messages: list[dict[str, Any]], names: dict[int, str]) -> list[dict[str, Any]]:
        """
        Парсит сообщения объекта chat_node ответа /runner/.

        FunPay отдаёт у сообщения ID, ID автора и HTML в разметке страницы чата.
        Автор 0 - оповещение FunPay. Ник автора в HTML есть только у первого
        сообщения серии, поэтому известные ники передаются в names ({ID автора: ник}).
        """
        names = dict(names)
        result: list[dict[str, Any]] = []
        for raw in messages:
            try:
                node_id = int(raw["id"])
                author_id = int(raw.get("author") or 0)
                item = BeautifulSoup(raw.get("html") or "", "html.parser")
                author_link = item.find("a", class_="chat-msg-author-link")
                if author_id and author_link:
                    names[author_id] = author_link.get_text(strip=True)
                result.append(
                    {
                        "node_id": node_id,
                        "author_id": author_id,
                        "sender": "FunPay" if author_id == 0 else names.get(author_id, "Unknown"),
                        "message": cls._message_text(item),
                        "is_system": author_id == 0,
                    }
                )
            except Exception as e:
                logger.debug(f"Не удалось распарсить сообщение из chat_node: {e}")
        return result

    @classmethod
    def parse_chat(cls, html_content: str) -> dict[str, Any]:
        """Парсит страницу https://funpay.com/chat/?node=..."""
        soup = BeautifulSoup(html_content, "html.parser")
        result: dict[str, Any] = {}
        chat_div = soup.find("div", class_="chat")
        if not chat_div:
            chat_div = soup.find("div", attrs={"data-id": re.compile(r"^\d+$")})
        body = soup.find("body")
        if not chat_div or not body:
            raise fpx_err.FpxNullDataError("На странице чата не найден блок переписки или тег body")
        chats = soup.find_all("div", class_="chat-msg-item")
        result["messages"] = []
        if chats:
            for chat in chats:
                try:
                    res: dict[str, Any] = {
                        "is_system": False,
                        "node_id": cls._get_str_attr(chat, "id").split("-")[-1],
                        "message": cls._message_text(chat),
                    }
                    author_block: Tag | None = None
                    current_node: Tag | None = chat
                    while current_node:
                        author_block = current_node.find("div", class_="media-user-name")
                        if author_block:
                            break
                        current_node = current_node.find_previous_sibling("div", class_="chat-msg-item")
                    if author_block:
                        author = author_block.find("a", class_="chat-msg-author-link")
                        if not author:
                            sender_lbl = author_block.find("span", class_="chat-msg-author-label")
                            res["sender"] = cls.clean_text(sender_lbl) if sender_lbl else "FunPay"
                            if res["sender"] and res["sender"].lower() == "оповещение":
                                res["sender"] = "FunPay"
                                res["is_system"] = True
                        else:
                            res["sender"] = author.get_text(strip=True)
                    else:
                        res["sender"] = "Unknown"
                    result["messages"].append(res)
                except Exception as e:
                    logger.debug(f"Не удалось распарсить N сообщение в чате: {e}")
        else:
            logger.debug("Сообщений не найдено!")
            # парсинг тех.данных
        try:
            result["data-name"] = cls._get_str_attr(chat_div, "data-name")
            result["data-id"] = cls._get_str_attr(chat_div, "data-id")
            app_data_str = cls._get_str_attr(body, "data-app-data", "{}") or "{}"
            app_data = json.loads(app_data_str)
            result["csrf-token"] = app_data.get("csrf-token", "")
            result["user-id"] = app_data.get("userId", "")
        except Exception as e:
            logger.debug(f"Ошибка извлечения системных данных чата: {e}")
            raise fpx_err.FpxParseError("Не удалось распарсить системные метаданные чата (CSRF/User ID)") from e
        return result
