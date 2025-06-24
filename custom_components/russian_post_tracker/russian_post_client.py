import logging
from datetime import datetime
from zeep import Client, Settings

_LOGGER = logging.getLogger(__name__)

WSDL_URL = "https://tracking.russianpost.ru/rtm34?wsdl"


class RussianPostTracker:
    def __init__(self, login: str, password: str):
        self.login = login
        self.password = password
        self.client = None

    def connect(self) -> bool:
        """Инициализация SOAP-клиента."""
        if self.client:
            return True
        try:
            settings = Settings(strict=False, xml_huge_tree=True)
            self.client = Client(wsdl=WSDL_URL, settings=settings)
            return True
        except Exception as e:
            _LOGGER.exception("Ошибка подключения к API Почты России: %s", e)
            self.client = None
            return False

    def get_last_operation(self, barcode: str):
        """
        Запрашивает историю по трек-номеру и возвращает словарь с последней операцией
        и полной историей.
        """
        if not self.connect():
            _LOGGER.error("SOAP клиент не инициализирован")
            return None

        try:
            auth_header = {
                "login": self.login,
                "password": self.password,
                "mustUnderstand": "1",
            }
            response = self.client.service.getOperationHistory(
                OperationHistoryRequest={
                    "Barcode": barcode,
                    "MessageType": "0",
                    "Language": "RUS",
                },
                AuthorizationHeader=auth_header,  # <-- передаём прямо
            )

            if not response:
                return None

            # Собираем историю
            history = []
            for rec in response:
                date = self._parse_date(getattr(rec, "OperDate", None))
                op_t = getattr(rec.OperationParameters.OperType, "Name", "")
                op_a = getattr(rec.OperationParameters.OperAttr, "Name", "")
                loc = getattr(
                    rec.AddressParameters.OperationAddress, "Description", ""
                )
                entry = f"{date} — {op_t}" + (f", {op_a}" if op_a else "") + f" ({loc})"
                history.append(entry)

            last = response[-1]
            return {
                "barcode": barcode,
                "status": getattr(last.OperationParameters.OperAttr, "Name", ""),
                "operation_type": getattr(
                    last.OperationParameters.OperType, "Name", ""
                ),
                "location": getattr(
                    last.AddressParameters.OperationAddress, "Description", ""
                ),
                "country_from": getattr(
                    getattr(last.AddressParameters, "CountryFrom", None),
                    "NameRU",
                    "",
                ),
                "operation_date": self._parse_date(getattr(last, "OperDate", None)),
                "history": history,
            }

        except Exception as e:
            _LOGGER.exception("Ошибка при запросе трека %s: %s", barcode, e)
            return None

    def _parse_date(self, date_input):
        """Конвертирует дату в ISO-формат."""
        if not date_input:
            return None
        try:
            return datetime.fromisoformat(str(date_input)).isoformat()
        except Exception:
            return str(date_input)
