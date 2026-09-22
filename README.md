# pykaspi

Python-библиотека для удалённой оплаты через Kaspi Pay. Ваше приложение создаёт
счёт по номеру покупателя и получает банковский статус: оплачено, отклонено,
истекло или ещё ожидает оплаты.

Это неофициальный клиент внутреннего API Kaspi Pay. Kaspi может менять
протокол или запрашивать повторную авторизацию.

## Установка

    pip install pykaspi

## Один файл терминала

Всё, что нужно библиотеке для работы от имени кассира, находится в одном
секретном JSON-файле. Не коммитьте этот файл и
не передавайте его содержимое: он даёт доступ к терминалу.

Один раз создайте файл для кассира:

    pykaspi-terminal-init \
      --state ./secrets/kaspi-terminal.json \
      --phone +77000000000

CLI запросит только те шаги, которые потребует Kaspi: пароль, SMS-код или
подтверждение в приложении. Повторный запуск этой же команды с тем же путём
проверит и при возможности обновит существующий терминал.

Если Kaspi запросит Face Check, библиотека не сможет пройти его вместо
человека. В таком случае завершите проверку в официальном приложении Kaspi Pay
либо используйте кассира, которому Kaspi выдаёт поддерживаемый способ входа.

## Использование в своём приложении

    import asyncio

    from pykaspi import KaspiTerminal


    async def create_payment() -> None:
        terminal = KaspiTerminal.load("./secrets/kaspi-terminal.json")

        async with terminal.client() as kaspi:
            invoice = await kaspi.invoice.create(
                terminal.session,
                phone_number="+77000000001",
                amount=100,
                comment="Заказ #42",
            )
            if not invoice.ok or invoice.data is None:
                raise RuntimeError(invoice.message or "Kaspi не создал счёт")

            operation_id = invoice.data.id or invoice.data.qr_operation_id
            if operation_id is None:
                raise RuntimeError("Kaspi не вернул ID счёта")

            # Сохраните operation_id в БД до дальнейшего ожидания.
            result = await kaspi.invoice.wait_for_payment(
                terminal.session, operation_id, timeout=300
            )
            if result.event == "payment.success":
                print("Оплата подтверждена Kaspi")
            else:
                print(result.event, result.status)


    asyncio.run(create_payment())

payment.success — единственный статус, подтверждающий оплату. Если получен
payment.timeout, это не отказ и не истечение счёта: сохранённый operation_id
надо проверить позже. При потере ответа создания не создавайте второй счёт,
пока не проверите историю Kaspi Pay.

Для серверного продукта лучше сразу записывать operation_id в БД и проверять
его отдельной фоновой задачей. Публикуйте событие только при переходе статуса,
чтобы не отправить два одинаковых уведомления.

## Методы

- kaspi.invoice.create, details, cancel, wait_for_payment — удалённые счета.
- kaspi.qr.create и status — Kaspi QR.
- kaspi.history — история операций.
- kaspi.refund — возврат, если Kaspi разрешает его для операции.

Номер покупателя принимается как 87000000000, +77000000000 или с пробелами.
Сумма — положительное число в тенге, до двух знаков после запятой.

## Проверка

При разработке самого пакета:

    uv sync --all-groups
    .venv/bin/python -m pytest -q
