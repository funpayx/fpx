"""Тесты LotParser — данные лотов, редактор, поднятие."""

import pytest

from fpx._parsers._lots import LotParser
from fpx.utils import errors as fpx_err


class TestLotParser:
    def test_parse_lot_menu_success(self):
        """Кнопка поднятия с data-game → возвращает ID игры."""
        html = """<button class="js-lot-raise" data-game="42">Поднять</button>"""
        assert LotParser.parse_lot_menu(html) == "42"

    def test_parse_lot_menu_fallback_button(self):
        """Fallback: кнопка без класса, но с data-game."""
        html = """<button data-game="99">Поднять</button>"""
        assert LotParser.parse_lot_menu(html) == "99"

    def test_parse_lot_menu_no_button_raises(self):
        """Нет кнопки → FpxNullDataError."""
        with pytest.raises(fpx_err.FpxNullDataError):
            LotParser.parse_lot_menu("<html><body>Нет кнопки</body></html>")

    def test_parse_current_lot_menu_success(self):
        """Парсинг лота: цена, краткое и подробное описание."""
        html = """
        <html>
          <div class="param-item"><h5>Краткое описание</h5><div>Кратко</div></div>
          <div class="param-item"><h5>Подробное описание</h5><div>Подробно</div></div>
          <option value="21" data-content='<span class="payment-value">100,50</span>'></option>
        </html>
        """
        result = LotParser.parse_current_lot_menu(html)
        assert result["short_desc"] == "Кратко"
        assert result["description"] == "Подробно"
        assert result["price"] == 100.50

    def test_parse_current_lot_menu_no_price_raises(self):
        """Нет опции с ценой → FpxNullDataError."""
        html = """
        <div class="param-item"><h5>Краткое описание</h5><div>Кратко</div></div>
        """
        with pytest.raises(fpx_err.FpxNullDataError):
            LotParser.parse_current_lot_menu(html)

    def test_parse_edit_lot_page_success(self):
        """Парсинг редактора: скрытые поля формы."""
        html = """
        <input type="hidden" name="csrf_token" value="abc123">
        <input type="hidden" name="offer_id" value="999">
        <select><option value="1">Опция</option></select>
        """
        result = LotParser.parse_edit_lot_page(html)
        assert result["csrf_token"] == "abc123"
        assert result["offer_id"] == "999"

    def test_parse_edit_lot_page_reads_checked_checkboxes(self):
        """Отмеченные чекбоксы попадают в поля как "on", снятые не попадают вовсе, как у браузера."""
        html = """
        <form class="form-offer-editor">
          <input type="hidden" name="offer_id" value="42">
          <select name="fields[type]"><option value="1" selected>Робуксы</option></select>
          <input class="form-control" type="text" name="price" value="100">
          <input type="checkbox" name="active" checked>
          <input type="checkbox" name="deactivate_after_sale">
          <input type="checkbox" name="auto_delivery" checked>
        </form>
        """
        result = LotParser.parse_edit_lot_page(html)
        assert result["active"] == "on"
        assert result["auto_delivery"] == "on"
        assert "deactivate_after_sale" not in result
        assert result["price"] == "100"

    @pytest.mark.parametrize("active", [True, False])
    def test_parse_edit_lot_page_real_form_markup(self, active):
        """«Активное» - чекбокс без value: браузер отправляет его как "on",
        а у выключенного лота не отправляет вовсе.
        """
        checked = 'checked=""' if active else ""
        html = f"""
        <form action="https://funpay.com/lots/offerSave" class="form-offer-editor" method="post">
        <input name="csrf_token" type="hidden" value="tok"/>
        <input name="form_created_at" type="hidden" value="1790000000"/>
        <input name="offer_id" type="hidden" value="42"/>
        <input name="node_id" type="hidden" value="1331"/>
        <input name="location" type="hidden" value=""/>
        <input name="deleted" type="hidden" value=""/>
        <div class="form-group lot-field" data-id="quantity"><label class="control-label">Количество робуксов</label>
        <select class="form-control lot-field-input" name="fields[quantity]">
        <option value=""> </option>
        <option value="40 робуксов">40 робуксов</option>
        <option selected="" value="Другое количество">Другое количество</option>
        </select>
        </div>
        <div class="form-group has-feedback w-200px">
        <label class="control-label">Цена за 1 шт.</label>
        <input autocomplete="off" class="form-control" inputmode="decimal" name="price" type="text" value="100"/>
        <span class="form-control-feedback">₽</span>
        </div>
        <div class="form-group">
        <div class="checkbox">
        <label>
        <input {checked} name="active" type="checkbox"/>
        <i></i>
        Активное
        </label>
        </div>
        </div>
        </form>
        """
        result = LotParser.parse_edit_lot_page(html)
        assert result["price"] == "100"
        assert result["fields[quantity]"] == "Другое количество"
        if active:
            assert result["active"] == "on"
        else:
            assert "active" not in result

    def test_parse_edit_lot_page_no_inputs_raises(self):
        """Нет скрытых input → FpxNullDataError."""
        with pytest.raises(fpx_err.FpxNullDataError):
            LotParser.parse_edit_lot_page("<html><body>Пусто</body></html>")

    def test_parse_edit_lot_page_no_selects_raises(self):
        """Есть inputs, но нет select → тоже ошибка."""
        html = """<input type="hidden" name="x" value="y">"""
        with pytest.raises(fpx_err.FpxNullDataError):
            LotParser.parse_edit_lot_page(html)
