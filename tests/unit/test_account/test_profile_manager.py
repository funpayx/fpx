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
    acc._client.get_blocked_page = AsyncMock()
    acc._client.get_2fa_settings_page = AsyncMock()
    acc._client.get_tg_conn_link = AsyncMock()
    acc._client.update_notice_channel = AsyncMock()
    acc._parser.parse_main_menu = MagicMock()
    acc._parser.parse_my_sells = MagicMock()
    acc._parser.parse_profile = MagicMock()
    acc._parser.parse_finanses = MagicMock()
    acc._parser.parse_2fa_status = MagicMock()
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


class TestCheckBanned:
    @pytest.mark.asyncio
    async def test_banned_when_blocked_page_returns_200(self, manager, account):
        response = MagicMock()
        response.status_code = 200
        account._client.get_blocked_page.return_value = response
        assert await manager.check_banned() is True
        account._client.get_blocked_page.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_banned_when_blocked_page_returns_404(self, manager, account):
        response = MagicMock()
        response.status_code = 404
        account._client.get_blocked_page.return_value = response
        assert await manager.check_banned() is False

    @pytest.mark.asyncio
    async def test_auth_error_reraised(self, manager, account):
        account._client.get_blocked_page.side_effect = fpx_err.FpxAuthError("Неверный gkey")
        with pytest.raises(fpx_err.FpxAuthError):
            await manager.check_banned()

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_blocked_page.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetProfileError):
            await manager.check_banned()


class TestGet2FAStatus:
    @pytest.mark.asyncio
    async def test_success_enabled(self, manager, account):
        html = '<input type="hidden" name="isEnabled" value="1">'
        account._client.get_2fa_settings_page.return_value = html
        account._parser.parse_2fa_status.return_value = True
        result = await manager.get_2fa_status()
        assert result is True
        account._client.get_2fa_settings_page.assert_awaited_once()
        account._parser.parse_2fa_status.assert_called_once_with(html)

    @pytest.mark.asyncio
    async def test_success_disabled(self, manager, account):
        html = '<input type="hidden" name="isEnabled" value="">'
        account._client.get_2fa_settings_page.return_value = html
        account._parser.parse_2fa_status.return_value = False
        result = await manager.get_2fa_status()
        assert result is False

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_2fa_settings_page.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetProfileError):
            await manager.get_2fa_status()

    @pytest.mark.asyncio
    async def test_auth_error_reraised(self, manager, account):
        account._client.get_2fa_settings_page.side_effect = fpx_err.FpxAuthError("bad cookies")
        with pytest.raises(fpx_err.FpxAuthError):
            await manager.get_2fa_status()


class TestGetTelegramConnectUrl:
    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        account._client.get_tg_conn_link.return_value = "https://t.me/funpaysmartbot?start=123"
        result = await manager.get_telegram_connect_url()
        assert result == "https://t.me/funpaysmartbot?start=123"
        account._client.get_tg_conn_link.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_tg_conn_link.side_effect = Exception("network error")
        with pytest.raises(fpx_err.FpxGetProfileError):
            await manager.get_telegram_connect_url()


class TestUpdateNoticeChannel:
    @pytest.mark.asyncio
    async def test_single_channel_by_str(self, manager, account):
        account._client.update_notice_channel.return_value = True
        result = await manager.update_notice_channel("telegram", True)
        assert result is True
        account._client.update_notice_channel.assert_awaited_once_with(3, True)

    @pytest.mark.asyncio
    async def test_list_of_channels(self, manager, account):
        account._client.update_notice_channel.return_value = True
        result = await manager.update_notice_channel(["email", 2], False)
        assert result == [True, True]
        assert account._client.update_notice_channel.await_count == 2

    @pytest.mark.asyncio
    async def test_invalid_channel_raises(self, manager, account):
        with pytest.raises(fpx_err.FpxAttributeError):
            await manager.update_notice_channel("unknown_channel", True)

    @pytest.mark.asyncio
    async def test_client_error_wrapped(self, manager, account):
        account._client.update_notice_channel.side_effect = Exception("api error")
        with pytest.raises(fpx_err.FpxPostProfileError):
            await manager.update_notice_channel("push", True)
