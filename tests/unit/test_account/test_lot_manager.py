"""Тесты LotManager — данные лотов, автовыдача, поднятие, создание."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fpx.classes.account.subclasses.lot import LotManager
from fpx.models.account import Profile
from fpx.models.lots import CurrentLotInfo, LotCreationFields, LotEditor
from fpx.utils import errors as fpx_err


@pytest.fixture
def account():
    acc = MagicMock()
    acc._client.get_lot_editor_data = AsyncMock()
    acc._client.get_lot_info = AsyncMock()
    acc._client.get_node_editor_data = AsyncMock()
    acc._client.create_lot = AsyncMock()
    acc._client.raise_lot = AsyncMock()
    acc._client.set_offers_hidden = AsyncMock()
    acc._parser.parse_edit_lot_page = MagicMock()
    acc._parser.parse_current_lot_menu = MagicMock()
    acc._parser.parse_create_lot_page = MagicMock()
    acc.profile.get_user_data = AsyncMock()
    acc.profile.profile = AsyncMock()
    acc.addons.get_game_id = AsyncMock()
    acc.data._csrf_token = "tok"
    acc.data.user_id = "42"
    return acc


@pytest.fixture
def manager(account):
    return LotManager(account)


class TestGetLotEditorDetails:
    @pytest.mark.asyncio
    async def test_success_splits_base_and_other_fields(self, manager, account):
        account._client.get_lot_editor_data.return_value = "<html></html>"
        account._parser.parse_edit_lot_page.return_value = {
            "csrf_token": "tok",
            "form_created_at": "ts",
            "offer_id": "1",
            "node_id": "2",
            "location": "",
            "deleted": "",
            "price": "100",
            "amount": "5",
        }
        result = await manager._get_lot_editor_details("1")
        assert isinstance(result, LotEditor)
        assert result.csrf_token == "tok"
        assert result.fields == {"price": "100", "amount": "5"}

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_lot_editor_data.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetLotEditorInfoError):
            await manager._get_lot_editor_details("1")


class TestGetLotSecrets:
    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        account._client.get_lot_editor_data.return_value = "<html></html>"
        account._parser.parse_edit_lot_page.return_value = {
            "csrf_token": "t",
            "form_created_at": "ts",
            "offer_id": "1",
            "node_id": "2",
            "location": "",
            "deleted": "",
            "secrets": "a\nb",
        }
        result = await manager.get_lot_secrets("1")
        assert result == ["a", "b"]

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_lot_editor_data.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetLotInfoError):
            await manager.get_lot_secrets("1")


class TestGetLotInfo:
    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        account._client.get_lot_info.return_value = "<html></html>"
        account._parser.parse_current_lot_menu.return_value = {
            "short_desc": "Short",
            "description": "Long",
            "price": "100.5",
        }
        result = await manager.get_lot_info("1")
        assert isinstance(result, CurrentLotInfo)
        assert result.price == 100.5
        assert result._client is account

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_lot_info.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetLotInfoError):
            await manager.get_lot_info("1")


class TestRaiseLots:
    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        account.data._csrf_token = "tok"
        account.profile.profile.return_value = Profile(category_ids=["1", "2"])
        account.addons.get_game_id.side_effect = ["g1", "g2"]
        account._client.raise_lot.side_effect = ["ok1", "ok2"]
        result = await manager.raise_lots()
        assert result == ["ok1", "ok2"]

    @pytest.mark.asyncio
    async def test_fetches_csrf_token_first_if_missing(self, manager, account):
        account.data._csrf_token = None
        account.profile.profile.return_value = Profile(category_ids=[])
        with pytest.raises(fpx_err.FpxRaisingLotError):
            await manager.raise_lots()
        account.profile.get_user_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_categories_raises(self, manager, account):
        account.profile.profile.return_value = Profile(category_ids=[])
        with pytest.raises(fpx_err.FpxRaisingLotError):
            await manager.raise_lots()

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account.profile.profile.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxRaisingLotError):
            await manager.raise_lots()


class TestGetNodeEditorData:
    @pytest.mark.asyncio
    async def test_success_builds_lot_creation_fields(self, manager, account):
        account._client.get_node_editor_data.return_value = "<html></html>"
        account._parser.parse_create_lot_page.return_value = {
            "csrf_token": "tok",
            "form_created_at": "ts",
            "offer_id": "1",
            "node_id": "2",
            "location": "",
            "deleted": "",
            "fields[type]": [{"Аренда": "1"}, {"Продажа": "2"}],
            "price": [],
        }
        result = await manager.get_node_editor_data("2")
        assert isinstance(result, LotCreationFields)
        assert result._csrf_token == "tok"
        type_field = result.get_field("fields[type]")
        # см. исходный код: key берётся из значений словаря, value - из ключей
        assert type_field.options[0].key == "1"
        assert type_field.options[0].value == "Аренда"
        price_field = result.get_field("price")
        assert price_field.options is None

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.get_node_editor_data.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxGetLotEditorInfoError):
            await manager.get_node_editor_data("2")


class TestCreateLot:
    def _valid_fields(self):
        fields = MagicMock(spec=LotCreationFields)
        fields.validate.return_value = True
        return fields

    @pytest.mark.asyncio
    async def test_success(self, manager, account):
        fields = self._valid_fields()
        response = MagicMock()
        response.status_code = 200
        account._client.create_lot.return_value = response
        result = await manager.create_lot(fields)
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_fields_raises(self, manager, account):
        fields = self._valid_fields()
        fields.validate.return_value = False
        with pytest.raises(fpx_err.FpxLotCreateError):
            await manager.create_lot(fields)

    @pytest.mark.asyncio
    async def test_non_200_response_raises(self, manager, account):
        fields = self._valid_fields()
        response = MagicMock()
        response.status_code = 500
        account._client.create_lot.return_value = response
        with pytest.raises(fpx_err.FpxLotCreateError):
            await manager.create_lot(fields)


class TestSetOffersHidden:
    @pytest.mark.asyncio
    async def test_hide_success(self, manager, account):
        response = MagicMock()
        response.status_code = 200
        account._client.set_offers_hidden.return_value = response
        result = await manager.set_offers_hidden(True)
        assert result is True
        account._client.set_offers_hidden.assert_awaited_once_with("42", True)
        account.profile.get_user_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_show_success(self, manager, account):
        response = MagicMock()
        response.status_code = 200
        account._client.set_offers_hidden.return_value = response
        result = await manager.set_offers_hidden(False)
        assert result is True
        account._client.set_offers_hidden.assert_awaited_once_with("42", False)

    @pytest.mark.asyncio
    async def test_fetches_user_id_if_missing(self, manager, account):
        account.data.user_id = None

        async def _fill_user_id():
            account.data.user_id = "99"

        account.profile.get_user_data = AsyncMock(side_effect=_fill_user_id)
        response = MagicMock()
        response.status_code = 200
        account._client.set_offers_hidden.return_value = response
        result = await manager.set_offers_hidden(True)
        assert result is True
        account.profile.get_user_data.assert_awaited_once()
        account._client.set_offers_hidden.assert_awaited_once_with("99", True)

    @pytest.mark.asyncio
    async def test_missing_user_id_after_fetch_raises(self, manager, account):
        account.data.user_id = None
        account.profile.get_user_data = AsyncMock()
        with pytest.raises(fpx_err.FpxLotEditingError):
            await manager.set_offers_hidden(True)
        account._client.set_offers_hidden.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_200_response_raises(self, manager, account):
        response = MagicMock()
        response.status_code = 500
        account._client.set_offers_hidden.return_value = response
        with pytest.raises(fpx_err.FpxLotEditingError):
            await manager.set_offers_hidden(True)

    @pytest.mark.asyncio
    async def test_auth_error_reraised(self, manager, account):
        account._client.set_offers_hidden.side_effect = fpx_err.FpxAuthError("Неверный gkey")
        with pytest.raises(fpx_err.FpxAuthError):
            await manager.set_offers_hidden(True)

    @pytest.mark.asyncio
    async def test_error_wrapped(self, manager, account):
        account._client.set_offers_hidden.side_effect = Exception("boom")
        with pytest.raises(fpx_err.FpxLotEditingError):
            await manager.set_offers_hidden(False)
