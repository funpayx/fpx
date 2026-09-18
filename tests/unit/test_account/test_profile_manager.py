"""Тесты ProfileManager — данные юзера, продажи, профиль, баланс."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fpx.classes.account.subclasses.profile import ProfileManager
from fpx.models.account import Balance, Order, Profile, UserData
from fpx.utils import errors as fpx_err


@pytest.fixture
def account():
    acc = MagicMock()
    acc.data.username = None
    acc.data.user_id = None
    acc.data._csrf_token = None
    acc._client.get_main_menu = AsyncMock()
    acc._client.get_my_sells = AsyncMock()
    acc._client.get_next_sells = AsyncMock()
    acc._client.get_user_profile = AsyncMock()
    acc._client.get_finance_page = AsyncMock()
    acc._client.get_telegram_connect_page = AsyncMock()
    acc._client.update_notice_channel = AsyncMock()
    acc._parser.parse_main_menu = MagicMock()
    acc._parser.parse_my_sells = MagicMock()
    acc._parser.parse_profile = MagicMock()
    acc._parser.parse_finanses = MagicMock()
    acc._parser.parse_telegram_connect_url = MagicMock()
    return acc


@pytest.fixture
def manager(account):
    return ProfileManager(account)


class TestGetUserData:
    @pytest.mark.asyncio
    async def test_success_updates_cache(self, manager, account):
        account._client.get_main_menu.return_value = "<html></html>"
        account._parser.parse_main_menu.return_value = {"username": "Bob", "user-id": "1", "csrf-token": "tok"}
        result = await manager.get_user_data()
        assert isinstance(result, UserData)
        assert account.data.username == "Bob"
        assert account.data.user_id == "1"
        assert account.data._csrf_token == "tok"

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_main_menu.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetUserDataError):
            await manager.get_user_data()


class TestGetMySells:
    @pytest.mark.asyncio
    async def test_single_page_without_next_page_marker_returns_empty(self, manager, account):
        """
        Документирует текущее поведение реализации: цикл добавляет 'sells' страницы
        в результат ТОЛЬКО если у этой же страницы найден 'next_page' (иначе брейк
        происходит раньше append). Так что единственная страница без next_page
        не попадёт в результат вообще.
        """
        account._client.get_my_sells.return_value = "<html></html>"
        account._parser.parse_my_sells.return_value = {
            "sells": [
                {
                    "order-id": "1",
                    "order-time": "10:00",
                    "client-name": "Bob",
                    "price": 10.0,
                    "status": "Оплачен",
                    "name": "Товар",
                    "category": "Cat",
                    "amount": 1,
                    "topup_data": None,
                }
            ]
        }
        result = await manager.get_my_sells()
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_pages_last_page_data_is_dropped(self, manager, account, monkeypatch):
        """
        Аналогично: при пагинации данные последней (без next_page) страницы
        не добавляются в результат — только страницы, у которых был next_page.
        """
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        account._client.get_my_sells.return_value = "<html></html>"
        page1 = {
            "sells": [
                {
                    "order-id": "1",
                    "order-time": "t",
                    "client-name": "Bob",
                    "price": 1.0,
                    "status": "s",
                    "name": "A",
                    "category": "c",
                    "amount": 1,
                    "topup_data": None,
                }
            ],
            "next_page": "page-2",
        }
        page2 = {
            "sells": [
                {
                    "order-id": "2",
                    "order-time": "t",
                    "client-name": "Bob",
                    "price": 2.0,
                    "status": "s",
                    "name": "B",
                    "category": "c",
                    "amount": 1,
                    "topup_data": None,
                }
            ]
        }
        account._parser.parse_my_sells.side_effect = [page1, page2]
        result = await manager.get_my_sells()
        assert len(result) == 1
        assert result[0].order_id == "1"
        assert isinstance(result[0], Order)

    @pytest.mark.asyncio
    async def test_limit_stops_pagination(self, manager, account, monkeypatch):
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        account._client.get_my_sells.return_value = "<html></html>"
        sells = [
            {
                "order-id": str(i),
                "order-time": "t",
                "client-name": "Bob",
                "price": 1.0,
                "status": "s",
                "name": "A",
                "category": "c",
                "amount": 1,
                "topup_data": None,
            }
            for i in range(5)
        ]
        account._parser.parse_my_sells.return_value = {"sells": sells, "next_page": "p2"}
        result = await manager.get_my_sells(limit=3)
        # финальный проход по data режет список согласно счётчику limit (см. реализацию)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_my_sells.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetUserSellsError):
            await manager.get_my_sells()


class TestProfile:
    @pytest.mark.asyncio
    async def test_success_with_explicit_user_id(self, manager, account):
        account._client.get_user_profile.return_value = "<html></html>"
        account._parser.parse_profile.return_value = {
            "category-ids": ["1"],
            "lots": [{"name": "Lot1", "id": "10"}],
            "reviews": [{"text": "OK", "stars": 5, "author": "A", "order_id": "1"}],
        }
        result = await manager.profile(user_id="42")
        assert isinstance(result, Profile)
        assert result.category_ids == ["1"]
        assert result.lots[0].name == "Lot1"
        assert result.reviews[0].stars == 5

    @pytest.mark.asyncio
    async def test_fetches_own_user_id_when_missing(self, manager, account):
        account.data.user_id = None
        manager.get_user_data = AsyncMock(return_value=UserData(csrf_token="tok", user_id="99"))
        account._client.get_user_profile.return_value = "<html></html>"
        account._parser.parse_profile.return_value = {"category-ids": [], "lots": [], "reviews": []}
        await manager.profile()
        manager.get_user_data.assert_awaited_once()
        account._client.get_user_profile.assert_awaited_once_with("99")

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account.data.user_id = "1"
        account._client.get_user_profile.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetProfileError):
            await manager.profile()


class TestGetBalance:
    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        account._client.get_finance_page.return_value = "<html></html>"
        account._parser.parse_finanses.return_value = Balance(rub=100.0, usd=1.0, eur=0.5)
        result = await manager.get_balance()
        assert isinstance(result, Balance)
        assert result.rub == 100.0

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_finance_page.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetProfileError):
            await manager.get_balance()


class TestGetTelegramConnectUrl:
    @pytest.mark.asyncio
    async def test_uses_redirect_url(self, manager, account):
        response = MagicMock()
        response.url = "https://t.me/funpaysmartbot?start=abc"
        response.headers = {}
        response.text = ""
        account._client.get_telegram_connect_page.return_value = response
        result = await manager.get_telegram_connect_url()
        assert result == "https://t.me/funpaysmartbot?start=abc"
        account._client.get_telegram_connect_page.assert_awaited_once()
        account._parser.parse_telegram_connect_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_location_header(self, manager, account):
        response = MagicMock()
        response.url = "https://funpay.com/account/linkTelegram"
        response.headers = {"Location": "https://t.me/funpaysmartbot?start=from-header"}
        response.text = ""
        account._client.get_telegram_connect_page.return_value = response
        result = await manager.get_telegram_connect_url()
        assert result == "https://t.me/funpaysmartbot?start=from-header"
        account._parser.parse_telegram_connect_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_parses_html_when_no_telegram_redirect(self, manager, account):
        response = MagicMock()
        response.url = "https://funpay.com/account/linkTelegram"
        response.headers = {}
        response.text = '<a href="https://t.me/funpaysmartbot?start=html">Telegram</a>'
        account._client.get_telegram_connect_page.return_value = response
        account._parser.parse_telegram_connect_url.return_value = "https://t.me/funpaysmartbot?start=html"
        result = await manager.get_telegram_connect_url()
        assert result == "https://t.me/funpaysmartbot?start=html"
        account._parser.parse_telegram_connect_url.assert_called_once_with(response.text)

    @pytest.mark.asyncio
    async def test_falls_back_to_response_url(self, manager, account):
        response = MagicMock()
        response.url = "https://funpay.com/account/settings"
        response.headers = {}
        response.text = "<html></html>"
        account._client.get_telegram_connect_page.return_value = response
        account._parser.parse_telegram_connect_url.side_effect = fpx_err.FpxParseError("no link")
        result = await manager.get_telegram_connect_url()
        assert result == "https://funpay.com/account/settings"

    @pytest.mark.asyncio
    async def test_auth_error_reraised(self, manager, account):
        account._client.get_telegram_connect_page.side_effect = fpx_err.FpxAuthError("bad cookies")
        with pytest.raises(fpx_err.FpxAuthError):
            await manager.get_telegram_connect_url()

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_telegram_connect_page.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetProfileError):
            await manager.get_telegram_connect_url()

    @pytest.mark.asyncio
    async def test_empty_response_wrapped(self, manager, account):
        response = MagicMock()
        response.url = ""
        response.headers = {}
        response.text = ""
        account._client.get_telegram_connect_page.return_value = response
        account._parser.parse_telegram_connect_url.side_effect = fpx_err.FpxNullDataError("empty")
        with pytest.raises(fpx_err.FpxGetProfileError):
            await manager.get_telegram_connect_url()


class TestUpdateNoticeChannel:
    @pytest.mark.asyncio
    async def test_enable_telegram_by_name(self, manager, account):
        response = MagicMock()
        response.status_code = 200
        account._client.update_notice_channel.return_value = response
        result = await manager.update_notice_channel("telegram", True)
        assert result is True
        account._client.update_notice_channel.assert_awaited_once_with(3, True)

    @pytest.mark.asyncio
    async def test_disable_email_by_id(self, manager, account):
        response = MagicMock()
        response.status_code = 200
        account._client.update_notice_channel.return_value = response
        result = await manager.update_notice_channel(1, False)
        assert result is True
        account._client.update_notice_channel.assert_awaited_once_with(1, False)

    @pytest.mark.asyncio
    async def test_accepts_string_channel_id(self, manager, account):
        response = MagicMock()
        response.status_code = 200
        account._client.update_notice_channel.return_value = response
        result = await manager.update_notice_channel("2", True)
        assert result is True
        account._client.update_notice_channel.assert_awaited_once_with(2, True)

    @pytest.mark.asyncio
    async def test_invalid_channel_raises_before_request(self, manager, account):
        with pytest.raises(fpx_err.FpxValidateError):
            await manager.update_notice_channel("sms", True)
        with pytest.raises(fpx_err.FpxValidateError):
            await manager.update_notice_channel(9, True)
        account._client.update_notice_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_bool_channel_is_rejected(self, manager, account):
        with pytest.raises(fpx_err.FpxValidateError):
            await manager.update_notice_channel(True, True)
        account._client.update_notice_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_200_response_raises(self, manager, account):
        response = MagicMock()
        response.status_code = 500
        account._client.update_notice_channel.return_value = response
        with pytest.raises(fpx_err.FpxGetProfileError):
            await manager.update_notice_channel("push", False)

    @pytest.mark.asyncio
    async def test_auth_error_reraised(self, manager, account):
        account._client.update_notice_channel.side_effect = fpx_err.FpxAuthError("Неверный gkey")
        with pytest.raises(fpx_err.FpxAuthError):
            await manager.update_notice_channel("telegram", True)

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.update_notice_channel.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetProfileError):
            await manager.update_notice_channel(3, False)
